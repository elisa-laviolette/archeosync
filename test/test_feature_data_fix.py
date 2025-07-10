# coding=utf-8
"""Test for feature data extraction fix.

This test verifies that the feature data extraction and usage works correctly
with the new list-based attributes structure.
"""

import unittest
from unittest.mock import Mock, patch

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsFeature, QgsGeometry, QgsFields, QgsField
    from qgis.PyQt.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


@unittest.skipIf(not QGIS_AVAILABLE, "QGIS not available")
class TestFeatureDataFix(unittest.TestCase):
    """Test cases for feature data extraction fix."""
    
    def test_feature_data_extraction_structure(self):
        """Test that feature data is extracted with correct structure."""
        # Create a test feature with fields
        fields = QgsFields()
        fields.append(QgsField("name", QVariant.String))
        fields.append(QgsField("number", QVariant.Int))
        fields.append(QgsField("description", QVariant.String))
        
        feature = QgsFeature(fields)
        feature.setId(123)
        feature.setAttribute(0, "Test Area")
        feature.setAttribute(1, 42)
        feature.setAttribute(2, "Test description")
        
        # Create a simple geometry
        geometry = QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
        feature.setGeometry(geometry)
        
        # Simulate the extraction process from the main plugin
        geometry_wkt = None
        if hasattr(feature, 'geometry') and feature.geometry():
            geom = feature.geometry()
            if geom and not geom.isNull():
                geometry_wkt = geom.asWkt()
        
        # Extract attributes as a list to preserve order
        attributes = []
        if hasattr(feature, 'attributes'):
            attributes = list(feature.attributes())
        
        # Extract feature ID
        feature_id = feature.id() if hasattr(feature, 'id') else None
        
        feature_data = {
            'id': feature_id,
            'geometry_wkt': geometry_wkt,
            'attributes': attributes
        }
        
        # Verify the structure
        self.assertEqual(feature_data['id'], 123)
        self.assertEqual(feature_data['geometry_wkt'], "Polygon ((0 0, 1 0, 1 1, 0 1, 0 0))")
        self.assertIsInstance(feature_data['attributes'], list)
        self.assertEqual(len(feature_data['attributes']), 3)
        self.assertEqual(feature_data['attributes'][0], "Test Area")
        self.assertEqual(feature_data['attributes'][1], 42)
        self.assertEqual(feature_data['attributes'][2], "Test description")
    
    def test_feature_data_usage_with_qgsfeature(self):
        """Test that extracted feature data can be used to create a new QgsFeature."""
        # Create test feature data (simulating extracted data)
        feature_data = {
            'id': 456,
            'geometry_wkt': "Polygon ((0 0, 1 0, 1 1, 0 1, 0 0))",
            'attributes': ["Test Area 2", 99, "Another description"]
        }
        
        # Create a new QgsFeature from the extracted data
        temp_feature = QgsFeature()
        temp_feature.setId(feature_data['id'])
        
        # Set attributes directly since they're already a list
        temp_feature.setAttributes(feature_data['attributes'])
        
        if feature_data['geometry_wkt']:
            temp_geom = QgsGeometry.fromWkt(feature_data['geometry_wkt'])
            temp_feature.setGeometry(temp_geom)
        
        # Verify the feature was created correctly
        self.assertEqual(temp_feature.id(), 456)
        self.assertEqual(temp_feature.attributes(), ["Test Area 2", 99, "Another description"])
        self.assertIsNotNone(temp_feature.geometry())
        self.assertEqual(temp_feature.geometry().asWkt(), "Polygon ((0 0, 1 0, 1 1, 0 1, 0 0))")
    
    def test_attribute_access_by_index(self):
        """Test accessing attributes by index from the list structure."""
        # Create test feature data
        feature_data = {
            'id': 789,
            'geometry_wkt': "Polygon ((0 0, 1 0, 1 1, 0 1, 0 0))",
            'attributes': ["Zone A", 15, "Test zone"]
        }
        
        # Simulate accessing attributes by field index
        field_idx = 1  # number field
        if field_idx >= 0 and field_idx < len(feature_data['attributes']):
            value = feature_data['attributes'][field_idx]
            self.assertEqual(value, 15)
        
        # Test accessing name field
        field_idx = 0  # name field
        if field_idx >= 0 and field_idx < len(feature_data['attributes']):
            value = feature_data['attributes'][field_idx]
            self.assertEqual(value, "Zone A")


if __name__ == '__main__':
    unittest.main() 