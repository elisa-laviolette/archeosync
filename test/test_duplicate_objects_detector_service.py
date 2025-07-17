"""
Tests for DuplicateObjectsDetectorService.

This module tests the duplicate objects detector service functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from services.duplicate_objects_detector_service import DuplicateObjectsDetectorService
except ImportError:
    from ..services.duplicate_objects_detector_service import DuplicateObjectsDetectorService


class TestDuplicateObjectsDetectorService(unittest.TestCase):
    """Test cases for DuplicateObjectsDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings_manager = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        
        self.service = DuplicateObjectsDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service
        )
    
    def test_detect_duplicate_objects_no_configuration(self):
        """Test that no warnings are returned when no configuration is set."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: None
        
        warnings = self.service.detect_duplicate_objects()
        
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_objects_no_layers(self):
        """Test that no warnings are returned when no layers are found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        self.mock_layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_duplicate_objects()
        
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_objects_no_new_objects_layer(self):
        """Test that no warnings are returned when no new objects layer is found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        mock_layer = Mock()
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        self.mock_layer_service.get_layer_by_name.return_value = None
        
        warnings = self.service.detect_duplicate_objects()
        
        self.assertEqual(warnings, [])
    
    def test_detect_duplicates_within_layer(self):
        """Test detection of duplicates within a single layer."""
        # Setup mocks
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "number_field"
        
        # Mock layer with features
        mock_layer = Mock()
        mock_layer.name.return_value = "Test Layer"
        
        # Mock features with same recording area and number
        mock_feature1 = Mock()
        mock_feature1.attributes.return_value = {"recording_area": 1, "number_field": 123}
        
        mock_feature2 = Mock()
        mock_feature2.attributes.return_value = {"recording_area": 1, "number_field": 123}
        
        mock_feature3 = Mock()
        mock_feature3.attributes.return_value = {"recording_area": 1, "number_field": 456}
        
        mock_layer.getFeatures.return_value = [mock_feature1, mock_feature2, mock_feature3]
        
        # Mock recording area name lookup
        self.service._get_recording_area_name = Mock(return_value="Test Area")
        
        # Mock recording areas layer
        mock_recording_areas_layer = Mock()
        
        warnings = self.service._detect_duplicates_within_layer(
            mock_layer, mock_recording_areas_layer, "number_field", "recording_area", "Test Layer"
        )
        
        self.assertEqual(len(warnings), 1)
        self.assertIn('Test Area', warnings[0])
        self.assertIn('123', warnings[0])
        self.assertIn('Test Layer', warnings[0])
    
    def test_get_recording_area_name_fallback(self):
        """Test getting recording area name with fallback to ID."""
        # Mock layer service to return None for display expression
        mock_recording_areas_layer = Mock()
        mock_recording_areas_layer.displayExpression.return_value = ""
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)
        
        self.assertEqual(name, "1")
    
    def test_get_recording_area_name_with_display_expression(self):
        """Test getting recording area name using display expression."""
        # Mock layer with display expression
        mock_recording_areas_layer = Mock()
        
        # Mock fields to return a field at index 0
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Name field found at index 0
        mock_recording_areas_layer.fields.return_value = mock_fields
        
        # Mock feature with name
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.__getitem__.return_value = "Display Name"  # Use __getitem__ instead of attribute
        mock_recording_areas_layer.getFeatures.return_value = [mock_feature]
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)
        
        self.assertEqual(name, "Display Name")
    
    def test_create_duplicate_warning_with_translation(self):
        """Test creating duplicate warning with translation."""
        # Mock the translation service to return the expected string
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has {count} objects with number {number} in {layer_name}"
        
        warning = self.service._create_duplicate_warning(
            recording_area_name="Test Area",
            count=2,
            number="123",
            layer_name="Test Layer"
        )
        
        self.assertEqual(warning, "Recording Area 'Test Area' has 2 objects with number 123 in Test Layer")
        self.mock_translation_service.tr.assert_called_once()
    
    def test_create_duplicate_warning_without_translation(self):
        """Test creating duplicate warning without translation service."""
        service = DuplicateObjectsDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
            translation_service=None
        )
        
        warning = service._create_duplicate_warning(
            recording_area_name="Test Area",
            number="123",
            layer_name="Test Layer",
            count=2
        )
        
        self.assertIn("Test Area", warning)
        self.assertIn("123", warning)
        self.assertIn("Test Layer", warning)
        self.assertIn("2", warning)


if __name__ == '__main__':
    unittest.main() 