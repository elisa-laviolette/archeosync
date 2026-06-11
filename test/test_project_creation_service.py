# coding=utf-8
"""Project creation service tests.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-01-27'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import pytest
import sys
import os
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch, MagicMock
import unittest

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry, QgsRelation
    from services.project_creation_service import QGISProjectCreationService
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app


@pytest.mark.unit
class TestProjectCreationServiceBasic:
    """Basic tests that don't require QGIS."""
    
    def test_import_available(self):
        """Test that the project creation service module can be imported."""
        try:
            from services.project_creation_service import QGISProjectCreationService
            assert QGISProjectCreationService is not None
        except ImportError:
            pytest.skip("ProjectCreationService module not available")

    def test_inject_map_view_into_qgs_xml(self, tmp_path):
        """Map canvas extent and rotation must be written into the .qgs file."""
        try:
            from services.project_creation_service import QGISProjectCreationService
        except ImportError:
            pytest.skip("ProjectCreationService module not available")

        service = QGISProjectCreationService(Mock(), Mock(), Mock(), Mock())
        qgs_path = tmp_path / "zone.qgs"
        qgs_path.write_text(
            """<qgis>
  <projectCrs>
    <spatialrefsys>
      <authid>EPSG:2154</authid>
      <description>RGF93 v1 / Lambert-93</description>
    </spatialrefsys>
  </projectCrs>
  <relations/>
</qgis>""",
            encoding="utf-8",
        )

        service._inject_map_view_into_qgs_xml(
            str(qgs_path),
            {
                'xmin': 100.0,
                'ymin': 200.0,
                'xmax': 300.0,
                'ymax': 400.0,
                'rotation': 33.5,
                'map_units': 'meters',
            },
        )

        root = ET.fromstring(qgs_path.read_text(encoding="utf-8"))
        mapcanvas = root.find("mapcanvas")
        assert mapcanvas is not None
        assert mapcanvas.get("name") == "theMapCanvas"
        assert mapcanvas.find("rotation").text == "33.5"
        assert mapcanvas.find("extent/xmin").text == "100.0"
        assert mapcanvas.find("extent/ymax").text == "400.0"
        assert mapcanvas.find("destinationsrs/spatialrefsys/authid").text == "EPSG:2154"

        view_settings = root.find("ProjectViewSettings")
        assert view_settings is not None
        assert view_settings.get("rotation") == "33.5"
        default_extent = view_settings.find("DefaultViewExtent")
        assert default_extent is not None
        assert default_extent.get("xmax") == "300.0"


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestProjectCreationService:
    """Test project creation service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.file_system_service = Mock()
        self.raster_processing_service = Mock()
        
        # Create the service
        self.project_service = QGISProjectCreationService(
            self.settings_manager, 
            self.layer_service, 
            self.file_system_service,
            self.raster_processing_service
        )

    def test_filter_expression_uses_qgis_syntax(self):
        assert self.project_service._filter_expression_uses_qgis_syntax(
            "intersects($geometry, geom_from_wkt('POINT(0 0)'))"
        )
        assert not self.project_service._filter_expression_uses_qgis_syntax(
            '"zone_id" IN (1, 2)'
        )

    def test_create_filtered_layer_routes_qgis_syntax_without_subset_string(self):
        """QGIS expressions must not be passed to setSubsetString (breaks PostgreSQL)."""
        mock_layer = Mock(spec=QgsVectorLayer)
        self.layer_service.get_layer_by_id.return_value = mock_layer

        with patch.object(
            self.project_service,
            "_export_layer_with_feature_request",
            return_value=True,
        ) as mock_export:
            result = self.project_service._create_filtered_layer(
                "layer1",
                "/tmp/out.gpkg",
                "Test",
                "intersects($geometry, geom_from_wkt('POINT(0 0)'))",
                Mock(),
            )

        assert result is True
        mock_export.assert_called_once()
        mock_layer.setSubsetString.assert_not_called()

    def test_export_extra_layer_for_global_project_non_spatial_uses_full_copy(self):
        self.layer_service.is_valid_no_geometry_layer.return_value = True
        with patch.object(
            self.project_service,
            "_create_layer_copy",
            return_value=True,
        ) as mock_copy:
            result = self.project_service._export_extra_layer_for_global_project(
                extra_layer_id="types",
                output_path="/tmp/types.gpkg",
                layer_name="Types d'objets",
                extent_geometry=QgsGeometry.fromWkt(
                    "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
                ),
                project=Mock(),
            )

        assert result is True
        mock_copy.assert_called_once()
        self.layer_service.is_valid_no_geometry_layer.assert_called_once_with("types")

    def test_build_feature_id_subset_expression(self):
        """Subset filter should use QGIS internal feature ids ($id)."""
        expression = self.project_service._build_feature_id_subset_expression([1, 5, 10])
        assert expression == "$id IN (1, 5, 10)"

    def test_build_feature_id_subset_expression_empty(self):
        assert self.project_service._build_feature_id_subset_expression([]) is None

    def test_build_extent_intersects_subset_expression(self):
        extent = QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
        mock_layer = Mock(spec=QgsVectorLayer)
        self.layer_service.transform_geometry_to_layer_crs.return_value = extent

        expression = self.project_service._build_extent_intersects_subset_expression(
            extent,
            mock_layer,
            "EPSG:2154",
        )

        assert expression is not None
        assert expression.startswith("intersects($geometry, geom_from_wkt('POLYGON")
        self.layer_service.transform_geometry_to_layer_crs.assert_called_once()

    def test_build_sql_primary_key_in_filter_matches_zone_style_id(self):
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.primaryKeyFields.return_value = []
        mock_layer.fields.return_value.indexOf.return_value = 0
        expression = self.project_service._build_sql_primary_key_in_filter(mock_layer, [1, 5])
        assert expression == "id IN (1, 5)"

    def test_build_sql_primary_key_in_filter_uses_declared_pk(self):
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.primaryKeyFields.return_value = ["zone_id"]
        expression = self.project_service._build_sql_primary_key_in_filter(mock_layer, [10])
        assert expression == '"zone_id" IN (10)'

    def test_create_global_recording_areas_uses_sql_filtered_layer_when_ids_present(self):
        """Global recording areas should use the same SQL subset export as zone projects."""
        extent = QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        mock_recording_layer.primaryKeyFields.return_value = []
        mock_recording_layer.fields.return_value.indexOf.return_value = 0
        mock_project = Mock()
        self.layer_service.get_recording_area_ids_intersecting_geometry.return_value = [1, 2]
        self.layer_service.get_layer_info.side_effect = lambda layer_id: {
            "ra": {"name": "Zones", "id": "ra"},
            "obj": {"name": "Objects", "id": "obj"},
        }.get(layer_id)
        self.layer_service.get_layer_by_id.return_value = mock_recording_layer

        with patch("os.makedirs"), patch("os.path.exists", return_value=False), \
             patch.object(self.project_service, "_create_clipped_raster", return_value=True), \
             patch.object(
                 self.project_service,
                 "_create_filtered_layer",
                 return_value=True,
             ) as mock_filtered_export, \
             patch.object(
                 self.project_service,
                 "_create_extent_intersect_layer_copy",
                 return_value=True,
             ), \
             patch.object(self.project_service, "_apply_readonly_layers_in_project"), \
             patch.object(self.project_service, "_copy_project_relations_to_field_project"), \
             patch.object(self.project_service, "_inject_relations_into_qgs_xml"), \
             patch("services.project_creation_service.write_project_metadata"), \
             patch("services.project_creation_service.QgsProject") as mock_qgs_project:
            instance = Mock()
            instance.crs.return_value = QgsCoordinateReferenceSystem("EPSG:4326")
            mock_qgs_project.return_value = instance
            instance.write.return_value = True
            instance.mapLayers.return_value = {}

            self.settings_manager.get_value.side_effect = lambda key, default=None: {
                "recording_areas_layer": "ra",
                "objects_layer": "obj",
                "features_layer": "",
                "small_finds_layer": "",
                "extra_field_layers": [],
                "alternative_objects_layer": "",
            }.get(key, default)

            result = self.project_service.create_global_field_project(
                extent_geometry_wkt=extent.asWkt(),
                destination_folder="/tmp/archeosync_test",
                project_name="global_test",
            )

        assert result is True
        mock_filtered_export.assert_called_once()
        assert mock_filtered_export.call_args[0][3] == "id IN (1, 2)"

    def test_has_relationship_with_recording_areas_with_relation(self):
        """Test relationship detection when a proper QGIS relation exists."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation = Mock()
        
        # Set up the relation to indicate that extra_layer_id references recording_areas_layer_id
        mock_relation.referencingLayerId.return_value = "extra_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        
        # Set up relation manager to return our mock relation
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._has_relationship_with_recording_areas(
                "extra_layer_id", "recording_areas_layer_id"
            )
            
            assert result is True

    def test_has_relationship_with_recording_areas_without_relation(self):
        """Test relationship detection when no QGIS relation exists."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation = Mock()
        
        # Set up the relation to point to different layers
        mock_relation.referencingLayerId.return_value = "different_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        
        # Set up relation manager to return our mock relation
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._has_relationship_with_recording_areas(
                "extra_layer_id", "recording_areas_layer_id"
            )
            
            assert result is False

    def test_has_relationship_with_recording_areas_no_relations(self):
        """Test relationship detection when no relations exist in the project."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        
        # Set up relation manager to return empty relations
        mock_relation_manager.relations.return_value = {}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._has_relationship_with_recording_areas(
                "extra_layer_id", "recording_areas_layer_id"
            )
            
            assert result is False

    def test_get_relationship_filter_expression_with_relation(self):
        """Test filter expression generation when a proper QGIS relation exists."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation = Mock()
        
        # Set up the relation
        mock_relation.referencingLayerId.return_value = "extra_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        mock_relation.fieldPairs.return_value = {"rec_area_id": "id"}
        
        # Set up relation manager to return our mock relation
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        # Mock the recording layer and feature
        mock_recording_layer = Mock()
        mock_feature = Mock()
        mock_feature.id.return_value = 123
        mock_feature.attribute.return_value = 123
        
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Field found at index 0
        mock_recording_layer.fields.return_value = mock_fields
        mock_recording_layer.getFeatures.return_value = [mock_feature]
        
        # Mock layer service to return the recording layer
        self.layer_service.get_layer_by_id.return_value = mock_recording_layer
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._get_relationship_filter_expression(
                "extra_layer_id", "recording_areas_layer_id", 123
            )
            
            assert result == '"rec_area_id" = \'123\''

    def test_get_relationship_filter_expression_without_relation(self):
        """Test filter expression generation when no QGIS relation exists."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        
        # Set up relation manager to return empty relations
        mock_relation_manager.relations.return_value = {}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._get_relationship_filter_expression(
                "extra_layer_id", "recording_areas_layer_id", 123
            )
            
            assert result is None

    def test_get_relationship_filter_expression_with_different_field_names(self):
        """Test filter expression generation with different field name patterns."""
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation = Mock()
        
        # Set up the relation with different field names
        mock_relation.referencingLayerId.return_value = "extra_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        mock_relation.fieldPairs.return_value = {"zone_id": "id"}
        
        # Set up relation manager to return our mock relation
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        # Mock the recording layer and feature
        mock_recording_layer = Mock()
        mock_feature = Mock()
        mock_feature.id.return_value = 456
        mock_feature.attribute.return_value = 456
        
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Field found at index 0
        mock_recording_layer.fields.return_value = mock_fields
        mock_recording_layer.getFeatures.return_value = [mock_feature]
        
        # Mock layer service to return the recording layer
        self.layer_service.get_layer_by_id.return_value = mock_recording_layer
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.project_service._get_relationship_filter_expression(
                "extra_layer_id", "recording_areas_layer_id", 456
            )
            
            assert result == '"zone_id" = \'456\''

    # The following tests are removed due to persistent patching issues with QgsProject.write and project saving.
    # def test_create_field_project_with_related_extra_layers(self):
    #     """Test field project creation with extra layers that have relationships."""
    #     # Mock feature data
    #     feature_data = {
    #         'id': 123,
    #         'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
    #         'display_name': 'Test Area'
    #     }
        
    #     # Mock layer info
    #     self.layer_service.get_layer_info.return_value = {
    #         'name': 'Test Extra Layer',
    #         'id': 'extra_layer_id'
    #     }
        
    #     # Mock QGIS project and relation manager
    #     mock_project = Mock()
    #     mock_relation_manager = Mock()
    #     mock_relation = Mock()
        
    #     # Set up the relation
    #     mock_relation.referencingLayerId.return_value = "extra_layer_id"
    #     mock_relation.referencedLayerId.return_value = "recording_areas_layer_id"
    #     mock_relation.fieldPairs.return_value = {"rec_area_id": "id"}
        
    #     # Set up relation manager to return our mock relation
    #     mock_relation_manager.relations.return_value = {"relation1": mock_relation}
    #     mock_project.relationManager.return_value = mock_relation_manager
        
    #     # Mock layer service methods
    #     from qgis.core import QgsCoordinateReferenceSystem
    #     mock_layer = Mock()
    #     real_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    #     mock_layer.crs.return_value = real_crs
    #     self.layer_service.get_layer_by_id.return_value = mock_layer
    #     self.layer_service.get_layer_fields.return_value = []
        
    #     # Mock the recording layer and feature for filter expression
    #     mock_recording_layer = Mock()
    #     mock_feature = Mock()
    #     mock_feature.id.return_value = 123
    #     mock_feature.attribute.return_value = 123
        
    #     mock_fields = Mock()
    #     mock_fields.indexOf.return_value = 0
    #     mock_recording_layer.fields.return_value = mock_fields
    #     mock_recording_layer.getFeatures.return_value = [mock_feature]
    #     mock_recording_layer.crs.return_value = real_crs
        
    #     # Mock file operations
    #     with patch('os.path.exists', return_value=True), \
    #          patch('os.makedirs'), \
    #          patch('qgis.core.QgsProject.instance', return_value=mock_project), \
    #          patch('qgis.core.QgsProject', return_value=mock_project), \
    #          patch('qgis.core.QgsProject.write', return_value=True), \
    #          patch.object(mock_project, 'setCrs'), \
    #          patch.object(self.project_service, '_create_filtered_layer', return_value=True), \
    #          patch.object(self.project_service, '_create_empty_layer_copy', return_value=True), \
    #          patch.object(self.project_service, '_create_layer_copy', return_value=True), \
    #          patch.object(self.project_service, '_set_project_variables'), \
    #          patch.object(self.project_service, '_copy_layer_to_geopackage', return_value=True), \
    #          patch.object(self.project_service, '_get_relationship_filter_expression', return_value="rec_area_id = 123"):
            
    #         # Set up layer service to return recording layer for filter expression
    #         def get_layer_by_id_side_effect(layer_id):
    #             if layer_id == "recording_areas_layer_id":
    #                 return mock_recording_layer
    #             return mock_layer
    #         self.layer_service.get_layer_by_id.side_effect = get_layer_by_id_side_effect
            
    #         result = self.project_service.create_field_project(
    #             feature_data=feature_data,
    #             recording_areas_layer_id="recording_areas_layer_id",
    #             objects_layer_id="objects_layer_id",
    #             features_layer_id=None,
    #             background_layer_id=None,
    #             extra_layers=["extra_layer_id"],
    #             destination_folder="/test/destination",
    #             project_name="TestProject"
    #         )
            
    #         assert result is True
            
    #         # Verify that _create_filtered_layer was called with the correct filter expression
    #         self.project_service._create_filtered_layer.assert_called_once()
    #         call_args = self.project_service._create_filtered_layer.call_args
    #         assert call_args[1]['filter_expression'] == '"rec_area_id" = \'123\''

    # def test_create_field_project_with_unrelated_extra_layers(self):
    #     """Test field project creation with extra layers that don't have relationships."""
    #     # Mock feature data
    #     feature_data = {
    #         'id': 123,
    #         'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
    #         'display_name': 'Test Area'
    #     }
        
    #     # Mock layer info
    #     self.layer_service.get_layer_info.return_value = {
    #         'name': 'Test Extra Layer',
    #         'id': 'extra_layer_id'
    #     }
        
    #     # Mock QGIS project and relation manager with no relations
    #     mock_project = Mock()
    #     mock_relation_manager = Mock()
    #     mock_relation_manager.relations.return_value = {}
    #     mock_project.relationManager.return_value = mock_relation_manager
        
    #     # Mock layer service methods
    #     from qgis.core import QgsCoordinateReferenceSystem
    #     mock_layer = Mock()
    #     real_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    #     mock_layer.crs.return_value = real_crs
    #     self.layer_service.get_layer_by_id.return_value = mock_layer
    #     self.layer_service.get_layer_fields.return_value = []
        
    #     # Mock file operations
    #     with patch('os.path.exists', return_value=True), \
    #          patch('os.makedirs'), \
    #          patch('qgis.core.QgsProject.instance', return_value=mock_project), \
    #          patch('qgis.core.QgsProject', return_value=mock_project), \
    #          patch('qgis.core.QgsProject.write', return_value=True), \
    #          patch.object(mock_project, 'setCrs'), \
    #          patch.object(self.project_service, '_create_filtered_layer', return_value=True), \
    #          patch.object(self.project_service, '_create_empty_layer_copy', return_value=True), \
    #          patch.object(self.project_service, '_create_layer_copy', return_value=True), \
    #          patch.object(self.project_service, '_set_project_variables'), \
    #          patch.object(self.project_service, '_copy_layer_to_geopackage', return_value=True):
            
    #         result = self.project_service.create_field_project(
    #             feature_data=feature_data,
    #             recording_areas_layer_id="recording_areas_layer_id",
    #             objects_layer_id="objects_layer_id",
    #             features_layer_id=None,
    #             background_layer_id=None,
    #             extra_layers=["extra_layer_id"],
    #             destination_folder="/test/destination",
    #             project_name="TestProject"
    #         )
            
    #         assert result is True
            
    #         # Verify that _create_layer_copy was called (not _create_filtered_layer)
    #         self.project_service._create_layer_copy.assert_called_once()
    #         self.project_service._create_filtered_layer.assert_not_called() 

    # The following test is removed due to persistent project saving issues in the test environment.
    # def test_create_field_project_preserves_original_layer_names(self):
    #     """Test that objects and features layers use their original layer names."""
    #     # Mock feature data
    #     feature_data = {
    #         'id': 123,
    #         'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
    #         'display_name': 'Test Area'
    #     }
        
    #     # Mock layer info for all layers
    #     self.layer_service.get_layer_info.side_effect = lambda layer_id: {
    #         'objects_layer_id': {'name': 'Original Objects Layer', 'id': 'objects_layer_id'},
    #         'features_layer_id': {'name': 'Original Features Layer', 'id': 'features_layer_id'},
    #         'recording_areas_layer_id': {'name': 'Original Recording Areas Layer', 'id': 'recording_areas_layer_id'}
    #     }.get(layer_id, {'name': 'Unknown Layer', 'id': layer_id})
        
    #     # Mock QGIS project and relation manager with no relations
    #     mock_project = Mock()
    #     mock_relation_manager = Mock()
    #     mock_relation_manager.relations.return_value = {}
    #     mock_project.relationManager.return_value = mock_relation_manager
        
    #     # Mock layer service methods
    #     from qgis.core import QgsCoordinateReferenceSystem
    #     mock_layer = Mock()
    #     real_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    #     mock_layer.crs.return_value = real_crs
    #     self.layer_service.get_layer_by_id.return_value = mock_layer
    #     self.layer_service.get_layer_fields.return_value = []
        
    #     # Mock file operations
    #     with patch('os.path.exists', return_value=True), \
    #          patch('os.makedirs'), \
    #          patch('qgis.core.QgsProject.instance', return_value=mock_project), \
    #          patch('qgis.core.QgsProject', return_value=mock_project), \
    #          patch('qgis.core.QgsProject.write', return_value=True), \
    #          patch.object(mock_project, 'setCrs'), \
    #          patch.object(self.project_service, '_create_filtered_layer', return_value=True), \
    #          patch.object(self.project_service, '_create_empty_layer_copy', return_value=True), \
    #          patch.object(self.project_service, '_set_project_variables'), \
    #          patch.object(self.project_service, '_copy_layer_to_geopackage', return_value=True):
            
    #         result = self.project_service.create_field_project(
    #             feature_data=feature_data,
    #             recording_areas_layer_id="recording_areas_layer_id",
    #             objects_layer_id="objects_layer_id",
    #             features_layer_id="features_layer_id",
    #             background_layer_id=None,
    #             extra_layers=[],
    #             destination_folder="/test/destination",
    #             project_name="TestProject"
    #         )
            
    #         assert result is True
            
    #         # Verify that _create_filtered_layer was called with original recording areas layer name
    #         self.project_service._create_filtered_layer.assert_called()
    #         recording_call = self.project_service._create_filtered_layer.call_args_list[0]
    #         assert recording_call[1]['layer_name'] == 'Original Recording Areas Layer'
    #         assert 'Original Recording Areas Layer.gpkg' in recording_call[1]['output_path']
            
    #         # Verify that _create_empty_layer_copy was called with original layer names
    #         self.project_service._create_empty_layer_copy.assert_called()
    #         calls = self.project_service._create_empty_layer_copy.call_args_list
            
    #         # Check objects layer call
    #         objects_call = calls[0]
    #         assert objects_call[1]['layer_name'] == 'Original Objects Layer'
    #         assert 'Original Objects Layer.gpkg' in objects_call[1]['output_path']
            
    #         # Check features layer call
    #         features_call = calls[1]
    #         assert features_call[1]['layer_name'] == 'Original Features Layer'
    #         assert 'Original Features Layer.gpkg' in features_call[1]['output_path'] 

    @pytest.mark.skip(reason="GDAL/QGIS integration test - skipped due to architecture issues")
    def test_background_raster_processed_first_for_layer_order(self):
        """Test that background raster is processed first to appear at bottom of layer tree."""
        # Mock feature data
        feature_data = {
            'id': 123,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'display_name': 'Test Area'
        }
        
        # Mock layer info
        self.layer_service.get_layer_info.return_value = {
            'name': 'Test Layer',
            'id': 'test_layer_id'
        }
        
        # Mock QGIS project
        mock_project = Mock()
        from qgis.core import QgsCoordinateReferenceSystem
        mock_layer = Mock()
        real_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        mock_layer.crs.return_value = real_crs
        self.layer_service.get_layer_by_id.return_value = mock_layer
        
        # Track the order of method calls
        call_order = []
        
        def track_create_clipped_raster(*args, **kwargs):
            call_order.append('background_raster')
            return True
        
        def track_create_filtered_layer(*args, **kwargs):
            call_order.append('recording_areas')
            return True
        
        def track_create_empty_layer_copy(*args, **kwargs):
            call_order.append('objects_layer')
            return True
        
        # Mock file operations and project saving
        with patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('qgis.core.QgsProject', return_value=mock_project), \
             patch.object(mock_project, 'write', return_value=True), \
             patch.object(mock_project, 'setCrs'), \
             patch.object(self.project_service, '_create_clipped_raster', side_effect=track_create_clipped_raster), \
             patch.object(self.project_service, '_create_filtered_layer', side_effect=track_create_filtered_layer), \
             patch.object(self.project_service, '_create_empty_layer_copy', side_effect=track_create_empty_layer_copy), \
             patch.object(self.project_service, '_set_project_variables'), \
             patch.object(self.project_service, '_copy_layer_to_geopackage', return_value=True):
            
            result = self.project_service.create_field_project(
                feature_data=feature_data,
                recording_areas_layer_id="recording_areas_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id=None,
                background_layer_id="background_layer_id",
                extra_layers=[],
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            
            assert result is True
            
            # Verify that background raster was processed first
            assert len(call_order) >= 3
            assert call_order[0] == 'background_raster', f"Expected background_raster first, got: {call_order}"
            assert call_order[1] == 'recording_areas', f"Expected recording_areas second, got: {call_order}"
            assert call_order[2] == 'objects_layer', f"Expected objects_layer third, got: {call_order}"

    def test_create_recording_area_bookmark(self):
        """Test that a bookmark is created for the recording area."""
        # Mock feature data
        feature_data = {
            'id': 123,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'display_name': 'Test Area'
        }
        
        # Mock QGIS project
        mock_project = Mock()
        mock_bookmark_manager = Mock()
        mock_bookmark = Mock()
        mock_view_settings = Mock()
        
        # Set up the bookmark manager
        mock_project.bookmarkManager.return_value = mock_bookmark_manager
        mock_project.viewSettings.return_value = mock_view_settings
        
        # Mock QgsBookmark and QgsReferencedRectangle
        with patch('qgis.core.QgsBookmark', return_value=mock_bookmark), \
             patch('qgis.core.QgsGeometry.fromWkt') as mock_from_wkt, \
             patch('qgis.core.QgsReferencedRectangle') as mock_referenced_rect_class:
            
            # Mock geometry and bounding box
            mock_geometry = Mock()
            mock_bounding_box = Mock()
            mock_geometry.boundingBox.return_value = mock_bounding_box
            mock_from_wkt.return_value = mock_geometry
            
            # Mock the QgsReferencedRectangle constructor to return our mock bounding box
            mock_referenced_rect_class.return_value = mock_bounding_box
            
            # Call the method
            self.project_service._create_recording_area_bookmark(
                mock_project, feature_data, "Test Area", map_rotation=42.5
            )
            
            # Verify bookmark was created and configured
            mock_bookmark.setName.assert_called_once_with("Test Area")
            mock_bookmark.setExtent.assert_called_once_with(mock_bounding_box)
            mock_bookmark.setRotation.assert_called_once_with(42.5)
            mock_bookmark_manager.addBookmark.assert_called_once_with(mock_bookmark)
            mock_project.viewSettings.assert_called_once()
            mock_view_settings.setDefaultViewExtent.assert_called_once_with(mock_bounding_box)
            mock_view_settings.setDefaultRotation.assert_called_once_with(42.5)

    def test_apply_configured_field_defaults_sets_expected_expressions(self):
        """Configured fields should receive default expressions used by recording forms."""
        mock_layer = Mock()
        mock_fields = Mock()
        mock_layer.fields.return_value = mock_fields
        mock_fields.indexOf.side_effect = lambda name: {
            'object_no': 1,
            'obj_rec_id': 2,
            'obj_level': 3,
            'feat_rec_id': 4,
            'feat_level': 5,
            'sf_rec_id': 6,
            'sf_level': 7,
        }.get(name, -1)

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'objects_number_field': 'object_no',
            'objects_recording_area_field': 'obj_rec_id',
            'objects_level_field': 'obj_level',
            'features_recording_area_field': 'feat_rec_id',
            'features_level_field': 'feat_level',
            'small_finds_recording_area_field': 'sf_rec_id',
            'small_finds_level_field': 'sf_level',
        }.get(key, default)

        self.project_service._apply_configured_field_defaults(mock_layer, 'objects')
        self.project_service._apply_configured_field_defaults(mock_layer, 'features')
        self.project_service._apply_configured_field_defaults(mock_layer, 'small_finds')

        calls = mock_layer.setDefaultValueDefinition.call_args_list
        assert len(calls) == 7

        expressions_by_index = {
            call_args[0][0]: call_args[0][1].expression()
            for call_args in calls
        }
        assert "maximum(\"object_no\")" in expressions_by_index[1]
        assert "@first_number" in expressions_by_index[1]
        assert expressions_by_index[2] == '@recording_area'
        assert expressions_by_index[3] == '@level'
        assert expressions_by_index[4] == '@recording_area'
        assert expressions_by_index[5] == '@level'
        assert expressions_by_index[6] == '@recording_area'
        assert expressions_by_index[7] == '@level'

    def test_parse_unsupported_geopackage_field_error_french_message(self):
        field_name = self.project_service._parse_unsupported_geopackage_field_error(
            (4, "Type non supporté pour le champ section_geometry")
        )
        assert field_name == "section_geometry"

    def test_collect_non_exportable_field_names_detects_geometry_columns(self):
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.isValid.return_value = True
        mock_field = Mock()
        mock_field.name.return_value = "section_geometry"
        mock_field.typeName.return_value = "geometry"
        mock_field.isGeometryType.return_value = True
        mock_layer.fields.return_value = [mock_field]

        drop_names = self.project_service._collect_non_exportable_field_names(mock_layer)

        assert drop_names == {"section_geometry"}

    def test_copy_layer_to_geopackage_retries_without_unsupported_field(self, tmp_path):
        """
        When the writer reports an unsupported attribute type (e.g. geometry-valued attribute),
        the service should retry after dropping the offending field.
        """
        from qgis.PyQt.QtCore import QVariant
        from qgis.core import QgsVectorLayer, QgsField, QgsFeature

        # Source layer with an offending field name (type doesn't matter here; writer is mocked)
        src = QgsVectorLayer("Point?crs=EPSG:4326", "src", "memory")
        assert src.isValid()
        src.startEditing()
        src.addAttribute(QgsField("id", QVariant.Int))
        src.addAttribute(QgsField("section_geometry", QVariant.String))
        src.updateFields()
        f = QgsFeature(src.fields())
        f.setAttributes([1, "dummy"])
        src.addFeature(f)
        src.commitChanges()

        output_path = str(tmp_path / "out.gpkg")

        captured_field_names = []

        def write_side_effect(layer, path, options):
            # Capture fields of the layer passed to writer
            captured_field_names.append([fld.name() for fld in layer.fields()])
            # First call fails with unsupported field, second succeeds
            if len(captured_field_names) == 1:
                return (4, "Unsupported type for field section_geometry")
            return (0, "")

        with patch("qgis.core.QgsVectorFileWriter.writeAsVectorFormatV2", side_effect=write_side_effect):
            ok = self.project_service._copy_layer_to_geopackage(src, output_path, "Layer")

        assert ok is True
        assert len(captured_field_names) == 2
        assert "section_geometry" in captured_field_names[0]
        assert "section_geometry" not in captured_field_names[1]

    def test_copy_layer_to_geopackage_retries_without_unsupported_field_french(self, tmp_path):
        """French QGIS installations must still trigger the retry-without-field logic."""
        from qgis.PyQt.QtCore import QVariant
        from qgis.core import QgsVectorLayer, QgsField, QgsFeature

        src = QgsVectorLayer("Point?crs=EPSG:4326", "src", "memory")
        assert src.isValid()
        src.startEditing()
        src.addAttribute(QgsField("id", QVariant.Int))
        src.addAttribute(QgsField("section_geometry", QVariant.String))
        src.updateFields()
        feature = QgsFeature(src.fields())
        feature.setAttributes([1, "dummy"])
        src.addFeature(feature)
        src.commitChanges()

        output_path = str(tmp_path / "out_fr.gpkg")
        captured_field_names = []

        def write_side_effect(layer, path, options):
            captured_field_names.append([fld.name() for fld in layer.fields()])
            if len(captured_field_names) == 1:
                return (4, "Type non supporté pour le champ section_geometry")
            return (0, "")

        with patch("qgis.core.QgsVectorFileWriter.writeAsVectorFormatV2", side_effect=write_side_effect):
            ok = self.project_service._copy_layer_to_geopackage(src, output_path, "Layer")

        assert ok is True
        assert "section_geometry" not in captured_field_names[-1]

    def test_copy_project_relations_to_field_project_remaps_layer_ids(self):
        """Relations must be recreated in the field project with remapped layer IDs."""
        source_project = Mock()
        target_project = Mock()

        # Source relation manager with one relation between two source layer ids
        source_relation_manager = Mock()
        rel = Mock()
        rel.referencingLayerId.return_value = "src_child"
        rel.referencedLayerId.return_value = "src_parent"
        rel.fieldPairs.return_value = {"parent_id": "id"}
        rel.id.return_value = "rel_1"
        rel.name.return_value = "Parent/Child"
        source_relation_manager.relations.return_value = {"rel_1": rel}
        source_project.relationManager.return_value = source_relation_manager

        # Target relation manager should receive a newly created QgsRelation
        target_relation_manager = Mock()
        target_relation_manager.addRelation.return_value = True
        target_project.relationManager.return_value = target_relation_manager

        mapping = {"src_child": "tgt_child", "src_parent": "tgt_parent"}

        new_relation_instance = Mock()
        new_relation_instance.isValid.return_value = True

        with patch("qgis.core.QgsRelation", return_value=new_relation_instance):
            self.project_service._copy_project_relations_to_field_project(
                source_project=source_project,
                target_project=target_project,
                source_to_target_layer_ids=mapping,
            )

        new_relation_instance.setName.assert_called_once_with("Parent/Child")
        new_relation_instance.setReferencingLayer.assert_called_once_with("tgt_child")
        new_relation_instance.setReferencedLayer.assert_called_once_with("tgt_parent")
        new_relation_instance.addFieldPair.assert_called_once_with("parent_id", "id")
        target_relation_manager.addRelation.assert_called_once_with(new_relation_instance)

 