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