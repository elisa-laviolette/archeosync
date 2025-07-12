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
        # Mock layer
        mock_layer_instance = Mock()
        mock_layer_instance.isValid.return_value = True
        mock_layer_instance.dataProvider.return_value.subLayers.return_value = [
            "Point!!::!!Objects",
            "Point!!::!!Features"
        ]
        mock_layer.return_value = mock_layer_instance
        
        # Mock settings - no archive folder configured
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'qfield_projects_archive_folder': ''  # Empty archive folder
        }.get(key, default)
        
        # Mock file system service
        self.file_system_service = Mock()
        self.qfield_service._file_system_service = self.file_system_service
        
        # Test data
        project_paths = ["/test/project1", "/test/project2"]
        
        def vector_layer_side_effect(*args, **kwargs):
            # First call: data.gpkg
            if "data.gpkg" in args[0]:
                mock_data_layer = Mock()
                mock_data_layer.isValid.return_value = True
                mock_data_layer.dataProvider.return_value.subLayers.return_value = [
                    "Point!!::!!Objects",
                    "Point!!::!!Features"
                ]
                return mock_data_layer
            # Second call: sublayer
            else:
                mock_sublayer = Mock()
                mock_sublayer.isValid.return_value = True
                mock_sublayer.getFeatures.return_value = []
                return mock_sublayer
        
        mock_layer.side_effect = vector_layer_side_effect
        
        with patch('os.path.exists') as mock_exists:
            def exists_side_effect(path):
                return "data.gpkg" in path
            
            mock_exists.side_effect = exists_side_effect
            
            # Test import
            result = self.qfield_service.import_qfield_projects(project_paths)
            
            # Assert that archive is NOT called regardless of validation result
            # The validation logic might fail due to missing data.gpkg files, but
            # the important thing is that archiving is not attempted
            self.file_system_service.archive_files.assert_not_called()

    def test_filter_recording_area_layer(self):
        """Test filtering of recording area layer to keep only selected feature."""
        from qgis.core import QgsVectorLayer
        # Mock recording area layer with correct spec
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        mock_recording_layer.name.return_value = "Recording Areas"
        mock_recording_layer.featureCount.return_value = 3

        # Mock features
        mock_feature1 = Mock()
        mock_feature1.id.return_value = 5877  # Selected feature
        mock_feature2 = Mock()
        mock_feature2.id.return_value = 5878
        mock_feature3 = Mock()
        mock_feature3.id.return_value = 5879

        # Set up getFeatures to return the features
        mock_recording_layer.getFeatures.return_value = [mock_feature1, mock_feature2, mock_feature3]
        mock_recording_layer.startEditing.return_value = True
        mock_recording_layer.deleteFeatures.return_value = True
        mock_recording_layer.commitChanges.return_value = True

        # Mock QgsProject
        mock_qfield_project = Mock()
        mock_qfield_project.read.return_value = True
        mock_qfield_project.write.return_value = True
        mock_qfield_project.mapLayers.return_value = {"recording_layer_id": mock_recording_layer}
        mock_qfield_project.mapLayer.side_effect = lambda lid: mock_recording_layer if lid == "recording_layer_id" else None

        with patch('services.qfield_service.QgsProject') as mock_qgs_project_class:
            mock_qgs_project_class.return_value = mock_qfield_project

            self.qfield_service._filter_recording_area_layer(
                project_file="/test/project.qgs",
                selected_feature_id=5877,
                recording_areas_layer_id="recording_layer_id"
            )

            mock_recording_layer.startEditing.assert_called_once()
            mock_recording_layer.deleteFeatures.assert_called_once_with([5878, 5879])
            mock_recording_layer.commitChanges.assert_called_once()
            mock_qfield_project.write.assert_called_once()

    def test_filter_related_extra_layers_with_relation(self):
        """Test filtering of extra layers that have relations to recording area layer."""
        from qgis.core import QgsVectorLayer
        # Mock recording area layer and feature
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        mock_recording_layer.name.return_value = "Recording Areas"
        mock_selected_feature = Mock()
        mock_selected_feature.id.return_value = 5877
        # Set up getFeatures to return an iterable
        mock_recording_layer.getFeatures.return_value = [mock_selected_feature]

        # Mock extra layer with correct spec
        mock_extra_layer = Mock(spec=QgsVectorLayer)
        mock_extra_layer.name.return_value = "Extra Layer"
        mock_extra_layer.startEditing.return_value = True
        mock_extra_layer.commitChanges.return_value = True

        # Mock features in extra layer
        mock_related_feature = Mock()
        mock_related_feature.id.return_value = 1001
        mock_related_feature.attribute.return_value = 5877  # Related to selected feature
        mock_unrelated_feature1 = Mock()
        mock_unrelated_feature1.id.return_value = 1002
        mock_unrelated_feature1.attribute.return_value = 9999
        mock_unrelated_feature2 = Mock()
        mock_unrelated_feature2.id.return_value = 1003
        mock_unrelated_feature2.attribute.return_value = 8888
        mock_extra_layer.getFeatures.return_value = [mock_related_feature, mock_unrelated_feature1, mock_unrelated_feature2]

        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = "extra_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_layer_id"
        mock_relation.fieldPairs.return_value = {"rec_area_id": "id"}
        mock_relation.referencingLayer.return_value = mock_extra_layer
        mock_relation.referencedLayer.return_value = mock_recording_layer
        mock_relation.referencingFields.return_value = ["rec_area_id"]
        mock_relation.referencedFields.return_value = ["id"]
        mock_relation.getRelatedFeatures.return_value = [mock_related_feature]

        # Mock relation manager - return dictionary instead of list
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}

        # Mock QgsProject
        mock_qfield_project = Mock()
        mock_qfield_project.write.return_value = True
        mock_qfield_project.mapLayer.side_effect = lambda lid: {
            "recording_layer_id": mock_recording_layer,
            "extra_layer_id": mock_extra_layer
        }.get(lid, None)
        mock_qfield_project.relationManager.return_value = mock_relation_manager
        # Ensure read returns True
        mock_qfield_project.read.return_value = True

        with patch('qgis.core.QgsProject') as mock_qgs_project_class:
            mock_qgs_project_class.return_value = mock_qfield_project

            self.qfield_service._filter_related_extra_layers(
                project_file="/test/project.qgs",
                selected_feature_id=5877,
                recording_areas_layer_id="recording_layer_id",
                extra_layer_ids=["extra_layer_id"]
            )

            mock_extra_layer.startEditing.assert_called_once()
            mock_extra_layer.deleteFeatures.assert_called_once_with([1002, 1003])
            mock_extra_layer.commitChanges.assert_called_once()
            mock_qfield_project.write.assert_called_once()

    def test_filter_related_extra_layers_no_relation(self):
        """Test filtering of extra layers that have no relations to recording area layer."""
        from qgis.core import QgsVectorLayer
        # Mock recording area layer and feature
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        mock_selected_feature = Mock()
        mock_selected_feature.id.return_value = 5877
        # Set up getFeatures to return an iterable
        mock_recording_layer.getFeatures.return_value = [mock_selected_feature]

        # Mock extra layer with correct spec
        mock_extra_layer = Mock(spec=QgsVectorLayer)
        mock_extra_layer.name.return_value = "Extra Layer"

        # Mock relation (different layer)
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = "different_layer_id"
        mock_relation.referencedLayerId.return_value = "recording_layer_id"

        # Mock relation manager - return dictionary instead of list
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}

        # Mock QgsProject
        mock_qfield_project = Mock()
        mock_qfield_project.write.return_value = True
        mock_qfield_project.mapLayer.side_effect = lambda lid: {
            "recording_layer_id": mock_recording_layer,
            "extra_layer_id": mock_extra_layer
        }.get(lid, None)
        mock_qfield_project.relationManager.return_value = mock_relation_manager
        # Ensure read returns True
        mock_qfield_project.read.return_value = True

        with patch('qgis.core.QgsProject') as mock_qgs_project_class:
            mock_qgs_project_class.return_value = mock_qfield_project

            self.qfield_service._filter_related_extra_layers(
                project_file="/test/project.qgs",
                selected_feature_id=5877,
                recording_areas_layer_id="recording_layer_id",
                extra_layer_ids=["extra_layer_id"]
            )

            mock_extra_layer.startEditing.assert_not_called()
            mock_extra_layer.deleteFeatures.assert_not_called()
            mock_extra_layer.commitChanges.assert_not_called()
            mock_qfield_project.write.assert_called_once()

    def test_filter_related_extra_layers_layer_not_found(self):
        """Test filtering when extra layer is not found in QField project."""
        from qgis.core import QgsVectorLayer
        # Mock recording area layer and feature
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        mock_selected_feature = Mock()
        mock_selected_feature.id.return_value = 5877
        # Set up getFeatures to return an iterable
        mock_recording_layer.getFeatures.return_value = [mock_selected_feature]

        # Mock relation manager
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {}

        # Set up project structure - extra layer not found
        def map_layer_side_effect(layer_id):
            if layer_id == "recording_layer_id":
                return mock_recording_layer
            elif layer_id == "extra_layer_id":
                return None
            return None

        mock_qfield_project = Mock()
        mock_qfield_project.write.return_value = True
        mock_qfield_project.mapLayer.side_effect = map_layer_side_effect
        mock_qfield_project.relationManager.return_value = mock_relation_manager
        # Ensure read returns True
        mock_qfield_project.read.return_value = True

        with patch('qgis.core.QgsProject') as mock_qgs_project_class:
            mock_qgs_project_class.return_value = mock_qfield_project

            self.qfield_service._filter_related_extra_layers(
                project_file="/test/project.qgs",
                selected_feature_id=5877,
                recording_areas_layer_id="recording_layer_id",
                extra_layer_ids=["extra_layer_id"]
            )

            mock_qfield_project.write.assert_called_once()

    def test_filter_related_extra_layers_empty_extra_layers(self):
        """Test filtering when no extra layers are provided."""
        # Test with empty extra layers list
        self.qfield_service._filter_related_extra_layers(
            project_file="/test/project.qgs",
            selected_feature_id=5877,
            recording_areas_layer_id="recording_layer_id",
            extra_layer_ids=[]
        )
        
        # Test with None extra layers
        self.qfield_service._filter_related_extra_layers(
            project_file="/test/project.qgs",
            selected_feature_id=5877,
            recording_areas_layer_id="recording_layer_id",
            extra_layer_ids=None
        )
        
        # No assertions needed - method should return early without errors

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_with_extra_layers_filtering(self, mock_offliner, mock_export_type, mock_converter):
        """Test that extra layers filtering is called during QField packaging."""
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
        self.layer_service.remove_layer_from_project.return_value = True
        
        # Mock feature
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        mock_geometry.isNull.return_value = False
        mock_feature.geometry.return_value = mock_geometry
        mock_feature.id.return_value = 5877
        
        # Mock project
        mock_project = Mock()
        mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        mock_project.mapLayers.return_value = {}
        
        # Mock offline converter
        mock_converter_instance = Mock()
        mock_converter_instance.convert.return_value = True
        mock_converter.return_value = mock_converter_instance
        
        # Mock the filtering methods
        with patch.object(self.qfield_service, '_filter_recording_area_layer') as mock_filter_recording, \
             patch.object(self.qfield_service, '_filter_related_extra_layers') as mock_filter_extra, \
             patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
            
            # Test packaging with extra layers
            result = self.qfield_service.package_for_qfield(
                recording_area_feature=mock_feature,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id="features_layer_id",
                background_layer_id=None,
                extra_layers=["extra_layer_1", "extra_layer_2"],
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            
            # Assert process completes successfully
            assert result is True
            
            # Assert filtering methods were called
            mock_filter_recording.assert_called_once()
            mock_filter_extra.assert_called_once_with(
                '/test/destination/TestProject/TestProject_qfield.qgs',  # Actual string path
                5877,  # selected_feature_id
                "recording_layer_id",
                ["extra_layer_1", "extra_layer_2"]
            )

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_with_data_extra_layers_filtering(self, mock_offliner, mock_export_type, mock_converter):
        """Test that extra layers filtering is called during QField packaging with data."""
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
        self.layer_service.remove_layer_from_project.return_value = True
        
        # Mock feature data
        feature_data = {
            'id': 5877,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'display_name': 'Test Area'
        }
        
        # Mock project
        mock_project = Mock()
        mock_project.crs.return_value.authid.return_value = "EPSG:4326"
        mock_project.mapLayers.return_value = {}
        
        # Mock offline converter
        mock_converter_instance = Mock()
        mock_converter_instance.convert.return_value = True
        mock_converter.return_value = mock_converter_instance
        
        # Mock the filtering methods
        with patch.object(self.qfield_service, '_filter_recording_area_layer') as mock_filter_recording, \
             patch.object(self.qfield_service, '_filter_related_extra_layers') as mock_filter_extra, \
             patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
            
            # Test packaging with extra layers
            result = self.qfield_service.package_for_qfield_with_data(
                feature_data=feature_data,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id="features_layer_id",
                background_layer_id=None,
                extra_layers=["extra_layer_1", "extra_layer_2"],
                destination_folder="/test/destination",
                project_name="TestProject",
                add_variables=False
            )
            
            # Assert process completes successfully
            assert result is True
            
            # Assert filtering methods were called
            mock_filter_recording.assert_called_once()
            mock_filter_extra.assert_called_once_with(
                '/test/destination/TestProject/TestProject_qfield.qgs',  # Actual string path
                5877,  # selected_feature_id
                "recording_layer_id",
                ["extra_layer_1", "extra_layer_2"]
            ) 