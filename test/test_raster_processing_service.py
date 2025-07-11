"""
Tests for the raster processing service.

This module tests the QGISRasterProcessingService implementation to ensure
it correctly handles raster clipping operations with GDAL.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

try:
    from qgis.core import QgsRasterLayer, QgsGeometry, QgsProject
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

try:
    from services.raster_processing_service import QGISRasterProcessingService
    from core.interfaces import IRasterProcessingService
except ImportError:
    QGISRasterProcessingService = None
    IRasterProcessingService = None


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
@pytest.mark.skipif(QGISRasterProcessingService is None, reason="Raster processing service not available")
class TestRasterProcessingService:
    """Test the raster processing service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.raster_service = QGISRasterProcessingService()
        self.settings_manager = Mock()
        self.raster_service._settings_manager = self.settings_manager

    def test_is_gdal_available(self):
        """Test GDAL availability check."""
        # Mock subprocess.run to return success
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            assert self.raster_service.is_gdal_available() is True

        # Mock subprocess.run to return failure
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            assert self.raster_service.is_gdal_available() is False

        # Mock subprocess.run to raise exception
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command not found")
            assert self.raster_service.is_gdal_available() is False

    def test_clip_raster_to_feature_invalid_layer(self):
        """Test clipping with invalid raster layer ID."""
        # Mock QgsProject to return None for layer
        with patch('qgis.core.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = None
            mock_project.instance.return_value = mock_instance

            result = self.raster_service.clip_raster_to_feature(
                raster_layer_id='invalid_id',
                feature_geometry=Mock(),
                offset_meters=0.2
            )
            assert result is None

    def test_clip_raster_to_feature_invalid_geometry(self):
        """Test clipping with invalid geometry."""
        # Mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.source.return_value = '/path/to/raster.tif'

        # Mock QgsProject
        with patch('qgis.core.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = mock_raster_layer
            mock_project.instance.return_value = mock_instance

        # Mock invalid geometry
        mock_geometry = Mock()
        mock_geometry.isValid.return_value = False

        result = self.raster_service.clip_raster_to_feature(
            raster_layer_id='valid_id',
            feature_geometry=mock_geometry,
            offset_meters=0.2
        )
        assert result is None

    def test_clip_raster_to_feature_missing_source(self):
        """Test clipping with missing raster source file."""
        # Mock raster layer with non-existent source
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.source.return_value = '/nonexistent/path.tif'

        # Mock QgsProject
        with patch('qgis.core.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_instance.mapLayer.return_value = mock_raster_layer
            mock_project.instance.return_value = mock_instance

        # Mock valid geometry
        mock_geometry = Mock()
        mock_geometry.isValid.return_value = True

        # Mock os.path.exists to return False
        with patch('os.path.exists', return_value=False):
            result = self.raster_service.clip_raster_to_feature(
                raster_layer_id='valid_id',
                feature_geometry=mock_geometry,
                offset_meters=0.2
            )
            assert result is None

    def test_create_temp_output_path(self):
        """Test temporary output path creation."""
        input_path = '/path/to/input.tif'
        result = self.raster_service._create_temp_output_path(input_path)
        
        assert result.endswith('.tif')
        assert 'clipped_' in result
        assert os.path.dirname(result) == tempfile.gettempdir()

    def test_wkt_to_coordinates(self):
        """Test WKT to coordinate conversion."""
        wkt = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        result = self.raster_service._wkt_to_coordinates(wkt)
        expected = "[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]"
        assert result == expected

    def test_wkt_to_coordinates_invalid(self):
        """Test WKT to coordinate conversion with invalid WKT."""
        wkt = "INVALID_WKT"
        result = self.raster_service._wkt_to_coordinates(wkt)
        assert result == ""

    def test_cleanup_temp_shapefile(self):
        """Test temporary shapefile cleanup."""
        # Create a temporary file to simulate shapefile
        with tempfile.NamedTemporaryFile(suffix='.shp', delete=False) as temp_file:
            temp_path = temp_file.name

        # Mock os.path.exists and os.remove
        with patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            
            self.raster_service._cleanup_temp_shapefile(temp_path)
            
            # Check that remove was called for each extension
            assert mock_remove.call_count >= 1

        # Clean up the actual temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_interface_implementation(self):
        """Test that the service implements the correct interface."""
        assert isinstance(self.raster_service, IRasterProcessingService)

    def test_clip_raster_to_feature_success(self):
        """Test successful raster clipping (integration test)."""
        # This test would require actual GDAL tools and a real raster file
        # For now, we'll just test the method signature and basic flow
        
        # Create mock raster layer with correct spec
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.id.return_value = 'valid_id'
        mock_raster_layer.source.return_value = '/path/to/raster.tif'
        
        # Create mock clipped raster layer
        mock_clipped_layer = Mock()
        mock_clipped_layer.id.return_value = 'clipped_layer_id'
        mock_clipped_layer.isValid.return_value = True
        
        # Create mock project
        mock_project = Mock()
        mock_project.mapLayer.return_value = mock_raster_layer
        mock_project.addMapLayer = Mock()
        mock_project.crs.return_value = Mock(authid=lambda: 'EPSG:4326')
        
        # Create mock geometry
        mock_geometry = Mock()
        mock_geometry.isValid.return_value = True
        mock_geometry.isNull.return_value = False
        mock_geometry.buffer.return_value = mock_geometry
        mock_geometry.asWkt.return_value = 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'
        
        # Mock all dependencies
        with patch.object(self.raster_service, 'is_gdal_available', return_value=True), \
             patch.object(self.raster_service, '_create_temp_shapefile', return_value='/temp/clip.shp'), \
             patch.object(self.raster_service, '_execute_gdalwarp', return_value=True), \
             patch.object(self.raster_service, '_cleanup_temp_shapefile'), \
             patch('os.path.exists', return_value=True), \
             patch('qgis.core.QgsRasterLayer', return_value=mock_clipped_layer), \
             patch('archeosync.services.raster_processing_service.QgsProject.instance') as mock_instance:
            mock_project = Mock()
            mock_project.mapLayer.return_value = mock_raster_layer
            mock_instance.return_value = mock_project
            # Test the method
            result = self.raster_service.clip_raster_to_feature(
                raster_layer_id='valid_id',
                feature_geometry=mock_geometry,
                offset_meters=0.2,
                output_path='/temp/clipped.tif'
            )
            # Verify result
            assert result == '/temp/clipped.tif'
            # Verify mocks were called
            mock_project.mapLayer.assert_called_with('valid_id') 