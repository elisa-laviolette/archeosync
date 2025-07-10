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
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.qfield_service = QGISQFieldService(self.settings_manager, self.layer_service)

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
        """Test QField packaging with empty layers creation."""
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
            
            # Verify empty layers were created
            self.layer_service.create_empty_layer_copy.assert_called()
            
            # Verify empty layers were removed
            self.layer_service.remove_layer_from_project.assert_called()

    @patch('services.qfield_service.OfflineConverter')
    @patch('services.qfield_service.ExportType')
    @patch('services.qfield_service.QgisCoreOffliner')
    def test_package_for_qfield_without_features_layer(self, mock_offliner, mock_export_type, mock_converter):
        """Test QField packaging when features layer is not configured."""
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
            
            # Test packaging without features layer
            result = self.qfield_service.package_for_qfield(
                recording_area_feature=mock_feature,
                recording_areas_layer_id="recording_layer_id",
                objects_layer_id="objects_layer_id",
                features_layer_id=None,  # No features layer
                background_layer_id=None,
                destination_folder="/test/destination",
                project_name="TestProject"
            )
            
            # Verify only objects layer was created (not features)
            create_calls = self.layer_service.create_empty_layer_copy.call_args_list
            assert len(create_calls) == 1  # Only objects layer
            assert create_calls[0][0][1] == "Objects"  # Check layer name

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
            'next_number': '15',
            'next_level': 'Level B',
            'background_image': 'raster_layer_id'
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
            result = self.qfield_service.package_for_qfield_with_data_and_variables(
                feature_data=feature_data,
                recording_areas_layer_id='recording_areas',
                objects_layer_id='objects',
                features_layer_id='features',
                background_layer_id='background',
                destination_folder='/tmp/test',
                project_name='TestProject',
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
            result = self.qfield_service.package_for_qfield_with_data_and_variables(
                feature_data=feature_data,
                recording_areas_layer_id='recording_areas',
                objects_layer_id='objects',
                features_layer_id='features',
                background_layer_id='background',
                destination_folder='/tmp/test',
                project_name='TestProject',
                next_values=next_values
            )
            assert result is True
            mock_add_vars.assert_called_once()

    def test_add_project_variables_to_qfield_project_file(self):
        """Test adding project variables to a QField project file."""
        # Mock QFieldSync available
        self.qfield_service._qfieldsync_available = True
        
        # Mock QGIS project for reading
        mock_qfield_project = Mock()
        mock_qfield_project.writeEntry = Mock()
        mock_qfield_project.readListEntry = Mock(side_effect=lambda group, key: ([], True) if key == 'variableNames' or key == 'variableValues' else ([], False))
        mock_qfield_project.write = Mock(return_value=True)
        
        # Mock QgsProject.read method to return True (success)
        with patch('services.qfield_service.QgsProject') as mock_qgs_project_class:
            mock_qgs_project_class.return_value = mock_qfield_project
            mock_qfield_project.read.return_value = True
            
            # Call the method with correct parameters
            self.qfield_service._add_project_variables_to_qfield_project(
                '/tmp/test/project.qgs',
                {
                    'attributes': {'display_name': 'Test Recording Area'}
                },
                {
                    'next_number': '15',
                    'next_level': 'Level B'
                }
            )
            
            # Verify that writeEntry was called with the correct values
            # Check that readListEntry was called for both variableNames and variableValues
            mock_qfield_project.readListEntry.assert_any_call('Variables', 'variableNames')
            mock_qfield_project.readListEntry.assert_any_call('Variables', 'variableValues')
            
            # Check that writeEntry was called to save the updated lists
            mock_qfield_project.writeEntry.assert_any_call('Variables', 'variableNames', ['recording_area', 'level', 'first_number'])
            mock_qfield_project.writeEntry.assert_any_call('Variables', 'variableValues', ['Test Recording Area', 'Level B', '15'])


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestQFieldServiceIntegration:
    """Integration tests for QFieldService with real QGIS environment."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.qfield_service = QGISQFieldService(self.settings_manager, self.layer_service)

    def test_qfield_service_with_real_environment(self):
        """Test QField service with real QGIS environment."""
        # Test basic functionality
        assert self.qfield_service is not None
        
        # Test QFieldSync availability check
        # This will depend on whether QFieldSync is actually available in the test environment
        assert hasattr(self.qfield_service, '_qfieldsync_available')
        
        # Test settings manager integration
        self.settings_manager.get_value.return_value = True
        assert self.qfield_service.is_qfield_enabled() is True 