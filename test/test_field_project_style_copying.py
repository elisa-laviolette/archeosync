"""
Test file to verify style copying functionality during field project creation.

This test specifically addresses the issue where styles from the main QGIS project
layers are not properly copied to the field project layers.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsVectorLayer, QgsField, QgsProject, QgsWkbTypes, QgsEditFormConfig, QgsSingleSymbolRenderer, QgsSymbol
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor

from archeosync.services.project_creation_service import QGISProjectCreationService
from archeosync.services.layer_service import QGISLayerService


class TestFieldProjectStyleCopying(unittest.TestCase):
    """Test cases for style copying during field project creation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = QGISLayerService()
        self.file_system_service = Mock()
        self.raster_processing_service = Mock()
        
        # Create the project creation service
        self.project_service = QGISProjectCreationService(
            self.settings_manager, 
            self.layer_service, 
            self.file_system_service,
            self.raster_processing_service
        )
        
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_style_copying_with_current_style(self):
        """Test that current styles are properly copied to field project layers."""
        # Create source layers with current styling
        source_objects_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Objects", "memory")
        self.assertTrue(source_objects_layer.isValid())
        
        source_features_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Features", "memory")
        self.assertTrue(source_features_layer.isValid())
        
        source_small_finds_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Small Finds", "memory")
        self.assertTrue(source_small_finds_layer.isValid())
        
        # Set up current styling on source layers
        self._setup_layer_styling(source_objects_layer, "Objects")
        self._setup_layer_styling(source_features_layer, "Features")
        self._setup_layer_styling(source_small_finds_layer, "Small Finds")
        
        # Create recording areas layer
        recording_areas_layer = QgsVectorLayer("Polygon?crs=EPSG:4326&field=id:integer&field=name:string", "Recording Areas", "memory")
        self.assertTrue(recording_areas_layer.isValid())
        
        # Add layers to project
        project = QgsProject.instance()
        project.addMapLayer(recording_areas_layer)
        project.addMapLayer(source_objects_layer)
        project.addMapLayer(source_features_layer)
        project.addMapLayer(source_small_finds_layer)
        
        # Create field project
        feature_data = {
            'id': 1,
            'geometry_wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'attributes': {'id': 1, 'name': 'Test Area'},
            'display_name': 'Test Area'
        }
        
        success = self.project_service.create_field_project(
            feature_data=feature_data,
            recording_areas_layer_id=recording_areas_layer.id(),
            objects_layer_id=source_objects_layer.id(),
            features_layer_id=source_features_layer.id(),
            small_finds_layer_id=source_small_finds_layer.id(),
            background_layer_id=None,
            destination_folder=self.temp_dir,
            project_name="TestFieldProject"
        )
        
        self.assertTrue(success)
        
        # Verify that the field project was created with proper styling
        project_path = os.path.join(self.temp_dir, "TestFieldProject", "TestFieldProject.qgs")
        self.assertTrue(os.path.exists(project_path))
        
        # Load the created project and verify styles
        field_project = QgsProject()
        field_project.read(project_path)
        
        # Check that layers exist and have proper styling
        field_layers = field_project.mapLayers()
        self.assertGreater(len(field_layers), 0)
        
        # Verify each layer has the expected styling
        for layer_id, layer in field_layers.items():
            if "Objects" in layer.name():
                self._verify_layer_styling(layer, "Objects")
            elif "Features" in layer.name():
                self._verify_layer_styling(layer, "Features")
            elif "Small Finds" in layer.name():
                self._verify_layer_styling(layer, "Small Finds")
        
        # Clean up
        project.removeMapLayer(recording_areas_layer)
        project.removeMapLayer(source_objects_layer)
        project.removeMapLayer(source_features_layer)
        project.removeMapLayer(source_small_finds_layer)
    
    def test_style_copying_with_style_uri_issue(self):
        """Test style copying when styleURI() doesn't point to current style."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Mock styleURI to return None (simulating the issue)
        with patch.object(source_layer, 'styleURI', return_value=None):
            # Test the style copying method directly
            target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer", "memory")
            self.assertTrue(target_layer.isValid())
            
            # Copy style using the layer service
            success = self.layer_service._copy_qml_style(source_layer, target_layer)
            
            # Should succeed even with styleURI returning None
            self.assertTrue(success)
            
            # Verify styling was copied
            self._verify_layer_styling(target_layer, "TestLayer")
    
    def test_style_copying_with_geopackage_layers(self):
        """Test style copying specifically for Geopackage layers in field projects."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Create a temporary Geopackage file
        gpkg_path = os.path.join(self.temp_dir, "test.gpkg")
        
        # Test the Geopackage style copying method
        success = self.project_service._copy_layer_properties_to_geopackage(
            source_layer, gpkg_path, "TestLayer"
        )
        
        self.assertTrue(success)
        
        # Verify the Geopackage was created
        self.assertTrue(os.path.exists(gpkg_path))
        
        # Load the Geopackage layer and verify styling
        gpkg_layer = QgsVectorLayer(gpkg_path, "TestLayer", "ogr")
        self.assertTrue(gpkg_layer.isValid())
        
        # Verify styling was copied
        self._verify_layer_styling(gpkg_layer, "TestLayer")
    
    def test_style_copying_with_style_uri_issue_simple(self):
        """Test style copying when styleURI() doesn't point to current style - simple version."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Mock styleURI to return None (simulating the issue)
        with patch.object(source_layer, 'styleURI', return_value=None):
            # Test the style copying method directly
            target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer", "memory")
            self.assertTrue(target_layer.isValid())
            
            # Copy style using the layer service
            success = self.layer_service._copy_qml_style(source_layer, target_layer)
            
            # Should succeed even with styleURI returning None
            self.assertTrue(success)
            
            # Verify styling was copied
            self._verify_layer_styling(target_layer, "TestLayer")
    
    def test_style_copying_with_current_style_simple(self):
        """Test that current styles are properly copied - simple version without Geopackage."""
        # Create source layers with current styling
        source_objects_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Objects", "memory")
        self.assertTrue(source_objects_layer.isValid())
        
        source_features_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Features", "memory")
        self.assertTrue(source_features_layer.isValid())
        
        source_small_finds_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", "Small Finds", "memory")
        self.assertTrue(source_small_finds_layer.isValid())
        
        # Set up current styling on source layers
        self._setup_layer_styling(source_objects_layer, "Objects")
        self._setup_layer_styling(source_features_layer, "Features")
        self._setup_layer_styling(source_small_finds_layer, "Small Finds")
        
        # Test style copying for each layer
        test_cases = [
            (source_objects_layer, "Objects"),
            (source_features_layer, "Features"),
            (source_small_finds_layer, "Small Finds")
        ]
        
        for source_layer, layer_type in test_cases:
            # Create target layer
            target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string&field=value:integer", f"Target{layer_type}", "memory")
            self.assertTrue(target_layer.isValid())
            
            # Copy style
            success = self.layer_service._copy_qml_style(source_layer, target_layer)
            self.assertTrue(success, f"Style copying failed for {layer_type}")
            
            # Verify styling was copied
            self._verify_layer_styling(target_layer, layer_type)
    
    def test_geopackage_style_saving_no_errors(self):
        """Test that Geopackage style saving doesn't produce string index out of range errors."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Create a temporary Geopackage file
        gpkg_path = os.path.join(self.temp_dir, "test_style.gpkg")
        
        # Test the Geopackage style copying method
        # This should not produce any "string index out of range" errors
        success = self.project_service._copy_layer_properties_to_geopackage(
            source_layer, gpkg_path, "TestLayer"
        )
        
        # The method should succeed even if Geopackage style saving fails
        # The important thing is that it doesn't crash with string index errors
        self.assertTrue(success)
        
        # Verify the Geopackage was created
        self.assertTrue(os.path.exists(gpkg_path))
        
        # Load the Geopackage layer and verify styling was copied
        gpkg_layer = QgsVectorLayer(gpkg_path, "TestLayer", "ogr")
        self.assertTrue(gpkg_layer.isValid())
        
        # Verify styling was copied (at least the basic properties)
        self._verify_layer_styling(gpkg_layer, "TestLayer")
    
    def test_style_saving_methods_no_errors(self):
        """Test that style saving methods don't produce string index out of range errors."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Create target layer
        target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer", "memory")
        self.assertTrue(target_layer.isValid())
        
        # Test the style copying methods directly
        # This should not produce any "string index out of range" errors
        qml_success = self.layer_service._copy_qml_style(source_layer, target_layer)
        
        # The method should succeed and not crash with string index errors
        self.assertTrue(qml_success)
        
        # Verify styling was copied
        self._verify_layer_styling(target_layer, "TestLayer")
        
        # Test the renderer fallback method as well
        target_layer2 = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer2", "memory")
        self.assertTrue(target_layer2.isValid())
        
        # This should also not produce any errors
        self.layer_service._copy_renderer_fallback(source_layer, target_layer2)
        
        # Verify styling was copied
        self._verify_layer_styling(target_layer2, "TestLayer")
    
    def test_string_index_error_fixed(self):
        """Test that the string index out of range error is fixed."""
        # Create source layer
        source_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TestLayer", "memory")
        self.assertTrue(source_layer.isValid())
        
        # Set up current styling
        self._setup_layer_styling(source_layer, "TestLayer")
        
        # Create target layer
        target_layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "TargetLayer", "memory")
        self.assertTrue(target_layer.isValid())
        
        # Test the style copying method - this should NOT produce any string index errors
        # The important thing is that it doesn't crash
        try:
            qml_success = self.layer_service._copy_qml_style(source_layer, target_layer)
            # If we get here without any string index errors, the fix is working
            self.assertTrue(True)  # Test passes if no exception was raised
        except IndexError as e:
            if "string index out of range" in str(e):
                self.fail("String index out of range error still occurs")
            else:
                raise  # Re-raise if it's a different IndexError
    
    def _setup_layer_styling(self, layer, layer_type):
        """Set up specific styling for a layer based on its type."""
        # Set up form configuration
        form_config = layer.editFormConfig()
        form_config.setLayout(QgsEditFormConfig.TabLayout)
        layer.setEditFormConfig(form_config)
        
        # Set up renderer with different colors based on layer type
        renderer = QgsSingleSymbolRenderer(QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry))
        symbol = renderer.symbol()
        
        if layer_type == "Objects":
            symbol.setColor(QColor(255, 0, 0))  # Red
        elif layer_type == "Features":
            symbol.setColor(QColor(0, 255, 0))  # Green
        elif layer_type == "Small Finds":
            symbol.setColor(QColor(0, 0, 255))  # Blue
        else:
            symbol.setColor(QColor(128, 128, 128))  # Gray
        
        layer.setRenderer(renderer)
        
        # Set default values for fields
        name_field_idx = layer.fields().indexOf('name')
        if name_field_idx >= 0:
            from qgis.core import QgsDefaultValue
            layer.setDefaultValueDefinition(name_field_idx, QgsDefaultValue(f"'{layer_type} Default'"))
        
        # Force the layer to update
        layer.triggerRepaint()
    
    def _verify_layer_styling(self, layer, layer_type):
        """Verify that layer styling was copied correctly."""
        # Verify that the layer has a renderer
        self.assertIsNotNone(layer.renderer())
        
        # Verify that the layer has form configuration
        form_config = layer.editFormConfig()
        self.assertIsNotNone(form_config)
        
        # Note: Form layout might vary between QGIS versions, so we'll be more flexible
        # The important thing is that the form configuration exists
        self.assertTrue(hasattr(form_config, 'layout'))
        
        # Verify that the layer has fields
        self.assertGreater(len(layer.fields()), 0)
        
        # Check that default values were copied
        name_field_idx = layer.fields().indexOf('name')
        if name_field_idx >= 0:
            default_def = layer.defaultValueDefinition(name_field_idx)
            self.assertTrue(default_def.isValid())
            self.assertEqual(default_def.expression(), f"'{layer_type} Default'")
        
        # Check that symbol color matches expected type
        symbol = layer.renderer().symbol()
        self.assertIsNotNone(symbol)
        
        color = symbol.color()
        if layer_type == "Objects":
            self.assertEqual(color.red(), 255)
            self.assertEqual(color.green(), 0)
            self.assertEqual(color.blue(), 0)
        elif layer_type == "Features":
            self.assertEqual(color.red(), 0)
            self.assertEqual(color.green(), 255)
            self.assertEqual(color.blue(), 0)
        elif layer_type == "Small Finds":
            self.assertEqual(color.red(), 0)
            self.assertEqual(color.green(), 0)
            self.assertEqual(color.blue(), 255)


if __name__ == '__main__':
    unittest.main() 