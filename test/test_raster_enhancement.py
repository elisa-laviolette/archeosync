"""
Tests for raster enhancement functionality.

This module tests the application of brightness, contrast, and saturation
settings to raster layers in field projects.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsRasterLayer, QgsProject, QgsRasterRenderer

try:
    from ..services.raster_processing_service import QGISRasterProcessingService
    from ..services.project_creation_service import QGISProjectCreationService
    from ..services.settings_service import QGISSettingsManager
    from ..services.layer_service import QGISLayerService
    from ..services.file_system_service import QGISFileSystemService
except ImportError:
    from services.raster_processing_service import QGISRasterProcessingService
    from services.project_creation_service import QGISProjectCreationService
    from services.settings_service import QGISSettingsManager
    from services.layer_service import QGISLayerService
    from services.file_system_service import QGISFileSystemService


class TestRasterEnhancement(unittest.TestCase):
    """Test cases for raster enhancement functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = QGISSettingsManager('ArcheoSync')
        self.layer_service = QGISLayerService()
        self.file_system_service = QGISFileSystemService(None)
        self.raster_processing_service = QGISRasterProcessingService()
        
        self.project_creation_service = QGISProjectCreationService(
            self.settings_manager,
            self.layer_service,
            self.file_system_service,
            self.raster_processing_service
        )

    def test_apply_raster_enhancement_settings(self):
        """Test applying brightness, contrast, and saturation to raster layer."""
        # Create a mock raster layer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_renderer = Mock(spec=QgsRasterRenderer)
        
        # Mock the renderer's brightness/contrast and hue/saturation methods
        mock_renderer.setBrightness = Mock()
        mock_renderer.setContrast = Mock()
        mock_renderer.setSaturation = Mock()
        
        mock_raster_layer.renderer.return_value = mock_renderer
        
        # Test enhancement values
        brightness = 50
        contrast = 25
        saturation = -10
        
        # Set settings
        self.settings_manager.set_value('raster_brightness', brightness)
        self.settings_manager.set_value('raster_contrast', contrast)
        self.settings_manager.set_value('raster_saturation', saturation)
        
        # Apply enhancement settings
        self.project_creation_service._apply_raster_enhancement(
            mock_raster_layer
        )
        
        # Verify the enhancement methods were called with correct values
        mock_renderer.setBrightness.assert_called_once_with(brightness)
        mock_renderer.setContrast.assert_called_once_with(contrast)
        mock_renderer.setSaturation.assert_called_once_with(saturation)

    def test_apply_raster_enhancement_zero_values(self):
        """Test applying zero enhancement values (no change)."""
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_renderer = Mock(spec=QgsRasterRenderer)
        
        mock_renderer.setBrightness = Mock()
        mock_renderer.setContrast = Mock()
        mock_renderer.setSaturation = Mock()
        
        mock_raster_layer.renderer.return_value = mock_renderer
        
        # Set settings to zero values
        self.settings_manager.set_value('raster_brightness', 0)
        self.settings_manager.set_value('raster_contrast', 0)
        self.settings_manager.set_value('raster_saturation', 0)
        
        # Apply zero enhancement values
        self.project_creation_service._apply_raster_enhancement(
            mock_raster_layer
        )
        
        # Verify the enhancement methods were called with zero values
        mock_renderer.setBrightness.assert_called_once_with(0)
        mock_renderer.setContrast.assert_called_once_with(0)
        mock_renderer.setSaturation.assert_called_once_with(0)

    def test_apply_raster_enhancement_negative_values(self):
        """Test applying negative enhancement values."""
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_renderer = Mock(spec=QgsRasterRenderer)
        
        mock_renderer.setBrightness = Mock()
        mock_renderer.setContrast = Mock()
        mock_renderer.setSaturation = Mock()
        
        mock_raster_layer.renderer.return_value = mock_renderer
        
        # Apply negative enhancement values
        brightness = -100
        contrast = -50
        saturation = -75
        
        # Set settings
        self.settings_manager.set_value('raster_brightness', brightness)
        self.settings_manager.set_value('raster_contrast', contrast)
        self.settings_manager.set_value('raster_saturation', saturation)
        
        self.project_creation_service._apply_raster_enhancement(
            mock_raster_layer
        )
        
        # Verify the enhancement methods were called with negative values
        mock_renderer.setBrightness.assert_called_once_with(brightness)
        mock_renderer.setContrast.assert_called_once_with(contrast)
        mock_renderer.setSaturation.assert_called_once_with(saturation)

    def test_apply_raster_enhancement_invalid_layer(self):
        """Test applying enhancement to invalid raster layer."""
        # Test with None layer
        result = self.project_creation_service._apply_raster_enhancement(
            None
        )
        self.assertFalse(result)
        
        # Test with layer that has no renderer
        mock_raster_layer = Mock(spec=QgsRasterLayer)
        mock_raster_layer.renderer.return_value = None
        
        result = self.project_creation_service._apply_raster_enhancement(
            mock_raster_layer
        )
        self.assertFalse(result)

    def test_create_clipped_raster_with_enhancement(self):
        """Test creating clipped raster with enhancement settings applied."""
        # Mock settings
        self.settings_manager.set_value('raster_brightness', 50)
        self.settings_manager.set_value('raster_contrast', 25)
        self.settings_manager.set_value('raster_saturation', -10)
        
        # Mock raster processing service
        with patch.object(self.raster_processing_service, 'clip_raster_to_geometry') as mock_clip:
            mock_clip.return_value = True
            
            # Patch both possible QgsRasterLayer import locations
            with patch('services.project_creation_service.QgsRasterLayer') as mock_raster_layer_class, \
                 patch('qgis.core.QgsRasterLayer', mock_raster_layer_class):
                # Create a mock layer that will be returned by the constructor
                mock_raster_layer = Mock(spec=QgsRasterLayer)
                mock_raster_layer.isValid.return_value = True
                mock_raster_layer_class.return_value = mock_raster_layer
                
                # Mock renderer
                mock_renderer = Mock()
                mock_renderer.setBrightness = Mock()
                mock_renderer.setContrast = Mock()
                mock_renderer.setSaturation = Mock()
                mock_raster_layer.renderer.return_value = mock_renderer
                
                # Mock project
                mock_project = Mock()
                mock_project.addMapLayer = Mock()
                
                # Test the method
                result = self.project_creation_service._create_clipped_raster(
                    'test_raster_id',
                    'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
                    '/tmp/test.tif',
                    mock_project,
                    0.2
                )
                
                # Verify the result
                self.assertTrue(result)
                
                # Verify the enhancement was applied
                mock_renderer.setBrightness.assert_called_once_with(50)
                mock_renderer.setContrast.assert_called_once_with(25)
                mock_renderer.setSaturation.assert_called_once_with(-10)

    def test_create_clipped_raster_without_enhancement(self):
        """Test creating clipped raster without enhancement settings."""
        # Mock settings with zero values
        self.settings_manager.set_value('raster_brightness', 0)
        self.settings_manager.set_value('raster_contrast', 0)
        self.settings_manager.set_value('raster_saturation', 0)
        
        # Mock raster processing service
        with patch.object(self.raster_processing_service, 'clip_raster_to_geometry') as mock_clip:
            mock_clip.return_value = True
            
            # Patch both possible QgsRasterLayer import locations
            with patch('services.project_creation_service.QgsRasterLayer') as mock_raster_layer_class, \
                 patch('qgis.core.QgsRasterLayer', mock_raster_layer_class):
                # Create a mock layer that will be returned by the constructor
                mock_raster_layer = Mock(spec=QgsRasterLayer)
                mock_raster_layer.isValid.return_value = True
                mock_raster_layer_class.return_value = mock_raster_layer
                
                # Mock renderer
                mock_renderer = Mock()
                mock_renderer.setBrightness = Mock()
                mock_renderer.setContrast = Mock()
                mock_renderer.setSaturation = Mock()
                mock_raster_layer.renderer.return_value = mock_renderer
                
                # Mock project
                mock_project = Mock()
                mock_project.addMapLayer = Mock()
                
                # Test the method
                result = self.project_creation_service._create_clipped_raster(
                    'test_raster_id',
                    'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
                    '/tmp/test.tif',
                    mock_project,
                    0.2
                )
                
                # Verify the result
                self.assertTrue(result)
                
                # Verify the enhancement was applied with zero values
                mock_renderer.setBrightness.assert_called_once_with(0)
                mock_renderer.setContrast.assert_called_once_with(0)
                mock_renderer.setSaturation.assert_called_once_with(0)

    def test_create_clipped_raster_clipping_fails(self):
        """Test creating clipped raster when clipping operation fails."""
        # Mock raster processing service to return failure
        with patch.object(self.raster_processing_service, 'clip_raster_to_geometry') as mock_clip:
            mock_clip.return_value = False
            
            # Mock project
            mock_project = Mock()
            
            # Test the method
            result = self.project_creation_service._create_clipped_raster(
                'test_raster_id',
                'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
                '/tmp/test.tif',
                mock_project,
                0.2
            )
            
            # Verify the result is False
            self.assertFalse(result)

    def test_create_clipped_raster_invalid_layer(self):
        """Test creating clipped raster when layer creation fails."""
        # Mock raster processing service
        with patch.object(self.raster_processing_service, 'clip_raster_to_geometry') as mock_clip:
            mock_clip.return_value = True
            
            # Mock QgsRasterLayer to return invalid layer
            with patch('qgis.core.QgsRasterLayer') as mock_raster_layer_class:
                mock_raster_layer = Mock(spec=QgsRasterLayer)
                mock_raster_layer.isValid.return_value = False
                mock_raster_layer_class.return_value = mock_raster_layer
                
                # Mock project
                mock_project = Mock()
                
                # Test the method
                result = self.project_creation_service._create_clipped_raster(
                    'test_raster_id',
                    'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
                    '/tmp/test.tif',
                    mock_project,
                    0.2
                )
                
                # Verify the result is False
                self.assertFalse(result)


if __name__ == '__main__':
    unittest.main() 