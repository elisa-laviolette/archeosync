"""
Tests for the SkippedNumbersDetectorService.

This module tests the SkippedNumbersDetectorService class to ensure it correctly
detects skipped numbers in recording areas and provides appropriate warnings.

Test Coverage:
- Detection of skipped numbers within a single layer
- Detection of skipped numbers across multiple layers
- Handling of missing configuration
- Handling of missing layers
- Translation support for warning messages
- Edge cases with non-numeric numbers
- Recording area name resolution
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsVectorLayer, QgsFeature, QgsField, QgsFields
from PyQt5.QtCore import QVariant

# Import the service to test
from ..services.skipped_numbers_detector_service import SkippedNumbersDetectorService


class TestSkippedNumbersDetectorService(unittest.TestCase):
    """Test cases for the SkippedNumbersDetectorService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_settings_manager = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        
        # Create service instance
        self.service = SkippedNumbersDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service
        )
    
    def test_detect_skipped_numbers_no_configuration(self):
        """Test detection when configuration is missing."""
        # Mock settings to return None/empty values
        self.mock_settings_manager.get_value.side_effect = lambda key: None
        
        warnings = self.service.detect_skipped_numbers()
        
        self.assertEqual(warnings, [])
        self.mock_settings_manager.get_value.assert_called()
    
    def test_detect_skipped_numbers_missing_layers(self):
        """Test detection when layers are not found."""
        # Mock settings to return valid configuration
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layer service to return None for layers
        self.mock_layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_skipped_numbers()
        
        self.assertEqual(warnings, [])
        self.mock_layer_service.get_layer_by_id.assert_called()
    
    def test_detect_skipped_numbers_no_relation(self):
        """Test detection when no relation exists between layers."""
        # Mock settings
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'objects_layer_id': mock_objects_layer,
            'recording_areas_layer_id': mock_recording_areas_layer
        }.get(layer_id)
        
        # Mock QgsProject and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_project.relationManager.return_value = mock_relation_manager
        mock_relation_manager.relations.return_value = {}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
        
        self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_original_layer_only_no_warnings(self):
        """Test that no warnings are generated for gaps in original objects layer alone."""
        # Mock settings
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'objects_layer_id': mock_objects_layer,
            'recording_areas_layer_id': mock_recording_areas_layer
        }.get(layer_id)
        
        # Mock fields
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda field_name: {
            'number_field': 0,
            'recording_area_field': 1
        }.get(field_name, -1)
        mock_objects_layer.fields.return_value = mock_fields
        
        # Mock features with gaps (1, 3, 5 - missing 2, 4)
        mock_features = []
        for i, number in enumerate([1, 3, 5]):
            mock_feature = Mock()
            # Create a proper mock that returns different values for different indices
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features.append(mock_feature)
        
        mock_objects_layer.getFeatures.return_value = mock_features
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QgsProject and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_project.relationManager.return_value = mock_relation_manager
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        # No New Objects layer found
        mock_project.mapLayersByName.return_value = []
        
        # Mock recording area name
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = 0
        mock_recording_areas_layer.getFeatures.return_value = [Mock()]
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
        
        # Should not detect any warnings since no New Objects layer exists
        self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_no_gaps(self):
        """Test detection when no gaps exist in numbering."""
        # Mock settings
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'objects_layer_id': mock_objects_layer,
            'recording_areas_layer_id': mock_recording_areas_layer
        }.get(layer_id)
        
        # Mock fields
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda field_name: {
            'number_field': 0,
            'recording_area_field': 1
        }.get(field_name, -1)
        mock_objects_layer.fields.return_value = mock_fields
        
        # Mock features with no gaps (1, 2, 3)
        mock_features = []
        for i, number in enumerate([1, 2, 3]):
            mock_feature = Mock()
            # Create a proper mock that returns different values for different indices
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features.append(mock_feature)
        
        mock_objects_layer.getFeatures.return_value = mock_features
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QgsProject and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_project.relationManager.return_value = mock_relation_manager
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
        
        # Should not detect any gaps
        self.assertEqual(warnings, [])
    
    def test_detect_skipped_numbers_non_numeric_values(self):
        """Test detection with non-numeric number values."""
        # Mock settings
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'objects_layer_id': mock_objects_layer,
            'recording_areas_layer_id': mock_recording_areas_layer
        }.get(layer_id)
        
        # Mock fields
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda field_name: {
            'number_field': 0,
            'recording_area_field': 1
        }.get(field_name, -1)
        mock_objects_layer.fields.return_value = mock_fields
        
        # Mock features with non-numeric values
        mock_features = []
        for i, number in enumerate(['A1', 'B2', 'C3']):
            mock_feature = Mock()
            # Create a proper mock that returns different values for different indices
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field (non-numeric)
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features.append(mock_feature)
        
        mock_objects_layer.getFeatures.return_value = mock_features
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QgsProject and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_project.relationManager.return_value = mock_relation_manager
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
        
        # Should not detect any gaps since non-numeric values are skipped
        self.assertEqual(warnings, [])
    
    def test_find_gaps_in_sequence(self):
        """Test the _find_gaps_in_sequence method."""
        # Test with gaps
        numbers = [1, 3, 5, 8]
        gaps = self.service._find_gaps_in_sequence(numbers)
        self.assertEqual(gaps, [2, 4, 6, 7])
        
        # Test with no gaps
        numbers = [1, 2, 3, 4]
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
    
    def test_get_recording_area_name_with_name_field(self):
        """Test getting recording area name with name field."""
        # Mock recording areas layer
        mock_recording_areas_layer = Mock()
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = 0
        
        # Mock feature
        mock_feature = Mock()
        mock_feature.id.return_value = 1
        mock_feature.attribute.return_value = "Test Area"
        mock_recording_areas_layer.getFeatures.return_value = [mock_feature]
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)
        
        self.assertEqual(name, "Test Area")
    
    def test_get_recording_area_name_fallback_to_id(self):
        """Test getting recording area name with fallback to ID."""
        # Mock recording areas layer with no name field
        mock_recording_areas_layer = Mock()
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1
        mock_recording_areas_layer.getFeatures.return_value = []
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)
        
        self.assertEqual(name, "1")
    
    def test_create_skipped_numbers_warning_with_translation(self):
        """Test creating skipped numbers warning with translation."""
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        warning = self.service._create_skipped_numbers_warning(
            recording_area_name="Test Area",
            gaps=[2, 4],
            layer_name="Test Layer"
        )
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: 2, 4 in Test Layer")
        self.mock_translation_service.tr.assert_called_once()
    
    def test_create_skipped_numbers_warning_single_gap(self):
        """Test creating warning with single gap."""
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        warning = self.service._create_skipped_numbers_warning(
            recording_area_name="Test Area",
            gaps=[2],
            layer_name="Test Layer"
        )
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: 2 in Test Layer")
    
    def test_create_skipped_numbers_warning_fallback_to_english(self):
        """Test creating warning with fallback to English when translation fails."""
        self.mock_translation_service.tr.side_effect = Exception("Translation error")
        
        warning = self.service._create_skipped_numbers_warning(
            recording_area_name="Test Area",
            gaps=[2, 4],
            layer_name="Test Layer"
        )
        
        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: 2, 4 in Test Layer")
    
    def test_find_layer_by_name(self):
        """Test finding layer by name."""
        # Mock QgsProject
        mock_project = Mock()
        mock_layer = Mock()
        mock_project.mapLayersByName.return_value = [mock_layer]
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.service._find_layer_by_name("Test Layer")
        
        self.assertEqual(result, mock_layer)
        mock_project.mapLayersByName.assert_called_once_with("Test Layer")
    
    def test_find_layer_by_name_not_found(self):
        """Test finding layer by name when not found."""
        # Mock QgsProject
        mock_project = Mock()
        mock_project.mapLayersByName.return_value = []
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            result = self.service._find_layer_by_name("Test Layer")
        
        self.assertIsNone(result)
    
    def test_detect_skipped_numbers_with_new_objects_layer(self):
        """Test detection including New Objects layer."""
        # Mock settings
        def mock_get_value(key):
            if key == 'objects_layer':
                return 'objects_layer_id'
            elif key == 'recording_areas_layer':
                return 'recording_areas_layer_id'
            elif key == 'objects_number_field':
                return 'number_field'
            return None
        
        self.mock_settings_manager.get_value.side_effect = mock_get_value
        
        # Mock layers
        mock_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        mock_new_objects_layer = Mock()
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'objects_layer_id': mock_objects_layer,
            'recording_areas_layer_id': mock_recording_areas_layer
        }.get(layer_id)
        
        # Mock fields
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda field_name: {
            'number_field': 0,
            'recording_area_field': 1
        }.get(field_name, -1)
        mock_objects_layer.fields.return_value = mock_fields
        mock_new_objects_layer.fields.return_value = mock_fields
        
        # Mock features with gaps in both layers
        mock_features_original = []
        for i, number in enumerate([1, 3]):  # Gap: 2
            mock_feature = Mock()
            # Create a proper mock that returns different values for different indices
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features_original.append(mock_feature)
        
        mock_features_new = []
        for i, number in enumerate([5, 7]):  # Gap: 6
            mock_feature = Mock()
            # Create a proper mock that returns different values for different indices
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features_new.append(mock_feature)
        
        mock_objects_layer.getFeatures.return_value = mock_features_original
        mock_new_objects_layer.getFeatures.return_value = mock_features_new
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QgsProject and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_project.relationManager.return_value = mock_relation_manager
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        mock_project.mapLayersByName.return_value = [mock_new_objects_layer]
        
        # Mock recording area name
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = 0
        mock_recording_areas_layer.getFeatures.return_value = [Mock()]
        
        # Mock translation
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()
        
        # Should detect gaps between layers (which includes gaps within New Objects layer)
        self.assertEqual(len(warnings), 1)
        # Check for gaps between layers (2, 4, 6)
        self.assertIn("2, 4, 6", warnings[0])
        self.assertIn("Objects and New Objects", warnings[0])
    
    def test_detect_skipped_numbers_between_layers(self):
        """Test detection of skipped numbers between original and new objects layers."""
        # Mock layers
        mock_objects_layer = Mock()
        mock_new_objects_layer = Mock()
        mock_recording_areas_layer = Mock()
        
        # Mock fields
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda field_name: {
            'number_field': 0,
            'recording_area_field': 1
        }.get(field_name, -1)
        mock_objects_layer.fields.return_value = mock_fields
        mock_new_objects_layer.fields.return_value = mock_fields
        
        # Mock features: original has 1, 3 and new has 5, 7 (gaps: 2, 4, 6)
        mock_features_original = []
        for number in [1, 3]:
            mock_feature = Mock()
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features_original.append(mock_feature)
        
        mock_features_new = []
        for number in [5, 7]:
            mock_feature = Mock()
            def make_attribute_side_effect(feature_number):
                def side_effect(idx):
                    if idx == 0:  # number field
                        return feature_number
                    elif idx == 1:  # recording area field
                        return 1
                    return None
                return side_effect
            
            mock_feature.attribute.side_effect = make_attribute_side_effect(number)
            mock_features_new.append(mock_feature)
        
        mock_objects_layer.getFeatures.return_value = mock_features_original
        mock_new_objects_layer.getFeatures.return_value = mock_features_new
        
        # Mock recording area name
        mock_recording_areas_layer.fields.return_value.indexOf.return_value = 0
        mock_recording_areas_layer.getFeatures.return_value = [Mock()]
        
        # Mock translation
        self.mock_translation_service.tr.return_value = "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        
        warnings = self.service._detect_skipped_numbers_between_layers(
            mock_objects_layer, mock_new_objects_layer, mock_recording_areas_layer,
            'number_field', 'recording_area_field'
        )
        
        # Should detect gaps 2, 4, 6 between the layers
        self.assertEqual(len(warnings), 1)
        self.assertIn("2, 4, 6", warnings[0])
        self.assertIn("Objects and New Objects", warnings[0]) 