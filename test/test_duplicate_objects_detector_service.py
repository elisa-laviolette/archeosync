"""
Tests for DuplicateObjectsDetectorService.

This module tests the duplicate objects detector service functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from services.duplicate_objects_detector_service import DuplicateObjectsDetectorService
    from core.data_structures import WarningData
except ImportError:
    from ..services.duplicate_objects_detector_service import DuplicateObjectsDetectorService
    from ..core.data_structures import WarningData


class TestDuplicateObjectsDetectorService(unittest.TestCase):
    """Test cases for DuplicateObjectsDetectorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings_manager = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        
        self.service = DuplicateObjectsDetectorService(
            settings_manager=self.mock_settings_manager,
            layer_service=self.mock_layer_service,
        )
    
    def test_detect_duplicate_objects_no_configuration(self):
        """Test that no warnings are returned when no configuration is set."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: None
        
        warnings = self.service.detect_duplicate_objects()
        
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_objects_no_layers(self):
        """Test that no warnings are returned when no layers are found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: "test_field"
        self.mock_layer_service.get_layer_by_id.return_value = None
        
        warnings = self.service.detect_duplicate_objects()
        
        self.assertEqual(warnings, [])
    
    def test_detect_duplicate_objects_no_new_objects_layer(self):
        """Test that no warnings are returned when no new objects layer is found."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            "enable_duplicate_objects_warnings": True,
            "objects_layer": "obj-id",
            "recording_areas_layer": "ra-id",
            "objects_number_field": "number",
        }.get(key, default)
        mock_layer = self._mock_layer_with_fields(["zone", "number"])
        recording_areas_layer = Mock()
        recording_areas_layer.getFeatures.return_value = []
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            "obj-id": mock_layer,
            "ra-id": recording_areas_layer,
        }.get(layer_id)
        self.service._find_layer_by_name = Mock(return_value=None)
        self.service._resolve_recording_area_field = Mock(return_value="zone")
        self.service._resolve_field_name_on_layer = Mock(return_value="number")

        with patch.object(self.service, "_build_identity_index", return_value={}) as mock_index, \
             patch.object(self.service, "_build_recording_area_name_lookup", return_value={}), \
             patch.object(self.service, "_warnings_from_within_layer_duplicates") as mock_within:
            warnings = self.service.detect_duplicate_objects()

        self.assertEqual(warnings, [])
        mock_index.assert_not_called()
        mock_within.assert_not_called()

    def test_detect_duplicate_objects_skips_within_definitive_layer(self):
        """Internal duplicates in the definitive layer must not produce warnings."""
        objects_layer = self._mock_layer_with_fields(["zone", "number"])
        objects_layer.name.return_value = "Objets relevés"
        recording_areas_layer = Mock()
        recording_areas_layer.getFeatures.return_value = []
        new_objects_layer = self._mock_layer_with_fields(["zone", "number"])

        self.mock_settings_manager.get_value.side_effect = lambda key, default=None: {
            "enable_duplicate_objects_warnings": True,
            "objects_layer": "obj-id",
            "recording_areas_layer": "ra-id",
            "objects_number_field": "number",
        }.get(key, default)
        self.mock_layer_service.get_layer_by_id.side_effect = lambda layer_id: {
            "obj-id": objects_layer,
            "ra-id": recording_areas_layer,
        }.get(layer_id)
        self.service._find_layer_by_name = Mock(return_value=new_objects_layer)
        self.service._resolve_recording_area_field = Mock(return_value="zone")
        self.service._resolve_field_name_on_layer = Mock(return_value="number")

        with patch.object(self.service, "_build_identity_index", side_effect=[{(1, 1): [Mock(), Mock()]}, {}]), \
             patch.object(self.service, "_build_recording_area_name_lookup", return_value={}), \
             patch.object(self.service, "_warnings_from_within_layer_duplicates", return_value=[]) as mock_within, \
             patch.object(self.service, "_detect_duplicates_between_layers", return_value=[]) as mock_between:
            warnings = self.service.detect_duplicate_objects()

        self.assertEqual(warnings, [])
        mock_within.assert_called_once()
        self.assertEqual(mock_within.call_args[0][5], "New Objects")
        mock_between.assert_called_once()
        original_index = mock_between.call_args.kwargs["original_index"]
        self.assertEqual(len(original_index[(1, 1)]), 2)
    
    def test_deduplicate_warnings_by_object_identity(self):
        """Only one warning per recording area / object number should be kept."""
        warnings = [
            WarningData(
                message="within",
                recording_area_name="Area A",
                layer_name="Objects",
                filter_expression="a",
                object_number=5,
            ),
            WarningData(
                message="between",
                recording_area_name="Area A",
                layer_name="New Objects",
                filter_expression="b",
                object_number=5,
            ),
        ]

        deduplicated = self.service._deduplicate_warnings_by_object_identity(warnings)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].message, "within")

    def _mock_layer_with_fields(self, field_names):
        """Build a mock layer whose fields().indexOf resolves field names to indices."""
        mock_layer = Mock()
        mock_fields = Mock()

        def index_of(field_name):
            lowered = {name.lower(): idx for idx, name in enumerate(field_names)}
            return lowered.get(field_name.lower(), -1)

        def at(index):
            field = Mock()
            field.name.return_value = field_names[index]
            return field

        mock_fields.indexOf.side_effect = index_of
        mock_fields.at.side_effect = at
        mock_layer.fields.return_value = mock_fields
        return mock_layer

    def _mock_feature_with_values(self, values_by_field):
        """Build a mock feature returning attribute values by field index."""
        mock_feature = Mock()

        def attribute(index):
            for field_name, value in values_by_field.items():
                if list(values_by_field.keys()).index(field_name) == index:
                    return value
            return None

        field_names = list(values_by_field.keys())
        indices = {name: idx for idx, name in enumerate(field_names)}
        mock_feature.attribute.side_effect = lambda index: values_by_field[field_names[index]]
        mock_feature.__getitem__.side_effect = lambda index: values_by_field[field_names[index]]
        return mock_feature

    def test_detect_duplicates_within_layer(self):
        """Test detection of duplicates within a single layer."""
        mock_layer = self._mock_layer_with_fields(["recording_area", "number_field"])
        mock_layer.name.return_value = "Test Layer"
        mock_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"recording_area": 1, "number_field": 123}),
            self._mock_feature_with_values({"recording_area": 1, "number_field": 123}),
            self._mock_feature_with_values({"recording_area": 1, "number_field": 456}),
        ]

        self.service._get_recording_area_name = Mock(return_value="Test Area")
        mock_recording_areas_layer = Mock()

        warnings = self.service._detect_duplicates_within_layer(
            mock_layer, mock_recording_areas_layer, "number_field", "recording_area", "Test Layer"
        )

        self.assertEqual(len(warnings), 1)
        self.assertIn("Test Area", warnings[0].message)
        self.assertIn("123", warnings[0].message)
        self.assertIn("Test Layer", warnings[0].message)

    def test_detect_duplicates_within_layer_case_insensitive_fields(self):
        """Field names from settings may differ in case from the layer schema."""
        mock_layer = self._mock_layer_with_fields(["Zone_ID", "Num"])
        mock_layer.name.return_value = "New Objects"
        mock_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"Zone_ID": 5, "Num": 7}),
            self._mock_feature_with_values({"Zone_ID": 5, "Num": 7}),
        ]

        self.service._get_recording_area_name = Mock(return_value="Zone A")

        warnings = self.service._detect_duplicates_within_layer(
            mock_layer, Mock(), "num", "zone_id", "New Objects"
        )

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].object_number, 7)

    def test_detect_duplicates_within_layer_normalizes_numeric_types(self):
        """Integer and float representations of the same number must match."""
        mock_layer = self._mock_layer_with_fields(["zone", "number"])
        mock_layer.name.return_value = "New Objects"
        mock_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone": 2, "number": 7}),
            self._mock_feature_with_values({"zone": 2, "number": 7.0}),
        ]

        self.service._get_recording_area_name = Mock(return_value="Zone B")

        warnings = self.service._detect_duplicates_within_layer(
            mock_layer, Mock(), "number", "zone", "New Objects"
        )

        self.assertEqual(len(warnings), 1)

    def test_resolve_recording_area_field_uses_settings_when_relation_missing(self):
        """Configured objects_recording_area_field is used when no QGIS relation exists."""
        mock_layer = self._mock_layer_with_fields(["zone_ref", "number"])

        def get_value(key, default=None):
            return {
                "recording_areas_layer": "ra-layer-id",
                "objects_recording_area_field": "zone_ref",
                "alternative_objects_recording_area_field": "",
            }.get(key, default)

        self.mock_settings_manager.get_value.side_effect = get_value
        self.mock_layer_service.get_layer_by_id.return_value = Mock()

        with patch.object(self.service, "_get_recording_area_field_from_relation", return_value=None):
            resolved = self.service._resolve_recording_area_field(mock_layer)

        self.assertEqual(resolved, "zone_ref")

    def test_detect_duplicates_between_layers_uses_alternative_recording_field(self):
        """New Objects may store the recording area in the alternative field name."""
        original_layer = self._mock_layer_with_fields(["zone_fk", "number"])
        new_layer = self._mock_layer_with_fields(["zone_text", "number"])
        original_layer.name.return_value = "Objects"
        original_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone_fk": 3, "number": 12}),
        ]
        new_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone_text": 3, "number": 12}),
        ]

        def get_value(key, default=None):
            return {
                "recording_areas_layer": "ra-layer-id",
                "objects_recording_area_field": "zone_fk",
                "alternative_objects_recording_area_field": "zone_text",
            }.get(key, default)

        self.mock_settings_manager.get_value.side_effect = get_value
        self.service._get_recording_area_name = Mock(return_value="Area C")

        warnings = self.service._detect_duplicates_between_layers(
            original_layer,
            new_layer,
            Mock(),
            "number",
            "zone_fk",
        )

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].object_number, 12)

    def test_detect_duplicates_between_layers(self):
        """Imported object with same zone/number as definitive layer triggers a warning."""
        original_layer = self._mock_layer_with_fields(["zone", "number"])
        new_layer = self._mock_layer_with_fields(["zone", "number"])
        original_layer.name.return_value = "Objects"
        original_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone": 3, "number": 12}),
        ]
        new_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone": 3, "number": 12}),
        ]

        self.service._get_recording_area_name = Mock(return_value="Area C")

        warnings = self.service._detect_duplicates_between_layers(
            original_layer,
            new_layer,
            Mock(),
            "number",
            "zone",
        )

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].second_layer_name, "New Objects")
    
    def test_get_recording_area_name_fallback(self):
        """Test getting recording area name with fallback to ID."""
        mock_recording_areas_layer = Mock()
        mock_fields = Mock()
        mock_fields.indexOf.return_value = -1
        mock_recording_areas_layer.fields.return_value = mock_fields

        mock_feature = Mock()
        mock_feature.isValid.return_value = False
        mock_recording_areas_layer.getFeature.return_value = mock_feature

        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)

        self.assertEqual(name, "1")

    def test_get_recording_area_name_with_display_expression(self):
        """Test getting recording area name using display expression."""
        mock_recording_areas_layer = Mock()
        mock_fields = Mock()
        mock_fields.indexOf.return_value = 0
        mock_recording_areas_layer.fields.return_value = mock_fields

        mock_feature = Mock()
        mock_feature.isValid.return_value = True
        mock_feature.__getitem__.return_value = "Display Name"
        mock_recording_areas_layer.getFeature.return_value = mock_feature

        name = self.service._get_recording_area_name(mock_recording_areas_layer, 1)

        self.assertEqual(name, "Display Name")
    
    def test_create_duplicate_warning_message(self):
        """Duplicate warning messages include area, count, number, and layer."""
        warning = self.service._create_duplicate_warning(
            recording_area_name="Test Area",
            count=2,
            number="123",
            layer_name="Test Layer",
        )

        self.assertIn("Test Area", warning)
        self.assertIn("123", warning)
        self.assertIn("Test Layer", warning)
        self.assertIn("2", warning)

    def test_build_identity_index_resolves_fields_once_per_layer(self):
        """Field resolution must not repeat for every feature in a large layer."""
        mock_layer = self._mock_layer_with_fields(["zone", "number"])
        features = [
            self._mock_feature_with_values({"zone": idx % 3, "number": idx})
            for idx in range(200)
        ]
        mock_layer.getFeatures.return_value = features

        with patch.object(
            self.service,
            "_collect_recording_area_field_candidates",
            wraps=self.service._collect_recording_area_field_candidates,
        ) as mock_collect:
            index = self.service._build_identity_index(
                mock_layer,
                "number",
                "zone",
            )

        self.assertEqual(len(index), 200)
        self.assertEqual(mock_collect.call_count, 1)

    def test_build_recording_area_name_lookup_indexes_all_features(self):
        """Recording area names are resolved once into a lookup table."""
        mock_recording_areas_layer = Mock()
        mock_fields = Mock()
        mock_fields.indexOf.side_effect = lambda name: 0 if name == "name" else -1
        mock_recording_areas_layer.fields.return_value = mock_fields

        features = []
        for feature_id, label in [(1, "Area One"), (2, "Area Two")]:
            feature = Mock()
            feature.id.return_value = feature_id
            feature.__getitem__.return_value = label
            features.append(feature)
        mock_recording_areas_layer.getFeatures.return_value = features

        lookup = self.service._build_recording_area_name_lookup(mock_recording_areas_layer)

        self.assertEqual(lookup[1], "Area One")
        self.assertEqual(lookup[2], "Area Two")

    def test_detect_duplicates_between_layers_reuses_original_index(self):
        """Between-layer detection should not rescan the original objects layer."""
        original_layer = self._mock_layer_with_fields(["zone", "number"])
        new_layer = self._mock_layer_with_fields(["zone", "number"])
        original_layer.name.return_value = "Objects"
        new_layer.getFeatures.return_value = [
            self._mock_feature_with_values({"zone": 3, "number": 12}),
        ]

        original_index = {
            (3, 12): [self._mock_feature_with_values({"zone": 3, "number": 12})],
        }
        self.service._get_recording_area_name = Mock(return_value="Area C")

        warnings = self.service._detect_duplicates_between_layers(
            original_layer,
            new_layer,
            Mock(),
            "number",
            "zone",
            original_index=original_index,
        )

        original_layer.getFeatures.assert_not_called()
        self.assertEqual(len(warnings), 1)


if __name__ == '__main__':
    unittest.main() 