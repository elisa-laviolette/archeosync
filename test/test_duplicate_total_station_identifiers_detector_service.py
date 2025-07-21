"""
Tests for the Duplicate Total Station Identifiers Detector Service.

This module tests the functionality of detecting duplicate identifiers in total station points.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY
from PyQt5.QtCore import QVariant

try:
    from services.duplicate_total_station_identifiers_detector_service import DuplicateTotalStationIdentifiersDetectorService
    from core.data_structures import WarningData
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.duplicate_total_station_identifiers_detector_service import DuplicateTotalStationIdentifiersDetectorService
    from core.data_structures import WarningData


class TestDuplicateTotalStationIdentifiersDetectorService(unittest.TestCase):
    """Test cases for DuplicateTotalStationIdentifiersDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.translation_service = Mock()
        
        # Set up translation service to return the input string (no translation)
        self.translation_service.translate = Mock(side_effect=lambda x: x)
        
        self.detector = DuplicateTotalStationIdentifiersDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            translation_service=self.translation_service
        )
    
    def test_find_common_identifier_field_with_id_in_name(self):
        """Test finding common identifier field when field name contains 'id'."""
        # Create mock layers with fields
        definitive_layer = Mock()
        temp_layer = Mock()
        
        # Create mock fields for definitive layer
        definitive_field1 = Mock()
        definitive_field1.name.return_value = "point_id"
        definitive_field1.typeName.return_value = "String"
        
        definitive_field2 = Mock()
        definitive_field2.name.return_value = "x_coord"
        definitive_field2.typeName.return_value = "Real"
        
        definitive_layer.fields.return_value = [definitive_field1, definitive_field2]
        
        # Create mock fields for temp layer
        temp_field1 = Mock()
        temp_field1.name.return_value = "point_id"  # Same field name
        temp_field1.typeName.return_value = "String"
        
        temp_field2 = Mock()
        temp_field2.name.return_value = "y_coord"
        temp_field2.typeName.return_value = "Real"
        
        temp_layer.fields.return_value = [temp_field1, temp_field2]
        
        # Test the method
        result = self.detector._find_common_identifier_field(definitive_layer, temp_layer)
        
        # Assert the correct field was found
        self.assertEqual(result, "point_id")
    
    def test_find_common_identifier_field_case_insensitive(self):
        """Test finding common identifier field with case-insensitive matching."""
        # Create mock layers with fields
        definitive_layer = Mock()
        temp_layer = Mock()
        
        # Create mock fields for definitive layer
        definitive_field1 = Mock()
        definitive_field1.name.return_value = "Point_ID"
        definitive_field1.typeName.return_value = "String"
        
        definitive_field2 = Mock()
        definitive_field2.name.return_value = "x_coord"
        definitive_field2.typeName.return_value = "Real"
        
        definitive_layer.fields.return_value = [definitive_field1, definitive_field2]
        
        # Create mock fields for temp layer
        temp_field1 = Mock()
        temp_field1.name.return_value = "point_id"  # Different case
        temp_field1.typeName.return_value = "String"
        
        temp_field2 = Mock()
        temp_field2.name.return_value = "y_coord"
        temp_field2.typeName.return_value = "Real"
        
        temp_layer.fields.return_value = [temp_field1, temp_field2]
        
        # Test the method
        result = self.detector._find_common_identifier_field(definitive_layer, temp_layer)
        
        # Assert the correct field was found (should preserve definitive layer case)
        self.assertEqual(result, "Point_ID")
    
    def test_find_common_identifier_field_with_common_patterns(self):
        """Test finding common identifier field using common patterns when no 'id' field exists."""
        # Create mock layers with fields
        definitive_layer = Mock()
        temp_layer = Mock()
        
        # Create mock fields for definitive layer
        definitive_field1 = Mock()
        definitive_field1.name.return_value = "x_coord"
        definitive_field1.typeName.return_value = "Real"
        
        definitive_field2 = Mock()
        definitive_field2.name.return_value = "identifier"
        definitive_field2.typeName.return_value = "String"
        
        definitive_layer.fields.return_value = [definitive_field1, definitive_field2]
        
        # Create mock fields for temp layer
        temp_field1 = Mock()
        temp_field1.name.return_value = "y_coord"
        temp_field1.typeName.return_value = "Real"
        
        temp_field2 = Mock()
        temp_field2.name.return_value = "identifier"  # Same field name
        temp_field2.typeName.return_value = "String"
        
        temp_layer.fields.return_value = [temp_field1, temp_field2]
        
        # Test the method
        result = self.detector._find_common_identifier_field(definitive_layer, temp_layer)
        
        # Assert the correct field was found
        self.assertEqual(result, "identifier")
    
    def test_find_common_identifier_field_no_common_fields(self):
        """Test finding common identifier field when no common string fields exist."""
        # Create mock layers with different fields
        definitive_layer = Mock()
        temp_layer = Mock()
        
        # Create mock fields for definitive layer
        definitive_field1 = Mock()
        definitive_field1.name.return_value = "point_id"
        definitive_field1.typeName.return_value = "String"
        
        definitive_layer.fields.return_value = [definitive_field1]
        
        # Create mock fields for temp layer
        temp_field1 = Mock()
        temp_field1.name.return_value = "different_field"
        temp_field1.typeName.return_value = "String"
        
        temp_layer.fields.return_value = [temp_field1]
        
        # Test the method
        result = self.detector._find_common_identifier_field(definitive_layer, temp_layer)
        
        # Assert no field was found
        self.assertIsNone(result)
    
    def test_find_common_identifier_field_no_temp_layer(self):
        """Test finding common identifier field when no temporary layer exists."""
        # Create mock definitive layer
        definitive_layer = Mock()
        
        # Create mock fields for definitive layer
        definitive_field1 = Mock()
        definitive_field1.name.return_value = "point_id"
        definitive_field1.typeName.return_value = "String"
        
        definitive_layer.fields.return_value = [definitive_field1]
        
        # Test the method with no temp layer
        result = self.detector._find_common_identifier_field(definitive_layer, None)
        
        # Should fall back to guessing from definitive layer only
        self.assertEqual(result, "point_id")
    
    def test_guess_identifier_field_with_id_in_name(self):
        """Test guessing identifier field when field name contains 'id'."""
        # Create a mock layer with fields
        layer = Mock()
        field1 = Mock()
        field1.name.return_value = "point_id"
        field1.typeName.return_value = "String"
        
        field2 = Mock()
        field2.name.return_value = "x_coord"
        field2.typeName.return_value = "Real"
        
        field3 = Mock()
        field3.name.return_value = "y_coord"
        field3.typeName.return_value = "Real"
        
        layer.fields.return_value = [field1, field2, field3]
        
        # Test the method
        result = self.detector._guess_identifier_field(layer)
        
        # Assert the correct field was found
        self.assertEqual(result, "point_id")
    
    def test_guess_identifier_field_with_common_patterns(self):
        """Test guessing identifier field using common patterns when no 'id' field exists."""
        # Create a mock layer with fields
        layer = Mock()
        field1 = Mock()
        field1.name.return_value = "x_coord"
        field1.typeName.return_value = "Real"
        
        field2 = Mock()
        field2.name.return_value = "identifier"
        field2.typeName.return_value = "String"
        
        field3 = Mock()
        field3.name.return_value = "y_coord"
        field3.typeName.return_value = "Real"
        
        layer.fields.return_value = [field1, field2, field3]
        
        # Test the method
        result = self.detector._guess_identifier_field(layer)
        
        # Assert the correct field was found
        self.assertEqual(result, "identifier")
    
    def test_guess_identifier_field_no_candidates(self):
        """Test guessing identifier field when no suitable field exists."""
        # Create a mock layer with no suitable fields
        layer = Mock()
        field1 = Mock()
        field1.name.return_value = "x_coord"
        field1.typeName.return_value = "Real"
        
        field2 = Mock()
        field2.name.return_value = "y_coord"
        field2.typeName.return_value = "Real"
        
        layer.fields.return_value = [field1, field2]
        
        # Test the method
        result = self.detector._guess_identifier_field(layer)
        
        # Assert no field was found
        self.assertIsNone(result)
    
    def test_detect_duplicates_within_layer(self):
        """Test detecting duplicates within a single layer."""
        # Create a mock layer
        layer = Mock()
        layer.name.return_value = "Test Layer"
        
        # Create mock fields
        field = Mock()
        field.name.return_value = "point_id"
        field.typeName.return_value = "String"
        
        # Create a proper mock for fields() that returns a list and has indexOf method
        fields_mock = Mock()
        fields_mock.indexOf.return_value = 0
        fields_mock.__iter__ = Mock(return_value=iter([field]))
        
        layer.fields.return_value = fields_mock
        
        # Create mock features with proper __getitem__ setup
        feature1 = Mock()
        feature1.__getitem__ = Mock(return_value="TS001")
        
        feature2 = Mock()
        feature2.__getitem__ = Mock(return_value="TS001")  # Duplicate
        
        feature3 = Mock()
        feature3.__getitem__ = Mock(return_value="TS002")
        
        layer.getFeatures.return_value = [feature1, feature2, feature3]
        
        # Test the method
        warnings = self.detector._detect_duplicates_within_layer(layer, "point_id", "Test Layer")
        
        # Assert warnings were created
        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn("TS001", warnings[0].message)
        self.assertIn("2", warnings[0].message)  # 2 features with same identifier
    
    def test_detect_duplicates_between_layers(self):
        """Test detecting duplicates between two layers."""
        # Create mock layers
        definitive_layer = Mock()
        definitive_layer.name.return_value = "Definitive Layer"
        
        temp_layer = Mock()
        temp_layer.name.return_value = "Imported_CSV_Points"
        
        # Create mock fields
        field = Mock()
        field.name.return_value = "point_id"
        field.typeName.return_value = "String"
        
        # Create a proper mock for fields() that returns a list and has indexOf method
        fields_mock = Mock()
        fields_mock.indexOf.return_value = 0
        fields_mock.__iter__ = Mock(return_value=iter([field]))
        
        definitive_layer.fields.return_value = fields_mock
        temp_layer.fields.return_value = fields_mock
        
        # Create mock features with proper __getitem__ setup
        definitive_feature = Mock()
        definitive_feature.__getitem__ = Mock(return_value="TS001")
        
        temp_feature = Mock()
        temp_feature.__getitem__ = Mock(return_value="TS001")  # Same identifier
        
        definitive_layer.getFeatures.return_value = [definitive_feature]
        temp_layer.getFeatures.return_value = [temp_feature]
        
        # Test the method
        warnings = self.detector._detect_duplicates_between_layers(
            definitive_layer, temp_layer, "point_id", "point_id"
        )
        
        # Assert warnings were created
        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn("TS001", warnings[0].message)
        self.assertIn("both imported and definitive", warnings[0].message)
    
    def test_detect_duplicates_between_layers_optimization(self):
        """Test that the between layers detection is optimized to only check matching identifiers."""
        # Create mock layers
        definitive_layer = Mock()
        definitive_layer.name.return_value = "Definitive Layer"
        
        temp_layer = Mock()
        temp_layer.name.return_value = "Imported_CSV_Points"
        
        # Create mock fields
        field = Mock()
        field.name.return_value = "point_id"
        field.typeName.return_value = "String"
        
        # Create a proper mock for fields() that returns a list and has indexOf method
        fields_mock = Mock()
        fields_mock.indexOf.return_value = 0
        fields_mock.__iter__ = Mock(return_value=iter([field]))
        
        definitive_layer.fields.return_value = fields_mock
        temp_layer.fields.return_value = fields_mock
        
        # Create mock features for definitive layer (many features, only one matching)
        definitive_features = []
        for i in range(100):  # 100 features in definitive layer
            feature = Mock()
            if i == 50:  # Only one feature with matching identifier
                feature.__getitem__ = Mock(return_value="TS001")
            else:
                feature.__getitem__ = Mock(return_value=f"DEF{i}")  # Different identifiers
            definitive_features.append(feature)
        
        # Create mock features for temp layer (only one feature)
        temp_feature = Mock()
        temp_feature.__getitem__ = Mock(return_value="TS001")  # Same identifier as one definitive feature
        
        definitive_layer.getFeatures.return_value = definitive_features
        temp_layer.getFeatures.return_value = [temp_feature]
        
        # Test the method
        warnings = self.detector._detect_duplicates_between_layers(
            definitive_layer, temp_layer, "point_id", "point_id"
        )
        
        # Assert warnings were created for the matching identifier
        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn("TS001", warnings[0].message)
        self.assertIn("both imported and definitive", warnings[0].message)
        
        # Verify that the method only processed the matching identifier
        # The optimization should have only added "TS001" to definitive_identifiers
        # and not processed all 100 features in the definitive layer
    
    def test_detect_duplicates_between_layers_no_matches(self):
        """Test that no warnings are created when there are no matching identifiers."""
        # Create mock layers
        definitive_layer = Mock()
        definitive_layer.name.return_value = "Definitive Layer"
        
        temp_layer = Mock()
        temp_layer.name.return_value = "Imported_CSV_Points"
        
        # Create mock fields
        field = Mock()
        field.name.return_value = "point_id"
        field.typeName.return_value = "String"
        
        # Create a proper mock for fields() that returns a list and has indexOf method
        fields_mock = Mock()
        fields_mock.indexOf.return_value = 0
        fields_mock.__iter__ = Mock(return_value=iter([field]))
        
        definitive_layer.fields.return_value = fields_mock
        temp_layer.fields.return_value = fields_mock
        
        # Create mock features with different identifiers
        definitive_feature = Mock()
        definitive_feature.__getitem__ = Mock(return_value="DEF001")
        
        temp_feature = Mock()
        temp_feature.__getitem__ = Mock(return_value="TEMP001")  # Different identifier
        
        definitive_layer.getFeatures.return_value = [definitive_feature]
        temp_layer.getFeatures.return_value = [temp_feature]
        
        # Test the method
        warnings = self.detector._detect_duplicates_between_layers(
            definitive_layer, temp_layer, "point_id", "point_id"
        )
        
        # Assert no warnings were created
        self.assertEqual(len(warnings), 0)
    
    def test_detect_duplicates_between_layers_empty_temp_layer(self):
        """Test that no warnings are created when temporary layer has no identifiers."""
        # Create mock layers
        definitive_layer = Mock()
        definitive_layer.name.return_value = "Definitive Layer"
        
        temp_layer = Mock()
        temp_layer.name.return_value = "Imported_CSV_Points"
        
        # Create mock fields
        field = Mock()
        field.name.return_value = "point_id"
        field.typeName.return_value = "String"
        
        # Create a proper mock for fields() that returns a list and has indexOf method
        fields_mock = Mock()
        fields_mock.indexOf.return_value = 0
        fields_mock.__iter__ = Mock(return_value=iter([field]))
        
        definitive_layer.fields.return_value = fields_mock
        temp_layer.fields.return_value = fields_mock
        
        # Create mock features - temp layer has no valid identifiers
        definitive_feature = Mock()
        definitive_feature.__getitem__ = Mock(return_value="DEF001")
        
        temp_feature = Mock()
        temp_feature.__getitem__ = Mock(return_value=None)  # No identifier
        
        definitive_layer.getFeatures.return_value = [definitive_feature]
        temp_layer.getFeatures.return_value = [temp_feature]
        
        # Test the method
        warnings = self.detector._detect_duplicates_between_layers(
            definitive_layer, temp_layer, "point_id", "point_id"
        )
        
        # Assert no warnings were created
        self.assertEqual(len(warnings), 0)
    
    def test_detect_duplicate_identifiers_warnings_no_configuration(self):
        """Test detection when no total station points layer is configured."""
        # Configure settings to return None
        self.settings_manager.get_value.return_value = None
        
        # Test the method
        warnings = self.detector.detect_duplicate_identifiers_warnings()
        
        # Assert no warnings were returned
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_identifiers_warnings_no_layer_found(self):
        """Test detection when the configured layer is not found."""
        # Configure settings to return a layer ID
        self.settings_manager.get_value.return_value = "test_layer_id"
        
        # Configure layer service to return None
        self.layer_service.get_layer_by_id.return_value = None
        
        # Test the method
        warnings = self.detector.detect_duplicate_identifiers_warnings()
        
        # Assert no warnings were returned
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_identifiers_warnings_no_common_field(self):
        """Test detection when no common identifier field is found."""
        # Configure settings to return a layer ID
        self.settings_manager.get_value.return_value = "test_layer_id"
        
        # Create mock definitive layer
        definitive_layer = Mock()
        definitive_layer.name.return_value = "Definitive Layer"
        
        # Create mock fields for definitive layer (no string fields)
        definitive_field = Mock()
        definitive_field.name.return_value = "x_coord"
        definitive_field.typeName.return_value = "Real"
        definitive_layer.fields.return_value = [definitive_field]
        
        # Configure layer service to return the definitive layer
        self.layer_service.get_layer_by_id.return_value = definitive_layer
        
        # Mock the _find_layer_by_name method to return a temp layer
        temp_layer = Mock()
        temp_layer.name.return_value = "Imported_CSV_Points"
        
        # Create mock fields for temp layer (different string field)
        temp_field = Mock()
        temp_field.name.return_value = "different_field"
        temp_field.typeName.return_value = "String"
        temp_layer.fields.return_value = [temp_field]
        
        with patch.object(self.detector, '_find_layer_by_name', return_value=temp_layer):
            # Test the method
            warnings = self.detector.detect_duplicate_identifiers_warnings()
            
            # Assert no warnings were returned
            self.assertEqual(warnings, [])
    
    def test_create_duplicate_warning(self):
        """Test creating a duplicate warning message."""
        # Test with translation service
        self.translation_service.translate.return_value = "Translated message"
        
        result = self.detector._create_duplicate_warning(3, "TS001", "Test Layer")
        
        # Assert translation was called
        self.translation_service.translate.assert_called_once()
        self.assertEqual(result, "Translated message")
    
    def test_create_between_layers_duplicate_warning(self):
        """Test creating a between-layers duplicate warning message."""
        # Test with translation service
        self.translation_service.translate.return_value = "Translated between layers message"
        
        result = self.detector._create_between_layers_duplicate_warning("TS001")
        
        # Assert translation was called
        self.translation_service.translate.assert_called_once()
        self.assertEqual(result, "Translated between layers message")
    
    def test_create_warning_without_translation_service(self):
        """Test creating warnings when no translation service is available."""
        # Create detector without translation service
        detector = DuplicateTotalStationIdentifiersDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            translation_service=None
        )
        
        # Test creating warning
        result = detector._create_duplicate_warning(2, "TS001", "Test Layer")
        
        # Assert English message was returned
        self.assertIn("2", result)
        self.assertIn("TS001", result)
        self.assertIn("Test Layer", result)


if __name__ == '__main__':
    unittest.main() 