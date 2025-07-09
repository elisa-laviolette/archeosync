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
from unittest.mock import Mock, patch, MagicMock

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer
    from services.layer_service import QGISLayerService
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app


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


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestLayerService:
    """Test layer service functionality."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        self.layer_service = QGISLayerService()

    def test_layer_service_creation(self):
        """Test that layer service can be created."""
        assert self.layer_service is not None
        assert hasattr(self.layer_service, 'get_polygon_layers')
        assert hasattr(self.layer_service, 'get_layer_by_id')
        assert hasattr(self.layer_service, 'is_valid_polygon_layer')
        assert hasattr(self.layer_service, 'get_layer_info')

    def test_get_polygon_layers_empty_project(self):
        """Test getting polygon layers from empty project."""
        # Clear the project
        project = QgsProject.instance()
        project.removeAllMapLayers()
        
        polygon_layers = self.layer_service.get_polygon_layers()
        assert isinstance(polygon_layers, list)
        assert len(polygon_layers) == 0

    def test_get_polygon_layers_with_mock_layers(self):
        """Test getting polygon layers with mock layers."""
        # Create mock polygon layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        mock_layer.id.return_value = "test_layer_id"
        mock_layer.name.return_value = "Test Polygon Layer"
        mock_layer.source.return_value = "/path/to/test.shp"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.featureCount.return_value = 10
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {"test_layer_id": mock_layer}
            mock_project.instance.return_value = mock_instance
            
            polygon_layers = self.layer_service.get_polygon_layers()
            
            assert len(polygon_layers) == 1
            layer_info = polygon_layers[0]
            assert layer_info['id'] == "test_layer_id"
            assert layer_info['name'] == "Test Polygon Layer"
            assert layer_info['source'] == "/path/to/test.shp"
            assert layer_info['crs'] == "EPSG:4326"
            assert layer_info['feature_count'] == 10

    def test_get_polygon_layers_filters_non_polygon(self):
        """Test that only polygon layers are returned."""
        # Create mock non-polygon layer
        mock_non_polygon_layer = Mock(spec=QgsVectorLayer)
        mock_non_polygon_layer.geometryType.return_value = 1  # LineGeometry
        
        # Create mock polygon layer (type 3)
        mock_polygon_layer = Mock(spec=QgsVectorLayer)
        mock_polygon_layer.geometryType.return_value = 3  # PolygonGeometry
        mock_polygon_layer.id.return_value = "polygon_layer_id"
        mock_polygon_layer.name.return_value = "Polygon Layer"
        mock_polygon_layer.source.return_value = "/path/to/polygon.shp"
        mock_polygon_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_polygon_layer.featureCount.return_value = 5
        
        # Create mock multipolygon layer (type 2)
        mock_multipolygon_layer = Mock(spec=QgsVectorLayer)
        mock_multipolygon_layer.geometryType.return_value = 2  # MultiPolygonGeometry
        mock_multipolygon_layer.id.return_value = "multipolygon_layer_id"
        mock_multipolygon_layer.name.return_value = "MultiPolygon Layer"
        mock_multipolygon_layer.source.return_value = "/path/to/multipolygon.shp"
        mock_multipolygon_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_multipolygon_layer.featureCount.return_value = 3
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {
                "line_layer_id": mock_non_polygon_layer,
                "polygon_layer_id": mock_polygon_layer,
                "multipolygon_layer_id": mock_multipolygon_layer
            }
            mock_project.instance.return_value = mock_instance
            
            polygon_layers = self.layer_service.get_polygon_layers()
            
            assert len(polygon_layers) == 2
            layer_ids = [layer['id'] for layer in polygon_layers]
            assert "polygon_layer_id" in layer_ids
            assert "multipolygon_layer_id" in layer_ids

    def test_get_layer_by_id_not_found(self):
        """Test getting layer by ID when not found."""
        # Clear the project
        project = QgsProject.instance()
        project.removeAllMapLayers()
        
        layer = self.layer_service.get_layer_by_id("non_existent_id")
        assert layer is None

    def test_get_layer_by_id_found(self):
        """Test getting layer by ID when found."""
        # Create mock layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = mock_layer
            mock_project.instance.return_value = mock_instance
            
            layer = self.layer_service.get_layer_by_id("test_layer_id")
            assert layer == mock_layer

    def test_get_layer_by_id_wrong_type(self):
        """Test getting layer by ID when layer exists but is wrong type."""
        # Create mock non-vector layer
        mock_non_vector_layer = Mock()
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = mock_non_vector_layer
            mock_project.instance.return_value = mock_instance
            
            layer = self.layer_service.get_layer_by_id("test_layer_id")
            assert layer is None

    def test_is_valid_polygon_layer_valid(self):
        """Test checking if layer is valid polygon layer."""
        # Create mock polygon layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
            assert is_valid is True

    def test_is_valid_polygon_layer_multipolygon(self):
        """Test checking if layer is valid polygon layer (MultiPolygon)."""
        # Create mock multipolygon layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 2  # MultiPolygonGeometry
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
            assert is_valid is True

    def test_is_valid_polygon_layer_invalid_geometry(self):
        """Test checking if layer is valid polygon layer with wrong geometry."""
        # Create mock non-polygon layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.geometryType.return_value = 1  # LineGeometry
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
            assert is_valid is False

    def test_is_valid_polygon_layer_not_found(self):
        """Test checking if layer is valid polygon layer when not found."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            is_valid = self.layer_service.is_valid_polygon_layer("test_layer_id")
            assert is_valid is False

    def test_get_layer_info_not_found(self):
        """Test getting layer info when layer not found."""
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
            layer_info = self.layer_service.get_layer_info("test_layer_id")
            assert layer_info is None

    def test_get_layer_info_found(self):
        """Test getting layer info when layer found."""
        # Create mock layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.id.return_value = "test_layer_id"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.source.return_value = "/path/to/test.shp"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.featureCount.return_value = 15
        mock_layer.isValid.return_value = True
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            layer_info = self.layer_service.get_layer_info("test_layer_id")
            
            assert layer_info is not None
            assert layer_info['id'] == "test_layer_id"
            assert layer_info['name'] == "Test Layer"
            assert layer_info['source'] == "/path/to/test.shp"
            assert layer_info['crs'] == "EPSG:4326"
            assert layer_info['feature_count'] == 15
            assert layer_info['geometry_type'] == "Polygon"
            assert layer_info['is_valid'] is True

    def test_get_layer_info_invalid_layer(self):
        """Test getting layer info for invalid layer."""
        # Create mock invalid layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.id.return_value = "test_layer_id"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.source.return_value = "/path/to/test.shp"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.featureCount.return_value = 15
        mock_layer.isValid.return_value = False
        mock_layer.geometryType.return_value = 3  # PolygonGeometry
        
        with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_layer):
            layer_info = self.layer_service.get_layer_info("test_layer_id")
            
            assert layer_info is not None
            assert layer_info['is_valid'] is False

    def test_get_raster_layers_empty_project(self):
        """Test getting raster layers from empty project."""
        # Clear the project
        project = QgsProject.instance()
        project.removeAllMapLayers()
        
        raster_layers = self.layer_service.get_raster_layers()
        assert isinstance(raster_layers, list)
        assert len(raster_layers) == 0

    def test_get_raster_layers_with_mock_layers(self):
        """Test getting raster layers with mock layers."""
        # Create mock raster layer
        mock_layer = Mock(spec=QgsRasterLayer)
        mock_layer.id.return_value = "test_raster_id"
        mock_layer.name.return_value = "Test Raster Layer"
        mock_layer.source.return_value = "/path/to/test.tif"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.width.return_value = 100
        mock_layer.height.return_value = 200
        mock_layer.extent.return_value = Mock()
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {"test_raster_id": mock_layer}
            mock_project.instance.return_value = mock_instance
            
            raster_layers = self.layer_service.get_raster_layers()
            
            assert len(raster_layers) == 1
            layer_info = raster_layers[0]
            assert layer_info['id'] == "test_raster_id"
            assert layer_info['name'] == "Test Raster Layer"
            assert layer_info['source'] == "/path/to/test.tif"
            assert layer_info['crs'] == "EPSG:4326"
            assert layer_info['width'] == 100
            assert layer_info['height'] == 200

    def test_get_raster_layers_filters_non_raster(self):
        """Test that only raster layers are returned."""
        # Create mock non-raster layer
        mock_vector_layer = Mock(spec=QgsVectorLayer)
        mock_vector_layer.geometryType.return_value = 3  # PolygonGeometry
        
        # Create mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.id.return_value = "raster_layer_id"
        mock_raster_layer.name.return_value = "Raster Layer"
        mock_raster_layer.source.return_value = "/path/to/raster.tif"
        mock_raster_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_raster_layer.width.return_value = 50
        mock_raster_layer.height.return_value = 100
        mock_raster_layer.extent.return_value = Mock()
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {
                "vector_layer_id": mock_vector_layer,
                "raster_layer_id": mock_raster_layer
            }
            mock_project.instance.return_value = mock_instance
            
            raster_layers = self.layer_service.get_raster_layers()
            
            assert len(raster_layers) == 1
            assert raster_layers[0]['id'] == "raster_layer_id"

    def test_get_layer_by_id_with_raster_layer(self):
        """Test getting raster layer by ID."""
        # Create mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.id.return_value = "test_raster_id"
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = mock_raster_layer
            mock_project.instance.return_value = mock_instance
            
            layer = self.layer_service.get_layer_by_id("test_raster_id")
            assert layer == mock_raster_layer

    def test_get_raster_layers_overlapping_feature(self):
        """Test getting raster layers that overlap with a feature."""
        # Create mock feature with geometry
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_feature.geometry.return_value = mock_geometry
        
        mock_extent = Mock()
        mock_geometry.boundingBox.return_value = mock_extent
        
        # Create mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.id.return_value = "overlapping_raster_id"
        mock_raster_layer.name.return_value = "Overlapping Raster"
        mock_raster_layer.source.return_value = "/path/to/overlapping.tif"
        mock_raster_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_raster_layer.width.return_value = 100
        mock_raster_layer.height.return_value = 100
        mock_raster_layer.extent.return_value = Mock()
        
        # Mock intersection
        mock_extent.intersects.return_value = True
        
        # Create mock recording layer
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {"overlapping_raster_id": mock_raster_layer}
            mock_project.instance.return_value = mock_instance
            
            with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_recording_layer):
                overlapping_layers = self.layer_service.get_raster_layers_overlapping_feature(
                    mock_feature, "recording_layer_id"
                )
                
                assert len(overlapping_layers) == 1
                layer_info = overlapping_layers[0]
                assert layer_info['id'] == "overlapping_raster_id"
                assert layer_info['name'] == "Overlapping Raster"

    def test_get_raster_layers_overlapping_feature_no_overlap(self):
        """Test getting raster layers when there's no overlap."""
        # Create mock feature with geometry
        mock_feature = Mock()
        mock_geometry = Mock()
        mock_feature.geometry.return_value = mock_geometry
        
        mock_extent = Mock()
        mock_geometry.boundingBox.return_value = mock_extent
        
        # Create mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.extent.return_value = Mock()
        
        # Mock no intersection
        mock_extent.intersects.return_value = False
        
        # Create mock recording layer
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {"raster_id": mock_raster_layer}
            mock_project.instance.return_value = mock_instance
            
            with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_recording_layer):
                overlapping_layers = self.layer_service.get_raster_layers_overlapping_feature(
                    mock_feature, "recording_layer_id"
                )
                
                assert len(overlapping_layers) == 0

    def test_get_raster_layers_overlapping_feature_no_recording_layer(self):
        """Test getting raster layers when recording layer is not found."""
        # Create mock feature
        mock_feature = Mock()
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {}
            mock_project.instance.return_value = mock_instance
            
            with patch.object(self.layer_service, 'get_layer_by_id', return_value=None):
                overlapping_layers = self.layer_service.get_raster_layers_overlapping_feature(
                    mock_feature, "non_existent_layer_id"
                )
                
                assert len(overlapping_layers) == 0

    def test_get_raster_layers_overlapping_feature_no_geometry(self):
        """Test getting raster layers when feature has no geometry."""
        # Create mock feature without geometry
        mock_feature = Mock()
        mock_feature.geometry.return_value = None
        
        # Create mock recording layer
        mock_recording_layer = Mock(spec=QgsVectorLayer)
        
        # Mock QgsProject - patch the import in the service module
        with patch('services.layer_service.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayers.return_value = {}
            mock_project.instance.return_value = mock_instance
            
            with patch.object(self.layer_service, 'get_layer_by_id', return_value=mock_recording_layer):
                overlapping_layers = self.layer_service.get_raster_layers_overlapping_feature(
                    mock_feature, "recording_layer_id"
                )
                
                assert len(overlapping_layers) == 0 


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestLayerServiceIntegration:
    """Integration tests for LayerService with real QGIS environment."""

    def setup_method(self):
        """Runs before each test."""
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        self.layer_service = QGISLayerService()

    def test_layer_service_with_real_project(self):
        """Test layer service with real QGIS project."""
        # Clear the project
        project = QgsProject.instance()
        project.removeAllMapLayers()
        
        # Test with empty project
        polygon_layers = self.layer_service.get_polygon_layers()
        assert isinstance(polygon_layers, list)
        assert len(polygon_layers) == 0
        
        # Test getting non-existent layer
        layer = self.layer_service.get_layer_by_id("non_existent")
        assert layer is None
        
        # Test layer info for non-existent layer
        layer_info = self.layer_service.get_layer_info("non_existent")
        assert layer_info is None
        
        # Test validation for non-existent layer
        is_valid = self.layer_service.is_valid_polygon_layer("non_existent")
        assert is_valid is False 