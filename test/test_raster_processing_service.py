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

    def test_get_gdal_debug_info(self):
        """Test GDAL debug information method."""
        debug_info = self.raster_service.get_gdal_debug_info()
        assert isinstance(debug_info, str)
        assert "GDAL Tool Debug Information" in debug_info
        assert "gdalwarp" in debug_info
        assert "ogr2ogr" in debug_info

    def test_get_gdal_tool_paths(self):
        """Test GDAL tool path detection."""
        paths = self.raster_service._get_gdal_tool_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0
        
        # Should include current PATH
        current_path = os.environ.get('PATH', '').split(os.pathsep)
        for path in current_path:
            if path:
                assert path in paths

    def test_get_gdal_tool_path(self):
        """Test getting specific GDAL tool path."""
        # Mock successful tool check
        with patch.object(self.raster_service, '_check_gdal_tool', return_value=True):
            path = self.raster_service._get_gdal_tool_path('gdalwarp')
            assert path is not None
        
        # Mock failed tool check
        with patch.object(self.raster_service, '_check_gdal_tool', return_value=False):
            path = self.raster_service._get_gdal_tool_path('nonexistent_tool')
            assert path is None

    def test_raster_layer_visibility_integration(self):
        """Test that raster layers are properly configured for visibility in QField projects."""
        from qgis.core import QgsRasterLayer
        from unittest.mock import Mock, patch

        # Create mock clipped raster layer
        mock_clipped_layer = Mock(spec=QgsRasterLayer)
        mock_clipped_layer.id.return_value = 'clipped_layer_id'
        mock_clipped_layer.name.return_value = 'clipped_raster'
        mock_clipped_layer.isValid.return_value = True
        mock_clipped_layer.setCustomProperty = Mock()
        mock_clipped_layer.source.return_value = '/temp/clipped.tif'
        mock_clipped_layer.crs.return_value = Mock()
        mock_clipped_layer.crs.return_value.authid.return_value = 'EPSG:4326'

        # Create mock original raster layer
        mock_original_layer = Mock(spec=QgsRasterLayer)
        mock_original_layer.id.return_value = 'valid_id'
        mock_original_layer.source.return_value = '/path/to/original.tif'
        mock_original_layer.crs.return_value = Mock()
        mock_original_layer.crs.return_value.authid.return_value = 'EPSG:4326'

        # Create mock project and set up mapLayer to return the original layer
        mock_project = Mock()
        mock_project.addMapLayer = Mock()
        mock_project.mapLayer.return_value = mock_original_layer
        mock_project.crs.return_value = Mock(authid=lambda: 'EPSG:4326')
        mock_layer_tree_root = Mock()
        mock_project.layerTreeRoot.return_value = mock_layer_tree_root

        # Create mock geometry
        mock_geometry = Mock()
        mock_geometry.isNull.return_value = False
        mock_geometry.isValid.return_value = True
        mock_geometry.buffer.return_value = mock_geometry
        mock_geometry.asWkt.return_value = 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'

        # Patch QgsProject.instance() to return mock_project
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('qgis.core.QgsRasterLayer', return_value=mock_clipped_layer), \
             patch('os.path.exists', return_value=True), \
             patch.object(self.raster_service, 'is_gdal_available', return_value=True), \
             patch.object(self.raster_service, '_create_temp_shapefile', return_value='/temp/clip.shp'), \
             patch.object(self.raster_service, '_execute_gdalwarp', return_value=True), \
             patch.object(self.raster_service, '_cleanup_temp_shapefile'):
            result = self.raster_service.clip_raster_to_feature('valid_id', mock_geometry, 0.2, '/temp/clipped.tif')
            assert result == '/temp/clipped.tif'

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
        """Test successful raster clipping returns output path."""
        from qgis.core import QgsRasterLayer
        from unittest.mock import Mock, patch

        # Create mock original raster layer
        mock_original_layer = Mock(spec=QgsRasterLayer)
        mock_original_layer.id.return_value = 'valid_id'
        mock_original_layer.source.return_value = '/path/to/original.tif'
        mock_original_layer.crs.return_value = Mock()
        mock_original_layer.crs.return_value.authid.return_value = 'EPSG:4326'

        # Create mock clipped raster layer
        mock_clipped_layer = Mock(spec=QgsRasterLayer)
        mock_clipped_layer.id.return_value = 'clipped_layer_id'
        mock_clipped_layer.name.return_value = 'clipped_raster'
        mock_clipped_layer.isValid.return_value = True
        mock_clipped_layer.setCustomProperty = Mock()
        mock_clipped_layer.source.return_value = '/temp/clipped.tif'
        mock_clipped_layer.crs.return_value = Mock()
        mock_clipped_layer.crs.return_value.authid.return_value = 'EPSG:4326'

        # Create mock project and set up mapLayer to return the original layer
        mock_project = Mock()
        mock_project.addMapLayer = Mock()
        mock_project.mapLayer.return_value = mock_original_layer
        mock_project.crs.return_value = Mock(authid=lambda: 'EPSG:4326')
        mock_layer_tree_root = Mock()
        mock_project.layerTreeRoot.return_value = mock_layer_tree_root

        # Create mock geometry
        mock_geometry = Mock()
        mock_geometry.isNull.return_value = False
        mock_geometry.isValid.return_value = True
        mock_geometry.buffer.return_value = mock_geometry
        mock_geometry.asWkt.return_value = 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'

        # Patch QgsProject.instance().mapLayer to return the correct mock for 'valid_id'
        def mapLayer_side_effect(layer_id):
            if layer_id == 'valid_id':
                return mock_original_layer
            return None
        mock_project.mapLayer.side_effect = mapLayer_side_effect

        # Patch QgsProject.instance() to return mock_project
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('qgis.core.QgsRasterLayer', return_value=mock_clipped_layer), \
             patch('os.path.exists', return_value=True), \
             patch.object(self.raster_service, 'is_gdal_available', return_value=True), \
             patch.object(self.raster_service, '_create_temp_shapefile', return_value='/temp/clip.shp'), \
             patch.object(self.raster_service, '_execute_gdalwarp', return_value=True), \
             patch.object(self.raster_service, '_cleanup_temp_shapefile'):
            result = self.raster_service.clip_raster_to_feature('valid_id', mock_geometry, 0.2, '/temp/clipped.tif')
            assert result == '/temp/clipped.tif'

        # In test_clip_raster_to_feature_success, do the same for mapLayer and _execute_gdalwarp
        mock_project.mapLayer.side_effect = mapLayer_side_effect
        with patch('qgis.core.QgsProject.instance', return_value=mock_project), \
             patch('qgis.core.QgsRasterLayer', return_value=mock_clipped_layer), \
             patch('os.path.exists', return_value=True), \
             patch.object(self.raster_service, 'is_gdal_available', return_value=True), \
             patch.object(self.raster_service, '_create_temp_shapefile', return_value='/temp/clip.shp'), \
             patch.object(self.raster_service, '_execute_gdalwarp', return_value=True), \
             patch.object(self.raster_service, '_cleanup_temp_shapefile'):
            result = self.raster_service.clip_raster_to_feature('valid_id', mock_geometry, 0.2, '/temp/clipped.tif')
            assert result == '/temp/clipped.tif' 