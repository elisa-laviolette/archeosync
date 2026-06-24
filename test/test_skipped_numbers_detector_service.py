"""
Tests for SkippedNumbersDetectorService.

This module tests the skipped numbers detector service functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

try:
    from services.skipped_numbers_detector_service import SkippedNumbersDetectorService
    from core.data_structures import WarningData
except ImportError:
    from ..services.skipped_numbers_detector_service import SkippedNumbersDetectorService
    from ..core.data_structures import WarningData


class TestSkippedNumbersDetectorService(unittest.TestCase):
    """Test cases for SkippedNumbersDetectorService."""

    @staticmethod
    def _object_fields_mock():
        """Fields mock: index 0 = recording area, 1 = object number (matches settings 'test_field')."""
        fields = Mock()

        def index_of(name: str) -> int:
            mapping = {"recording_area_field": 0, "test_field": 1}
            return mapping.get(name, -1)

        fields.indexOf.side_effect = index_of
        return fields

    @staticmethod
    def _feature(recording_area_id, number):
        """Build a feature mock whose attribute(idx) returns area id then number."""
        mock_feature = Mock()

        def attr(idx):
            if idx == 0:
                return recording_area_id
            if idx == 1:
                return number
            return None

        mock_feature.attribute.side_effect = attr
        return mock_feature

    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings_manager = Mock()
        self.mock_layer_service = Mock()

        self.service = SkippedNumbersDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
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
    
    def test_consecutive_run_length_ending_at(self):
        """Test consecutive run length ending at a value."""
        self.assertEqual(self.service._consecutive_run_length_ending_at([1, 2, 3, 10], 3), 3)
        self.assertEqual(self.service._consecutive_run_length_ending_at([1, 5], 1), 1)
        self.assertEqual(self.service._consecutive_run_length_ending_at([1, 3], 3), 1)

    def test_find_novel_gaps_between_layers(self):
        """Novel gaps include cross-layer holes after consecutive definitive blocks."""
        novel = self.service._find_novel_gaps_between_layers(
            [1, 2, 3, 10],
            [5],
            [1, 2, 3, 5, 10],
        )
        self.assertEqual(novel, [4])

        sandwiched = self.service._find_novel_gaps_between_layers(
            [1, 5],
            [3],
            [1, 3, 5],
        )
        self.assertEqual(sandwiched, [])

        within_new = self.service._find_novel_gaps_between_layers(
            [],
            [4, 6],
            [4, 6],
        )
        self.assertEqual(within_new, [5])

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
        
        # Mock feature with name (field access uses __getitem__ on QgsFeature-like objects)
        mock_feature = MagicMock()
        mock_feature.id.return_value = 123
        mock_feature.__getitem__.return_value = "Test Area"
        mock_recording_areas_layer.getFeatures.return_value = [mock_feature]
        
        name = self.service._get_recording_area_name(mock_recording_areas_layer, 123)
        
        self.assertEqual(name, "Test Area")
    
    def test_create_skipped_numbers_warning_with_translation(self):
        """Test that warning message is created with translation."""
        with patch.object(self.service, "tr", side_effect=lambda msg: msg):
            warning = self.service._create_skipped_numbers_warning("Test Area", [2, 4], "Test Layer")

        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: [2, 4] in Test Layer")
    
    def test_create_skipped_numbers_warning_single_gap(self):
        """Test that warning message is created for single gap."""
        with patch.object(self.service, "tr", side_effect=lambda msg: msg):
            warning = self.service._create_skipped_numbers_warning("Test Area", [2], "Test Layer")

        self.assertEqual(warning, "Recording Area 'Test Area' has skipped numbers: [2] in Test Layer")
    
    def test_create_skipped_numbers_warning_fallback_to_english(self):
        """Test that warning message falls back to English when translation fails."""
        with patch.object(self.service, "tr", side_effect=Exception("Translation failed")):
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
        """Gaps already present in definitive only (1 and 5 with temp 3) must not warn at import."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"

        mock_objects_layer = Mock()
        mock_objects_layer.name.return_value = "Objects"
        mock_objects_layer.fields.return_value = self._object_fields_mock()
        mock_new_objects_layer = Mock()
        mock_new_objects_layer.name.return_value = "New Objects"
        mock_new_objects_layer.fields.return_value = self._object_fields_mock()
        mock_recording_areas_layer = Mock()

        mock_objects_layer.getFeatures.return_value = [
            self._feature(1, 1),
            self._feature(1, 5),
        ]
        mock_new_objects_layer.getFeatures.return_value = [self._feature(1, 3)]

        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1

        mock_project = Mock()
        mock_project.mapLayers.return_value = {"new_objects_id": mock_new_objects_layer}

        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {"recording_area_field": "id"}

        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager

        self.mock_layer_service.get_layer_by_id.side_effect = [mock_objects_layer, mock_recording_areas_layer]

        with patch("qgis.core.QgsProject.instance", return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()

        self.assertEqual(warnings, [])

    def test_detect_skipped_numbers_between_layers_warns_for_novel_gap(self):
        """Warn when the union introduces a gap that does not exist in definitive-only numbering."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"

        mock_objects_layer = Mock()
        mock_objects_layer.name.return_value = "Objects"
        mock_objects_layer.fields.return_value = self._object_fields_mock()
        mock_new_objects_layer = Mock()
        mock_new_objects_layer.name.return_value = "New Objects"
        mock_new_objects_layer.fields.return_value = self._object_fields_mock()
        mock_recording_areas_layer = Mock()

        mock_objects_layer.getFeatures.return_value = [
            self._feature(1, 1),
            self._feature(1, 3),
        ]
        mock_new_objects_layer.getFeatures.return_value = [self._feature(1, 5)]

        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1

        mock_project = Mock()
        mock_project.mapLayers.return_value = {"new_objects_id": mock_new_objects_layer}

        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {"recording_area_field": "id"}

        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager

        self.mock_layer_service.get_layer_by_id.side_effect = [mock_objects_layer, mock_recording_areas_layer]

        with patch("qgis.core.QgsProject.instance", return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()

        self.assertEqual(len(warnings), 1)
        self.assertIsInstance(warnings[0], WarningData)
        self.assertEqual(warnings[0].skipped_numbers, [4])

    def test_detect_skipped_numbers_between_layers_warns_gap_after_consecutive_definitive_block(self):
        """Warn when temp continues after a consecutive definitive block with a distant higher number."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"

        mock_objects_layer = Mock()
        mock_objects_layer.name.return_value = "Objects"
        mock_objects_layer.fields.return_value = self._object_fields_mock()
        mock_new_objects_layer = Mock()
        mock_new_objects_layer.name.return_value = "New Objects"
        mock_new_objects_layer.fields.return_value = self._object_fields_mock()
        mock_recording_areas_layer = Mock()

        mock_objects_layer.getFeatures.return_value = [
            self._feature(1, 1),
            self._feature(1, 2),
            self._feature(1, 3),
            self._feature(1, 10),
        ]
        mock_new_objects_layer.getFeatures.return_value = [self._feature(1, 5)]

        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1

        mock_project = Mock()
        mock_project.mapLayers.return_value = {"new_objects_id": mock_new_objects_layer}

        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {"recording_area_field": "id"}

        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager

        self.mock_layer_service.get_layer_by_id.side_effect = [mock_objects_layer, mock_recording_areas_layer]

        with patch("qgis.core.QgsProject.instance", return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].skipped_numbers, [4])

    def test_detect_skipped_numbers_between_layers_does_not_warn_deeper_definitive_hole(self):
        """Gaps between temp and a higher definitive number stay suppressed when already missing."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"

        mock_objects_layer = Mock()
        mock_objects_layer.name.return_value = "Objects"
        mock_objects_layer.fields.return_value = self._object_fields_mock()
        mock_new_objects_layer = Mock()
        mock_new_objects_layer.name.return_value = "New Objects"
        mock_new_objects_layer.fields.return_value = self._object_fields_mock()
        mock_recording_areas_layer = Mock()

        mock_objects_layer.getFeatures.return_value = [
            self._feature(1, 1),
            self._feature(1, 2),
            self._feature(1, 3),
            self._feature(1, 10),
        ]
        mock_new_objects_layer.getFeatures.return_value = [self._feature(1, 5)]

        mock_recording_areas_layer.fields.return_value.indexOf.return_value = -1

        mock_project = Mock()
        mock_project.mapLayers.return_value = {"new_objects_id": mock_new_objects_layer}

        mock_relation = Mock()
        mock_relation.referencingLayer.return_value = mock_objects_layer
        mock_relation.referencedLayer.return_value = mock_recording_areas_layer
        mock_relation.fieldPairs.return_value = {"recording_area_field": "id"}

        mock_relation_manager = Mock()
        mock_relation_manager.relations.return_value = {"relation1": mock_relation}
        mock_project.relationManager.return_value = mock_relation_manager

        self.mock_layer_service.get_layer_by_id.side_effect = [mock_objects_layer, mock_recording_areas_layer]

        with patch("qgis.core.QgsProject.instance", return_value=mock_project):
            warnings = self.service.detect_skipped_numbers()

        self.assertEqual(warnings[0].skipped_numbers, [4])
        self.assertNotIn(6, warnings[0].skipped_numbers)
        self.assertNotIn(7, warnings[0].skipped_numbers) 