"""
Tests for the HeightDifferenceDetectorService.

This module tests the height difference detection functionality between close
total station points.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields, QgsProject
from PyQt5.QtCore import QVariant

try:
    from services.height_difference_detector_service import HeightDifferenceDetectorService
    from core.data_structures import WarningData
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.height_difference_detector_service import HeightDifferenceDetectorService
    from core.data_structures import WarningData


class TestHeightDifferenceDetectorService(unittest.TestCase):
    """Test cases for HeightDifferenceDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.translation_service = Mock()
        
        # Mock translation service
        self.translation_service.translate.return_value = "Test warning message"
        
        # Mock settings values
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'height_max_distance': 1.0,
            'height_max_difference': 0.2,
            'total_station_points_layer': 'test_layer_id'
        }.get(key, default)
        
        # Create the service
        self.service = HeightDifferenceDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            translation_service=self.translation_service
        )
    
    def test_init(self):
        """Test service initialization."""
        self.assertEqual(self.service._max_distance_meters, 1.0)
        self.assertEqual(self.service._max_height_difference_meters, 0.2)
        self.assertEqual(self.service._settings_manager, self.settings_manager)
        self.assertEqual(self.service._layer_service, self.layer_service)
        self.assertEqual(self.service._translation_service, self.translation_service)
    
    def test_detect_height_difference_warnings_no_layer_configured(self):
        """Test detection when no layer is configured."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_height_warnings': True,
            'height_max_distance': 1.0,
            'height_max_difference': 0.2,
            'total_station_points_layer': None
        }.get(key, default)
        
        warnings = self.service.detect_height_difference_warnings()
        
        self.assertEqual(warnings, [])
        self.settings_manager.get_value.assert_any_call('total_station_points_layer')
    
    def test_detect_height_difference_warnings_layer_not_found(self):
        """Test detection when layer is not found."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = None
        self.layer_service.get_layer_by_name.return_value = None
        
        warnings = self.service.detect_height_difference_warnings()
        
        self.assertEqual(warnings, [])
        self.layer_service.get_layer_by_id.assert_called()
    
    def test_detect_height_difference_warnings_no_z_field(self):
        """Test detection when Z field is not found."""
        # Mock layer
        layer = Mock()
        layer.name.return_value = "Total Station Points"
        layer.fields.return_value.indexOf.return_value = -1
        
        # Mock fields list behavior
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        layer.fields.return_value.__iter__ = lambda self: iter([field1, field2])
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = layer
        self.layer_service.get_layer_by_name.return_value = None
        
        warnings = self.service.detect_height_difference_warnings()
        
        self.assertEqual(warnings, [])
    
    def test_detect_height_difference_warnings_with_z_field(self):
        """Test detection when Z field exists."""
        # Mock layer
        layer = Mock()
        layer.name.return_value = "Total Station Points"
        
        # Mock fields
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        field3 = Mock()
        field3.name.return_value = "Z"
        
        # Mock fields collection
        fields_collection = Mock()
        fields_collection.indexOf.return_value = 2  # Z field at index 2
        fields_collection.__getitem__ = lambda idx: [field1, field2, field3][idx]
        fields_collection.__iter__ = lambda self: iter([field1, field2, field3])
        
        layer.fields.return_value = fields_collection
        
        # Mock features with height difference issues
        feature1 = Mock()
        feature1.id.return_value = 1
        
        # Create proper geometry mock for feature1
        geom1 = Mock()
        geom1.asPoint.return_value = QgsPointXY(0, 0)
        geom1.isEmpty.return_value = False
        feature1.geometry.return_value = geom1
        feature1.attribute.return_value = 100.0  # Z value
        
        feature2 = Mock()
        feature2.id.return_value = 2
        
        # Create proper geometry mock for feature2
        geom2 = Mock()
        geom2.asPoint.return_value = QgsPointXY(0.5, 0)  # Close horizontally but different height
        geom2.isEmpty.return_value = False
        feature2.geometry.return_value = geom2
        feature2.attribute.return_value = 120.5  # Z value with 20.5cm difference
        
        layer.getFeatures.return_value = [feature1, feature2]
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = layer
        self.layer_service.get_layer_by_name.return_value = None
        
        # Mock QgsDistanceArea
        with patch('qgis.core.QgsDistanceArea') as mock_distance_area:
            mock_calculator = Mock()
            mock_calculator.measureLine.return_value = 0.5  # 0.5 meters distance
            mock_calculator.convertLengthMeasurement.return_value = 0.5  # Return same value
            mock_distance_area.return_value = mock_calculator
            
            warnings = self.service.detect_height_difference_warnings()
            
            # Debug output
            print(f"[TEST DEBUG] Number of warnings: {len(warnings)}")
            if warnings:
                print(f"[TEST DEBUG] First warning: {warnings[0]}")
            
            # Should have warnings due to height difference > 20cm
            self.assertGreater(len(warnings), 0)
            self.assertIsInstance(warnings[0], WarningData)
    
    def test_detect_height_difference_warnings_no_height_difference(self):
        """Test detection when features have no significant height difference."""
        # Mock layer
        layer = Mock()
        layer.name.return_value = "Total Station Points"
        
        # Mock fields
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        field3 = Mock()
        field3.name.return_value = "Z"
        
        # Mock fields collection
        fields_collection = Mock()
        fields_collection.indexOf.return_value = 2  # Z field at index 2
        fields_collection.__getitem__ = lambda idx: [field1, field2, field3][idx]
        fields_collection.__iter__ = lambda self: iter([field1, field2, field3])
        
        layer.fields.return_value = fields_collection
        
        # Mock features with similar heights
        feature1 = Mock()
        feature1.id.return_value = 1
        
        # Create proper geometry mock for feature1
        geom1 = Mock()
        geom1.asPoint.return_value = QgsPointXY(0, 0)
        geom1.isEmpty.return_value = False
        feature1.geometry.return_value = geom1
        feature1.attribute.return_value = 100.0  # Z value
        
        feature2 = Mock()
        feature2.id.return_value = 2
        
        # Create proper geometry mock for feature2
        geom2 = Mock()
        geom2.asPoint.return_value = QgsPointXY(0.5, 0)  # Close horizontally
        geom2.isEmpty.return_value = False
        feature2.geometry.return_value = geom2
        feature2.attribute.return_value = 100.1  # Z value with only 10cm difference
        
        layer.getFeatures.return_value = [feature1, feature2]
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = layer
        self.layer_service.get_layer_by_name.return_value = None
        
        # Mock QgsDistanceArea
        with patch('qgis.core.QgsDistanceArea') as mock_distance_area:
            mock_calculator = Mock()
            mock_calculator.measureLine.return_value = 0.5  # 0.5 meters distance
            mock_calculator.convertLengthMeasurement.return_value = 0.5  # Return same value
            mock_distance_area.return_value = mock_calculator
            
            warnings = self.service.detect_height_difference_warnings()
            
            # Should have no warnings due to small height difference
            self.assertEqual(len(warnings), 0)
    
    def test_detect_height_difference_warnings_features_too_far(self):
        """Test detection when features are too far apart."""
        # Mock layer
        layer = Mock()
        layer.name.return_value = "Total Station Points"
        
        # Mock fields
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        field3 = Mock()
        field3.name.return_value = "Z"
        
        # Mock fields collection
        fields_collection = Mock()
        fields_collection.indexOf.return_value = 2  # Z field at index 2
        fields_collection.__getitem__ = lambda idx: [field1, field2, field3][idx]
        fields_collection.__iter__ = lambda self: iter([field1, field2, field3])
        
        layer.fields.return_value = fields_collection
        
        # Mock features that are far apart
        feature1 = Mock()
        feature1.id.return_value = 1
        
        # Create proper geometry mock for feature1
        geom1 = Mock()
        geom1.asPoint.return_value = QgsPointXY(0, 0)
        feature1.geometry.return_value = geom1
        feature1.attribute.return_value = 100.0  # Z value
        
        feature2 = Mock()
        feature2.id.return_value = 2
        
        # Create proper geometry mock for feature2
        geom2 = Mock()
        geom2.asPoint.return_value = QgsPointXY(10, 10)  # Far away
        feature2.geometry.return_value = geom2
        feature2.attribute.return_value = 150.0  # Z value with large difference
        
        layer.getFeatures.return_value = [feature1, feature2]
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = layer
        self.layer_service.get_layer_by_name.return_value = None
        
        # Mock QgsDistanceArea
        with patch('qgis.core.QgsDistanceArea') as mock_distance_area:
            mock_calculator = Mock()
            mock_calculator.measureLine.return_value = 15.0  # 15 meters distance (far)
            mock_calculator.convertLengthMeasurement.return_value = 15.0  # Return same value
            mock_distance_area.return_value = mock_calculator
            
            warnings = self.service.detect_height_difference_warnings()
            
            # Should have no warnings due to distance > 1m
            self.assertEqual(len(warnings), 0)
    
    def test_find_z_field_index_exact_match(self):
        """Test finding Z field with exact match."""
        # Mock layer
        layer = Mock()
        layer.fields.return_value.indexOf.return_value = 2
        
        result = self.service._find_z_field_index(layer)
        
        self.assertEqual(result, 2)
        layer.fields.return_value.indexOf.assert_called_with("Z")
    
    def test_find_z_field_index_case_insensitive(self):
        """Test finding Z field with case-insensitive match."""
        # Mock layer
        layer = Mock()
        layer.fields.return_value.indexOf.return_value = -1
        
        # Mock fields
        field1 = Mock()
        field1.name.return_value = "x"
        field2 = Mock()
        field2.name.return_value = "y"
        field3 = Mock()
        field3.name.return_value = "z"  # Lowercase z
        
        layer.fields.return_value.__iter__ = lambda self: iter([field1, field2, field3])
        
        result = self.service._find_z_field_index(layer)
        
        self.assertEqual(result, 2)
    
    def test_find_z_field_index_variations(self):
        """Test finding Z field with common variations."""
        # Mock layer
        layer = Mock()
        layer.fields.return_value.indexOf.return_value = -1
        
        # Mock fields
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        field3 = Mock()
        field3.name.return_value = "height"  # Variation
        
        layer.fields.return_value.__iter__ = lambda self: iter([field1, field2, field3])
        
        result = self.service._find_z_field_index(layer)
        
        self.assertEqual(result, 2)
    
    def test_find_z_field_index_not_found(self):
        """Test finding Z field when not found."""
        # Mock layer
        layer = Mock()
        layer.fields.return_value.indexOf.return_value = -1
        
        # Mock fields without Z
        field1 = Mock()
        field1.name.return_value = "X"
        field2 = Mock()
        field2.name.return_value = "Y"
        
        layer.fields.return_value.__iter__ = lambda self: iter([field1, field2])
        
        result = self.service._find_z_field_index(layer)
        
        self.assertEqual(result, -1)
    
    def test_get_distance_range(self):
        """Test distance range categorization."""
        self.assertEqual(self.service._get_distance_range(0.05), "0-10cm")
        self.assertEqual(self.service._get_distance_range(0.3), "10-50cm")
        self.assertEqual(self.service._get_distance_range(0.8), "50cm-1m")
    
    def test_get_feature_identifier(self):
        """Test feature identifier generation."""
        # Mock feature with ID field
        feature = Mock()
        feature.id.return_value = 123
        feature.fields.return_value.indexOf.return_value = 0
        feature.attribute.return_value = "POINT_001"
        
        result = self.service._get_feature_identifier(feature, "Total Station Point")
        
        self.assertEqual(result, "Total Station Point POINT_001")
    
    def test_get_feature_identifier_fallback(self):
        """Test feature identifier fallback to feature ID."""
        # Mock feature without ID field
        feature = Mock()
        feature.id.return_value = 123
        feature.fields.return_value.indexOf.return_value = -1
        
        result = self.service._get_feature_identifier(feature, "Total Station Point")
        
        self.assertEqual(result, "Total Station Point 123")
    
    def test_create_height_difference_warning(self):
        """Test height difference warning message creation."""
        feature1_identifiers = ["Total Station Point 1"]
        feature2_identifiers = ["Total Station Point 2"]
        max_distance = 0.5
        max_height_difference = 0.25
        
        result = self.service._create_height_difference_warning(
            feature1_identifiers, feature2_identifiers, max_distance, max_height_difference
        )
        
        self.assertEqual(result, "Test warning message")
        self.translation_service.translate.assert_called_with(
            "HeightDifferenceDetectorService",
            "Total Station Point 1 and Total Station Point 2 are separated by 50.0 cm but have a height difference of 25.0 cm (maximum allowed: 20.0 cm)"
        )
    
    def test_create_height_difference_warning_multiple_pairs(self):
        """Test height difference warning message creation for multiple pairs."""
        feature1_identifiers = ["Total Station Point 1", "Total Station Point 3"]
        feature2_identifiers = ["Total Station Point 2", "Total Station Point 4"]
        max_distance = 0.5
        max_height_difference = 0.25
        
        result = self.service._create_height_difference_warning(
            feature1_identifiers, feature2_identifiers, max_distance, max_height_difference
        )
        
        self.assertEqual(result, "Test warning message")
        self.translation_service.translate.assert_called_with(
            "HeightDifferenceDetectorService",
            "2 point pairs are separated by 50.0 cm but have a height difference of 25.0 cm (maximum allowed: 20.0 cm)"
        )

    def test_filter_expression_fallbacks_to_fid(self):
        """Test that filter expression uses 'fid' if no identifier field exists in the layer."""
        # Mock layer with no identifier fields
        layer = Mock()
        layer.name.return_value = "NoIdLayer"
        # Only X, Y, Z fields
        field1 = Mock(); field1.name.return_value = "X"; field1.typeName.return_value = "double"
        field2 = Mock(); field2.name.return_value = "Y"; field2.typeName.return_value = "double"
        field3 = Mock(); field3.name.return_value = "Z"; field3.typeName.return_value = "double"
        fields_collection = Mock()
        fields_collection.indexOf.side_effect = lambda name: {"X": 0, "Y": 1, "Z": 2}.get(name, -1)
        fields_collection.__getitem__ = lambda idx: [field1, field2, field3][idx]
        fields_collection.__iter__ = lambda self: iter([field1, field2, field3])
        layer.fields.return_value = fields_collection
        # Two features with different Z values
        feature1 = Mock(); feature1.id.return_value = 1; feature1.fields.return_value = fields_collection
        geom1 = Mock(); geom1.asPoint.return_value = QgsPointXY(0, 0); geom1.isEmpty.return_value = False
        feature1.geometry.return_value = geom1; feature1.attribute.side_effect = lambda idx: 100.0 if idx == 2 else None
        feature2 = Mock(); feature2.id.return_value = 2; feature2.fields.return_value = fields_collection
        geom2 = Mock(); geom2.asPoint.return_value = QgsPointXY(0.5, 0); geom2.isEmpty.return_value = False
        feature2.geometry.return_value = geom2; feature2.attribute.side_effect = lambda idx: 120.5 if idx == 2 else None
        layer.getFeatures.return_value = [feature1, feature2]
        self.settings_manager.get_value.side_effect = lambda key, default=None: 'test_layer_id'
        self.layer_service.get_layer_by_id.return_value = layer
        self.layer_service.get_layer_by_name.return_value = None
        with patch('qgis.core.QgsDistanceArea') as mock_distance_area:
            mock_calculator = Mock(); mock_calculator.measureLine.return_value = 0.5
            mock_distance_area.return_value = mock_calculator
            warnings = self.service.detect_height_difference_warnings()
            self.assertGreater(len(warnings), 0)
            # The filter_expression should use 'fid' and both feature IDs
            filter_expr = warnings[0].filter_expression
            self.assertTrue(filter_expr.startswith('"fid"'))
            self.assertIn('1', filter_expr)
            self.assertIn('2', filter_expr)


if __name__ == '__main__':
    unittest.main() 