# coding=utf-8
"""QField service tests.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry
    from services.qfield_service import QGISQFieldService
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app


@pytest.mark.unit
class TestQFieldServiceBasic:
    """Basic tests that don't require QGIS."""
    
    def test_import_available(self):
        """Test that the QField service module can be imported."""
        try:
            from services.qfield_service import QGISQFieldService
            assert QGISQFieldService is not None
        except ImportError:
            pytest.skip("QFieldService module not available")


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestQFieldService:
    """Test QField service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.file_system_service = Mock()
        
        # Mock QGIS objects
        self.mock_project = Mock()
        self.mock_layer = Mock()
        self.mock_feature = Mock()
        self.mock_geometry = Mock()
        
        # Set up mock returns
        self.mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        self.mock_layer.isValid.return_value = True
        self.mock_feature.geometry.return_value = self.mock_geometry
        self.mock_geometry.type.return_value = 1  # Point geometry
        
        # Mock QgsProject.instance()
        with patch('archeosync.services.qfield_service.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = self.mock_project
            mock_qgs_project.instance.return_value.addMapLayer = Mock()
            
            # Mock QgsVectorLayer
            with patch('archeosync.services.qfield_service.QgsVectorLayer') as mock_vector_layer:
                mock_vector_layer.return_value = self.mock_layer
                
                # Create the service with the new parameter
                self.qfield_service = QGISQFieldService(self.settings_manager, self.layer_service, self.file_system_service)

    def test_qfield_service_creation(self):
        """Test that QField service can be created."""
        assert self.qfield_service is not None
        assert hasattr(self.qfield_service, 'package_for_qfield')
        assert hasattr(self.qfield_service, 'package_for_qfield_with_data')
        assert hasattr(self.qfield_service, 'is_qfield_enabled')

    def test_is_qfield_enabled(self):
        """Test QField enabled status."""
        # Test when QField is enabled
        self.settings_manager.get_value.return_value = True
        assert self.qfield_service.is_qfield_enabled() is True
        
        # Test when QField is disabled
        self.settings_manager.get_value.return_value = False
        assert self.qfield_service.is_qfield_enabled() is False

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_with_empty_layers(self, mock_offliner, mock_export_type, mock_converter):
        """Test QField packaging with original layers used directly."""
        # Mock ExportType
        mock_export_type.Cable = "Cable"
        
        # Mock QgisCoreOffliner
        mock_offliner_instance = Mock()
        mock_offliner.return_value = mock_offliner_instance
        
        # Mock QFieldSync availability
        self.qfield_service._qfieldsync_available = True
        
        # Mock settings
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'use_qfield': True
        }.get(key, default)
        
        # Mock layer service
        self.layer_service.create_empty_layer_copy.return_value = "empty_layer_id"
        self.layer_service.remove_layer_from_project.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        mock_geometry.isNull.return_value = False
        mock_feature.geometry.return_value = mock_geometry
        
        # Mock project
        mock_project = Mock()
        mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        mock_project.mapLayers.return_value = {}
        
        # Mock offline converter
        mock_converter_instance = Mock()
        mock_converter_instance.convert.return_value = True
        mock_converter.return_value = mock_converter_instance
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
            # Test packaging
            result = self.qfield_service.package_for_qfield(
                recording_area_feature=mock_feature,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id="features_layer_id",
                background_layer_id=None,
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            # Assert process completes successfully
            assert result is True
            # Assert create_empty_layer_copy is NOT called
            self.layer_service.create_empty_layer_copy.assert_not_called()
            # Assert remove_layer_from_project is NOT called
            self.layer_service.remove_layer_from_project.assert_not_called()

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_without_features_layer(self, mock_offliner, mock_export_type, mock_converter):
        """Test QField packaging when features layer is not configured, using original objects layer directly."""
        # Mock ExportType
        mock_export_type.Cable = "Cable"
        
        # Mock QgisCoreOffliner
        mock_offliner_instance = Mock()
        mock_offliner.return_value = mock_offliner_instance
        
        # Mock QFieldSync availability
        self.qfield_service._qfieldsync_available = True
        
        # Mock settings
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'use_qfield': True
        }.get(key, default)
        
        # Mock layer service
        self.layer_service.create_empty_layer_copy.return_value = "empty_layer_id"
        self.layer_service.remove_layer_from_project.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        mock_geometry.isNull.return_value = False
        mock_feature.geometry.return_value = mock_geometry
        
        # Mock project
        mock_project = Mock()
        mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        mock_project.mapLayers.return_value = {}
        
        # Mock offline converter
        mock_converter_instance = Mock()
        mock_converter_instance.convert.return_value = True
        mock_converter.return_value = mock_converter_instance
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
            # Test packaging
            result = self.qfield_service.package_for_qfield(
                recording_area_feature=mock_feature,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id=None,
                background_layer_id=None,
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            # Assert process completes successfully
            assert result is True
            # Assert create_empty_layer_copy is NOT called
            self.layer_service.create_empty_layer_copy.assert_not_called()
            # Assert remove_layer_from_project is NOT called
            self.layer_service.remove_layer_from_project.assert_not_called()

    def test_package_for_qfield_qfieldsync_not_available(self):
        """Test QField packaging when QFieldSync is not available."""
        # Mock QFieldSync not available
        self.qfield_service._qfieldsync_available = False
        
        # Mock feature
        mock_feature = Mock()
        
        # Test packaging
        result = self.qfield_service.package_for_qfield(
            recording_area_feature=mock_feature,
            recording_areas_layer_id="recording_layer_id",
            objects_layer_id="objects_layer_id",
            features_layer_id=None,
            background_layer_id=None,
            destination_folder="/test/destination",
            project_name="TestProject"
        )
        
        # Should return False when QFieldSync is not available
        assert result is False

    def test_package_for_qfield_missing_parameters(self):
        """Test QField packaging with missing parameters."""
        # Mock QFieldSync available
        self.qfield_service._qfieldsync_available = True
        
        # Test with missing recording area feature
        result = self.qfield_service.package_for_qfield(
            recording_area_feature=None,
            recording_areas_layer_id="recording_layer_id",
            objects_layer_id="objects_layer_id",
            features_layer_id=None,
            background_layer_id=None,
            destination_folder="/test/destination",
            project_name="TestProject"
        )
        
        # Should return False with missing parameters
        assert result is False
        
        # Test with missing objects layer
        mock_feature = Mock()
        result = self.qfield_service.package_for_qfield(
            recording_area_feature=mock_feature,
            recording_areas_layer_id="recording_layer_id",
            objects_layer_id="",  # Empty objects layer
            features_layer_id=None,
            background_layer_id=None,
            destination_folder="/test/destination",
            project_name="TestProject"
        )
        
        # Should return False with missing parameters
        assert result is False

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_empty_layer_creation_failure(self, mock_offliner, mock_export_type, mock_converter):
        """Test QField packaging when empty layer creation fails."""
        # Mock ExportType
        mock_export_type.Cable = "Cable"
        
        # Mock QgisCoreOffliner
        mock_offliner_instance = Mock()
        mock_offliner.return_value = mock_offliner_instance
        
        # Mock QFieldSync availability
        self.qfield_service._qfieldsync_available = True
        
        # Mock settings
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'use_qfield': True
        }.get(key, default)
        
        # Mock layer service to fail creating empty layers
        self.layer_service.create_empty_layer_copy.return_value = None
        self.layer_service.remove_layer_from_project.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        mock_geometry.isNull.return_value = False
        mock_feature.geometry.return_value = mock_geometry
        
        # Mock project
        mock_project = Mock()
        mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        mock_project.mapLayers.return_value = {}
        
        # Mock offline converter
        mock_converter_instance = Mock()
        mock_converter_instance.convert.return_value = True
        mock_converter.return_value = mock_converter_instance
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
            
            # Test packaging
            result = self.qfield_service.package_for_qfield(
                recording_area_feature=mock_feature,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id="features_layer_id",
                background_layer_id=None,
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            
            # Verify no layers were removed (since none were created)
            self.layer_service.remove_layer_from_project.assert_not_called()

    def test_add_project_variables_to_qfield_project(self):
        """Test adding project variables to a QField project."""
        self.qfield_service._qfieldsync_available = True
        
        # Mock QgsProject properly
        mock_project_instance = Mock()
        mock_project_instance.mapLayers.return_value = {}
        mock_project_instance.crs.return_value = Mock(authid=lambda: "EPSG:4326")
        
        # Mock QgsProject class
        mock_project_class = Mock()
        mock_project_class.instance.return_value = mock_project_instance
        
        feature_data = {
            'id': 1,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'attributes': {'name': 'Test Area', 'display_name': 'Test Recording Area'}
        }
        next_values = {
            'next_number': '15',
            'next_level': 'Level B',
            'background_image': 'raster_layer_id'
        }
        mock_offliner = Mock()
        mock_offliner.create_empty_layer_copy.return_value = Mock()
        class MockExportType:
            Cable = "cable"
        with patch('services.qfield_service.QgsProject', mock_project_class), \
             patch('services.qfield_service.QgisCoreOffliner', lambda *a, **k: mock_offliner), \
             patch('services.qfield_service.ExportType', MockExportType), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)), \
             patch.object(self.qfield_service, '_package_with_offline_converter', return_value=True), \
             patch.object(self.qfield_service, '_add_project_variables_to_qfield_project') as mock_add_vars:
            result = self.qfield_service.package_for_qfield_with_data(
                feature_data=feature_data,
                recording_areas_layer_id='recording_areas',
                objects_layer_id='objects',
                features_layer_id='features',
                background_layer_id='background',
                destination_folder='/tmp/test',
                project_name='TestProject',
                add_variables=True,
                next_values=next_values
            )
            assert result is True
            mock_add_vars.assert_called_once()

    def test_add_project_variables_with_missing_values(self):
        """Test adding project variables with missing next values."""
        self.qfield_service._qfieldsync_available = True
        mock_project = Mock()
        mock_project.instance.return_value = mock_project
        mock_project.mapLayers.return_value = {}
        mock_project.crs.return_value = Mock(authid=lambda: "EPSG:4326")
        feature_data = {
            'id': 1,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'attributes': {'name': 'Test Area', 'display_name': 'Test Recording Area'}
        }
        next_values = {
            'next_number': None,
            'next_level': None,
            'background_image': None
        }
        mock_offliner = Mock()
        mock_offliner.create_empty_layer_copy.return_value = Mock()
        class MockExportType:
            Cable = "cable"
        with patch('services.qfield_service.QgsProject', return_value=mock_project), \
             patch('services.qfield_service.QgisCoreOffliner', lambda *a, **k: mock_offliner), \
             patch('services.qfield_service.ExportType', MockExportType), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)), \
             patch.object(self.qfield_service, '_package_with_offline_converter', return_value=True), \
             patch.object(self.qfield_service, '_add_project_variables_to_qfield_project') as mock_add_vars:
            result = self.qfield_service.package_for_qfield_with_data(
                feature_data=feature_data,
                recording_areas_layer_id='recording_areas',
                objects_layer_id='objects',
                features_layer_id='features',
                background_layer_id='background',
                destination_folder='/tmp/test',
                project_name='TestProject',
                add_variables=True,
                next_values=next_values
            )
            assert result is True
            mock_add_vars.assert_called_once()

    def test_add_project_variables_to_qfield_project_file(self):
        """Test adding project variables to QField project file."""
        # Mock project file path
        project_file = "/test/project.qgs"
        
        # Mock feature data
        feature_data = {
            'display_name': 'Test Recording Area',
            'attributes': {
                'name': 'Test Area'
            }
        }
        
        # Mock next values
        next_values = {
            'next_level': 'A1',
            'next_number': '1001'
        }
        
        # Mock QgsProject
        mock_project = Mock()
        mock_project.read.return_value = True
        mock_project.readListEntry.side_effect = lambda group, key: ([], []) if key == 'variableNames' else ([], [])
        mock_project.write.return_value = True
        mock_project.writeEntry = Mock()
        
        with patch('services.qfield_service.QgsProject', return_value=mock_project), \
             patch('os.path.exists', return_value=True):
            
            # Test adding project variables
            self.qfield_service._add_project_variables_to_qfield_project(
                project_file, feature_data, next_values
            )
            
            # Verify project was read and written
            mock_project.read.assert_called_once_with(project_file)
            mock_project.write.assert_called_once_with(project_file)
    
    def test_import_qfield_projects_empty_list(self):
        """Test importing QField projects with empty list."""
        result = self.qfield_service.import_qfield_projects([])
        
        assert result.is_valid is False
        assert "No project paths provided" in result.message
    
    @patch('os.path.exists')
    @patch('services.qfield_service.QgsVectorLayer')
    def test_import_qfield_projects_no_data_gpkg(self, mock_vector_layer, mock_exists):
        """Test importing QField projects when data.gpkg doesn't exist."""
        # Mock that data.gpkg doesn't exist
        mock_exists.return_value = False
        
        result = self.qfield_service.import_qfield_projects(["/test/project1"])
        
        assert result.is_valid is False
        assert "No Objects or Features layers found" in result.message
    
    @patch('os.path.exists')
    @patch('services.qfield_service.QgsVectorLayer')
    def test_import_qfield_projects_invalid_data_gpkg(self, mock_vector_layer, mock_exists):
        """Test importing QField projects with invalid data.gpkg."""
        # Mock that data.gpkg exists but is invalid
        mock_exists.return_value = True
        
        # Mock invalid vector layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = False
        mock_vector_layer.return_value = mock_layer
        
        result = self.qfield_service.import_qfield_projects(["/test/project1"])
        
        assert result.is_valid is False
        assert "No Objects or Features layers found" in result.message
    
    @patch('os.path.exists')
    @patch('services.qfield_service.QgsVectorLayer')
    @patch('services.qfield_service.QgsProject')
    def test_import_qfield_projects_with_objects_layer(self, mock_project, mock_vector_layer, mock_exists):
        """Test importing QField projects with Objects layer."""
        # Mock that data.gpkg exists
        mock_exists.return_value = True
        
        # Mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Polygon!!::!!EPSG:4326"
        ]
        
        # Mock Objects sublayer
        mock_objects_layer = Mock()
        mock_objects_layer.isValid.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.type.return_value = 3  # PolygonGeometry
        mock_feature.geometry.return_value = mock_geometry
        # Mock feature fields
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "Integer"
        mock_feature.fields.return_value = [mock_field]
        
        mock_objects_layer.getFeatures.return_value = [mock_feature]
        
        # Mock merged layer
        mock_merged_layer = Mock()
        mock_merged_layer.isValid.return_value = True
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_project_instance.crs.return_value.authid.return_value = "EPSG:3857"
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            # Debug print to see what is being called
            print(f"QgsVectorLayer called with args: {args}")
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "New Objects" in args[1]:
                assert "crs=EPSG:3857" in args[0]
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        result = self.qfield_service.import_qfield_projects(["/test/project1"])
        
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message

    @patch('os.path.exists')
    @patch('services.qfield_service.QgsVectorLayer')
    @patch('services.qfield_service.QgsProject')
    def test_import_qfield_projects_with_features_layer(self, mock_project, mock_vector_layer, mock_exists):
        """Test importing QField projects with Features layer."""
        # Mock that data.gpkg exists
        mock_exists.return_value = True
        
        # Mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Features_xyz456!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock Features sublayer
        mock_features_layer = Mock()
        mock_features_layer.isValid.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.type.return_value = 1  # PointGeometry
        mock_feature.geometry.return_value = mock_geometry
        # Mock feature fields
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "Integer"
        mock_feature.fields.return_value = [mock_field]
        
        mock_features_layer.getFeatures.return_value = [mock_feature]
        
        # Mock merged layer
        mock_merged_layer = Mock()
        mock_merged_layer.isValid.return_value = True
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_project_instance.crs.return_value.authid.return_value = "EPSG:3857"
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            print(f"QgsVectorLayer called with args: {args}")
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Features" in args[1]:
                return mock_features_layer
            elif len(args) > 1 and "New Features" in args[1]:
                assert "crs=EPSG:3857" in args[0]
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        result = self.qfield_service.import_qfield_projects(["/test/project1"])
        
        assert result.is_valid is True
        assert "Successfully imported 1 layer(s)" in result.message

    @patch('os.path.exists')
    @patch('services.qfield_service.QgsVectorLayer')
    @patch('services.qfield_service.QgsProject')
    def test_import_qfield_projects_with_both_layers(self, mock_project, mock_vector_layer, mock_exists):
        """Test importing QField projects with both Objects and Features layers."""
        # Mock that data.gpkg exists
        mock_exists.return_value = True
        
        # Mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Objects_abc123!!::!!Polygon!!::!!EPSG:4326",
            "1!!::!!Features_xyz456!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Mock Objects sublayer
        mock_objects_layer = Mock()
        mock_objects_layer.isValid.return_value = True
        
        # Mock Features sublayer
        mock_features_layer = Mock()
        mock_features_layer.isValid.return_value = True
        
        # Mock features
        mock_objects_feature = Mock()
        mock_objects_geometry = Mock()
        mock_objects_geometry.type.return_value = 3  # PolygonGeometry
        mock_objects_feature.geometry.return_value = mock_objects_geometry
        # Mock feature fields
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "Integer"
        mock_objects_feature.fields.return_value = [mock_field]
        
        mock_features_feature = Mock()
        mock_features_geometry = Mock()
        mock_features_geometry.type.return_value = 1  # PointGeometry
        mock_features_feature.geometry.return_value = mock_features_geometry
        # Mock feature fields
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "Integer"
        mock_features_feature.fields.return_value = [mock_field]
        
        mock_objects_layer.getFeatures.return_value = [mock_objects_feature]
        mock_features_layer.getFeatures.return_value = [mock_features_feature]
        
        # Mock merged layer
        mock_merged_layer = Mock()
        mock_merged_layer.isValid.return_value = True
        
        # Mock project instance and CRS
        mock_project_instance = Mock()
        mock_project_instance.crs.return_value.authid.return_value = "EPSG:3857"
        mock_project.instance.return_value = mock_project_instance
        
        # Patch addMapLayer to accept any argument
        mock_project_instance.addMapLayer = Mock()

        # Mock vector layer creation with proper side effect
        def vector_layer_side_effect(*args, **kwargs):
            print(f"QgsVectorLayer called with args: {args}")
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "Features" in args[1]:
                return mock_features_layer
            elif len(args) > 1 and ("New Objects" in args[1] or "New Features" in args[1]):
                assert "crs=EPSG:3857" in args[0]
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_vector_layer.side_effect = vector_layer_side_effect
        
        result = self.qfield_service.import_qfield_projects(["/test/project1"])
        
        assert result.is_valid is True
        assert "Successfully imported 2 layer(s)" in result.message
    
    def test_create_merged_layer_empty_features(self):
        """Test creating merged layer with empty features list."""
        result = self.qfield_service._create_merged_layer("Test Layer", [])
        
        assert result is False
    
    @patch('qgis.core.QgsVectorLayer')
    @patch('qgis.core.QgsProject')
    def test_create_merged_layer_invalid_layer(self, mock_project, mock_vector_layer):
        """Test creating merged layer that becomes invalid."""
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.type.return_value = 1  # PointGeometry
        mock_feature.geometry.return_value = mock_geometry
        # Mock feature fields
        mock_field = Mock()
        mock_field.name.return_value = "id"
        mock_field.typeName.return_value = "Integer"
        mock_feature.fields.return_value = [mock_field]
        
        # Mock invalid vector layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = False
        mock_vector_layer.return_value = mock_layer
        
        result = self.qfield_service._create_merged_layer("Test Layer", [mock_feature])
        
        assert result is False 

    def test_import_qfield_projects_no_paths(self):
        """Test import with no project paths."""
        result = self.qfield_service.import_qfield_projects([])
        assert result.is_valid is False
        assert "No project paths provided" in result.message
    
    @patch('archeosync.services.qfield_service.QgsVectorLayer')
    def test_import_qfield_projects_archives_projects_when_configured(self, mock_layer):
        """Test that QField projects are archived after successful import when archive folder is configured."""
        # Mock settings to return archive folder
        self.settings_manager.get_value.return_value = "/archive/path"
        
        # Mock file system service
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.create_directory.return_value = True
        self.file_system_service.move_directory.return_value = True
        
        # Create mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Objects_layer!!::!!Polygon!!::!!EPSG:4326",
            "1!!::!!Features_layer!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Create mock sublayers
        mock_objects_layer = Mock()
        mock_objects_layer.isValid.return_value = True
        mock_objects_layer.getFeatures.return_value = [self.mock_feature]
        
        mock_features_layer = Mock()
        mock_features_layer.isValid.return_value = True
        mock_features_layer.getFeatures.return_value = [self.mock_feature]
        
        # Create mock merged layer
        mock_merged_layer = Mock()
        mock_merged_layer.isValid.return_value = True
        
        # Set up side effect for QgsVectorLayer
        def vector_layer_side_effect(*args, **kwargs):
            # First call: data.gpkg
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            # Second/third calls: sublayers
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "Features" in args[1]:
                return mock_features_layer
            # Merged layer
            elif len(args) > 1 and ("New Objects" in args[1] or "New Features" in args[1]):
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_layer.side_effect = vector_layer_side_effect
        
        with patch('archeosync.services.qfield_service.QgsProject') as mock_project:
            mock_project.instance.return_value = self.mock_project
            
            # Mock os.path.exists to return True for data.gpkg and project directory
            def exists_side_effect(path):
                return path.endswith("data.gpkg") or path == "/test/project"
            
            with patch('archeosync.services.qfield_service.os.path.exists', side_effect=exists_side_effect):
                # Instantiate the service after patching
                from archeosync.services.qfield_service import QGISQFieldService
                qfield_service = QGISQFieldService(self.settings_manager, self.layer_service, self.file_system_service)
                result = qfield_service.import_qfield_projects(["/test/project"])
                
                # Verify import was successful
                assert result.is_valid is True
                
                # Verify archive folder was checked
                self.settings_manager.get_value.assert_called_with('qfield_archive_folder', '')
                
                # Verify project was moved to archive
                self.file_system_service.move_directory.assert_called_once()

    @patch('archeosync.services.qfield_service.QgsVectorLayer')
    def test_import_qfield_projects_does_not_archive_when_not_configured(self, mock_layer):
        """Test that QField projects are not archived when archive folder is not configured."""
        # Mock settings to return empty archive folder
        self.settings_manager.get_value.return_value = ""
        
        # Create mock data layer
        mock_data_layer = Mock()
        mock_data_layer.isValid.return_value = True
        mock_data_layer.dataProvider.return_value.subLayers.return_value = [
            "0!!::!!Objects_layer!!::!!Polygon!!::!!EPSG:4326",
            "1!!::!!Features_layer!!::!!Point!!::!!EPSG:4326"
        ]
        
        # Create mock sublayers
        mock_objects_layer = Mock()
        mock_objects_layer.isValid.return_value = True
        mock_objects_layer.getFeatures.return_value = [self.mock_feature]
        
        mock_features_layer = Mock()
        mock_features_layer.isValid.return_value = True
        mock_features_layer.getFeatures.return_value = [self.mock_feature]
        
        # Create mock merged layer
        mock_merged_layer = Mock()
        mock_merged_layer.isValid.return_value = True
        
        # Set up side effect for QgsVectorLayer
        def vector_layer_side_effect(*args, **kwargs):
            # First call: data.gpkg
            if len(args) > 1 and args[0].endswith("data.gpkg") and args[1] == "temp_data":
                return mock_data_layer
            # Second/third calls: sublayers
            elif len(args) > 1 and "Objects" in args[1]:
                return mock_objects_layer
            elif len(args) > 1 and "Features" in args[1]:
                return mock_features_layer
            # Merged layer
            elif len(args) > 1 and ("New Objects" in args[1] or "New Features" in args[1]):
                return mock_merged_layer
            else:
                return mock_merged_layer
        
        mock_layer.side_effect = vector_layer_side_effect
        
        with patch('archeosync.services.qfield_service.QgsProject') as mock_project:
            mock_project.instance.return_value = self.mock_project
            
            # Mock os.path.exists to return True for data.gpkg and project directory
            def exists_side_effect(path):
                return path.endswith("data.gpkg") or path == "/test/project"
            
            with patch('archeosync.services.qfield_service.os.path.exists', side_effect=exists_side_effect):
                # Instantiate the service after patching
                from archeosync.services.qfield_service import QGISQFieldService
                qfield_service = QGISQFieldService(self.settings_manager, self.layer_service, self.file_system_service)
                result = qfield_service.import_qfield_projects(["/test/project"])
                
                # Verify import was successful
                assert result.is_valid is True
                
                # Verify archive folder was checked
                self.settings_manager.get_value.assert_called_with('qfield_archive_folder', '')
                
                # Verify no file operations were performed
                self.file_system_service.move_directory.assert_not_called() 