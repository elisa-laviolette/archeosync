"""
Tests for the MissingTotalStationDetectorService.

This module tests the missing total station point detection functionality for objects
that don't have corresponding total station points.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields, QgsProject, QgsRelation
from PyQt5.QtCore import QVariant

try:
    from services.missing_total_station_detector_service import MissingTotalStationDetectorService
    from core.data_structures import WarningData
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.missing_total_station_detector_service import MissingTotalStationDetectorService
    from core.data_structures import WarningData


class TestMissingTotalStationDetectorService(unittest.TestCase):
    """Test cases for MissingTotalStationDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.translation_service = Mock()
        
        # Mock translation service
        self.translation_service.translate.return_value = "Test warning message"
        
        # Create the service
        self.service = MissingTotalStationDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            translation_service=self.translation_service
        )
    
    def test_init(self):
        """Test service initialization."""
        self.assertEqual(self.service._settings_manager, self.settings_manager)
        self.assertEqual(self.service._layer_service, self.layer_service)
        self.assertEqual(self.service._translation_service, self.translation_service)
    
    def test_detect_missing_total_station_warnings_no_layers_configured(self):
        """Test detection when no layers are configured."""
        # Mock settings to return None for layer IDs
        self.settings_manager.get_value.side_effect = lambda key: None
        
        warnings = self.service.detect_missing_total_station_warnings()
        
        self.assertEqual(warnings, [])
        self.settings_manager.get_value.assert_called()
    
    def test_detect_missing_total_station_warnings_layers_not_found(self):
        """Test detection when layers are not found."""
        # Mock settings to return layer IDs
        self.settings_manager.get_value.side_effect = lambda key: {
            'total_station_points_layer': 'points_layer_id',
            'objects_layer': 'objects_layer_id'
        }.get(key)
        
        # Mock layer service to return None for layers
        self.layer_service.get_layer_by_name.return_value = None
        self.layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_missing_total_station_warnings()
        
        self.assertEqual(warnings, [])
    
    def test_detect_missing_total_station_warnings_no_relation(self):
        """Test detection when no relation exists between layers."""
        # Mock settings
        self.settings_manager.get_value.side_effect = lambda key: {
            'total_station_points_layer': 'points_layer_id',
            'objects_layer': 'objects_layer_id'
        }.get(key)
        
        # Mock layers
        points_layer = Mock()
        points_layer.name.return_value = "Points Layer"
        points_layer.id.return_value = "points_layer_id"
        
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects Layer"
        objects_layer.id.return_value = "objects_layer_id"
        
        self.layer_service.get_layer_by_name.return_value = None
        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'points_layer_id': points_layer,
            'objects_layer_id': objects_layer
        }.get(layer_id)
        
        # Mock QGIS project and relation manager
        with patch('qgis.core.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_project.instance.return_value = mock_instance
            
            mock_relation_manager = Mock()
            mock_instance.relationManager.return_value = mock_relation_manager
            mock_relation_manager.relations.return_value = {}
            
            warnings = self.service.detect_missing_total_station_warnings()
            
            self.assertEqual(warnings, [])
    
    def test_detect_missing_total_station_warnings_with_relation(self):
        """Test detection when relation exists and objects are missing total station points."""
        # Mock settings
        self.settings_manager.get_value.side_effect = lambda key: {
            'total_station_points_layer': 'points_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number'
        }.get(key)
        
        # Mock translation service to return the actual message
        self.translation_service.translate.side_effect = lambda key, default: {
            ("MissingTotalStationDetectorService", "Object 2 have no matching total station points"): 
            "Object 2 have no matching total station points"
        }.get((key, default), default)
        
        # Mock layers
        points_layer = Mock()
        points_layer.name.return_value = "Points Layer"
        points_layer.id.return_value = "points_layer_id"
        
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects Layer"
        objects_layer.id.return_value = "objects_layer_id"
        
        # Mock fields
        points_fields = QgsFields()
        points_fields.append(QgsField("relation_field", QVariant.String))
        points_layer.fields.return_value = points_fields
        
        objects_fields = QgsFields()
        objects_fields.append(QgsField("relation_field", QVariant.String))
        objects_fields.append(QgsField("number", QVariant.Int))
        objects_layer.fields.return_value = objects_fields
        
        # Mock indexOf method for both layers
        points_layer.fields().indexOf = Mock(return_value=0)
        objects_layer.fields().indexOf = Mock(return_value=0)
        
        self.layer_service.get_layer_by_name.return_value = None
        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'points_layer_id': points_layer,
            'objects_layer_id': objects_layer
        }.get(layer_id)
        
        # Mock features
        points_feature = Mock()
        points_feature.id.return_value = 1
        points_feature.attribute.return_value = "REL1"
        
        objects_feature1 = Mock()
        objects_feature1.id.return_value = 1
        objects_feature1.attribute.side_effect = lambda idx: "REL1" if idx == 0 else 1
        
        objects_feature2 = Mock()
        objects_feature2.id.return_value = 2
        objects_feature2.attribute.side_effect = lambda idx: "REL2" if idx == 0 else 2
        
        # Mock the feature identifier method to avoid the lambda issue
        self.service._get_feature_identifier = Mock(return_value="Object 2")
        
        points_layer.getFeatures.return_value = [points_feature]
        objects_layer.getFeatures.return_value = [objects_feature1, objects_feature2]
        
        # Mock relation
        relation = Mock()
        relation.name.return_value = "Test Relation"
        relation.id.return_value = "relation_id"
        relation.fieldPairs.return_value = {"relation_field": "relation_field"}
        relation.referencingLayer.return_value = points_layer
        relation.referencedLayer.return_value = objects_layer
        
        # Mock QGIS project and relation manager
        with patch('qgis.core.QgsProject') as mock_project:
            mock_instance = Mock()
            mock_project.instance.return_value = mock_instance
            
            mock_relation_manager = Mock()
            mock_instance.relationManager.return_value = mock_relation_manager
            mock_relation_manager.relations.return_value = {"relation_id": relation}
            
            warnings = self.service.detect_missing_total_station_warnings()
            
            # Should find one warning for object with REL2 that has no matching point
            self.assertEqual(len(warnings), 1)
            self.assertIsInstance(warnings[0], WarningData)
            self.assertIn("Object 2", warnings[0].message)
            self.assertIn("no matching total station points", warnings[0].message)
    
    def test_get_feature_identifier_with_number_field(self):
        """Test getting feature identifier when number field is configured."""
        # Mock settings
        self.settings_manager.get_value.return_value = "number"
        
        # Mock feature
        feature = Mock()
        feature.attribute.return_value = 123
        feature.id.return_value = 1
        
        identifier = self.service._get_feature_identifier(feature, "Object")
        
        self.assertEqual(identifier, "Object 123")
    
    def test_get_feature_identifier_without_number_field(self):
        """Test getting feature identifier when number field is not configured."""
        # Mock settings
        self.settings_manager.get_value.return_value = ""
        
        # Mock feature
        feature = Mock()
        feature.id.return_value = 1
        
        identifier = self.service._get_feature_identifier(feature, "Object")
        
        self.assertEqual(identifier, "Object 1")
    
    def test_create_missing_total_station_warning_single_object(self):
        """Test creating warning message for single object."""
        object_identifiers = ["Object 123"]
        
        # Mock translation service to return the actual message
        self.translation_service.translate.side_effect = lambda key, default: {
            ("MissingTotalStationDetectorService", "Object 123 have no matching total station points"): 
            "Object 123 have no matching total station points"
        }.get((key, default), default)
        
        message = self.service._create_missing_total_station_warning(object_identifiers)
        
        self.assertIn("Object 123", message)
        self.assertIn("no matching total station points", message)
    
    def test_create_missing_total_station_warning_multiple_objects(self):
        """Test creating warning message for multiple objects."""
        object_identifiers = ["Object 123", "Object 456", "Object 789"]
        
        # Mock translation service to return the actual message
        self.translation_service.translate.side_effect = lambda key, default: {
            ("MissingTotalStationDetectorService", "3 objects have no matching total station points"): 
            "3 objects have no matching total station points"
        }.get((key, default), default)
        
        message = self.service._create_missing_total_station_warning(object_identifiers)
        
        self.assertIn("3 objects", message)
        self.assertIn("no matching total station points", message)


if __name__ == '__main__':
    unittest.main() 