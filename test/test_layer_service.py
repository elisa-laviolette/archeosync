# coding=utf-8
"""Layer service tests.

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
from unittest.mock import Mock, patch, create_autospec, mock_open
import unittest

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsMapLayer, QgsWkbTypes, QgsGeometry, QgsSingleSymbolRenderer, QgsSymbol, QgsEditFormConfig, QgsEditorWidgetSetup, QgsMapLayer, QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app
from archeosync.services.layer_service import QGISLayerService
from PyQt5.QtCore import QVariant


@pytest.mark.unit
class TestLayerServiceBasic:
    """Basic tests that don't require QGIS."""
    
    def test_import_available(self):
        """Test that the layer service module can be imported."""
        try:
            from services.layer_service import QGISLayerService
            assert QGISLayerService is not None
        except ImportError:
            pytest.skip("LayerService module not available")


class TestLayerService(unittest.TestCase):
    """Test cases for QGISLayerService."""

    def setUp(self):
        """Set up test fixtures."""
        self.layer_service = QGISLayerService()

    def test_layer_service_creation(self):
        """Test that QGISLayerService can be created."""
        self.assertIsNotNone(self.layer_service)

    def test_get_polygon_layers_empty_project(self):
        """Test getting polygon layers when project is empty."""
        # Mock empty project
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_project.instance.return_value.mapLayers.return_value = {}
            self.layer_service = QGISLayerService()
            polygon_layers = self.layer_service.get_polygon_layers()
            self.assertEqual(len(polygon_layers), 0)

    def test_get_layer_by_id_not_found(self):
        """Test getting layer by ID when layer does not exist."""
        # Patch QgsProject in the correct module and create the service after patching
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_project.instance.return_value.mapLayer.return_value = None
            self.layer_service = QGISLayerService()
            layer = self.layer_service.get_layer_by_id("nonexistent_layer")
            self.assertIsNone(layer)

    def test_get_layer_info_not_found(self):
        """Test getting layer info when layer does not exist."""
        # Mock layer not found
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            info = self.layer_service.get_layer_info("nonexistent_layer")
            self.assertIsNone(info)

    def test_get_layer_info_found(self):
        """Test getting layer info when layer exists."""
        # Create a simple mock layer for this test
        mock_layer = Mock()
        mock_layer.id.return_value = "test_layer"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.source.return_value = "test_source"
        mock_layer.crs.return_value = Mock(authid=lambda: "EPSG:4326")
        mock_layer.featureCount.return_value = 10
        mock_layer.isValid.return_value = True

        # Mock get_layer_by_id to return our mock layer
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            info = self.layer_service.get_layer_info("test_layer")
            self.assertIsNotNone(info)
            self.assertEqual(info['id'], "test_layer")
            self.assertEqual(info['name'], "Test Layer")
            self.assertEqual(info['source'], "test_source")
            self.assertEqual(info['crs'], "EPSG:4326")
            self.assertEqual(info['feature_count'], 10)
            self.assertTrue(info['is_valid'])

    def test_get_raster_layers_empty_project(self):
        """Test getting raster layers when project is empty."""
        # Mock empty project
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_project.instance.return_value.mapLayers.return_value = {}
            self.layer_service = QGISLayerService()
            raster_layers = self.layer_service.get_raster_layers()
            self.assertEqual(len(raster_layers), 0)

    def test_get_raster_layers_overlapping_feature_no_geometry(self):
        """Test getting raster layers overlapping a feature with no geometry."""
        # Create mock feature with no geometry
        mock_feature = Mock()
        mock_feature.geometry.return_value = None

        layers = self.layer_service.get_raster_layers_overlapping_feature(mock_feature, "recording_areas")
        self.assertEqual(len(layers), 0)

    def test_get_raster_layers_overlapping_feature_no_recording_layer(self):
        """Test getting raster layers overlapping a feature when recording layer not found."""
        # Create mock feature with geometry
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.boundingBox.return_value = Mock()
        mock_feature.geometry.return_value = mock_geometry

        # Mock get_layer_by_id to return None for recording layer
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            layers = self.layer_service.get_raster_layers_overlapping_feature(mock_feature, "nonexistent_recording_layer")
            self.assertEqual(len(layers), 0)

    def test_get_raster_layers_overlapping_feature_no_overlap(self):
        """Test getting raster layers overlapping a feature when no overlap exists."""
        # Create mock feature with geometry
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        mock_geometry.boundingBox.return_value = Mock()
        mock_feature.geometry.return_value = mock_geometry

        # Create mock raster layer
        mock_raster_layer = create_autospec(QgsRasterLayer)
        mock_raster_layer.id.return_value = "raster_layer_1"
        mock_raster_layer.name.return_value = "Raster Layer 1"
        mock_raster_layer.type.return_value = QgsMapLayer.RasterLayer
        mock_raster_layer.source.return_value = "test_source"
        mock_raster_layer.crs.return_value = Mock(authid=lambda: "EPSG:4326")
        mock_raster_layer.isValid.return_value = True
        mock_raster_layer.width.return_value = 100
        mock_raster_layer.height.return_value = 100
        mock_raster_layer.extent.return_value = Mock()

        # Mock get_raster_layers
        with patch.object(self.layer_service, 'get_raster_layers', return_value=[{
            'id': 'raster_layer_1',
            'name': 'Raster Layer 1',
            'layer': mock_raster_layer
        }]):
            # Mock spatial intersection check
            with patch('services.layer_service.QgsGeometry.fromWkt') as mock_from_wkt:
                mock_qgs_geometry = Mock()
                mock_qgs_geometry.intersects.return_value = False
                mock_from_wkt.return_value = mock_qgs_geometry
                
                layers = self.layer_service.get_raster_layers_overlapping_feature(mock_feature, "recording_areas")
                self.assertEqual(len(layers), 0)

    def test_calculate_next_level_string_increment(self):
        """Test calculating next level with string increment."""
        # Create mock layer with fields
        mock_layer = Mock()
        mock_fields = [
            Mock(name='level', type=lambda: QVariant.String),
            Mock(name='name', type=lambda: QVariant.String)
        ]
        mock_layer.fields.return_value = mock_fields

        # Mock get_layer_by_id
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            # Mock data provider to return features
            mock_provider = Mock()
            mock_layer.dataProvider.return_value = mock_provider

            # Create mock features
            mock_feature1 = Mock()
            mock_feature1.attributes.return_value = ['A1', 'Feature 1']
            mock_feature2 = Mock()
            mock_feature2.attributes.return_value = ['A2', 'Feature 2']

            mock_provider.getFeatures.return_value = [mock_feature1, mock_feature2]

            level = self.layer_service.calculate_next_level('A2', 'level', 'test_layer')
            self.assertEqual(level, 'A3')

    def test_remove_layer_from_project_success(self):
        """Test successful removal of layer from project."""
        # Create mock layer
        mock_layer = Mock()
        mock_layer.id.return_value = "test_layer_1"

        # Mock QgsProject.instance()
        with patch('qgis.core.QgsProject.instance') as mock_project:
            mock_project_instance = Mock()
            mock_project_instance.mapLayer.return_value = mock_layer
            mock_project.return_value = mock_project_instance

            result = self.layer_service.remove_layer_from_project("test_layer_1")
            self.assertTrue(result)

    def test_remove_layer_from_project_layer_not_found(self):
        """Test removing layer that doesn't exist."""
        # Mock QgsProject.instance()
        with patch('qgis.core.QgsProject.instance') as mock_project:
            mock_project_instance = Mock()
            mock_project_instance.mapLayer.return_value = None
            mock_project.return_value = mock_project_instance

            result = self.layer_service.remove_layer_from_project("non_existent_layer")
            self.assertFalse(result)

    def test_remove_layer_from_project_exception(self):
        """Test exception handling in layer removal."""
        # Mock QgsProject.instance() to raise exception
        with patch('qgis.core.QgsProject.instance') as mock_project:
            mock_project_instance = Mock()
            mock_project_instance.mapLayer.side_effect = Exception("Test exception")
            mock_project.return_value = mock_project_instance

            result = self.layer_service.remove_layer_from_project("test_layer")
            self.assertFalse(result)

    def test_copy_qml_style_with_style_uri(self):
        """Test copying QML style when source layer has style URI."""
        # Create mock layers
        mock_source_layer = Mock()
        mock_target_layer = Mock()
        
        # Mock the style URI to return a QML file path
        mock_source_layer.styleURI.return_value = "/path/to/style.qml"
        mock_source_layer.name.return_value = "Source Layer"
        mock_target_layer.name.return_value = "Target Layer"
        
        # Mock file operations
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="<qgis>test</qgis>")), \
             patch('os.path.dirname', return_value="/path/to"), \
             patch('os.path.join', return_value="/path/to/Target Layer.qml"):
            # Mock loadNamedStyle to return success
            mock_target_layer.loadNamedStyle.return_value = (True, "")
            # Also mock fallback methods
            mock_target_layer.setRenderer = Mock()
            mock_target_layer.setEditFormConfig = Mock()
            layer_service = QGISLayerService()
            result = layer_service._copy_qml_style(mock_source_layer, mock_target_layer)
            self.assertTrue(result)
            # Accept either loadNamedStyle or fallback renderer as success
            called = (mock_target_layer.loadNamedStyle.called or
                      mock_target_layer.setRenderer.called or
                      mock_target_layer.setEditFormConfig.called)
            self.assertTrue(called, "Expected at least one style method to be called.")

    def test_copy_qml_style_without_style_uri(self):
        """Test copying QML style when source layer has no style URI."""
        # Create mock layers
        mock_source_layer = Mock()
        mock_target_layer = Mock()
        
        # Mock the style URI to return None (no QML file)
        mock_source_layer.styleURI.return_value = None
        mock_source_layer.name.return_value = "Source Layer"
        mock_target_layer.name.return_value = "Target Layer"
        
        # Mock saveNamedStyle to return success
        mock_source_layer.saveNamedStyle.return_value = (True, "/tmp/temp.qml")
        mock_target_layer.loadNamedStyle.return_value = (True, "")
        # Also mock fallback methods
        mock_target_layer.setRenderer = Mock()
        mock_target_layer.setEditFormConfig = Mock()
        # Mock file operations
        with patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
             patch('builtins.open', mock_open(read_data="<qgis>test</qgis>")), \
             patch('os.path.dirname', return_value="/path/to"), \
             patch('os.path.join', return_value="/path/to/Target Layer.qml"), \
             patch('os.unlink'):
            # Set up the temporary file mock
            mock_temp_file.return_value.__enter__.return_value.name = "/tmp/temp.qml"
            layer_service = QGISLayerService()
            result = layer_service._copy_qml_style(mock_source_layer, mock_target_layer)
            self.assertTrue(result)
            # Accept either loadNamedStyle or fallback renderer as success
            called = (mock_target_layer.loadNamedStyle.called or
                      mock_target_layer.setRenderer.called or
                      mock_target_layer.setEditFormConfig.called)
            self.assertTrue(called, "Expected at least one style method to be called.")

    def test_copy_qml_style_exception_handling(self):
        """Test exception handling in QML style copying."""
        # Create mock layers
        mock_source_layer = Mock()
        mock_target_layer = Mock()
        
        # Mock the style URI to raise exception
        mock_source_layer.styleURI.side_effect = Exception("Test exception")
        
        # Test the method
        layer_service = QGISLayerService()
        layer_service._copy_qml_style(mock_source_layer, mock_target_layer)
        
        # Method should not raise exception and should handle it gracefully
        # No assertions needed as we're just testing that no exception is raised 

    def test_is_valid_point_or_multipoint_layer_valid(self):
        """Test validation of valid point/multipoint layer."""
        # Create mock layer with point geometry
        mock_layer = Mock()
        mock_layer.geometryType.return_value = 1  # Point/MultiPoint geometry type
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_point_or_multipoint_layer("test_layer")
            self.assertTrue(result)

    def test_is_valid_point_or_multipoint_layer_invalid(self):
        """Test validation of invalid point/multipoint layer."""
        # Create mock layer with polygon geometry
        mock_layer = Mock()
        mock_layer.geometryType.return_value = 2  # Polygon geometry type
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_point_or_multipoint_layer("test_layer")
            self.assertFalse(result)

    def test_is_valid_point_or_multipoint_layer_not_found(self):
        """Test validation of point/multipoint layer that doesn't exist."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.is_valid_point_or_multipoint_layer("nonexistent_layer")
            self.assertFalse(result)

    def test_is_valid_no_geometry_layer_valid(self):
        """Test validation of valid no geometry layer."""
        # Create mock layer with no geometry
        mock_layer = Mock()
        mock_layer.geometryType.return_value = 0  # NoGeometry type
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_no_geometry_layer("test_layer")
            self.assertTrue(result)

    def test_is_valid_no_geometry_layer_invalid(self):
        """Test validation of invalid no geometry layer."""
        # Create mock layer with point geometry
        mock_layer = Mock()
        mock_layer.geometryType.return_value = 1  # Point geometry type
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            result = self.layer_service.is_valid_no_geometry_layer("test_layer")
            self.assertFalse(result)

    def test_is_valid_no_geometry_layer_not_found(self):
        """Test validation of no geometry layer that doesn't exist."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            result = self.layer_service.is_valid_no_geometry_layer("nonexistent_layer")
            self.assertFalse(result)

    def test_get_point_and_multipoint_layers_empty_project(self):
        """Test getting point and multipoint layers when project is empty."""
        # Mock empty project
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_project.instance.return_value.mapLayers.return_value = {}
            self.layer_service = QGISLayerService()
            point_layers = self.layer_service.get_point_and_multipoint_layers()
            self.assertEqual(len(point_layers), 0)

    def test_get_point_and_multipoint_layers_with_layers(self):
        """Test getting point and multipoint layers when layers exist."""
        # Create mock point layer
        mock_point_layer = create_autospec(QgsVectorLayer)
        mock_point_layer.id.return_value = "point_layer_1"
        mock_point_layer.name.return_value = "Point Layer 1"
        mock_point_layer.source.return_value = "test_source"
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:4326"
        mock_point_layer.crs.return_value = mock_crs
        mock_point_layer.featureCount.return_value = 5
        mock_point_layer.geometryType.return_value = 1  # Point/MultiPoint geometry type
        mock_point_layer.isValid.return_value = True

        # Prepare the layers dict
        layers_dict = {"point_layer_1": mock_point_layer}

        # Patch isinstance to return True for any layer in layers_dict
        def mock_isinstance(obj, cls):
            return obj in layers_dict.values()

        # Mock project with layers
        with patch('services.layer_service.QgsProject') as mock_project, \
             patch('services.layer_service.isinstance', side_effect=mock_isinstance):
            mock_project.instance.return_value.mapLayers.return_value = layers_dict
            self.layer_service = QGISLayerService()
            point_layers = self.layer_service.get_point_and_multipoint_layers()
            
            self.assertEqual(len(point_layers), 1)
            self.assertEqual(point_layers[0]['id'], "point_layer_1")
            self.assertEqual(point_layers[0]['name'], "Point Layer 1")

    def test_get_no_geometry_layers_empty_project(self):
        """Test getting no geometry layers when project is empty."""
        # Mock empty project
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_project.instance.return_value.mapLayers.return_value = {}
            self.layer_service = QGISLayerService()
            no_geom_layers = self.layer_service.get_no_geometry_layers()
            self.assertEqual(len(no_geom_layers), 0)

    def test_get_no_geometry_layers_with_layers(self):
        """Test getting no geometry layers when layers exist."""
        # Create mock no geometry layer
        mock_no_geom_layer = create_autospec(QgsVectorLayer)
        mock_no_geom_layer.id.return_value = "no_geom_layer_1"
        mock_no_geom_layer.name.return_value = "No Geometry Layer 1"
        mock_no_geom_layer.source.return_value = "test_source"
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:4326"
        mock_no_geom_layer.crs.return_value = mock_crs
        mock_no_geom_layer.featureCount.return_value = 10
        mock_no_geom_layer.geometryType.return_value = 0  # NoGeometry type
        mock_no_geom_layer.isValid.return_value = True

        # Prepare the layers dict
        layers_dict = {"no_geom_layer_1": mock_no_geom_layer}

        # Patch isinstance to return True for any layer in layers_dict
        def mock_isinstance(obj, cls):
            return obj in layers_dict.values()

        # Mock project with layers
        with patch('services.layer_service.QgsProject') as mock_project, \
             patch('services.layer_service.isinstance', side_effect=mock_isinstance):
            mock_project.instance.return_value.mapLayers.return_value = layers_dict
            self.layer_service = QGISLayerService()
            no_geom_layers = self.layer_service.get_no_geometry_layers()
            
            self.assertEqual(len(no_geom_layers), 1)
            self.assertEqual(no_geom_layers[0]['id'], "no_geom_layer_1")
            self.assertEqual(no_geom_layers[0]['name'], "No Geometry Layer 1") 