# coding=utf-8
"""Services tests.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import unittest
import tempfile
import os
import shutil
from unittest.mock import Mock, patch, MagicMock

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsFields, QgsField
    from services.settings_service import QGISSettingsManager
    from services.file_system_service import QGISFileSystemService
    from services.layer_service import QGISLayerService
    from services.translation_service import QGISTranslationService
    from services.configuration_validator import ArcheoSyncConfigurationValidator
    from core.interfaces import ISettingsManager, IFileSystemService, ILayerService, ITranslationService, IConfigurationValidator
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app


class TestQGISSettingsManager(unittest.TestCase):
    """Test cases for QGISSettingsManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_patcher = patch('services.settings_service.QSettings')
        self.mock_qsettings_class = self.settings_patcher.start()
        self.mock_qsettings = Mock()
        self.mock_qsettings_class.return_value = self.mock_qsettings
        
        self.settings_manager = QGISSettingsManager()
    
    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()
    
    def test_implements_interface(self):
        """Test that QGISSettingsManager implements ISettingsManager."""
        self.assertIsInstance(self.settings_manager, ISettingsManager)
    
    def test_init(self):
        """Test settings manager initialization."""
        self.mock_qsettings_class.assert_called_once()
        self.assertEqual(self.settings_manager.plugin_group, 'ArcheoSync')
    
    def test_set_value(self):
        """Test setting a value."""
        key = 'test_key'
        value = 'test_value'
        
        self.settings_manager.set_value(key, value)
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.setValue.assert_called_with(key, value)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_get_value_with_default(self):
        """Test getting a value with default."""
        key = 'test_key'
        default = 'default_value'
        
        self.mock_qsettings.value.return_value = default
        
        result = self.settings_manager.get_value(key, default)
        
        self.assertEqual(result, default)
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.value.assert_called_with(key, default)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_get_value_existing(self):
        """Test getting an existing value."""
        key = 'test_key'
        stored_value = 'stored_value'
        default = 'default_value'
        
        self.mock_qsettings.value.return_value = stored_value
        
        result = self.settings_manager.get_value(key, default)
        
        self.assertEqual(result, stored_value)
    
    def test_remove_value(self):
        """Test removing a value."""
        key = 'test_key'
        
        self.settings_manager.remove_value(key)
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.remove.assert_called_with(key)
        self.mock_qsettings.endGroup.assert_called()
    
    def test_clear_all(self):
        """Test clearing all settings."""
        self.settings_manager.clear_all()
        
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.clear.assert_called()
        self.mock_qsettings.endGroup.assert_called()
    
    def test_custom_plugin_group(self):
        """Test using a custom plugin group."""
        custom_group = 'CustomPlugin'
        settings_manager = QGISSettingsManager(custom_group)
        
        self.assertEqual(settings_manager.plugin_group, custom_group)
        
        # Test that it uses the custom group
        settings_manager.set_value('test', 'value')
        self.mock_qsettings.beginGroup.assert_called_with(custom_group)


class TestQGISFileSystemService(unittest.TestCase):
    """Test cases for QGISFileSystemService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parent_widget = Mock()
        self.file_system_service = QGISFileSystemService(self.parent_widget)
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.temp_file, 'w') as f:
            f.write('test content')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that QGISFileSystemService implements IFileSystemService."""
        self.assertIsInstance(self.file_system_service, IFileSystemService)
    
    @patch('services.file_system_service.QFileDialog')
    def test_select_directory(self, mock_file_dialog):
        """Test directory selection."""
        mock_file_dialog.getExistingDirectory.return_value = self.temp_dir
        
        result = self.file_system_service.select_directory("Test Title", "/initial/path")
        
        self.assertEqual(result, self.temp_dir)
        mock_file_dialog.getExistingDirectory.assert_called_with(
            self.parent_widget, "Test Title", "/initial/path"
        )
    
    @patch('services.file_system_service.QFileDialog')
    def test_select_directory_cancelled(self, mock_file_dialog):
        """Test directory selection when cancelled."""
        mock_file_dialog.getExistingDirectory.return_value = ""
        
        result = self.file_system_service.select_directory("Test Title")
        
        self.assertIsNone(result)
    
    def test_path_exists(self):
        """Test path existence check."""
        self.assertTrue(self.file_system_service.path_exists(self.temp_dir))
        self.assertTrue(self.file_system_service.path_exists(self.temp_file))
        self.assertFalse(self.file_system_service.path_exists('/nonexistent/path'))
    
    def test_create_directory(self):
        """Test directory creation."""
        new_dir = os.path.join(self.temp_dir, 'new_dir')
        
        # Test creating new directory
        result = self.file_system_service.create_directory(new_dir)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(new_dir))
        
        # Test creating existing directory
        result = self.file_system_service.create_directory(new_dir)
        self.assertTrue(result)
    
    def test_is_directory(self):
        """Test directory check."""
        self.assertTrue(self.file_system_service.is_directory(self.temp_dir))
        self.assertFalse(self.file_system_service.is_directory(self.temp_file))
    
    def test_is_file(self):
        """Test file check."""
        self.assertTrue(self.file_system_service.is_file(self.temp_file))
        self.assertFalse(self.file_system_service.is_file(self.temp_dir))
    
    def test_get_file_extension(self):
        """Test file extension extraction."""
        self.assertEqual(self.file_system_service.get_file_extension('test.txt'), '.txt')
        self.assertEqual(self.file_system_service.get_file_extension('test.TXT'), '.TXT')
        self.assertEqual(self.file_system_service.get_file_extension('test'), '')
        self.assertEqual(self.file_system_service.get_file_extension('test.file.txt'), '.txt')
    
    def test_list_files(self):
        """Test file listing."""
        # Create test files
        test_files = ['test1.txt', 'test2.csv', 'test3.txt']
        for filename in test_files:
            with open(os.path.join(self.temp_dir, filename), 'w') as f:
                f.write('content')
        
        # Test listing all files
        all_files = self.file_system_service.list_files(self.temp_dir)
        self.assertEqual(len(all_files), 4)  # 3 test files + 1 from setUp
        
        # Test listing with extension filter
        txt_files = self.file_system_service.list_files(self.temp_dir, '.txt')
        self.assertEqual(len(txt_files), 3)
        
        # Test listing with non-existent directory
        result = self.file_system_service.list_files('/nonexistent')
        self.assertEqual(result, [])
        
        # Test listing with file instead of directory
        result = self.file_system_service.list_files(self.temp_file)
        self.assertEqual(result, [])
    
    def test_move_file_success(self):
        """Test successful file move operation."""
        source_file = os.path.join(self.temp_dir, 'source.txt')
        dest_file = os.path.join(self.temp_dir, 'dest.txt')
        
        # Create source file
        with open(source_file, 'w') as f:
            f.write('source content')
        
        # Test move
        result = self.file_system_service.move_file(source_file, dest_file)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(dest_file))
        self.assertFalse(os.path.exists(source_file))
    
    def test_move_file_source_not_exists(self):
        """Test file move when source file does not exist."""
        result = self.file_system_service.move_file('/nonexistent/file.txt', '/dest/file.txt')
        self.assertFalse(result)
    
    def test_move_file_destination_exists(self):
        """Test file move when destination already exists."""
        source_file = os.path.join(self.temp_dir, 'source.txt')
        dest_file = os.path.join(self.temp_dir, 'dest.txt')
        
        # Create both files
        with open(source_file, 'w') as f:
            f.write('source content')
        with open(dest_file, 'w') as f:
            f.write('dest content')
        
        # Test move - should create a new filename
        result = self.file_system_service.move_file(source_file, dest_file)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(source_file))
        # Should have created a new file with _1 suffix
        new_files = [f for f in os.listdir(self.temp_dir) if f.startswith('dest') and f.endswith('.txt')]
        self.assertEqual(len(new_files), 2)  # Original dest.txt and new dest_1.txt
        self.assertTrue('dest.txt' in new_files)
        self.assertTrue('dest_1.txt' in new_files)
    
    def test_move_directory_success(self):
        """Test successful directory move operation."""
        source_dir = os.path.join(self.temp_dir, 'source_dir')
        dest_dir = os.path.join(self.temp_dir, 'dest_dir')
        
        # Create source directory with a file
        os.makedirs(source_dir)
        with open(os.path.join(source_dir, 'test.txt'), 'w') as f:
            f.write('test content')
        
        # Test move
        result = self.file_system_service.move_directory(source_dir, dest_dir)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(dest_dir))
        self.assertFalse(os.path.exists(source_dir))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, 'test.txt')))
    
    def test_move_directory_source_not_exists(self):
        """Test directory move when source directory does not exist."""
        result = self.file_system_service.move_directory('/nonexistent/dir', '/dest/dir')
        self.assertFalse(result)
    
    def test_move_directory_source_not_directory(self):
        """Test directory move when source is not a directory."""
        result = self.file_system_service.move_directory(self.temp_file, '/dest/dir')
        self.assertFalse(result)
    
    def test_move_directory_destination_exists(self):
        """Test directory move when destination already exists."""
        source_dir = os.path.join(self.temp_dir, 'source_dir')
        dest_dir = os.path.join(self.temp_dir, 'dest_dir')
        
        # Create both directories
        os.makedirs(source_dir)
        os.makedirs(dest_dir)
        with open(os.path.join(source_dir, 'test.txt'), 'w') as f:
            f.write('source content')
        with open(os.path.join(dest_dir, 'existing.txt'), 'w') as f:
            f.write('dest content')
        
        # Test move - should create a new directory name
        result = self.file_system_service.move_directory(source_dir, dest_dir)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(source_dir))
        # Should have created a new directory with _1 suffix
        new_dirs = [d for d in os.listdir(self.temp_dir) if d.startswith('dest_dir')]
        self.assertEqual(len(new_dirs), 2)  # Original dest_dir and new dest_dir_1
        self.assertTrue('dest_dir' in new_dirs)
        self.assertTrue('dest_dir_1' in new_dirs)


class TestQGISLayerService(unittest.TestCase):
    """Test cases for QGISLayerService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.layer_service = QGISLayerService()
    
    def test_implements_interface(self):
        """Test that QGISLayerService implements ILayerService."""
        self.assertIsInstance(self.layer_service, ILayerService)
    
    @patch('services.layer_service.QgsProject')
    def test_get_polygon_layers_empty_project(self, mock_project):
        """Test getting polygon layers from empty project."""
        mock_instance = Mock()
        mock_instance.mapLayers.return_value = {}
        mock_project.instance.return_value = mock_instance
        
        polygon_layers = self.layer_service.get_polygon_layers()
        
        self.assertIsInstance(polygon_layers, list)
        self.assertEqual(len(polygon_layers), 0)
    
    @patch('services.layer_service.QgsProject')
    def test_get_polygon_layers_with_polygon_layer(self, mock_project):
        """Test getting polygon layers with polygon layer."""
        # Create mock polygon layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        mock_layer.id.return_value = "test_layer_id"
        mock_layer.name.return_value = "Test Polygon Layer"
        mock_layer.source.return_value = "/path/to/test.shp"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.featureCount.return_value = 10
        
        mock_instance = Mock()
        mock_instance.mapLayers.return_value = {"test_layer_id": mock_layer}
        mock_project.instance.return_value = mock_instance
        
        polygon_layers = self.layer_service.get_polygon_layers()
        
        self.assertEqual(len(polygon_layers), 1)
        layer_info = polygon_layers[0]
        self.assertEqual(layer_info['id'], "test_layer_id")
        self.assertEqual(layer_info['name'], "Test Polygon Layer")
        self.assertEqual(layer_info['source'], "/path/to/test.shp")
        self.assertEqual(layer_info['crs'], "EPSG:4326")
        self.assertEqual(layer_info['feature_count'], 10)
    
    @patch('services.layer_service.QgsProject')
    def test_get_polygon_layers_filters_non_polygon(self, mock_project):
        """Test that only polygon layers are returned."""
        # Create mock non-polygon layer
        mock_non_polygon_layer = Mock(spec=QgsVectorLayer)
        mock_non_polygon_layer.geometryType.return_value = 1  # LineGeometry
        
        # Create mock polygon layer
        mock_polygon_layer = Mock(spec=QgsVectorLayer)
        mock_polygon_layer.geometryType.return_value = 3  # PolygonGeometry
        mock_polygon_layer.id.return_value = "polygon_layer_id"
        mock_polygon_layer.name.return_value = "Polygon Layer"
        mock_polygon_layer.source.return_value = "/path/to/polygon.shp"
        mock_polygon_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_polygon_layer.featureCount.return_value = 5
        
        mock_instance = Mock()
        mock_instance.mapLayers.return_value = {
            "line_layer_id": mock_non_polygon_layer,
            "polygon_layer_id": mock_polygon_layer
        }
        mock_project.instance.return_value = mock_instance
        
        polygon_layers = self.layer_service.get_polygon_layers()
        
        self.assertEqual(len(polygon_layers), 1)
        self.assertEqual(polygon_layers[0]['id'], "polygon_layer_id")
    
    @patch('services.layer_service.QgsProject')
    def test_get_layer_by_id_not_found(self, mock_project):
        """Test getting layer by ID when not found."""
        mock_instance = Mock()
        mock_instance.mapLayer.return_value = None
        mock_project.instance.return_value = mock_instance
        
        layer = self.layer_service.get_layer_by_id("non_existent_id")
        self.assertIsNone(layer)
    
    @patch('services.layer_service.QgsProject')
    def test_get_layer_by_id_found(self, mock_project):
        """Test getting layer by ID when found."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        
        mock_instance = Mock()
        mock_instance.mapLayer.return_value = mock_layer
        mock_project.instance.return_value = mock_instance
        
        layer = self.layer_service.get_layer_by_id("test_layer_id")
        self.assertEqual(layer, mock_layer)
    
    @patch('services.layer_service.QgsProject')
    def test_get_layer_by_id_wrong_type(self, mock_project):
        """Test getting layer by ID when layer exists but is wrong type."""
        mock_non_vector_layer = Mock()
        
        mock_instance = Mock()
        mock_instance.mapLayer.return_value = mock_non_vector_layer
        mock_project.instance.return_value = mock_instance
        
        layer = self.layer_service.get_layer_by_id("test_layer_id")
        self.assertIsNone(layer)
    
    @patch.object(QGISLayerService, 'get_layer_by_id')
    def test_is_valid_polygon_layer_valid(self, mock_get_layer):
        """Test checking if layer is valid polygon layer."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        mock_get_layer.return_value = mock_layer
        
        is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
        self.assertTrue(is_valid)
    
    @patch.object(QGISLayerService, 'get_layer_by_id')
    def test_is_valid_polygon_layer_invalid_geometry(self, mock_get_layer):
        """Test checking if layer is valid polygon layer with wrong geometry."""
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 1  # LineGeometry
        mock_get_layer.return_value = mock_layer
        
        is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
        self.assertFalse(is_valid)
    
    @patch.object(QGISLayerService, 'get_layer_by_id')
    def test_is_valid_polygon_layer_not_found(self, mock_get_layer):
        """Test checking if layer is valid polygon layer when not found."""
        mock_get_layer.return_value = None
        
        is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
        self.assertFalse(is_valid)
    
    @patch.object(QGISLayerService, 'get_layer_by_id')
    def test_get_layer_info_not_found(self, mock_get_layer):
        """Test getting layer info when layer not found."""
        mock_get_layer.return_value = None
        
        layer_info = self.layer_service.get_layer_info("test_layer_id")
        self.assertIsNone(layer_info)
    
    @patch.object(QGISLayerService, 'get_layer_by_id')
    def test_get_layer_info_found(self, mock_get_layer):
        """Test getting layer info when layer found."""
        mock_layer = Mock()
        mock_layer.id = Mock(return_value="test_layer_id")
        mock_layer.name = Mock(return_value="Test Layer")
        mock_layer.source = Mock(return_value="/path/to/test.shp")
        mock_layer.crs = Mock()
        mock_layer.crs().authid = Mock(return_value="EPSG:4326")
        mock_layer.featureCount = Mock(return_value=15)
        mock_layer.isValid = Mock(return_value=True)
        
        mock_get_layer.return_value = mock_layer
        
        layer_info = self.layer_service.get_layer_info("test_layer_id")
        
        self.assertIsNotNone(layer_info)
        self.assertEqual(layer_info['id'], "test_layer_id")
        self.assertEqual(layer_info['name'], "Test Layer")
        self.assertEqual(layer_info['source'], "/path/to/test.shp")
        self.assertEqual(layer_info['crs'], "EPSG:4326")
        self.assertEqual(layer_info['feature_count'], 15)
        self.assertEqual(layer_info['geometry_type'], 2)  # Polygon geometry type
        self.assertTrue(layer_info['is_valid'])

    @patch('services.layer_service.QgsProject')
    @patch('services.layer_service.isinstance')
    def test_get_polygon_layers(self, mock_isinstance, mock_qgs_project):
        """Test getting polygon layers from the service."""
        # Mock QGIS project and layers
        mock_layer1 = Mock()
        mock_layer1.id.return_value = "layer1"
        mock_layer1.name.return_value = "Test Layer 1"
        mock_layer1.source.return_value = "/path/to/layer1.shp"
        mock_layer1.crs.return_value = Mock()
        mock_layer1.crs().authid.return_value = "EPSG:4326"
        mock_layer1.featureCount.return_value = 10
        mock_layer1.geometryType.return_value = 2  # Polygon/MultiPolygon
        
        mock_layer2 = Mock()
        mock_layer2.id.return_value = "layer2"
        mock_layer2.name.return_value = "Test Layer 2"
        mock_layer2.source.return_value = "/path/to/layer2.shp"
        mock_layer2.crs.return_value = Mock()
        mock_layer2.crs().authid.return_value = "EPSG:4326"
        mock_layer2.featureCount.return_value = 5
        mock_layer2.geometryType.return_value = 3  # Polygon
        
        # Mock isinstance to return True for our mock layers
        def mock_isinstance_func(obj, cls):
            return obj in [mock_layer1, mock_layer2]
        mock_isinstance.side_effect = mock_isinstance_func
        
        mock_project = Mock()
        mock_project.mapLayers.return_value = {
            "layer1": mock_layer1,
            "layer2": mock_layer2
        }
        
        mock_qgs_project.instance.return_value = mock_project
        
        layer_service = QGISLayerService()
        polygon_layers = layer_service.get_polygon_layers()
        
        self.assertEqual(len(polygon_layers), 2)
        self.assertEqual(polygon_layers[0]['id'], "layer1")
        self.assertEqual(polygon_layers[0]['name'], "Test Layer 1")
        self.assertEqual(polygon_layers[0]['feature_count'], 10)
        self.assertEqual(polygon_layers[1]['id'], "layer2")
        self.assertEqual(polygon_layers[1]['name'], "Test Layer 2")
        self.assertEqual(polygon_layers[1]['feature_count'], 5)
    
    @patch('services.layer_service.QgsProject')
    @patch('services.layer_service.isinstance')
    def test_get_polygon_and_multipolygon_layers(self, mock_isinstance, mock_qgs_project):
        """Test getting polygon and multipolygon layers from the service."""
        # Mock QGIS project and layers
        mock_layer1 = Mock()
        mock_layer1.id.return_value = "layer1"
        mock_layer1.name.return_value = "Test Layer 1"
        mock_layer1.source.return_value = "/path/to/layer1.shp"
        mock_layer1.crs.return_value = Mock()
        mock_layer1.crs().authid.return_value = "EPSG:4326"
        mock_layer1.featureCount.return_value = 10
        mock_layer1.geometryType.return_value = 2  # Polygon/MultiPolygon
        
        mock_layer2 = Mock()
        mock_layer2.id.return_value = "layer2"
        mock_layer2.name.return_value = "Test Layer 2"
        mock_layer2.source.return_value = "/path/to/layer2.shp"
        mock_layer2.crs.return_value = Mock()
        mock_layer2.crs().authid.return_value = "EPSG:4326"
        mock_layer2.featureCount.return_value = 5
        mock_layer2.geometryType.return_value = 3  # Polygon
        
        # Mock isinstance to return True for our mock layers
        def mock_isinstance_func(obj, cls):
            return obj in [mock_layer1, mock_layer2]
        mock_isinstance.side_effect = mock_isinstance_func
        
        mock_project = Mock()
        mock_project.mapLayers.return_value = {
            "layer1": mock_layer1,
            "layer2": mock_layer2
        }
        
        mock_qgs_project.instance.return_value = mock_project
        
        layer_service = QGISLayerService()
        layers = layer_service.get_polygon_and_multipolygon_layers()
        
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0]['id'], "layer1")
        self.assertEqual(layers[0]['name'], "Test Layer 1")
        self.assertEqual(layers[0]['feature_count'], 10)
        self.assertEqual(layers[1]['id'], "layer2")
        self.assertEqual(layers[1]['name'], "Test Layer 2")
        self.assertEqual(layers[1]['feature_count'], 5)
    
    def test_is_valid_polygon_or_multipolygon_layer(self):
        """Test validation of polygon or multipolygon layers."""
        # Mock layer service
        mock_layer = Mock()
        mock_layer.geometryType.return_value = 2  # Polygon/MultiPolygon
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_polygon_or_multipolygon_layer("test_layer")
            self.assertTrue(result)
        
        # Test with polygon geometry
        mock_layer.geometryType.return_value = 3  # Polygon
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_polygon_or_multipolygon_layer("test_layer")
            self.assertTrue(result)
        
        # Test with invalid geometry
        mock_layer.geometryType.return_value = 1  # Line
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_polygon_or_multipolygon_layer("test_layer")
            self.assertFalse(result)
        
        # Test with non-existent layer
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.is_valid_polygon_or_multipolygon_layer("non_existent")
            self.assertFalse(result)

    def test_get_layer_fields_success(self):
        """Test successful retrieval of layer fields."""
        # Create mock layer with fields
        mock_layer = MagicMock()
        mock_field1 = MagicMock()
        mock_field1.name.return_value = "id"
        mock_field1.typeName.return_value = "Integer"
        mock_field1.type.return_value = 2  # QGIS integer type
        mock_field1.comment.return_value = "Primary key"
        mock_field1.isNumeric.return_value = True
        
        mock_field2 = MagicMock()
        mock_field2.name.return_value = "name"
        mock_field2.typeName.return_value = "String"
        mock_field2.type.return_value = 10  # QGIS string type
        mock_field2.comment.return_value = "Feature name"
        mock_field2.isNumeric.return_value = False
        
        mock_layer.fields.return_value = [mock_field1, mock_field2]
        mock_layer.id.return_value = "test_layer_id"
        
        # Mock the layer service to return the layer when get_layer_by_id is called
        self.layer_service.get_layer_by_id = MagicMock(return_value=mock_layer)
        
        # Test field retrieval
        fields = self.layer_service.get_layer_fields("test_layer_id")
        
        # Verify results
        self.assertIsNotNone(fields)
        self.assertEqual(len(fields), 2)
        
        # Check first field (integer)
        self.assertEqual(fields[0]['name'], "id")
        self.assertEqual(fields[0]['type'], "Integer")
        self.assertEqual(fields[0]['type_id'], 2)
        self.assertEqual(fields[0]['comment'], "Primary key")
        self.assertTrue(fields[0]['is_numeric'])
        self.assertTrue(fields[0]['is_integer'])
        
        # Check second field (string)
        self.assertEqual(fields[1]['name'], "name")
        self.assertEqual(fields[1]['type'], "String")
        self.assertEqual(fields[1]['type_id'], 10)
        self.assertEqual(fields[1]['comment'], "Feature name")
        self.assertFalse(fields[1]['is_numeric'])
        self.assertFalse(fields[1]['is_integer'])
    
    def test_get_layer_fields_integer_vs_real_types(self):
        """Test that Real type fields are not marked as integer fields."""
        # Create mock layer with integer and real fields
        mock_layer = MagicMock()
        
        # Integer field
        mock_integer_field = MagicMock()
        mock_integer_field.name.return_value = "integer_field"
        mock_integer_field.typeName.return_value = "Integer"
        mock_integer_field.type.return_value = 2  # QGIS integer type
        mock_integer_field.comment.return_value = "Integer field"
        mock_integer_field.isNumeric.return_value = True
        
        # Real (float) field
        mock_real_field = MagicMock()
        mock_real_field.name.return_value = "real_field"
        mock_real_field.typeName.return_value = "Real"
        mock_real_field.type.return_value = 6  # QGIS real type
        mock_real_field.comment.return_value = "Real field"
        mock_real_field.isNumeric.return_value = True
        
        # String field
        mock_string_field = MagicMock()
        mock_string_field.name.return_value = "string_field"
        mock_string_field.typeName.return_value = "String"
        mock_string_field.type.return_value = 10  # QGIS string type
        mock_string_field.comment.return_value = "String field"
        mock_string_field.isNumeric.return_value = False
        
        mock_layer.fields.return_value = [mock_integer_field, mock_real_field, mock_string_field]
        mock_layer.id.return_value = "test_layer_id"
        
        # Mock the layer service to return the layer when get_layer_by_id is called
        self.layer_service.get_layer_by_id = MagicMock(return_value=mock_layer)
        
        # Test field retrieval
        fields = self.layer_service.get_layer_fields("test_layer_id")
        
        # Verify results
        self.assertIsNotNone(fields)
        self.assertEqual(len(fields), 3)
        
        # Check integer field
        integer_field = next(f for f in fields if f['name'] == 'integer_field')
        self.assertTrue(integer_field['is_integer'])
        self.assertTrue(integer_field['is_numeric'])
        
        # Check real field - should NOT be marked as integer
        real_field = next(f for f in fields if f['name'] == 'real_field')
        self.assertFalse(real_field['is_integer'])
        self.assertTrue(real_field['is_numeric'])
        
        # Check string field
        string_field = next(f for f in fields if f['name'] == 'string_field')
        self.assertFalse(string_field['is_integer'])
        self.assertFalse(string_field['is_numeric'])
    
    def test_get_layer_fields_layer_not_found(self):
        """Test field retrieval when layer is not found."""
        # Mock the layer service with no layers
        self.layer_service._qgis_interface = MagicMock()
        self.layer_service._qgis_interface.mapCanvas.return_value.layers.return_value = []
        
        # Test field retrieval
        fields = self.layer_service.get_layer_fields("nonexistent_layer_id")
        
        # Verify result
        self.assertIsNone(fields)
    
    def test_get_layer_fields_empty_fields(self):
        """Test field retrieval when layer has no fields."""
        # Create mock layer with no fields
        mock_layer = MagicMock()
        mock_layer.fields.return_value = []
        mock_layer.id.return_value = "test_layer_id"
        
        # Mock the layer service to return the layer when get_layer_by_id is called
        self.layer_service.get_layer_by_id = MagicMock(return_value=mock_layer)
        
        # Test field retrieval
        fields = self.layer_service.get_layer_fields("test_layer_id")
        
        # Verify results
        self.assertIsNotNone(fields)
        self.assertEqual(len(fields), 0)

    def test_get_selected_features_count_layer_not_found(self):
        """Test getting selected features count when layer is not found."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.get_selected_features_count('non_existent_layer_id')
            self.assertEqual(result, 0)

    def test_get_selected_features_count_no_selection(self):
        """Test getting selected features count when no features are selected."""
        # Mock layer with no selected features
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = []
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.get_selected_features_count('test_layer_id')
            self.assertEqual(result, 0)

    def test_get_selected_features_count_with_selection(self):
        """Test getting selected features count when features are selected."""
        # Mock layer with selected features
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = [Mock(), Mock(), Mock()]  # 3 selected features
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.get_selected_features_count('test_layer_id')
            self.assertEqual(result, 3)

    def test_get_selected_features_info_layer_not_found(self):
        """Test getting selected features info when layer is not found."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.get_selected_features_info('non_existent_layer_id')
            self.assertEqual(result, [])

    def test_get_selected_features_info_no_selection(self):
        """Test getting selected features info when no features are selected."""
        # Mock layer with no selected features
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = []
        mock_layer.displayExpression.return_value = ''
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.get_selected_features_info('test_layer_id')
            self.assertEqual(result, [])

    def test_get_selected_features_info_with_display_expression(self):
        """Test getting selected features info with display expression."""
        from qgis.core import QgsFeature, QgsFields, QgsField
        from qgis.PyQt.QtCore import QVariant

        # Create fields
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))

        # Create features
        feature1 = QgsFeature(fields)
        feature1.setAttribute("name", "Area A")
        feature2 = QgsFeature(fields)
        feature2.setAttribute("name", "Area B")

        # Mock layer with display expression
        mock_layer = Mock()
        mock_layer.selectedFeatures.return_value = [feature1, feature2]
        mock_layer.displayExpression.return_value = 'name'
        mock_fields = Mock()
        mock_fields.indexOf.return_value = -1
        mock_layer.fields.return_value = mock_fields

        # Patch layerScope and appendScope as before
        with patch('qgis.core.QgsExpressionContextUtils.layerScope', return_value=Mock()):
            with patch('qgis.core.QgsExpressionContext.appendScope', return_value=None):
                with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
                    result = self.layer_service.get_selected_features_info('test_layer_id')
                    # Should be sorted alphabetically
                    self.assertEqual(len(result), 2)
                    self.assertEqual(result[0]['name'], "Area A")
                    self.assertEqual(result[1]['name'], "Area B")

    def test_get_selected_features_info_with_empty_display_expression(self):
        """Test getting selected features info with empty display expression."""
        # Create mock layer with empty display expression
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.displayExpression.return_value = ""
        mock_layer.fields.return_value = Mock()
        mock_layer.fields().indexOf.return_value = -1  # No name fields found
        
        # Create mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 123
        mock_layer.selectedFeatures.return_value = [mock_feature]
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            features_info = self.layer_service.get_selected_features_info("test_layer_id")
            
            self.assertEqual(len(features_info), 1)
            self.assertEqual(features_info[0]['name'], "123")

    def test_get_layer_relationships_layer_not_found(self):
        """Test getting layer relationships when layer is not found."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            relations = self.layer_service.get_layer_relationships("non_existent_layer")
            self.assertEqual(relations, [])

    @patch('services.layer_service.QgsProject')
    def test_get_layer_relationships_with_relations(self, mock_project):
        """Test getting layer relationships when relations exist."""
        # Create mock layer
        mock_layer = Mock(spec=QgsVectorLayer)
        
        # Create mock relations
        mock_relation1 = Mock()
        mock_relation1.referencingLayerId.return_value = "child_layer"
        mock_relation1.referencedLayerId.return_value = "parent_layer"
        
        mock_relation2 = Mock()
        mock_relation2.referencingLayerId.return_value = "other_child"
        mock_relation2.referencedLayerId.return_value = "child_layer"
        
        # Create mock relation manager
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {
            "relation1": mock_relation1,
            "relation2": mock_relation2
        }
        
        # Create mock project
        mock_project_instance = Mock()
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            relations = self.layer_service.get_layer_relationships("child_layer")
            
            # Should find both relations: one where child_layer is referencing, one where it's referenced
            self.assertEqual(len(relations), 2)
            self.assertIn(mock_relation1, relations)
            self.assertIn(mock_relation2, relations)

    def test_get_related_objects_info_no_objects_layer(self):
        """Test getting related objects info when no objects layer is configured."""
        # Mock feature
        mock_feature = Mock()
        
        result = self.layer_service.get_related_objects_info(
            mock_feature, '', 'number_field', 'level_field', None
        )
        
        self.assertEqual(result['last_number'], '')
        self.assertEqual(result['last_level'], '')

    def test_get_related_objects_info_objects_layer_not_found(self):
        """Test getting related objects info when objects layer is not found."""
        # Mock feature
        mock_feature = Mock()
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.get_related_objects_info(
                mock_feature, 'objects_layer_id', 'number_field', 'level_field', None
            )
            
            self.assertEqual(result['last_number'], '')
            self.assertEqual(result['last_level'], '')

    @patch('services.layer_service.QgsProject')
    def test_get_related_objects_info_no_relations(self, mock_project):
        """Test getting related objects info when no relations exist."""
        # Mock feature and layer
        mock_feature = Mock()
        mock_layer = Mock()
        mock_feature.layer.return_value = Mock()
        mock_feature.layer().id.return_value = 'recording_layer_id'
        
        # Mock project and relation manager
        mock_project_instance = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {}
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.get_related_objects_info(
                mock_feature, 'objects_layer_id', 'number_field', 'level_field', None
            )
            
            self.assertEqual(result['last_number'], '')
            self.assertEqual(result['last_level'], '')

    @patch('services.layer_service.QgsProject')
    def test_get_related_objects_info_with_relations_no_related_features(self, mock_project):
        """Test getting related objects info when relations exist but no related features."""
        # Mock feature and layer
        mock_feature = Mock()
        mock_layer = Mock()
        mock_feature.layer.return_value = Mock()
        mock_feature.layer().id.return_value = 'recording_layer_id'
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = 'objects_layer_id'
        mock_relation.referencedLayerId.return_value = 'recording_layer_id'
        mock_relation.getRelatedFeatures.return_value = []
        
        # Mock project and relation manager
        mock_project_instance = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.get_related_objects_info(
                mock_feature, 'objects_layer_id', 'number_field', 'level_field', None
            )
            
            self.assertEqual(result['last_number'], '')
            self.assertEqual(result['last_level'], '')

    @patch('services.layer_service.QgsProject')
    def test_get_related_objects_info_with_number_field(self, mock_project):
        """Test getting related objects info with number field configured."""
        # Mock feature and layer
        mock_feature = Mock()
        mock_layer = Mock()
        mock_feature.layer.return_value = Mock()
        mock_feature.layer().id.return_value = 'recording_layer_id'
        
        # Mock related object features
        mock_obj_feature1 = Mock()
        mock_obj_feature1.attribute.return_value = 5
        
        mock_obj_feature2 = Mock()
        mock_obj_feature2.attribute.return_value = 10
        
        # Mock layer fields
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Field found at index 0
        mock_layer.fields.return_value = mock_fields
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = 'objects_layer_id'
        mock_relation.referencedLayerId.return_value = 'recording_layer_id'
        mock_relation.getRelatedFeatures.return_value = [mock_obj_feature1, mock_obj_feature2]
        
        # Mock project and relation manager
        mock_project_instance = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            with patch.object(self.layer_service, 'get_layer_fields', return_value=None):
                result = self.layer_service.get_related_objects_info(
                    mock_feature, 'objects_layer_id', 'number_field', None, 'recording_layer_id'
                )
                
                self.assertEqual(result['last_number'], '10')  # Highest number
                self.assertEqual(result['last_level'], '')

    @patch('services.layer_service.QgsProject')
    def test_get_related_objects_info_with_level_field_string(self, mock_project):
        """Test getting related objects info with string level field."""
        # Mock feature and layer
        mock_feature = Mock()
        mock_layer = Mock()
        mock_feature.layer.return_value = Mock()
        mock_feature.layer().id.return_value = 'recording_layer_id'
        
        # Mock related object features
        mock_obj_feature1 = Mock()
        mock_obj_feature1.attribute.return_value = 'Level A'
        
        mock_obj_feature2 = Mock()
        mock_obj_feature2.attribute.return_value = 'Level B'
        
        # Mock layer fields
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Field found at index 0
        mock_layer.fields.return_value = mock_fields
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = 'objects_layer_id'
        mock_relation.referencedLayerId.return_value = 'recording_layer_id'
        mock_relation.getRelatedFeatures.return_value = [mock_obj_feature1, mock_obj_feature2]
        
        # Mock project and relation manager
        mock_project_instance = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        # Mock field info (string field)
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
                result = self.layer_service.get_related_objects_info(
                    mock_feature, 'objects_layer_id', None, 'level_field', 'recording_layer_id'
                )
                
                self.assertEqual(result['last_number'], '')
                self.assertEqual(result['last_level'], 'Level B')  # Alphabetically last

    @patch('services.layer_service.QgsProject')
    def test_get_related_objects_info_with_level_field_integer(self, mock_project):
        """Test getting related objects info with integer level field."""
        # Mock feature and layer
        mock_feature = Mock()
        mock_layer = Mock()
        mock_feature.layer.return_value = Mock()
        mock_feature.layer().id.return_value = 'recording_layer_id'
        
        # Mock related object features
        mock_obj_feature1 = Mock()
        mock_obj_feature1.attribute.return_value = 5
        
        mock_obj_feature2 = Mock()
        mock_obj_feature2.attribute.return_value = 10
        
        # Mock layer fields
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Field found at index 0
        mock_layer.fields.return_value = mock_fields
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = 'objects_layer_id'
        mock_relation.referencedLayerId.return_value = 'recording_layer_id'
        mock_relation.getRelatedFeatures.return_value = [mock_obj_feature1, mock_obj_feature2]
        
        # Mock project and relation manager
        mock_project_instance = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project_instance.relationManager.return_value = mock_relation_manager
        mock_project.instance.return_value = mock_project_instance
        
        # Mock field info (integer field)
        field_info = [{'name': 'level_field', 'is_integer': True}]
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
                result = self.layer_service.get_related_objects_info(
                    mock_feature, 'objects_layer_id', None, 'level_field', 'recording_layer_id'
                )
                
                self.assertEqual(result['last_number'], '')
                self.assertEqual(result['last_level'], '10')  # Numerically highest

    def test_calculate_next_level_empty_last_level(self):
        """Test calculating next level when last level is empty."""
        # Mock field info for string field
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            result = self.layer_service.calculate_next_level('', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'a')  # Should start with 'a' for string fields
        
        # Mock field info for integer field
        field_info = [{'name': 'level_field', 'is_integer': True}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            result = self.layer_service.calculate_next_level('', 'level_field', 'objects_layer_id')
            self.assertEqual(result, '1')  # Should start with '1' for integer fields

    def test_calculate_next_level_string_field_single_char(self):
        """Test calculating next level for string field with single character levels."""
        # Mock field info for string field
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test basic alphabetical increment
            result = self.layer_service.calculate_next_level('a', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'b')
            
            result = self.layer_service.calculate_next_level('b', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'c')
            
            # Test wrap-around from 'z' to 'aa'
            result = self.layer_service.calculate_next_level('z', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'aa')

    def test_calculate_next_level_integer_field(self):
        """Test calculating next level for integer field."""
        # Mock field info for integer field
        field_info = [{'name': 'level_field', 'is_integer': True}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test basic numeric increment
            result = self.layer_service.calculate_next_level('1', 'level_field', 'objects_layer_id')
            self.assertEqual(result, '2')
            
            result = self.layer_service.calculate_next_level('10', 'level_field', 'objects_layer_id')
            self.assertEqual(result, '11')
            
            result = self.layer_service.calculate_next_level('99', 'level_field', 'objects_layer_id')
            self.assertEqual(result, '100')

    def test_calculate_next_level_mixed_content(self):
        """Test calculating next level for mixed content levels."""
        # Mock field info for string field
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test numeric string
            result = self.layer_service.calculate_next_level('5', 'level_field', 'objects_layer_id')
            self.assertEqual(result, '6')  # Should increment numerically
            
            # Test mixed content
            result = self.layer_service.calculate_next_level('Level A', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'Level A1')

    def test_calculate_next_level_field_info_not_available(self):
        """Test calculating next level when field info is not available."""
        with patch.object(self.layer_service, 'get_layer_fields', return_value=None):
            result = self.layer_service.calculate_next_level('', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'a')  # Default to 'a'
            
            result = self.layer_service.calculate_next_level('a', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'b')

    def test_calculate_next_level_field_not_found(self):
        """Test calculating next level when field is not found in field info."""
        # Mock field info without the target field
        field_info = [{'name': 'other_field', 'is_integer': True}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            result = self.layer_service.calculate_next_level('a', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'b')  # Should fall back to string increment

    def test_calculate_next_level_invalid_number_conversion(self):
        """Test calculating next level when number conversion fails."""
        # Mock field info for integer field
        field_info = [{'name': 'level_field', 'is_integer': True}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test with non-numeric string that can't be converted to int
            result = self.layer_service.calculate_next_level('abc', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'abc1')  # Should append '1' as fallback

    def test_calculate_next_level_case_sensitivity(self):
        """Test calculating next level with case sensitivity."""
        # Mock field info for string field
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test uppercase letters - should preserve case
            result = self.layer_service.calculate_next_level('A', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'B')  # Should preserve uppercase and increment
            
            result = self.layer_service.calculate_next_level('Z', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'AA')  # Should wrap around to 'AA' for uppercase
            
            # Test lowercase letters - should preserve case
            result = self.layer_service.calculate_next_level('a', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'b')  # Should preserve lowercase and increment
            
            result = self.layer_service.calculate_next_level('z', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'aa')  # Should wrap around to 'aa' for lowercase

    def test_calculate_next_level_complex_strings(self):
        """Test calculating next level with complex string values."""
        # Mock field info for string field
        field_info = [{'name': 'level_field', 'is_integer': False}]
        
        with patch.object(self.layer_service, 'get_layer_fields', return_value=field_info):
            # Test with spaces and special characters
            result = self.layer_service.calculate_next_level('Level 1', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'Level 11')  # Should append '1'
            
            # Test with mixed content
            result = self.layer_service.calculate_next_level('A1', 'level_field', 'objects_layer_id')
            self.assertEqual(result, 'A2')  # Should increment to 'A2'


class TestQGISTranslationService(unittest.TestCase):
    """Test cases for QGISTranslationService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.plugin_dir = tempfile.mkdtemp()
        self.translation_service = QGISTranslationService(self.plugin_dir, 'TestPlugin')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.plugin_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that QGISTranslationService implements ITranslationService."""
        self.assertIsInstance(self.translation_service, ITranslationService)
    
    @patch('services.translation_service.QSettings')
    @patch('services.translation_service.QTranslator')
    @patch('services.translation_service.QCoreApplication')
    def test_init_with_translation_file(self, mock_core_app, mock_translator_class, mock_settings_class):
        """Test initialization with translation file."""
        # Mock QSettings
        mock_settings = Mock()
        mock_settings.value.return_value = 'en'
        mock_settings_class.return_value = mock_settings
        
        # Mock QTranslator
        mock_translator = Mock()
        mock_translator.load.return_value = True
        mock_translator_class.return_value = mock_translator
        
        # Create translation file
        i18n_dir = os.path.join(self.plugin_dir, 'i18n')
        os.makedirs(i18n_dir)
        translation_file = os.path.join(i18n_dir, 'TestPlugin_en.qm')
        with open(translation_file, 'w') as f:
            f.write('dummy content')
        
        service = QGISTranslationService(self.plugin_dir, 'TestPlugin')
        
        self.assertEqual(service.get_current_locale(), 'en')
        self.assertTrue(service.is_translation_loaded())
    
    @patch('services.translation_service.QCoreApplication')
    def test_translate(self, mock_core_app):
        """Test translation functionality."""
        mock_core_app.translate.return_value = 'Translated Message'
        
        result = self.translation_service.translate('Test Message')
        
        self.assertEqual(result, 'Translated Message')
        # The service uses the plugin name passed to constructor, which is 'TestPlugin' in setUp
        mock_core_app.translate.assert_called_with('TestPlugin', 'Test Message')
    
    def test_get_current_locale(self):
        """Test getting current locale."""
        locale = self.translation_service.get_current_locale()
        self.assertIsInstance(locale, str)
        self.assertGreater(len(locale), 0)
    
    def test_is_translation_loaded(self):
        """Test translation loaded status."""
        # Should be False when no translation file exists
        self.assertFalse(self.translation_service.is_translation_loaded())
    
    def test_get_translation_file_path(self):
        """Test getting translation file path."""
        # Should return None when no translation file exists
        self.assertIsNone(self.translation_service.get_translation_file_path())
        
        # Create translation file
        i18n_dir = os.path.join(self.plugin_dir, 'i18n')
        os.makedirs(i18n_dir)
        # Use the plugin name from setUp ('TestPlugin')
        translation_file = os.path.join(i18n_dir, 'TestPlugin_en.qm')
        with open(translation_file, 'w') as f:
            f.write('dummy content')
        
        path = self.translation_service.get_translation_file_path()
        self.assertEqual(path, translation_file)


class TestArcheoSyncConfigurationValidator(unittest.TestCase):
    """Test cases for ArcheoSyncConfigurationValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.file_system_service = Mock()
        self.layer_service = Mock()
        self.validator = ArcheoSyncConfigurationValidator(self.file_system_service, self.layer_service)
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.temp_file, 'w') as f:
            f.write('test content')
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_implements_interface(self):
        """Test that ArcheoSyncConfigurationValidator implements IConfigurationValidator."""
        self.assertIsInstance(self.validator, IConfigurationValidator)
    
    def test_validate_field_projects_folder_empty_path(self):
        """Test validation of empty field projects folder path."""
        errors = self.validator.validate_field_projects_folder('')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field projects folder path is required', errors[0])
    
    def test_validate_field_projects_folder_nonexistent(self):
        """Test validation of non-existent field projects folder path."""
        self.file_system_service.path_exists.return_value = False
        
        errors = self.validator.validate_field_projects_folder('/nonexistent/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field projects folder does not exist', errors[0])
    
    def test_validate_field_projects_folder_not_directory(self):
        """Test validation of field projects folder path that is not a directory."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = False
        
        errors = self.validator.validate_field_projects_folder('/path/to/file')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field projects path is not a directory', errors[0])
    
    def test_validate_field_projects_folder_not_writable(self):
        """Test validation of field projects folder that is not writable."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.is_writable.return_value = False
        
        errors = self.validator.validate_field_projects_folder('/readonly/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field projects folder is not writable', errors[0])
    
    def test_validate_total_station_folder_no_csv_files(self):
        """Test validation of total station folder with no CSV files."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.list_files.return_value = []
        
        errors = self.validator.validate_total_station_folder('/path/to/folder')
        self.assertEqual(len(errors), 0)  # No CSV files required, folder just needs to exist
    

    
    def test_validate_recording_areas_layer_empty_layer_id(self):
        """Test validation of empty recording areas layer ID."""
        errors = self.validator.validate_recording_areas_layer('')
        self.assertEqual(len(errors), 0)  # Empty layer ID is optional
    
    def test_validate_recording_areas_layer_nonexistent_layer(self):
        """Test validation of non-existent recording areas layer."""
        self.layer_service.is_valid_polygon_layer.return_value = False
        
        errors = self.validator.validate_recording_areas_layer('non_existent_layer_id')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not a valid polygon layer', errors[0])
    
    def test_validate_recording_areas_layer_invalid_layer(self):
        """Test validation of invalid recording areas layer."""
        self.layer_service.is_valid_polygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': False
        }
        
        errors = self.validator.validate_recording_areas_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not valid', errors[0])
    
    def test_validate_recording_areas_layer_layer_not_found(self):
        """Test validation of recording areas layer that doesn't exist."""
        self.layer_service.is_valid_polygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = None
        
        errors = self.validator.validate_recording_areas_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Layer not found in current project', errors[0])
    
    def test_validate_objects_layer_empty_layer_id(self):
        """Test validation of empty objects layer ID."""
        errors = self.validator.validate_objects_layer('')
        self.assertEqual(len(errors), 1)  # Empty layer ID is now mandatory
        self.assertIn('Objects layer is required', errors[0])
    
    def test_validate_objects_layer_nonexistent_layer(self):
        """Test validation of non-existent objects layer."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = False
        
        errors = self.validator.validate_objects_layer('non_existent_layer_id')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not a valid polygon or multipolygon layer', errors[0])
    
    def test_validate_objects_layer_invalid_layer(self):
        """Test validation of invalid objects layer."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': False
        }
        
        errors = self.validator.validate_objects_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not valid', errors[0])
    
    def test_validate_objects_layer_layer_not_found(self):
        """Test validation of objects layer that doesn't exist."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = None
        
        errors = self.validator.validate_objects_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Layer not found in current project', errors[0])
    
    def test_validate_features_layer_empty_layer_id(self):
        """Test validation of empty features layer ID."""
        errors = self.validator.validate_features_layer('')
        self.assertEqual(len(errors), 0)  # Empty layer ID is optional
    
    def test_validate_features_layer_nonexistent_layer(self):
        """Test validation of non-existent features layer."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = False
        
        errors = self.validator.validate_features_layer('non_existent_layer_id')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not a valid polygon or multipolygon layer', errors[0])
    
    def test_validate_features_layer_invalid_layer(self):
        """Test validation of invalid features layer."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': False
        }
        
        errors = self.validator.validate_features_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not valid', errors[0])
    
    def test_validate_features_layer_layer_not_found(self):
        """Test validation of features layer that doesn't exist."""
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = None
        
        errors = self.validator.validate_features_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Layer not found in current project', errors[0])

    def test_validate_small_finds_layer_empty_layer_id(self):
        """Test validation of empty small finds layer ID."""
        errors = self.validator.validate_small_finds_layer('')
        self.assertEqual(len(errors), 0)  # Empty layer ID is optional

    def test_validate_small_finds_layer_valid_point_layer(self):
        """Test validation of valid point/multipoint small finds layer."""
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.is_valid_no_geometry_layer.return_value = False
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': True
        }
        
        errors = self.validator.validate_small_finds_layer('test_layer')
        self.assertEqual(len(errors), 0)

    def test_validate_small_finds_layer_valid_no_geometry_layer(self):
        """Test validation of valid no geometry small finds layer."""
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = False
        self.layer_service.is_valid_no_geometry_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': True
        }
        
        errors = self.validator.validate_small_finds_layer('test_layer')
        self.assertEqual(len(errors), 0)

    def test_validate_small_finds_layer_invalid_layer(self):
        """Test validation of invalid small finds layer (neither point nor no geometry)."""
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = False
        self.layer_service.is_valid_no_geometry_layer.return_value = False
        
        errors = self.validator.validate_small_finds_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not a valid point/multipoint layer or no geometry layer', errors[0])

    def test_validate_small_finds_layer_layer_not_found(self):
        """Test validation of small finds layer that doesn't exist."""
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.is_valid_no_geometry_layer.return_value = False
        self.layer_service.get_layer_info.return_value = None
        
        errors = self.validator.validate_small_finds_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Layer not found in current project', errors[0])

    def test_validate_small_finds_layer_invalid_layer_info(self):
        """Test validation of small finds layer with invalid layer info."""
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.is_valid_no_geometry_layer.return_value = False
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': False
        }
        
        errors = self.validator.validate_small_finds_layer('test_layer')
        self.assertEqual(len(errors), 1)
        self.assertIn('Selected layer is not valid', errors[0])
    
    def test_validate_csv_archive_folder_empty_path(self):
        """Test validation of empty CSV archive folder path."""
        errors = self.validator.validate_csv_archive_folder('')
        self.assertEqual(len(errors), 0)  # Empty path is valid (optional)
    
    def test_validate_csv_archive_folder_not_exists(self):
        """Test validation of CSV archive folder that does not exist."""
        self.file_system_service.path_exists.return_value = False
        
        errors = self.validator.validate_csv_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('CSV archive folder does not exist', errors[0])
    
    def test_validate_csv_archive_folder_not_directory(self):
        """Test validation of CSV archive folder that is not a directory."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = False
        
        errors = self.validator.validate_csv_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('CSV archive path is not a directory', errors[0])
    
    def test_validate_csv_archive_folder_not_writable(self):
        """Test validation of CSV archive folder that is not writable."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.is_writable.return_value = False
        
        errors = self.validator.validate_csv_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('CSV archive folder is not writable', errors[0])
    
    def test_validate_csv_archive_folder_valid(self):
        """Test validation of valid CSV archive folder."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.is_writable.return_value = True
        
        errors = self.validator.validate_csv_archive_folder('/test/path')
        self.assertEqual(len(errors), 0)
    
    def test_validate_field_project_archive_folder_empty_path(self):
        """Test validation of empty field project archive folder path."""
        errors = self.validator.validate_field_project_archive_folder('')
        self.assertEqual(len(errors), 0)  # Empty path is valid (optional)
    
    def test_validate_field_project_archive_folder_not_exists(self):
        """Test validation of field project archive folder that does not exist."""
        self.file_system_service.path_exists.return_value = False
        
        errors = self.validator.validate_field_project_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field project archive folder does not exist', errors[0])
    
    def test_validate_field_project_archive_folder_not_directory(self):
        """Test validation of field project archive folder that is not a directory."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = False
        
        errors = self.validator.validate_field_project_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field project archive path is not a directory', errors[0])
    
    def test_validate_field_project_archive_folder_not_writable(self):
        """Test validation of field project archive folder that is not writable."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.is_writable.return_value = False
        
        errors = self.validator.validate_field_project_archive_folder('/test/path')
        self.assertEqual(len(errors), 1)
        self.assertIn('Field project archive folder is not writable', errors[0])
    
    def test_validate_field_project_archive_folder_valid(self):
        """Test validation of valid field project archive folder."""
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.is_writable.return_value = True
        
        errors = self.validator.validate_field_project_archive_folder('/test/path')
        self.assertEqual(len(errors), 0)
    

    
    def test_validate_all_settings(self):
        """Test validation of all settings at once."""
        # Mock file system service for valid paths
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.list_files.return_value = ['test.csv']
        # Mock writability and readability checks
        self.file_system_service.is_writable.return_value = True
        self.file_system_service.is_readable.return_value = True
        
        # Mock layer service for valid layers but no relationships
        self.layer_service.is_valid_polygon_layer.return_value = True
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': True
        }
        # Mock get_layer_fields to return a list of field dicts (not a Mock)
        self.layer_service.get_layer_fields.return_value = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True},
            {'name': 'level', 'is_integer': False}
        ]
        # Mock no relationships
        self.layer_service.get_layer_relationships.return_value = []
        
        settings = {
            'field_projects_folder': '/valid/path',
            'total_station_folder': '/valid/path',
            'completed_projects_folder': '/valid/path',
            'total_station_points_layer': 'test_points_layer',
            'raster_brightness': 50,
            'raster_contrast': 25,
            'raster_saturation': -10
        }
        
        results = self.validator.validate_all_settings(settings)
        
        # Debug: print all results to see what's failing
        print(f"Validation results: {results}")
        
        self.assertIn('field_projects_folder', results)
        self.assertIn('total_station_folder', results)
        self.assertIn('completed_projects_folder', results)
        self.assertIn('total_station_points_layer', results)
        self.assertIn('raster_brightness', results)
        self.assertIn('raster_contrast', results)
        self.assertIn('raster_saturation', results)
        
        # All validations should pass
        for field_name, field_errors in results.items():
            if field_errors:  # If there are errors, print them
                print(f"Errors in {field_name}: {field_errors}")
            self.assertEqual(len(field_errors), 0, f"Field {field_name} has errors: {field_errors}")

    def test_has_validation_errors(self):
        """Test checking if validation results contain errors."""
        # Test with no errors
        results_no_errors = {
            'field_projects_folder': [],
            'total_station_folder': []
        }
        self.assertFalse(self.validator.has_validation_errors(results_no_errors))
        
        # Test with errors
        results_with_errors = {
            'field_projects_folder': ['Path is required'],
            'total_station_folder': []
        }
        self.assertTrue(self.validator.has_validation_errors(results_with_errors))
    
    def test_get_all_errors(self):
        """Test getting all error messages from validation results."""
        results = {
            'field_projects_folder': ['Path is required'],
            'total_station_folder': ['Path does not exist', 'Path is not readable']
        }
        
        all_errors = self.validator.get_all_errors(results)
        self.assertIsInstance(all_errors, list)
        self.assertEqual(len(all_errors), 3)
        self.assertTrue(any('field_projects_folder: Path is required' in error for error in all_errors))
        self.assertTrue(any('total_station_folder: Path does not exist' in error for error in all_errors))
        self.assertTrue(any('total_station_folder: Path is not readable' in error for error in all_errors))



    def test_validate_objects_layer_fields_no_layer_selected(self):
        """Test field validation when no layer is selected."""
        result = self.validator.validate_objects_layer_fields("", "number_field", "level_field")
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.message, "No layer selected, field validation skipped")
    
    def test_validate_objects_layer_fields_layer_not_found(self):
        """Test field validation when layer is not found."""
        # Mock layer service to return None for fields
        self.validator._layer_service.get_layer_fields.return_value = None
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", "number_field", "level_field")
        
        self.assertFalse(result.is_valid)
        self.assertIn("Could not retrieve fields for layer test_layer_id", result.message)
    
    def test_validate_objects_layer_fields_valid_selections(self):
        """Test field validation with valid field selections."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True},
            {'name': 'level', 'is_integer': False},
            {'name': 'name', 'is_integer': False}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", "number", "level")
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.message, "Field validation successful")
    
    def test_validate_objects_layer_fields_number_field_not_found(self):
        """Test field validation when number field is not found."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'level', 'is_integer': False}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", "nonexistent_number", "level")
        
        self.assertFalse(result.is_valid)
        self.assertIn("Number field 'nonexistent_number' not found in layer", result.message)
    
    def test_validate_objects_layer_fields_number_field_not_integer(self):
        """Test field validation when number field is not an integer."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': False},  # Not an integer field
            {'name': 'level', 'is_integer': False}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", "number", "level")
        
        self.assertFalse(result.is_valid)
        self.assertIn("Number field 'number' must be an integer field", result.message)
    
    def test_validate_objects_layer_fields_level_field_not_found(self):
        """Test field validation when level field is not found."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", "number", "nonexistent_level")
        
        self.assertFalse(result.is_valid)
        self.assertIn("Level field 'nonexistent_level' not found in layer", result.message)
    
    def test_validate_objects_layer_fields_optional_fields_not_selected(self):
        """Test field validation when optional fields are not selected."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True},
            {'name': 'level', 'is_integer': False}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        result = self.validator.validate_objects_layer_fields("test_layer_id", None, None)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.message, "Field validation successful")
    
    def test_validate_objects_layer_fields_partial_selection(self):
        """Test field validation when only one field is selected."""
        # Mock fields data
        fields = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True},
            {'name': 'level', 'is_integer': False}
        ]
        self.validator._layer_service.get_layer_fields.return_value = fields
        
        # Test with only number field selected
        result = self.validator.validate_objects_layer_fields("test_layer_id", "number", None)
        self.assertTrue(result.is_valid)
        
        # Test with only level field selected
        result = self.validator.validate_objects_layer_fields("test_layer_id", None, "level")
        self.assertTrue(result.is_valid)

    def test_validate_layer_relationships_no_recording_areas_layer(self):
        """Test relationship validation when no recording areas layer is set."""
        # When recording areas layer is not set, relationships are not required
        errors = self.validator.validate_layer_relationships("", "objects_layer_id", "features_layer_id", "")
        self.assertEqual(len(errors), 0)

    def test_validate_layer_relationships_no_child_layers(self):
        """Test relationship validation when no child layers are set."""
        # When no child layers are set, relationships are not required
        errors = self.validator.validate_layer_relationships("recording_areas_layer_id", "", "", "")
        self.assertEqual(len(errors), 0)

    def test_validate_layer_relationships_missing_objects_relationship(self):
        """Test relationship validation when objects layer relationship is missing."""
        # Mock layer service to return no relationships
        self.layer_service.get_layer_relationships.return_value = []
        
        errors = self.validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "",
            ""
        )
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Objects layer must have a relationship with Recording areas layer", errors[0])

    def test_validate_layer_relationships_missing_features_relationship(self):
        """Test relationship validation when features layer relationship is missing."""
        # Mock layer service to return no relationships
        self.layer_service.get_layer_relationships.return_value = []
        
        errors = self.validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "features_layer_id",
            ""
        )
        
        self.assertEqual(len(errors), 2)
        self.assertIn("Objects layer must have a relationship with Recording areas layer", errors[0])
        self.assertIn("Features layer must have a relationship with Recording areas layer", errors[1])

    def test_validate_layer_relationships_missing_small_finds_relationship(self):
        """Test relationship validation when small finds layer relationship is missing."""
        # Mock layer service to return no relationships
        self.layer_service.get_layer_relationships.return_value = []
        
        errors = self.validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "features_layer_id",
            "small_finds_layer_id"
        )
        
        self.assertEqual(len(errors), 3)
        self.assertIn("Objects layer must have a relationship with Recording areas layer", errors[0])
        self.assertIn("Features layer must have a relationship with Recording areas layer", errors[1])
        self.assertIn("Small finds layer must have a relationship with Recording areas layer", errors[2])

    def test_validate_layer_relationships_valid_relationships(self):
        """Test relationship validation when all relationships are valid."""
        # Mock layer service to return valid relationships
        mock_objects_relation = Mock()
        mock_objects_relation.referencingLayerId.return_value = "objects_layer_id"
        mock_objects_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        
        mock_features_relation = Mock()
        mock_features_relation.referencingLayerId.return_value = "features_layer_id"
        mock_features_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        
        mock_small_finds_relation = Mock()
        mock_small_finds_relation.referencingLayerId.return_value = "small_finds_layer_id"
        mock_small_finds_relation.referencedLayerId.return_value = "recording_areas_layer_id"
        
        self.layer_service.get_layer_relationships.return_value = [
            mock_objects_relation, 
            mock_features_relation,
            mock_small_finds_relation
        ]
        
        errors = self.validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "features_layer_id",
            "small_finds_layer_id"
        )
        
        self.assertEqual(len(errors), 0)

    def test_validate_layer_relationships_wrong_parent_layer(self):
        """Test relationship validation when relationship points to wrong parent."""
        # Mock layer service to return relationship with wrong parent
        mock_relation = Mock()
        mock_relation.referencingLayerId.return_value = "objects_layer_id"
        mock_relation.referencedLayerId.return_value = "wrong_parent_layer_id"
        
        self.layer_service.get_layer_relationships.return_value = [mock_relation]
        
        errors = self.validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "",
            ""
        )
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Objects layer must have a relationship with Recording areas layer", errors[0])

    def test_validate_layer_relationships_layer_service_not_available(self):
        """Test relationship validation when layer service is not available."""
        validator = ArcheoSyncConfigurationValidator(self.file_system_service, None)
        
        errors = validator.validate_layer_relationships(
            "recording_areas_layer_id", 
            "objects_layer_id", 
            "features_layer_id",
            ""
        )
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Layer service not available for relationship validation", errors[0])

    def test_validate_all_settings_with_missing_relationships(self):
        """Test that validate_all_settings includes relationship validation errors."""
        # Mock file system service for valid paths
        self.file_system_service.path_exists.return_value = True
        self.file_system_service.is_directory.return_value = True
        self.file_system_service.list_files.return_value = ['test.csv']
        
        # Mock layer service for valid layers but no relationships
        self.layer_service.is_valid_polygon_layer.return_value = True
        self.layer_service.is_valid_polygon_or_multipolygon_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Layer',
            'is_valid': True
        }
        # Mock get_layer_fields to return a list of field dicts (not a Mock)
        self.layer_service.get_layer_fields.return_value = [
            {'name': 'id', 'is_integer': True},
            {'name': 'number', 'is_integer': True},
            {'name': 'level', 'is_integer': False}
        ]
        # Mock no relationships
        self.layer_service.get_layer_relationships.return_value = []
        
        settings = {
            'field_projects_folder': '/valid/path',
            'total_station_folder': '/valid/path',
            'completed_projects_folder': '/valid/path',
            'template_project_folder': '/valid/path',
            'recording_areas_layer': 'recording_layer',
            'objects_layer': 'objects_layer',
            'features_layer': 'features_layer',
            'use_qfield': False
        }
        
        results = self.validator.validate_all_settings(settings)
        
        # Should have relationship validation errors
        self.assertIn('layer_relationships', results)
        self.assertGreater(len(results['layer_relationships']), 0)
        self.assertIn("Objects layer must have a relationship with Recording areas layer", results['layer_relationships'])
        self.assertIn("Features layer must have a relationship with Recording areas layer", results['layer_relationships'])

    def test_validate_raster_brightness_valid(self):
        """Test validation of valid raster brightness setting."""
        errors = self.validator.validate_raster_brightness(0)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_brightness(100)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_brightness(-100)
        self.assertEqual(len(errors), 0)
    
    def test_validate_raster_brightness_invalid_type(self):
        """Test validation of invalid raster brightness type."""
        errors = self.validator.validate_raster_brightness("invalid")
        self.assertEqual(len(errors), 1)
        self.assertIn("Brightness value must be an integer", errors[0])
    
    def test_validate_raster_brightness_out_of_range(self):
        """Test validation of raster brightness out of range."""
        errors = self.validator.validate_raster_brightness(300)
        self.assertEqual(len(errors), 1)
        self.assertIn("Brightness value must be between -255 and 255", errors[0])
        
        errors = self.validator.validate_raster_brightness(-300)
        self.assertEqual(len(errors), 1)
        self.assertIn("Brightness value must be between -255 and 255", errors[0])
    
    def test_validate_raster_contrast_valid(self):
        """Test validation of valid raster contrast setting."""
        errors = self.validator.validate_raster_contrast(0)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_contrast(50)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_contrast(-50)
        self.assertEqual(len(errors), 0)
    
    def test_validate_raster_contrast_invalid_type(self):
        """Test validation of invalid raster contrast type."""
        errors = self.validator.validate_raster_contrast("invalid")
        self.assertEqual(len(errors), 1)
        self.assertIn("Contrast value must be an integer", errors[0])
    
    def test_validate_raster_contrast_out_of_range(self):
        """Test validation of raster contrast out of range."""
        errors = self.validator.validate_raster_contrast(150)
        self.assertEqual(len(errors), 1)
        self.assertIn("Contrast value must be between -100 and 100", errors[0])
        
        errors = self.validator.validate_raster_contrast(-150)
        self.assertEqual(len(errors), 1)
        self.assertIn("Contrast value must be between -100 and 100", errors[0])
    
    def test_validate_raster_saturation_valid(self):
        """Test validation of valid raster saturation setting."""
        errors = self.validator.validate_raster_saturation(0)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_saturation(50)
        self.assertEqual(len(errors), 0)
        
        errors = self.validator.validate_raster_saturation(-50)
        self.assertEqual(len(errors), 0)
    
    def test_validate_raster_saturation_invalid_type(self):
        """Test validation of invalid raster saturation type."""
        errors = self.validator.validate_raster_saturation("invalid")
        self.assertEqual(len(errors), 1)
        self.assertIn("Saturation value must be an integer", errors[0])
    
    def test_validate_raster_saturation_out_of_range(self):
        """Test validation of raster saturation out of range."""
        errors = self.validator.validate_raster_saturation(150)
        self.assertEqual(len(errors), 1)
        self.assertIn("Saturation value must be between -100 and 100", errors[0])
        
        errors = self.validator.validate_raster_saturation(-150)
        self.assertEqual(len(errors), 1)
        self.assertIn("Saturation value must be between -100 and 100", errors[0])

    def test_validate_total_station_points_layer_valid(self):
        """Test validation of valid total station points layer."""
        # Mock layer service for valid point layer
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Points Layer',
            'is_valid': True
        }
        
        result = self.validator.validate_total_station_points_layer('test_layer')
        
        self.assertEqual(result, [])
        self.layer_service.is_valid_point_or_multipoint_layer.assert_called_once_with('test_layer')
        self.layer_service.get_layer_info.assert_called_once_with('test_layer')
    
    def test_validate_total_station_points_layer_empty(self):
        """Test validation of empty total station points layer (should be valid)."""
        result = self.validator.validate_total_station_points_layer('')
        
        self.assertEqual(result, [])
    
    def test_validate_total_station_points_layer_invalid_geometry(self):
        """Test validation of total station points layer with invalid geometry type."""
        # Mock layer service for invalid geometry type
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = False
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Polygon Layer',
            'is_valid': True
        }
        
        result = self.validator.validate_total_station_points_layer('test_layer')
        
        self.assertEqual(len(result), 1)
        self.assertIn("not a valid point/multipoint layer", result[0])
    
    def test_validate_total_station_points_layer_not_found(self):
        """Test validation of total station points layer that doesn't exist."""
        # Mock layer service for non-existent layer
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.get_layer_info.return_value = None
        
        result = self.validator.validate_total_station_points_layer('nonexistent_layer')
        
        self.assertEqual(len(result), 1)
        self.assertIn("Layer not found", result[0])
    
    def test_validate_total_station_points_layer_invalid_layer(self):
        """Test validation of total station points layer that is invalid."""
        # Mock layer service for invalid layer
        self.layer_service.is_valid_point_or_multipoint_layer.return_value = True
        self.layer_service.get_layer_info.return_value = {
            'id': 'test_layer',
            'name': 'Test Invalid Layer',
            'is_valid': False
        }
        
        result = self.validator.validate_total_station_points_layer('test_layer')
        
        self.assertEqual(len(result), 1)
        self.assertIn("not valid", result[0])
    
    def test_validate_total_station_points_layer_no_service(self):
        """Test validation of total station points layer without layer service."""
        validator = ArcheoSyncConfigurationValidator(self.file_system_service, None)
        
        result = validator.validate_total_station_points_layer('test_layer')
        
        self.assertEqual(len(result), 1)
        self.assertIn("Layer service not available", result[0])


if __name__ == '__main__':
    unittest.main() 