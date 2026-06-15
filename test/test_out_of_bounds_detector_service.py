"""
Tests for the OutOfBoundsDetectorService.

This module contains comprehensive tests for the OutOfBoundsDetectorService,
which detects features located outside their recording areas by more than
a specified distance (default 20 cm).
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
    from core.data_structures import WarningData
except ImportError:
    from ..services.out_of_bounds_detector_service import OutOfBoundsDetectorService
    from ..core.data_structures import WarningData

try:
    from qgis.core import QgsGeometry, QgsPointXY, QgsPolygonXY, QgsFeature, QgsFields, QgsField
    from PyQt5.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class TestOutOfBoundsDetectorService(unittest.TestCase):
    """Test cases for OutOfBoundsDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_manager = Mock()
        self.layer_service = Mock()
        self.translation_service = Mock()
        self.translation_service.translate.return_value = "Translated message"
        
        # Mock settings values
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'bounds_max_distance': 0.2,
            'enable_bounds_warnings': True,
            'recording_areas_layer': 'test_layer_id',
            'objects_layer': 'test_layer_id'
        }.get(key, default)
        
        self.layer_service.get_layer_by_name.return_value = None

        self.service = OutOfBoundsDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
        )
    
    def test_init_with_default_distance(self):
        """Test initialization with default distance."""
        service = OutOfBoundsDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
        )
        self.assertEqual(service._max_distance_meters, 0.2)
    
    def test_init_with_custom_distance(self):
        """Test initialization with custom distance."""
        # Mock settings to return custom distance
        self.settings_manager.get_value.return_value = 0.5
        service = OutOfBoundsDetectorService(
            settings_manager=self.settings_manager,
            layer_service=self.layer_service,
        )
        self.assertEqual(service._max_distance_meters, 0.5)
    
    def test_detect_out_of_bounds_features_no_configuration(self):
        """Test detection when no configuration is available."""
        self.settings_manager.get_value.return_value = ''
        
        warnings = self.service.detect_out_of_bounds_features()
        
        self.assertEqual(warnings, [])
        # Check that it was called at least once with recording_areas_layer
        self.settings_manager.get_value.assert_any_call('recording_areas_layer')
    
    def test_detect_out_of_bounds_features_no_recording_areas_layer(self):
        """Test detection when recording areas layer is not found."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_bounds_warnings': True,
            'bounds_max_distance': 0.2,
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id'
        }.get(key, default)
        
        self.layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_out_of_bounds_features()
        
        self.assertEqual(warnings, [])
        self.layer_service.get_layer_by_id.assert_called_with('recording_layer_id')
    
    def test_detect_out_of_bounds_features_no_objects_layer(self):
        """Test detection when objects layer is not configured."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': '',
            'features_layer': '',
            'small_finds_layer': ''
        }.get(key, default)
        
        recording_layer = Mock()
        self.layer_service.get_layer_by_id.return_value = recording_layer
        
        warnings = self.service.detect_out_of_bounds_features()
        
        self.assertEqual(warnings, [])
    
    def test_detect_out_of_bounds_features_no_relation(self):
        """Test detection when no relation exists between layers."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")
        
        self.settings_manager.get_value.side_effect = lambda key: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id'
        }.get(key, '')
        
        recording_layer = Mock()
        objects_layer = Mock()
        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'objects_layer_id': objects_layer
        }.get(layer_id)
        
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {}
        
        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager
            
            warnings = self.service.detect_out_of_bounds_features()
            
            self.assertEqual(warnings, [])
    
    def test_detect_out_of_bounds_features_with_relation_no_out_of_bounds(self):
        """Test detection when features are within bounds."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")
        
        self.settings_manager.get_value.side_effect = lambda key: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id'
        }.get(key, '')
        
        # Create mock layers
        recording_layer = Mock()
        definitive_objects_layer = Mock()
        definitive_objects_layer.id.return_value = 'objects_layer_id'
        definitive_objects_layer.name.return_value = "Objects"

        temp_objects_layer = Mock()
        temp_objects_layer.id.return_value = 'temp_objects_layer_id'
        temp_objects_layer.name.return_value = "New Objects"
        
        # Create mock geometries
        recording_geometry = QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 10), QgsPointXY(0, 0)]])
        feature_geometry = QgsGeometry.fromPointXY(QgsPointXY(5, 5))
        
        # Create mock features
        recording_feature = Mock()
        recording_feature.id.return_value = 1
        recording_feature.geometry.return_value = recording_geometry
        
        feature = Mock()
        feature.geometry.return_value = feature_geometry
        feature.attribute.return_value = 1  # recording area ID
        feature.id.return_value = 1
        
        # Set up layer mocks
        recording_layer.getFeatures.return_value = [recording_feature]
        temp_objects_layer.getFeatures.return_value = [feature]
        temp_objects_layer.fields.return_value = Mock()
        temp_objects_layer.fields.return_value.indexOf.return_value = 0
        
        self.layer_service.get_layer_by_name.side_effect = lambda name: {
            "New Objects": temp_objects_layer,
            "New Features": None,
            "New Small Finds": None,
            "Imported_CSV_Points": None,
        }.get(name)

        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'temp_objects_layer_id': temp_objects_layer,
            'objects_layer_id': definitive_objects_layer,
        }.get(layer_id)
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = definitive_objects_layer
        mock_relation.referencedLayer.return_value = recording_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        
        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager
            
            warnings = self.service.detect_out_of_bounds_features()
            
            self.assertEqual(warnings, [])
    
    def test_detect_out_of_bounds_features_with_out_of_bounds(self):
        """Test detection when features are out of bounds."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")
        
        self.settings_manager.get_value.side_effect = lambda key: {
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'objects_number_field': 'number'
        }.get(key, '')
        
        # Create mock layers
        recording_layer = Mock()
        definitive_objects_layer = Mock()
        definitive_objects_layer.id.return_value = 'objects_layer_id'
        definitive_objects_layer.name.return_value = "Objects"

        temp_objects_layer = Mock()
        temp_objects_layer.id.return_value = 'temp_objects_layer_id'
        temp_objects_layer.name.return_value = "New Objects"
        
        # Create mock geometries
        recording_geometry = QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 10), QgsPointXY(0, 0)]])
        feature_geometry = QgsGeometry.fromPointXY(QgsPointXY(15, 15))  # Outside the polygon
        
        # Create mock features
        recording_feature = Mock()
        recording_feature.id.return_value = 1
        recording_feature.geometry.return_value = recording_geometry
        recording_feature.attribute.return_value = "Test Area"  # name
        
        feature = Mock()
        feature.geometry.return_value = feature_geometry
        feature.attribute.side_effect = lambda idx: 1 if idx == 0 else "123"  # recording area ID, then number
        feature.id.return_value = 1
        feature.fields.return_value = Mock()
        feature.fields.return_value.indexOf.return_value = 0
        
        # Set up layer mocks
        recording_layer.getFeatures.return_value = [recording_feature]
        recording_layer.fields.return_value = Mock()
        recording_layer.fields.return_value.indexOf.return_value = 0  # name field index
        
        temp_objects_layer.getFeatures.return_value = [feature]
        temp_objects_layer.fields.return_value = Mock()
        temp_objects_layer.fields.return_value.indexOf.return_value = 0
        
        self.layer_service.get_layer_by_name.side_effect = lambda name: {
            "New Objects": temp_objects_layer,
            "New Features": None,
            "New Small Finds": None,
            "Imported_CSV_Points": None,
        }.get(name)

        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'temp_objects_layer_id': temp_objects_layer,
            'objects_layer_id': definitive_objects_layer,
        }.get(layer_id)
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = definitive_objects_layer
        mock_relation.referencedLayer.return_value = recording_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        
        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager
            
            warnings = self.service.detect_out_of_bounds_features()
            
            self.assertEqual(len(warnings), 1)
            self.assertIsInstance(warnings[0], WarningData)
            self.assertIn("Test Area", warnings[0].message)
            self.assertIn("Object 123", warnings[0].message)
    
    def test_get_recording_area_field(self):
        """Test getting recording area field from relations."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")
        
        layer = Mock()
        recording_areas_layer = Mock()
        
        # Mock relation
        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = layer
        mock_relation.referencedLayer.return_value = recording_areas_layer
        mock_relation.fieldPairs.return_value = {'recording_area_field': 'id'}
        
        # Mock QGIS project and relation manager
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {'relation1': mock_relation}
        
        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager
            
            result = self.service._get_recording_area_field(layer, recording_areas_layer)
            
            self.assertEqual(result, 'recording_area_field')
    
    def test_get_recording_area_field_no_relation(self):
        """Test getting recording area field when no relation exists."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")
        
        layer = Mock()
        recording_areas_layer = Mock()
        
        # Mock QGIS project and relation manager with no relations
        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {}
        
        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager
            
            result = self.service._get_recording_area_field(layer, recording_areas_layer)
            
            self.assertIsNone(result)
    
    def test_get_recording_area_name_with_name_field(self):
        """Test getting recording area name when name field exists."""
        recording_areas_layer = Mock()
        recording_areas_layer.fields.return_value = Mock()
        recording_areas_layer.fields.return_value.indexOf.return_value = 0  # name field found
        
        feature = Mock()
        feature.id.return_value = 1
        feature.attribute.return_value = "Test Area"
        
        recording_areas_layer.getFeatures.return_value = [feature]
        
        result = self.service._get_recording_area_name(recording_areas_layer, 1)
        
        self.assertEqual(result, "Test Area")
    
    def test_get_recording_area_name_without_name_field(self):
        """Test getting recording area name when name field doesn't exist."""
        recording_areas_layer = Mock()
        recording_areas_layer.fields.return_value = Mock()
        recording_areas_layer.fields.return_value.indexOf.return_value = -1  # name field not found
        
        feature = Mock()
        feature.id.return_value = 1
        
        recording_areas_layer.getFeatures.return_value = [feature]
        
        result = self.service._get_recording_area_name(recording_areas_layer, 1)
        
        self.assertEqual(result, "1")
    
    def test_get_feature_identifier_with_number_field(self):
        """Test getting feature identifier when number field exists."""
        self.settings_manager.get_value.return_value = 'number'
        
        feature = Mock()
        feature.fields.return_value = Mock()
        feature.fields.return_value.indexOf.return_value = 0
        feature.attribute.return_value = "123"
        
        result = self.service._get_feature_identifier(feature, "Objects")
        
        self.assertEqual(result, "Object 123")
    
    def test_get_feature_identifier_without_number_field(self):
        """Test getting feature identifier when number field doesn't exist."""
        self.settings_manager.get_value.return_value = None
        
        feature = Mock()
        feature.id.return_value = 1
        
        result = self.service._get_feature_identifier(feature, "Objects")
        
        self.assertEqual(result, "Objects 1")
    
    def test_create_out_of_bounds_warning_single_feature(self):
        """Test creating warning message for single feature."""
        recording_area_name = "Test Area"
        layer_type = "Objects"
        feature_identifiers = ["Object 123"]
        max_distance = 0.5
        
        # Mock the translation service to return the actual message
        self.translation_service.translate.return_value = f"{feature_identifiers[0]} in recording area '{recording_area_name}' is located 50.0 cm outside the recording area boundary (maximum allowed: 20.0 cm)"
        
        result = self.service._create_out_of_bounds_warning(
            recording_area_name, layer_type, feature_identifiers, max_distance
        )
        
        self.assertIn("Object 123", result)
        self.assertIn("Test Area", result)
        self.assertIn("50.0 cm", result)  # 0.5 meters = 50 cm
        self.translation_service.translate.assert_called_once()
    
    def test_create_out_of_bounds_warning_multiple_features(self):
        """Test creating warning message for multiple features."""
        recording_area_name = "Test Area"
        layer_type = "Objects"
        feature_identifiers = ["Object 123", "Object 124", "Object 125"]
        max_distance = 0.3
        
        # Mock the translation service to return the actual message
        self.translation_service.translate.return_value = f"{len(feature_identifiers)} features in recording area '{recording_area_name}' is located 30.0 cm outside the recording area boundary (maximum allowed: 20.0 cm)"
        
        result = self.service._create_out_of_bounds_warning(
            recording_area_name, layer_type, feature_identifiers, max_distance
        )
        
        self.assertIn("3 features", result)
        self.assertIn("Test Area", result)
        self.assertIn("30.0 cm", result)  # 0.3 meters = 30 cm

    def test_skips_definitive_layers_during_import_when_temp_layer_missing(self):
        """Only pending temp import layers are checked while an import is in progress."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_bounds_warnings': True,
            'bounds_max_distance': 0.2,
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'features_layer': 'features_layer_id',
            'small_finds_layer': 'small_finds_layer_id',
        }.get(key, default)

        recording_layer = Mock()
        recording_layer.name.return_value = "Recording Areas"
        recording_layer.featureCount.return_value = 0

        temp_objects_layer = Mock()
        temp_objects_layer.name.return_value = "New Objects"
        temp_objects_layer.id.return_value = 'temp_objects_layer_id'

        features_layer = Mock()
        features_layer.name.return_value = "Features"
        features_layer.getFeatures.side_effect = AssertionError(
            "Definitive features layer must not be scanned during object import"
        )

        self.layer_service.get_layer_by_name.side_effect = lambda name: {
            "New Objects": temp_objects_layer,
            "New Features": None,
            "New Small Finds": None,
            "Imported_CSV_Points": None,
        }.get(name)

        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'temp_objects_layer_id': temp_objects_layer,
            'features_layer_id': features_layer,
        }.get(layer_id)

        with patch.object(
            self.service,
            '_detect_out_of_bounds_in_layer',
            return_value=[],
        ) as detect_mock:
            warnings = self.service.detect_out_of_bounds_features()

        self.assertEqual(warnings, [])
        detect_mock.assert_called_once_with(
            'temp_objects_layer_id', recording_layer, "Objects"
        )

    def test_skips_definitive_layers_when_only_csv_temp_layer_present(self):
        """CSV-only import must not scan definitive object/feature/small-find layers."""
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_bounds_warnings': True,
            'bounds_max_distance': 0.2,
            'recording_areas_layer': 'recording_layer_id',
            'objects_layer': 'objects_layer_id',
            'features_layer': 'features_layer_id',
            'small_finds_layer': 'small_finds_layer_id',
            'total_station_points_layer': 'def_topo_id',
        }.get(key, default)

        recording_layer = Mock()
        recording_layer.name.return_value = "Recording Areas"
        recording_layer.featureCount.return_value = 0

        temp_topo = Mock()
        temp_topo.name.return_value = "Imported_CSV_Points"
        temp_topo.id.return_value = 'temp_topo_id'

        definitive_objects = Mock()
        definitive_objects.getFeatures.side_effect = AssertionError(
            "Definitive objects layer must not be scanned during CSV-only import"
        )

        self.layer_service.get_layer_by_name.side_effect = lambda name: {
            "Imported_CSV_Points": temp_topo,
            "New Objects": None,
            "New Features": None,
            "New Small Finds": None,
        }.get(name)

        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'objects_layer_id': definitive_objects,
            'def_topo_id': Mock(),
            'temp_topo_id': temp_topo,
        }.get(layer_id)

        with patch.object(
            self.service,
            '_detect_topo_points_out_of_bounds',
            return_value=[],
        ) as topo_mock:
            warnings = self.service.detect_out_of_bounds_features()

        self.assertEqual(warnings, [])
        topo_mock.assert_called_once()

    def test_detect_topo_points_out_of_bounds_via_indirect_relation(self):
        """Topo points linked to recording areas through an intermediate layer."""
        if not QGIS_AVAILABLE:
            self.skipTest("QGIS not available")

        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'enable_bounds_warnings': True,
            'bounds_max_distance': 0.2,
            'recording_areas_layer': 'recording_layer_id',
            'total_station_points_layer': 'def_topo_id',
        }.get(key, default)

        recording_geometry = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 10), QgsPointXY(0, 0)]]
        )
        point_geometry = QgsGeometry.fromPointXY(QgsPointXY(15, 15))

        recording_layer = Mock()
        recording_layer.name.return_value = "Recording Areas"
        recording_layer.featureCount.return_value = 1
        recording_layer.fields.return_value = Mock()
        recording_layer.fields.return_value.indexOf.return_value = 0
        recording_layer.displayExpression.return_value = ""

        recording_feature = Mock()
        recording_feature.id.return_value = 1
        recording_feature.geometry.return_value = recording_geometry
        recording_feature.isValid.return_value = True
        recording_feature.attribute.return_value = "Area A"
        recording_layer.getFeatures.return_value = [recording_feature]

        def_topo = Mock()
        def_topo.id.return_value = 'def_topo_id'
        def_topo.name.return_value = "Topo Points"

        inter = Mock()
        inter.id.return_value = 'inter_id'
        inter.name.return_value = "Link"

        temp_topo = Mock()
        temp_topo.id.return_value = 'temp_topo_id'
        temp_topo.name.return_value = "Imported_CSV_Points"
        temp_topo.featureCount.return_value = 1
        temp_topo.fields.return_value = Mock()
        temp_topo.fields.return_value.indexOf.side_effect = lambda name: 0 if name == 'identifier' else -1
        temp_topo.fields.return_value.__getitem__ = lambda self, idx: Mock(name='identifier')

        point_feature = Mock()
        point_feature.geometry.return_value = point_geometry
        point_feature.id.return_value = 1
        point_feature.fields.return_value = temp_topo.fields.return_value
        point_feature.attribute.side_effect = lambda idx: 'PT1' if idx == 0 else None
        temp_topo.getFeatures.return_value = [point_feature]

        inter.fields.return_value = Mock()
        inter.fields.return_value.indexOf.side_effect = lambda name: {
            'pt_pk': 0,
            'ra_fk': 1,
        }.get(name, -1)
        inter.fields.return_value.__iter__ = lambda self=None: iter(
            [Mock(name='pt_pk'), Mock(name='ra_fk')]
        )

        link_feature = Mock()
        link_feature.attribute.side_effect = lambda idx: 'PT1' if idx == 0 else 1
        inter.getFeatures.return_value = [link_feature]

        def_topo.fields.return_value = Mock()
        def_topo.fields.return_value.indexOf.return_value = 0
        def_topo.fields.return_value.__iter__ = lambda self=None: iter([Mock(name='pt_fk')])

        rel_pi = Mock()
        rel_pi.id.return_value = 'rel_pi'
        rel_pi.fieldPairs.return_value = {'pt_fk': 'pt_pk'}
        rel_pi.referencingLayer.return_value = def_topo
        rel_pi.referencedLayer.return_value = inter

        rel_ir = Mock()
        rel_ir.id.return_value = 'rel_ir'
        rel_ir.fieldPairs.return_value = {'ra_fk': 'id'}
        rel_ir.referencingLayer.return_value = inter
        rel_ir.referencedLayer.return_value = recording_layer

        self.layer_service.get_layer_by_name.side_effect = lambda name: {
            "Imported_CSV_Points": temp_topo,
            "New Objects": None,
            "New Features": None,
            "New Small Finds": None,
        }.get(name)

        self.layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            'recording_layer_id': recording_layer,
            'def_topo_id': def_topo,
            'temp_topo_id': temp_topo,
        }.get(layer_id)

        mock_project = Mock()
        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {
            'rel_pi': rel_pi,
            'rel_ir': rel_ir,
        }

        with patch('qgis.core.QgsProject') as mock_qgs_project:
            mock_qgs_project.instance.return_value = mock_project
            mock_project.relationManager.return_value = mock_relation_manager

            warnings = self.service.detect_out_of_bounds_features()

        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertIn("Area A", warnings[0].message)

    def test_skips_recording_area_index_when_layer_has_no_geometry(self):
        """Avoid building the recording-area index when no feature has geometry."""
        layer = Mock()
        layer.name.return_value = "New Objects"
        layer.fields.return_value = Mock()
        layer.fields.return_value.indexOf.return_value = 0

        feature_without_geometry = Mock()
        feature_without_geometry.geometry.return_value = None
        layer.getFeatures.return_value = [feature_without_geometry]

        recording_areas_layer = Mock()
        recording_areas_layer.getFeatures.side_effect = AssertionError(
            "Recording areas must not be indexed when there is nothing to check"
        )

        self.layer_service.get_layer_by_id.return_value = layer

        with patch.object(self.service, '_get_recording_area_field', return_value='recording_area_field'), \
             patch.object(self.service, '_get_relation_for_layer') as relation_mock:
            relation_mock.return_value.fieldPairs.return_value = {
                'recording_area_field': 'id',
            }
            warnings = self.service._detect_out_of_bounds_in_layer(
                'layer_id', recording_areas_layer, "Objects"
            )

        self.assertEqual(warnings, [])
        recording_areas_layer.getFeatures.assert_not_called()


if __name__ == '__main__':
    unittest.main() 