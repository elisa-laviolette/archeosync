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
        )
    
    def test_init(self):
        """Test service initialization."""
        self.assertEqual(self.service._max_distance_meters, 0.05)
        self.assertEqual(self.service._settings_manager, self.settings_manager)
        self.assertEqual(self.service._layer_service, self.layer_service)
    
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

    def test_detect_distance_warnings_with_only_definitive_layers(self):
        """Detection still works when temporary import layers are unavailable."""
        points_layer = Mock()
        points_layer.name.return_value = "Points topo"
        points_layer.fields.return_value.indexOf.return_value = 0

        objects_layer = Mock()
        objects_layer.name.return_value = "Objets relevés"
        objects_layer.fields.return_value.indexOf.return_value = 0

        points_field = Mock()
        points_field.name.return_value = "object_id"
        objects_field = Mock()
        objects_field.name.return_value = "id"
        points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'points_id',
            'objects_layer': 'objects_id'
        }.get(key, default)

        self.layer_service.get_layer_by_name.return_value = None
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            points_layer if lid == 'points_id' else objects_layer if lid == 'objects_id' else None
        )

        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.fieldPairs.return_value = {"object_id": "id"}
        mock_relation.referencingLayer.return_value = points_layer
        mock_relation.referencedLayer.return_value = objects_layer
        mock_relation.id.return_value = "rel_direct"

        point_feature = Mock()
        point_feature.id.return_value = 1
        point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        point_feature.attribute.return_value = "obj1"

        object_feature = Mock()
        object_feature.id.return_value = 2
        object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(1, 0))
        object_feature.attribute.return_value = "obj1"

        points_layer.getFeatures.return_value = [point_feature]
        objects_layer.getFeatures.return_value = [object_feature]

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"test_relation": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager

            warnings = self.service.detect_distance_warnings()

        self.assertGreater(len(warnings), 0)
        self.assertIsInstance(warnings[0], WarningData)

    def test_detect_distance_warnings_skips_definitive_pair_when_temp_exists(self):
        """Do not emit definitive-definitive warnings while a temp points layer exists."""
        temp_points_layer = Mock()
        temp_points_layer.name.return_value = "Imported_CSV_Points"
        temp_points_layer.fields.return_value.indexOf.return_value = 0

        definitive_points_layer = Mock()
        definitive_points_layer.name.return_value = "Points topo"
        definitive_points_layer.fields.return_value.indexOf.return_value = 0

        definitive_objects_layer = Mock()
        definitive_objects_layer.name.return_value = "Objets relevés"
        definitive_objects_layer.fields.return_value.indexOf.return_value = 0

        points_field = Mock()
        points_field.name.return_value = "object_id"
        objects_field = Mock()
        objects_field.name.return_value = "id"
        temp_points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        definitive_points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        definitive_objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'points_id',
            'objects_layer': 'objects_id'
        }.get(key, default)

        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_points_layer if name == "Imported_CSV_Points" else None
        )
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            definitive_points_layer if lid == 'points_id'
            else definitive_objects_layer if lid == 'objects_id'
            else None
        )

        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.fieldPairs.return_value = {"object_id": "id"}
        mock_relation.referencingLayer.return_value = definitive_points_layer
        mock_relation.referencedLayer.return_value = definitive_objects_layer
        mock_relation.id.return_value = "rel_direct"

        # Temp-vs-definitive pair should not raise (overlap).
        temp_point_feature = Mock()
        temp_point_feature.id.return_value = 1
        temp_point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        temp_point_feature.attribute.return_value = "obj1"

        # Definitive-vs-definitive would raise if processed (far away).
        definitive_point_feature = Mock()
        definitive_point_feature.id.return_value = 2
        definitive_point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(10, 10))
        definitive_point_feature.attribute.return_value = "obj1"

        object_feature = Mock()
        object_feature.id.return_value = 3
        object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        object_feature.attribute.return_value = "obj1"

        temp_points_layer.getFeatures.return_value = [temp_point_feature]
        definitive_points_layer.getFeatures.return_value = [definitive_point_feature]
        definitive_objects_layer.getFeatures.return_value = [object_feature]

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"test_relation": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager

            warnings = self.service.detect_distance_warnings()

        self.assertEqual(warnings, [])

    def test_detect_distance_warnings_ignores_stale_csv_layer_when_import_has_no_csv(self):
        """A leftover Imported_CSV_Points layer must not affect an object-only import."""
        temp_points_layer = Mock()
        temp_points_layer.name.return_value = "Imported_CSV_Points"
        points_fields = QgsFields()
        points_fields.append(QgsField("identifier", QVariant.String))
        temp_points_layer.fields.return_value = points_fields

        point_features = []
        for i in range(50):
            point = QgsFeature(points_fields)
            point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(i), 0)))
            point.setAttribute("identifier", "7")
            point_features.append(point)
        temp_points_layer.getFeatures.return_value = point_features

        objects_fields = QgsFields()
        objects_fields.append(QgsField("recording_area_id", QVariant.Int))
        temp_objects_layer = Mock()
        temp_objects_layer.name.return_value = "New Objects"
        temp_objects_layer.fields.return_value = objects_fields

        object_feature = QgsFeature(objects_fields)
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100, 100)))
        object_feature.setAttribute("recording_area_id", 7)
        temp_objects_layer.getFeatures.return_value = [object_feature]

        definitive_points_layer = Mock()
        definitive_points_layer.name.return_value = "Points topo"
        definitive_points_layer.id.return_value = "points_id"
        definitive_objects_layer = Mock()
        definitive_objects_layer.name.return_value = "Objets"
        definitive_objects_layer.id.return_value = "objects_id"

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'points_id',
            'objects_layer': 'objects_id',
            'recording_areas_layer': 'zones_id',
            'objects_recording_area_field': 'recording_area_id',
        }.get(key, default)

        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: (
                temp_objects_layer if name == "New Objects"
                else temp_points_layer if name == "Imported_CSV_Points"
                else None
            )
        )
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            definitive_points_layer if lid == 'points_id'
            else definitive_objects_layer if lid == 'objects_id'
            else None
        )

        service = DistanceDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
            import_context={'csv_points_count': 0, 'objects_count': 1},
        )
        warnings = service.detect_distance_warnings()
        self.assertEqual(warnings, [])

    def test_detect_distance_warnings_object_only_import_returns_empty_without_topo_fields(self):
        """Object-only import must not run relation/recording-area distance pairing."""
        temp_objects_layer = Mock()
        temp_objects_layer.name.return_value = "New Objects"
        temp_objects_layer.fields.return_value = QgsFields()

        definitive_points_layer = Mock()
        definitive_points_layer.name.return_value = "Points topo"
        definitive_points_layer.getFeatures.return_value = [Mock()] * 1625

        definitive_objects_layer = Mock()
        definitive_objects_layer.name.return_value = "Objets relevés"

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'points_id',
            'objects_layer': 'objects_id',
            'recording_areas_layer': 'zones_id',
        }.get(key, default)

        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_objects_layer if name == "New Objects" else None
        )
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            definitive_points_layer if lid == 'points_id'
            else definitive_objects_layer if lid == 'objects_id'
            else None
        )

        warnings = self.service.detect_distance_warnings()
        self.assertEqual(warnings, [])

    def test_detect_distance_warnings_skips_definitive_points_to_temp_objects(self):
        """Imported objects without imported points should not be matched to definitive points."""
        temp_objects_layer = Mock()
        temp_objects_layer.name.return_value = "New Objects"
        temp_objects_layer.fields.return_value.indexOf.return_value = 0

        definitive_points_layer = Mock()
        definitive_points_layer.name.return_value = "Points topo"
        definitive_points_layer.fields.return_value.indexOf.return_value = 0

        definitive_objects_layer = Mock()
        definitive_objects_layer.name.return_value = "Objets relevés"
        definitive_objects_layer.fields.return_value.indexOf.return_value = 0

        points_field = Mock()
        points_field.name.return_value = "identifier"
        objects_field = Mock()
        objects_field.name.return_value = "identifier"
        temp_objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field
        definitive_points_layer.fields.return_value.__getitem__ = lambda idx: points_field
        definitive_objects_layer.fields.return_value.__getitem__ = lambda idx: objects_field

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'points_id',
            'objects_layer': 'objects_id'
        }.get(key, default)

        # No imported points layer in the project.
        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_objects_layer if name == "New Objects" else None
        )
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            definitive_points_layer if lid == 'points_id'
            else definitive_objects_layer if lid == 'objects_id'
            else None
        )

        mock_relation = Mock()
        mock_relation.name.return_value = "test_relation"
        mock_relation.fieldPairs.return_value = {"identifier": "identifier"}
        mock_relation.referencingLayer.return_value = definitive_points_layer
        mock_relation.referencedLayer.return_value = definitive_objects_layer
        mock_relation.id.return_value = "rel_direct"

        definitive_point_feature = Mock()
        definitive_point_feature.id.return_value = 2
        definitive_point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(10, 10))
        definitive_point_feature.attribute.return_value = "obj1"

        temp_object_feature = Mock()
        temp_object_feature.id.return_value = 3
        temp_object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        temp_object_feature.attribute.return_value = "obj1"

        definitive_object_feature = Mock()
        definitive_object_feature.id.return_value = 4
        definitive_object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        definitive_object_feature.attribute.return_value = "obj1"

        definitive_points_layer.getFeatures.return_value = [definitive_point_feature]
        temp_objects_layer.getFeatures.return_value = [temp_object_feature]
        definitive_objects_layer.getFeatures.return_value = [definitive_object_feature]

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"test_relation": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager

            warnings = self.service.detect_distance_warnings()

        self.assertEqual(warnings, [])

    def test_detect_distance_by_topo_identifiers_no_warning_when_points_missing(self):
        """Objects linked via first_identifier must not warn when topo points are absent."""
        points_fields = QgsFields()
        points_fields.append(QgsField("identifier", QVariant.String))
        points_layer = Mock()
        points_layer.name.return_value = "Imported_CSV_Points"
        points_layer.fields.return_value = points_fields
        points_layer.getFeatures.return_value = []

        objects_fields = QgsFields()
        objects_fields.append(QgsField("first_identifier", QVariant.String))
        objects_fields.append(QgsField("last_identifier", QVariant.String))
        objects_fields.append(QgsField("recording_area_id", QVariant.Int))
        objects_layer = Mock()
        objects_layer.name.return_value = "New Objects"
        objects_layer.fields.return_value = objects_fields

        object_feature = QgsFeature(objects_fields)
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        object_feature.setAttribute("first_identifier", "I103_28")
        object_feature.setAttribute("last_identifier", "")
        object_feature.setAttribute("recording_area_id", 7)
        objects_layer.getFeatures.return_value = [object_feature]

        warnings = self.service._detect_distance_by_topo_identifiers(
            objects_layer,
            primary_points_layer=points_layer,
            definitive_points_layer=None,
        )
        self.assertEqual(warnings, [])

    def test_detect_distance_by_topo_identifiers_uses_topo_not_recording_area(self):
        """Many points sharing a recording-area key must not pair with imported objects."""
        points_fields = QgsFields()
        points_fields.append(QgsField("identifier", QVariant.String))
        points_features = []
        for i in range(50):
            point = QgsFeature(points_fields)
            point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(i), 0)))
            point.setAttribute("identifier", f"P{i}")
            points_features.append(point)

        points_layer = Mock()
        points_layer.name.return_value = "Points topo"
        points_layer.fields.return_value = points_fields
        points_layer.getFeatures.return_value = points_features

        objects_fields = QgsFields()
        objects_fields.append(QgsField("first_identifier", QVariant.String))
        objects_fields.append(QgsField("last_identifier", QVariant.String))
        objects_fields.append(QgsField("recording_area_id", QVariant.Int))
        objects_layer = Mock()
        objects_layer.name.return_value = "New Objects"
        objects_layer.fields.return_value = objects_fields

        object_feature = QgsFeature(objects_fields)
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100, 100)))
        object_feature.setAttribute("first_identifier", "MISSING_TOPO")
        object_feature.setAttribute("last_identifier", "")
        object_feature.setAttribute("recording_area_id", 7)
        objects_layer.getFeatures.return_value = [object_feature]

        warnings = self.service._detect_distance_by_topo_identifiers(
            objects_layer,
            primary_points_layer=None,
            definitive_points_layer=points_layer,
        )
        self.assertEqual(warnings, [])

    def test_detect_distance_issues_skips_high_multiplicity_relation_keys(self):
        """Relation keys shared by too many points must not trigger cartesian distance checks."""
        points_fields = QgsFields()
        points_fields.append(QgsField("zone_id", QVariant.Int))
        points_layer = Mock()
        points_layer.name.return_value = "Imported_CSV_Points"
        points_layer.fields.return_value = points_fields

        objects_fields = QgsFields()
        objects_fields.append(QgsField("zone_id", QVariant.Int))
        objects_layer = Mock()
        objects_layer.name.return_value = "New Objects"
        objects_layer.fields.return_value = objects_fields

        point_features = []
        for i in range(30):
            point = QgsFeature(points_fields)
            point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(i), 0)))
            point.setAttribute("zone_id", 7)
            point_features.append(point)

        object_feature = QgsFeature(objects_fields)
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100, 100)))
        object_feature.setAttribute("zone_id", 7)

        points_layer.getFeatures.return_value = point_features
        objects_layer.getFeatures.return_value = [object_feature]

        warnings = self.service._detect_distance_issues(
            points_layer,
            objects_layer,
            0,
            0,
            True,
        )
        self.assertEqual(warnings, [])

    def test_object_feature_has_point_association_with_empty_identifiers(self):
        """If first/last identifiers exist but are empty, object is not associated to points."""
        fields = QgsFields()
        fields.append(QgsField("first_identifier", QVariant.String))
        fields.append(QgsField("last_identifier", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields

        feature = QgsFeature(fields)
        feature.setAttribute("first_identifier", "")
        feature.setAttribute("last_identifier", None)

        has_assoc = self.service._object_feature_has_point_association(feature, layer)
        self.assertFalse(has_assoc)

    def test_object_feature_has_point_association_with_values(self):
        """A non-empty first/last identifier means object-point association exists."""
        fields = QgsFields()
        fields.append(QgsField("first_identifier", QVariant.String))
        fields.append(QgsField("last_identifier", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields

        feature = QgsFeature(fields)
        feature.setAttribute("first_identifier", "P100")
        feature.setAttribute("last_identifier", "")

        has_assoc = self.service._object_feature_has_point_association(feature, layer)
        self.assertTrue(has_assoc)
    
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
        
        self.assertIn("15.0 cm", message)
        self.assertIn("5.0 cm", message)

    def test_detect_distance_issues_ignores_empty_relation_values(self):
        """Empty identifiers must not be considered as valid point/object links."""
        points_layer = Mock()
        objects_layer = Mock()
        points_layer.name.return_value = "Imported_CSV_Points"
        objects_layer.name.return_value = "New Objects"

        points_fields = QgsFields()
        points_fields.append(QgsField("identifier", QVariant.String))
        points_layer.fields.return_value = points_fields

        objects_fields = QgsFields()
        objects_fields.append(QgsField("identifier", QVariant.String))
        objects_layer.fields.return_value = objects_fields

        point_feature = QgsFeature(points_fields)
        point_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        point_feature.setAttribute("identifier", "")

        object_feature = QgsFeature(objects_fields)
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 0)))
        object_feature.setAttribute("identifier", "")

        points_layer.getFeatures.return_value = [point_feature]
        objects_layer.getFeatures.return_value = [object_feature]

        warnings = self.service._detect_distance_issues(
            points_layer,
            objects_layer,
            0,
            0,
            True,
        )
        self.assertEqual(warnings, [])

    def test_create_distance_warning_uses_unique_identifiers(self):
        """Repeated pairings should not inflate object/point counts in warning text."""
        points_layer = Mock()
        points_layer.name.return_value = "Imported_CSV_Points"
        objects_layer = Mock()
        objects_layer.name.return_value = "New Objects"

        points_fields = QgsFields()
        points_fields.append(QgsField("identifier", QVariant.String))
        points_layer.fields.return_value = points_fields

        objects_fields = QgsFields()
        objects_fields.append(QgsField("identifier", QVariant.String))
        objects_layer.fields.return_value = objects_fields

        p1 = QgsFeature(points_fields)
        p1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        p1.setAttribute("identifier", "A1")
        p2 = QgsFeature(points_fields)
        p2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0.2)))
        p2.setAttribute("identifier", "A1")

        o1 = QgsFeature(objects_fields)
        o1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 0)))
        o1.setAttribute("identifier", "A1")

        points_layer.getFeatures.return_value = [p1, p2]
        objects_layer.getFeatures.return_value = [o1]

        warnings = self.service._detect_distance_issues(
            points_layer,
            objects_layer,
            0,
            0,
            True,
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("1 points and 1 objects", warnings[0].message)
    
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

    def test_ordered_relations_prefers_points_as_referencing(self):
        """When two directions exist, prefer the relation whose referencing layer is points."""
        pts = Mock()
        pts.id.return_value = 'pid'
        obj = Mock()
        obj.id.return_value = 'oid'
        rel_objects_referencing = Mock()
        rel_objects_referencing.referencingLayer.return_value = obj
        rel_objects_referencing.referencedLayer.return_value = pts
        rel_points_referencing = Mock()
        rel_points_referencing.referencingLayer.return_value = pts
        rel_points_referencing.referencedLayer.return_value = obj
        ordered = self.service._ordered_relations_for_distance(
            [rel_objects_referencing, rel_points_referencing], pts
        )
        self.assertEqual(ordered, [rel_points_referencing, rel_objects_referencing])

    def test_get_relation_between_layers_returns_preferred_when_multiple(self):
        """_get_relation_between_layers returns the points-referencing relation first."""
        pts = Mock()
        pts.id.return_value = 'pid'
        obj = Mock()
        obj.id.return_value = 'oid'
        rel_objects_referencing = Mock()
        rel_objects_referencing.referencingLayer.return_value = obj
        rel_objects_referencing.referencedLayer.return_value = pts
        rel_points_referencing = Mock()
        rel_points_referencing.referencingLayer.return_value = pts
        rel_points_referencing.referencedLayer.return_value = obj
        with patch.object(
            self.service,
            '_collect_relations_between_layers',
            return_value=[rel_objects_referencing, rel_points_referencing],
        ):
            chosen = self.service._get_relation_between_layers(pts, obj)
        self.assertIs(chosen, rel_points_referencing)

    def test_find_relation_field_synonym_ptid_for_identifier_on_points(self):
        """CSV memory layers often expose ptid while the QGIS relation uses identifier."""
        fields = QgsFields()
        fields.append(QgsField("ptid", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields
        found = self.service._find_relation_field_on_layer(
            layer, "identifier", is_point_layer=True
        )
        self.assertEqual(found, "ptid")

    def test_find_relation_field_label_court_for_identifier_on_objects(self):
        fields = QgsFields()
        fields.append(QgsField("Label_court", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields
        found = self.service._find_relation_field_on_layer(
            layer, "identifier", is_point_layer=False
        )
        self.assertEqual(found, "Label_court")

    def test_find_relation_field_nonstandard_name_no_synonym_expansion(self):
        """Do not map arbitrary relation field names to ptid/id."""
        fields = QgsFields()
        fields.append(QgsField("ptid", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields
        found = self.service._find_relation_field_on_layer(
            layer, "ref_chantier", is_point_layer=True
        )
        self.assertIsNone(found)

    def test_find_relation_field_identifier_does_not_fallback_to_id(self):
        """For standard names like identifier, do not fallback to id/fid."""
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields

        found = self.service._find_relation_field_on_layer(
            layer, "identifier", is_point_layer=False
        )
        self.assertIsNone(found)

    def test_find_relation_field_id_can_still_match_id(self):
        """Explicit id relation should still resolve to id field."""
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.String))
        layer = Mock()
        layer.fields.return_value = fields

        found = self.service._find_relation_field_on_layer(
            layer, "id", is_point_layer=False
        )
        self.assertEqual(found, "id")

    def test_case_insensitive_relation_matching(self):
        """Test that relation values are matched case-insensitively."""
        # Mock layers
        points_layer = Mock()
        objects_layer = Mock()
        points_layer.name.return_value = "Imported_CSV_Points"
        objects_layer.name.return_value = "Objects"
        
        # Mock fields
        points_field = QgsField("identifier", QVariant.String)
        objects_field = QgsField("identifier", QVariant.String)
        points_layer.fields.return_value = QgsFields()
        objects_layer.fields.return_value = QgsFields()
        points_layer.fields().append(points_field)
        objects_layer.fields().append(objects_field)
        
        # Create features with identifiers differing only by case
        point_feature = QgsFeature(points_layer.fields())
        point_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        point_feature.setAttribute("identifier", "abc123")
        
        object_feature = QgsFeature(objects_layer.fields())
        object_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 0)))
        object_feature.setAttribute("identifier", "ABC123")
        
        # Set up getFeatures to return the features
        points_layer.getFeatures.return_value = [point_feature]
        objects_layer.getFeatures.return_value = [object_feature]
        
        # Patch the layer_service to return our mocks
        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: points_layer if layer_id == 'test_layer_id' else objects_layer
        self.layer_service.get_layer_by_name.side_effect = lambda name: points_layer if name == "Imported_CSV_Points" else objects_layer if name == "Objects" else None
        
        # Patch the relation finding to simulate a valid relation
        with patch.object(self.service, '_get_relation_between_layers', return_value=Mock(fieldPairs=lambda: {"identifier": "identifier"}, referencingLayer=lambda: points_layer)):
            warnings = self.service._detect_distance_issues(points_layer, objects_layer, 0, 0, True)
        
        # There should be a warning because the points are 1m apart (threshold is 0.05m)
        self.assertTrue(any("abc123" in w.message.lower() or "ABC123" in w.message for w in warnings))

    def test_find_shortest_relation_path_none_without_link(self):
        """No path when the graph has no route between the two layers."""
        pts = Mock()
        pts.id.return_value = 'pid'
        obj = Mock()
        obj.id.return_value = 'oid'
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            path = self.service._find_shortest_relation_path(pts, obj)
        self.assertIsNone(path)

    def test_find_shortest_relation_path_two_hops(self):
        """BFS finds points -> intermediate -> objects when no direct edge exists."""
        pts = Mock()
        pts.id.return_value = 'pid'
        inter = Mock()
        inter.id.return_value = 'iid'
        obj = Mock()
        obj.id.return_value = 'oid'

        rel_pi = Mock()
        rel_pi.referencingLayer.return_value = pts
        rel_pi.referencedLayer.return_value = inter

        rel_io = Mock()
        rel_io.referencingLayer.return_value = inter
        rel_io.referencedLayer.return_value = obj

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {
                'pi': rel_pi,
                'io': rel_io,
            }
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            path = self.service._find_shortest_relation_path(pts, obj)

        self.assertEqual(path, [rel_pi, rel_io])

    def test_find_shortest_relation_path_skips_forbidden_direct_edge(self):
        """When direct points↔objects is forbidden, BFS returns the two-hop path."""
        pts = Mock()
        pts.id.return_value = 'pid'
        inter = Mock()
        inter.id.return_value = 'iid'
        obj = Mock()
        obj.id.return_value = 'oid'

        rel_direct = Mock()
        rel_direct.id.return_value = 'direct'
        rel_direct.referencingLayer.return_value = pts
        rel_direct.referencedLayer.return_value = obj

        rel_pi = Mock()
        rel_pi.id.return_value = 'pi'
        rel_pi.referencingLayer.return_value = pts
        rel_pi.referencedLayer.return_value = inter

        rel_io = Mock()
        rel_io.id.return_value = 'io'
        rel_io.referencingLayer.return_value = inter
        rel_io.referencedLayer.return_value = obj

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {
                'direct': rel_direct,
                'pi': rel_pi,
                'io': rel_io,
            }
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager
            path = self.service._find_shortest_relation_path(
                pts, obj, forbidden_relation_ids=frozenset({'direct'})
            )

        self.assertEqual(path, [rel_pi, rel_io])

    def test_detect_distance_warnings_indirect_relation_two_hops(self):
        """Distance check follows an indirect QGIS relation chain (points -> link -> objects)."""
        def_pts = Mock()
        def_pts.id.return_value = 'def_pid'
        def_pts.name.return_value = 'Def Points'

        def_obj = Mock()
        def_obj.id.return_value = 'def_oid'
        def_obj.name.return_value = 'Def Objects'

        inter = Mock()
        inter.id.return_value = 'inter_id'
        inter.name.return_value = 'Link table'

        rel_pi = Mock()
        rel_pi.id.return_value = 'rel_pi'
        rel_pi.fieldPairs.return_value = {'pt_fk': 'pt_pk'}
        rel_pi.referencingLayer.return_value = def_pts
        rel_pi.referencedLayer.return_value = inter

        rel_io = Mock()
        rel_io.id.return_value = 'rel_io'
        rel_io.fieldPairs.return_value = {'obj_fk': 'obj_pk'}
        rel_io.referencingLayer.return_value = inter
        rel_io.referencedLayer.return_value = def_obj

        # Fields on each layer (names match relation expectations)
        def _fields(names):
            m = Mock()
            m.indexOf.side_effect = lambda n: names.index(n) if n in names else -1
            m.__getitem__ = lambda self, i: Mock(name=names[i])
            m.__iter__ = lambda self=None: iter([Mock(name=n) for n in names])
            return m

        def_pts.fields.return_value = _fields(['pt_fk'])
        inter.fields.return_value = _fields(['pt_pk', 'obj_fk'])
        def_obj.fields.return_value = _fields(['obj_pk'])

        temp_pts = Mock()
        temp_pts.name.return_value = "Imported_CSV_Points"
        temp_pts.fields.return_value = _fields(['pt_fk'])

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'def_pid',
            'objects_layer': 'def_oid',
        }.get(key, default)

        self.layer_service.get_layer_by_id.side_effect = lambda lid: {
            'def_pid': def_pts,
            'def_oid': def_obj,
        }.get(lid)

        temp_obj = Mock()
        temp_obj.name.return_value = 'New Objects'
        temp_obj.fields.return_value = _fields(['obj_pk'])
        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: (
                temp_obj if name == 'New Objects'
                else temp_pts if name == 'Imported_CSV_Points'
                else None
            )
        )

        point_feature = Mock()
        point_feature.id.return_value = 1
        point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
        point_feature.attribute.return_value = 'L1'

        inter_feature = Mock()
        inter_feature.id.return_value = 10
        inter_feature.attribute.side_effect = lambda idx: ('L1', 'O9')[idx]

        object_feature = Mock()
        object_feature.id.return_value = 2
        object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(10, 10))
        object_feature.attribute.return_value = 'O9'

        def_pts.getFeatures.return_value = [point_feature]
        temp_pts.getFeatures.return_value = [point_feature]
        inter.getFeatures.return_value = [inter_feature]
        def_obj.getFeatures.return_value = [object_feature]
        temp_obj.getFeatures.return_value = [object_feature]

        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {'pi': rel_pi, 'io': rel_io}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager

            warnings = self.service.detect_distance_warnings()

        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn('cm', warnings[0].message)

    def test_detect_distance_warnings_uses_indirect_when_direct_has_no_overlap(self):
        """Fallback to indirect path when direct mapping resolves but links no features."""
        temp_points = Mock()
        temp_points.name.return_value = "Imported_CSV_Points"
        def_pts = Mock()
        def_pts.id.return_value = 'def_pid'
        def_pts.name.return_value = 'Points topo'
        def_obj = Mock()
        def_obj.id.return_value = 'def_oid'
        def_obj.name.return_value = 'Objets relevés'
        inter = Mock()
        inter.id.return_value = 'inter_id'
        inter.name.return_value = 'Points topo mobilier'

        def _fields(names):
            fields = QgsFields()
            for n in names:
                fields.append(QgsField(n, QVariant.String))
            return fields

        temp_points.fields.return_value = _fields(['pt_fk', 'direct_id'])
        def_pts.fields.return_value = _fields(['pt_fk', 'direct_id'])
        def_obj.fields.return_value = _fields(['artifact_id', 'obj_pk'])
        inter.fields.return_value = _fields(['pt_pk', 'obj_fk'])

        rel_direct = Mock()
        rel_direct.id.return_value = 'rel_direct'
        rel_direct.fieldPairs.return_value = {'direct_id': 'artifact_id'}
        rel_direct.referencingLayer.return_value = def_pts
        rel_direct.referencedLayer.return_value = def_obj

        rel_pi = Mock()
        rel_pi.id.return_value = 'rel_pi'
        rel_pi.fieldPairs.return_value = {'pt_fk': 'pt_pk'}
        rel_pi.referencingLayer.return_value = def_pts
        rel_pi.referencedLayer.return_value = inter

        rel_io = Mock()
        rel_io.id.return_value = 'rel_io'
        rel_io.fieldPairs.return_value = {'obj_fk': 'obj_pk'}
        rel_io.referencingLayer.return_value = inter
        rel_io.referencedLayer.return_value = def_obj

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'def_pid',
            'objects_layer': 'def_oid',
        }.get(key, default)
        self.layer_service.get_layer_by_name.side_effect = (
            lambda name: temp_points if name == "Imported_CSV_Points" else None
        )
        self.layer_service.get_layer_by_id.side_effect = lambda lid: (
            def_pts if lid == 'def_pid' else def_obj if lid == 'def_oid' else None
        )

        p = QgsFeature(temp_points.fields())
        p.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        p.setAttribute('pt_fk', 'MOB2222')
        p.setAttribute('direct_id', 'NO_MATCH')

        i = QgsFeature(inter.fields())
        i.setAttribute('pt_pk', 'MOB2222')
        i.setAttribute('obj_fk', 'A7')

        o = QgsFeature(def_obj.fields())
        o.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2, 0)))
        o.setAttribute('artifact_id', '7')
        o.setAttribute('obj_pk', 'A7')

        temp_points.getFeatures.return_value = [p]
        def_pts.getFeatures.return_value = []
        inter.getFeatures.return_value = [i]
        def_obj.getFeatures.return_value = [o]

        with patch('qgis.core.QgsProject') as mock_project:
            rm = Mock()
            rm.relations.return_value = {
                'rel_direct': rel_direct,
                'rel_pi': rel_pi,
                'rel_io': rel_io,
            }
            mock_project.instance.return_value.relationManager.return_value = rm
            warnings = self.service.detect_distance_warnings()

        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn('mob2222', warnings[0].message.lower())

    def test_temp_total_station_and_definitive_objects_layer(self):
        """Test detection when only the temporary total station layer exists and objects layer is definitive."""
        # Mock temporary total station layer (Imported_CSV_Points)
        temp_points_layer = Mock()
        temp_points_layer.name.return_value = "Imported_CSV_Points"
        # Simulate fields: ['ptid']
        temp_points_fields = Mock()
        temp_points_fields.indexOf.side_effect = lambda name: 0 if name.lower() == 'ptid' else -1
        temp_points_fields.__getitem__ = lambda idx: Mock(name='ptid')
        temp_points_fields.__iter__ = lambda self=None: iter([Mock(name='ptid')])
        temp_points_layer.fields.return_value = temp_points_fields

        # Mock definitive objects layer
        objects_layer = Mock()
        objects_layer.name.return_value = "Objects"
        objects_fields = Mock()
        objects_fields.indexOf.side_effect = lambda name: 0 if name.lower() == 'ptid' else -1
        objects_fields.__getitem__ = lambda idx: Mock(name='PtID')
        objects_fields.__iter__ = lambda self=None: iter([Mock(name='PtID')])
        objects_layer.fields.return_value = objects_fields

        # Mock settings to return only the definitive objects layer id
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_distance_warnings': True,
            'distance_max_distance': 0.05,
            'total_station_points_layer': 'definitive_points_layer_id',
            'objects_layer': 'definitive_objects_layer_id'
        }.get(key, default)

        # Layer service returns temp points layer for name, definitive objects for id
        self.layer_service.get_layer_by_name.side_effect = lambda name: temp_points_layer if name == "Imported_CSV_Points" else None
        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: objects_layer if layer_id == 'definitive_objects_layer_id' else Mock(name='definitive_points_layer')

        # Mock relation between definitive layers
        mock_relation = Mock()
        mock_relation.fieldPairs.return_value = {'PtID': 'PtID'}
        mock_relation.referencingLayer.return_value = Mock(name='definitive_points_layer')
        mock_relation.referencedLayer.return_value = objects_layer

        # Patch QgsProject to return the relation
        with patch('qgis.core.QgsProject') as mock_project:
            mock_relation_manager = Mock()
            mock_relation_manager.relations.return_value = {"rel": mock_relation}
            mock_project.instance.return_value.relationManager.return_value = mock_relation_manager

            # Create features: one point and one object with matching ptid, but far apart
            point_feature = Mock()
            point_feature.id.return_value = 1
            point_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
            point_feature.attribute.return_value = "I103_28"
            
            object_feature = Mock()
            object_feature.id.return_value = 2
            object_feature.geometry.return_value = QgsGeometry.fromPointXY(QgsPointXY(0, 0.07))  # 7cm away
            object_feature.attribute.return_value = "I103_28"

            temp_points_layer.getFeatures.return_value = [point_feature]
            objects_layer.getFeatures.return_value = [object_feature]

            warnings = self.service.detect_distance_warnings()

            self.assertGreater(len(warnings), 0)
            self.assertIsInstance(warnings[0], WarningData)
            self.assertIn("I103_28", warnings[0].message)


if __name__ == '__main__':
    unittest.main() 