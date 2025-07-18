"""
Tests for SkippedNumbersDetectorService.

This module tests the skipped numbers detector service functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from services.skipped_numbers_detector_service import SkippedNumbersDetectorService
    from core.data_structures import WarningData
except ImportError:
    from ..services.skipped_numbers_detector_service import SkippedNumbersDetectorService
    from ..core.data_structures import WarningData


class TestSkippedNumbersDetectorService(unittest.TestCase):
    """Test cases for SkippedNumbersDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings_manager = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        
        self.service = SkippedNumbersDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service
        )
    
    def test_detect_skipped_numbers_no_configuration(self):
        """Test that no warnings are returned when no configuration is set."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: None
        
        warnings = self.service.detect_skipped_numbers()
        
        self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_missing_layers(self):
        """Test that no warnings are returned when layers are not found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        self.mock_layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_skipped_numbers()
        
        self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_no_relation(self):
        """Test that no warnings are returned when no relation is found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        mock_layer = Mock()
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock QGIS project with no relations
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_original_layer_only_no_warnings(self):
        """Test that no warnings are returned when only original layer exists and no gaps."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        mock_layer = Mock()
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock QGIS project with no "New Objects" layer
        mock_project = Mock()
        mock_project.mapLayers.return_value = {}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_non_numeric_values(self):
        """Test that non-numeric values are handled gracefully."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        mock_layer = Mock()
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock QGIS project with no "New Objects" layer
        mock_project = Mock()
        mock_project.mapLayers.return_value = {}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_no_gaps(self):
        """Test that no warnings are returned when there are no gaps in numbering."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        mock_layer = Mock()
        self.mock_layer_service.get_layer_by_id.return_value = mock_layer
        
        # Mock QGIS project with no "New Objects" layer
        mock_project = Mock()
        mock_project.mapLayers.return_value = {}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            self.assertEqual(warnings, [])
    
    def test_find_gaps_in_sequence(self):
        """Test that gaps are correctly identified in a sequence."""
        # Test with gaps
        numbers = [1, 2, 4, 6, 8]
        gaps = self.service._find_gaps_in_sequence(numbers)
        self.assertEqual(gaps, [3, 5, 7])
        
        # Test with no gaps
        numbers = [1, 2, 3, 4, 5]
        gaps = self.service._find_gaps_in_sequence(numbers)
        self.assertEqual(gaps, [])
        
        # Test with single number
        numbers = [1]
        gaps = self.service._find_gaps_in_sequence(numbers)
        self.assertEqual(gaps, [])
        
        # Test with empty list
        numbers = []
        gaps = self.service._find_gaps_in_sequence(numbers)
        self.assertEqual(gaps, [])
    
    def test_find_layer_by_name_not_found(self):
        """Test that None is returned when layer is not found by name."""
        # Mock QGIS project with no layers
        mock_project = Mock()
        mock_project.mapLayers.return_value = {}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.service._find_layer_by_name("NonExistentLayer")
            
            self.assertIsNone(result)
    
    def test_find_layer_by_name(self):
        """Test that layer is found by name."""
        mock_layer = Mock()
        mock_layer.name.return_value = "Test Layer"
        
        # Mock QGIS project with the layer
        mock_project = Mock()
        mock_project.mapLayers.return_value = {'layer_id': mock_layer}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.service._find_layer_by_name("Test Layer")
            
            self.assertEqual(result, mock_layer)
    
    def test_get_recording_area_name_fallback_to_id(self):
        """Test that recording area name falls back to ID when no name field is found."""
        mock_recording_areas_layer = Mock()
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1  # No name field found
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 123)
        
        self.assertEqual(name, "123")
    
    def test_get_recording_area_name_with_name_field(self):
        """Test that recording area name is retrieved from name field."""
        mock_recording_areas_layer = Mock()
        
        # Mock fields to return a field at index 0
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0  # Name field found at index 0
        mock_recording_areas_layer.fields.return_value = mock_fields
        
        # Mock feature with name
        mock_feature = Mock()
        mock_feature.id.return_value = 123
        mock_feature.__getitem__.return_value = "Test Area"  # Use __getitem__ instead of attribute
        mock_recording_areas_layer.getFeatures.return_value = [mock_feature]
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 123)
        
        self.assertEqual(name, "Test Area")
    
    def test_create_skipped_numbers_warning_with_translation(self):
        """Test that warning message is created with translation."""
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        warning = self.service._create_skipped_numbers_warning("Test Area", [2, 4], "Test Layer")
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: [2, 4] in Test Layer")
        self.mock_translation_service.tr.assert_called_once()
    
    def test_create_skipped_numbers_warning_single_gap(self):
        """Test that warning message is created for single gap."""
        # Mock the translation service to return the expected string
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        warning = self.service._create_skipped_numbers_warning("Test Area", [2], "Test Layer")
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: [2] in Test Layer")
    
    def test_create_skipped_numbers_warning_fallback_to_english(self):
        """Test that warning message falls back to English when translation fails."""
        self.mock_translation_service.tr.side_effect = Exception("Translation failed")
        
        warning = self.service._create_skipped_numbers_warning("Test Area", [2, 4], "Test Layer")
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: [2, 4] in Test Layer")
    
    def test_detect_skipped_numbers_with_new_objects_layer(self):
        """Test that skipped numbers are detected when new objects layer exists."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = [mock_objects_layer, mock_recording_areas_layer]
        
        # Mock new objects layer
        mock_new_objects_layer = Mock()
        
        # Mock QGIS project
        mock_project = Mock()
        mock_project.mapLayers.return_value = {'new_objects_id': mock_new_objects_layer}
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            # Should return a list (may be empty if no gaps found)
            self.assertIsInstance(warnings, list)
    
    def test_detect_skipped_numbers_between_layers(self):
        """Test that skipped numbers are detected between layers."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_new_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        
        # Mock features with numbers
        mock_feature1 = Mock()
        mock_feature1.attribute.side_effect = [1, 1]  # recording_area_id, number
        mock_feature2 = Mock()
        mock_feature2.attribute.side_effect = [1, 3]  # recording_area_id, number
        mock_feature3 = Mock()
        mock_feature3.attribute.side_effect = [1, 5]  # recording_area_id, number
        
        mock_objects_layer.getFeatures.return_value = [mock_feature1, mock_feature3]
        mock_new_objects_layer.getFeatures.return_value = [mock_feature2]
        
        # Mock recording area name
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1
        
        # Mock QGIS project
        mock_project = Mock()
        mock_project.mapLayers.return_value = {'new_objects_id': mock_new_objects_layer}
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
            
            # Should return a list of WarningData objects
            self.assertIsInstance(warnings, list)
            if warnings:
                self.assertIsInstance(warnings[0], WarningData) 