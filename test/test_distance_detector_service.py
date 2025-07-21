"""
Tests for the DistanceDetectorService.

This module tests the distance detection functionality between total station points
and their related objects.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields, QgsProject, QgsRelation
from PyQt5.QtCore import QVariant

try:
    from services.distance_detector_service import DistanceDetectorService
    from core.data_structures import WarningData
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.distance_detector_service import DistanceDetectorService
    from core.data_structures import WarningData


class TestDistanceDetectorService(unittest.TestCase):
    """Test cases for DistanceDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.translation_service = Mock()
        
        # Mock translation service
        self.translation_service.translate.return_value = "Test warning message"
        
        # Mock settings values
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'distance_max_distance': 0.05,
            'enable_distance_warnings': True,
            'total_station_points_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        
        # Create the service
        self.service = DistanceDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            translation_service=self.translation_service
        )
    
    def test_init(self):
        """Test service initialization."""
        self.assertEqual(self.service._max_distance_meters, 0.05)
        self.assertEqual(self.service._settings_manager, self.settings_manager)
        self.assertEqual(self.service._layer_service, self.layer_service)
        self.assertEqual(self.service._translation_service, self.translation_service)
    
    def test_detect_distance_warnings_no_layers_configured(self):
        """Test detection when no layers are configured."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': None,
            'objects_layer': None
        }.get(key, default)
        
        warnings = self.service.detect_distance_warnings()
        
        self.assertEqual(warnings, [])
        # Check that both layer types were queried
        self.settings_manager.get_value.assert_any_call('total_station_points_layer')
        self.settings_manager.get_value.assert_any_call('objects_layer')
    
    def test_detect_distance_warnings_layers_not_found(self):
        """Test detection when layers are not found."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        self.layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_distance_warnings()
        
        self.assertEqual(warnings, [])
        self.layer_service.get_layer_by_id.assert_called()
    
    def test_detect_distance_warnings_no_relation(self):
        """Test detection when no relation exists between layers."""
        # Mock layers
        points_layer = Mock()
        points_layer.name.return_value = "Total Station Points"
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects"
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        self.layer_service.get_layer_by_id.side_effect = [points_layer, objects_layer]
        
        # Mock no relation
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            
            warnings = self.service.detect_distance_warnings()
            
            self.assertEqual(warnings, [])
    
    def test_detect_distance_warnings_with_relation(self):
        """Test detection when relation exists between layers."""
        # Mock layers
        points_layer = Mock()
        points_layer.name.return_value = "Total Station Points"
        points_layer.fields.return_value.indexOf.return_value = 0
        
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects"
        objects_layer.fields.return_value.indexOf.return_value = 0
        
        # Mock fields
        points_field = Mock()
        points_field.name.return_value = "object_id"
        objects_field = Mock()
        objects_field.name.return_value = "id"
        
        # Mock fields list behavior
        points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        self.layer_service.get_layer_by_id.side_effect = [points_layer, objects_layer]
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.fieldPairs.return_value = {"object_id": "id"}
        mock_relation.referencingLayer.return_value = points_layer
        mock_relation.referencedLayer.return_value = objects_layer
        
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"test_relation": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            
            # Mock features with distance issues
            point_feature = Mock()
            point_feature.id.return_value = 1
            point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
            point_feature.attribute.return_value = "obj1"
            
            object_feature = Mock()
            object_feature.id.return_value = 1
            object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(10, 10))  # Far away
            object_feature.attribute.return_value = "obj1"
            
            points_layer.getFeatures.return_value = [point_feature]
            objects_layer.getFeatures.return_value = [object_feature]
            
            warnings = self.service.detect_distance_warnings()
            
            # Should have warnings due to distance > 5cm
            self.assertGreater(len(warnings), 0)
            self.assertIsInstance(warnings[0], WarningData)
    
    def test_detect_distance_warnings_overlapping_features(self):
        """Test detection when features overlap (no distance issue)."""
        # Mock layers
        points_layer = Mock()
        points_layer.name.return_value = "Total Station Points"
        points_layer.fields.return_value.indexOf.return_value = 0
        
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects"
        objects_layer.fields.return_value.indexOf.return_value = 0
        
        # Mock fields
        points_field = Mock()
        points_field.name.return_value = "object_id"
        objects_field = Mock()
        objects_field.name.return_value = "id"
        
        # Mock fields list behavior
        points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field
        
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        self.layer_service.get_layer_by_id.side_effect = [points_layer, objects_layer]
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.fieldPairs.return_value = {"object_id": "id"}
        mock_relation.referencingLayer.return_value = points_layer
        mock_relation.referencedLayer.return_value = objects_layer
        
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"test_relation": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            
            # Mock overlapping features
            point_feature = Mock()
            point_feature.id.return_value = 1
            point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
            point_feature.attribute.return_value = "obj1"
            
            object_feature = Mock()
            object_feature.id.return_value = 1
            object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))  # Same location
            object_feature.attribute.return_value = "obj1"
            
            points_layer.getFeatures.return_value = [point_feature]
            objects_layer.getFeatures.return_value = [object_feature]
            
            warnings = self.service.detect_distance_warnings()
            
            # Should have no warnings due to overlapping features
            self.assertEqual(len(warnings), 0)
    
    def test_get_feature_identifier(self):
        """Test feature identifier generation."""
        # Mock feature with point_id field
        feature = Mock()
        feature.id.return_value = 1
        feature.fields.return_value.indexOf.side_effect = lambda name: 0 if name == 'point_id' else -1
        feature.attribute.return_value = "P001"
        
        identifier = self.service._get_feature_identifier(feature, "Total Station Point")
        self.assertEqual(identifier, "Point P001")
        
        # Mock feature with object_number field
        feature.fields.return_value.indexOf.side_effect = lambda name: 0 if name == 'object_number' else -1
        feature.attribute.return_value = "123"
        
        identifier = self.service._get_feature_identifier(feature, "Object")
        self.assertEqual(identifier, "Object 123")
        
        # Mock feature with no identifier fields
        feature.fields.return_value.indexOf.return_value = -1
        feature.attribute.return_value = None
        
        identifier = self.service._get_feature_identifier(feature, "Object")
        self.assertEqual(identifier, "Object 1")
    
    def test_create_distance_warning(self):
        """Test distance warning message creation."""
        point_identifiers = ["Point P001", "Point P002"]
        object_identifiers = ["Object 123"]
        max_distance = 0.15  # 15 cm
        
        message = self.service._create_distance_warning(point_identifiers, object_identifiers, max_distance)
        
        self.assertEqual(message, "Test warning message")
    
    def test_get_relation_between_layers(self):
        """Test finding relations between layers."""
        layer1 = Mock()
        layer1.name.return_value = "Layer1"
        layer2 = Mock()
        layer2.name.return_value = "Layer2"
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.referencingLayer.return_value = layer1
        mock_relation.referencedLayer.return_value = layer2
        
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            
            relation = self.service._get_relation_between_layers(layer1, layer2)
            
            self.assertIsNone(relation)
    
    def test_get_relation_between_layers_reverse(self):
        """Test finding relations between layers in reverse order."""
        layer1 = Mock()
        layer1.name.return_value = "Layer1"
        layer2 = Mock()
        layer2.name.return_value = "Layer2"
        
        # Mock relation with reverse order
        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.referencingLayer.return_value = layer2
        mock_relation.referencedLayer.return_value = layer1
        
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            
            relation = self.service._get_relation_between_layers(layer1, layer2)
            
            self.assertIsNone(relation)


if __name__ == '__main__':
    unittest.main() 