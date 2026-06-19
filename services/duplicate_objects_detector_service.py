"""
Duplicate Objects Detector Service for ArcheoSync plugin.

This module provides a service that detects duplicate objects with the same
recording area and number within the "New Objects" layer and the original
objects layer.

Key Features:
- Detects objects with same recording area and number in both layers
- Provides detailed warnings for each duplicate found
- Integrates with existing layer service and settings
- Supports translation for warning messages
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles duplicate object detection
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection rules

Usage:
    detector = DuplicateObjectsDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
    )

    warnings = detector.detect_duplicate_objects()
"""

from typing import Any, List, Optional, Tuple, Union

from qgis.PyQt.QtCore import QObject

try:
    from ..core.data_structures import WarningData
    from ..core.interfaces import ILayerService, ISettingsManager
    from ..core.ui_responsiveness import maybe_yield_to_ui
except ImportError:
    from core.data_structures import WarningData
    from core.interfaces import ILayerService, ISettingsManager
    from core.ui_responsiveness import maybe_yield_to_ui


class DuplicateObjectsDetectorService(QObject):
    """
    Service for detecting duplicate objects with the same recording area and number.

    Detects objects that have the same recording area and number within:
    - The "New Objects" layer (imported objects)
    - The original objects layer (existing objects)
    - Between both layers
    """

    def __init__(self, settings_manager: ISettingsManager, layer_service: ILayerService):
        super().__init__()
        self._settings_manager = settings_manager
        self._layer_service = layer_service

    def _find_layer_by_name(self, layer_name: str) -> Optional[Any]:
        """Find a layer by name in the current QGIS project."""
        try:
            from qgis.core import QgsProject

            project = QgsProject.instance()
            for layer in project.mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
        except Exception as exc:
            print(f"Error finding layer by name: {exc}")
            return None

    def detect_duplicate_objects(self) -> List[Union[str, WarningData]]:
        """
        Detect duplicate objects with the same recording area and number.

        Returns:
            List of warning messages or structured warning data about duplicate objects
        """
        if not self._settings_manager.get_value("enable_duplicate_objects_warnings", True):
            print("[DEBUG] Duplicate objects warnings are disabled, skipping detection")
            return []
        warnings: List[Union[str, WarningData]] = []

        try:
            objects_layer_id = self._settings_manager.get_value("objects_layer")
            recording_areas_layer_id = self._settings_manager.get_value("recording_areas_layer")
            number_field = self._settings_manager.get_value("objects_number_field")

            if not objects_layer_id or not recording_areas_layer_id or not number_field:
                return warnings

            objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)

            if not objects_layer or not recording_areas_layer:
                return warnings

            recording_area_field = self._resolve_recording_area_field(objects_layer)
            if not recording_area_field:
                return warnings

            resolved_number_field = self._resolve_field_name_on_layer(objects_layer, number_field)
            if not resolved_number_field:
                return warnings

            original_warnings = self._detect_duplicates_within_layer(
                objects_layer,
                recording_areas_layer,
                resolved_number_field,
                recording_area_field,
                objects_layer.name(),
            )
            warnings.extend(original_warnings)

            new_objects_layer = self._find_layer_by_name("New Objects")
            if new_objects_layer:
                new_warnings = self._detect_duplicates_within_layer(
                    new_objects_layer,
                    recording_areas_layer,
                    resolved_number_field,
                    recording_area_field,
                    "New Objects",
                )
                warnings.extend(new_warnings)

                between_warnings = self._detect_duplicates_between_layers(
                    objects_layer,
                    new_objects_layer,
                    recording_areas_layer,
                    resolved_number_field,
                    recording_area_field,
                )
                warnings.extend(between_warnings)

            warnings = self._deduplicate_warnings_by_object_identity(warnings)

        except Exception as exc:
            print(f"Error in duplicate objects detection: {exc}")
            import traceback

            traceback.print_exc()

        return warnings

    def _deduplicate_warnings_by_object_identity(
        self,
        warnings: List[Union[str, WarningData]],
    ) -> List[Union[str, WarningData]]:
        """Keep a single warning per recording area / object number pair."""
        deduplicated: List[Union[str, WarningData]] = []
        seen_keys = set()

        for warning in warnings:
            if isinstance(warning, WarningData):
                identity = (
                    warning.recording_area_name,
                    warning.object_number,
                )
                if identity in seen_keys:
                    continue
                seen_keys.add(identity)
            deduplicated.append(warning)

        return deduplicated

    @staticmethod
    def _normalize_identity_value(value: Any) -> Any:
        """Normalize attribute values used in recording-area / number identity keys."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "" or stripped.lower() == "null":
                return None
            return stripped
        try:
            if isinstance(value, float) and value.is_integer():
                return int(value)
        except (TypeError, ValueError):
            pass
        return value

    @staticmethod
    def _identity_value_is_set(value: Any) -> bool:
        """Return True when a zone or number value can participate in duplicate detection."""
        return DuplicateObjectsDetectorService._normalize_identity_value(value) is not None

    def _get_field_index_case_insensitive(self, layer: Any, field_name: str) -> int:
        """Return a field index, matching field names case-insensitively when needed."""
        field_idx = layer.fields().indexOf(field_name)
        if field_idx >= 0:
            return field_idx
        target = field_name.lower()
        for field in layer.fields():
            if field.name().lower() == target:
                return layer.fields().indexOf(field.name())
        return -1

    def _resolve_field_name_on_layer(self, layer: Any, field_name: str) -> Optional[str]:
        """Return the canonical field name present on ``layer`` for ``field_name``."""
        field_idx = self._get_field_index_case_insensitive(layer, field_name)
        if field_idx < 0:
            return None
        return layer.fields().at(field_idx).name()

    def _field_exists_on_layer(self, layer: Any, field_name: str) -> bool:
        """Return True when ``field_name`` exists on ``layer`` (case-insensitive)."""
        return self._get_field_index_case_insensitive(layer, field_name) >= 0

    def _get_recording_area_field_from_relation(
        self,
        objects_layer: Any,
        recording_areas_layer: Any,
    ) -> Optional[str]:
        """Return the objects-layer field that references recording areas via project relations."""
        try:
            from qgis.core import QgsProject

            relation_manager = QgsProject.instance().relationManager()
            objects_layer_id = objects_layer.id()
            recording_areas_layer_id = recording_areas_layer.id()
            for relation in relation_manager.relations().values():
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                if referencing_layer is None or referenced_layer is None:
                    continue
                if (
                    referencing_layer.id() == objects_layer_id
                    and referenced_layer.id() == recording_areas_layer_id
                ):
                    field_pairs = relation.fieldPairs()
                    if field_pairs:
                        return list(field_pairs.keys())[0]
        except Exception as exc:
            print(f"Error resolving recording-area relation field: {exc}")
        return None

    def _resolve_recording_area_field(self, objects_layer: Any) -> Optional[str]:
        """
        Resolve the recording-area foreign-key field on the objects layer.

        Uses QGIS relations first, then configured settings fallbacks.
        """
        recording_areas_layer_id = self._settings_manager.get_value("recording_areas_layer", "")
        if recording_areas_layer_id:
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_areas_layer:
                relation_field = self._get_recording_area_field_from_relation(
                    objects_layer,
                    recording_areas_layer,
                )
                if relation_field and self._field_exists_on_layer(objects_layer, relation_field):
                    return self._resolve_field_name_on_layer(objects_layer, relation_field)

        configured_field = self._settings_manager.get_value("objects_recording_area_field", "")
        if configured_field and self._field_exists_on_layer(objects_layer, configured_field):
            return self._resolve_field_name_on_layer(objects_layer, configured_field)

        alternative_field = self._settings_manager.get_value(
            "alternative_objects_recording_area_field",
            "",
        )
        if alternative_field and self._field_exists_on_layer(objects_layer, alternative_field):
            return self._resolve_field_name_on_layer(objects_layer, alternative_field)

        return None

    def _collect_recording_area_field_candidates(
        self,
        objects_layer: Any,
        preferred_field: Optional[str] = None,
    ) -> List[str]:
        """Return ordered recording-area field names to try on ``objects_layer``."""
        candidates: List[str] = []

        def add_candidate(field_name: Optional[str]) -> None:
            if not field_name:
                return
            resolved = self._resolve_field_name_on_layer(objects_layer, field_name)
            if resolved and resolved not in candidates:
                candidates.append(resolved)

        add_candidate(preferred_field)
        add_candidate(self._resolve_recording_area_field(objects_layer))

        configured_field = self._settings_manager.get_value("objects_recording_area_field", "")
        add_candidate(configured_field)

        alternative_field = self._settings_manager.get_value(
            "alternative_objects_recording_area_field",
            "",
        )
        add_candidate(alternative_field)
        return candidates

    def _feature_identity_key(
        self,
        feature: Any,
        objects_layer: Any,
        number_field: str,
        recording_area_field: str,
    ) -> Optional[Tuple[Any, Any]]:
        """Build a (recording_area_id, object_number) identity key for a feature."""
        resolved_number_field = self._resolve_field_name_on_layer(objects_layer, number_field)
        if not resolved_number_field:
            return None

        number_idx = self._get_field_index_case_insensitive(objects_layer, resolved_number_field)
        if number_idx < 0:
            return None

        object_number = self._normalize_identity_value(feature.attribute(number_idx))
        if not self._identity_value_is_set(object_number):
            return None

        recording_area_id = None
        for candidate_field in self._collect_recording_area_field_candidates(
            objects_layer,
            preferred_field=recording_area_field,
        ):
            recording_area_idx = self._get_field_index_case_insensitive(
                objects_layer,
                candidate_field,
            )
            if recording_area_idx < 0:
                continue
            candidate_value = self._normalize_identity_value(
                feature.attribute(recording_area_idx)
            )
            if self._identity_value_is_set(candidate_value):
                recording_area_id = candidate_value
                break

        if not self._identity_value_is_set(recording_area_id):
            return None
        return (recording_area_id, object_number)

    def _detect_duplicates_within_layer(
        self,
        objects_layer: Any,
        recording_areas_layer: Any,
        number_field: str,
        recording_area_field: str,
        layer_name: str,
    ) -> List[Union[str, WarningData]]:
        """Detect duplicates within a single layer."""
        warnings: List[Union[str, WarningData]] = []

        try:
            duplicates: dict = {}
            for feature in objects_layer.getFeatures():
                maybe_yield_to_ui()
                identity = self._feature_identity_key(
                    feature,
                    objects_layer,
                    number_field,
                    recording_area_field,
                )
                if identity is None:
                    continue
                duplicates.setdefault(identity, []).append(feature)

            print(
                f"[DEBUG] Found {len(duplicates)} unique recording area/number combinations in {layer_name}"
            )

            for (recording_area_id, number), features in duplicates.items():
                if len(features) <= 1:
                    continue
                recording_area_name = self._get_recording_area_name(
                    recording_areas_layer,
                    recording_area_id,
                )
                warnings.append(
                    WarningData(
                        message=self._create_duplicate_warning(
                            recording_area_name,
                            len(features),
                            number,
                            layer_name,
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=layer_name,
                        filter_expression=(
                            f'"{recording_area_field}" = \'{recording_area_id}\' '
                            f'AND "{number_field}" = {number}'
                        ),
                        object_number=number,
                    )
                )

        except Exception as exc:
            print(f"[DEBUG] Error in _detect_duplicates_within_layer: {exc}")
            import traceback

            traceback.print_exc()

        return warnings

    def _detect_duplicates_between_layers(
        self,
        original_objects_layer: Any,
        new_objects_layer: Any,
        recording_areas_layer: Any,
        number_field: str,
        recording_area_field: str,
    ) -> List[Union[str, WarningData]]:
        """Detect duplicates between "New Objects" and original objects layers."""
        warnings: List[Union[str, WarningData]] = []

        try:
            original_objects: dict = {}
            for feature in original_objects_layer.getFeatures():
                maybe_yield_to_ui()
                identity = self._feature_identity_key(
                    feature,
                    original_objects_layer,
                    number_field,
                    recording_area_field,
                )
                if identity is None:
                    continue
                original_objects.setdefault(identity, []).append(feature)

            warned_between_layer_keys = set()
            for feature in new_objects_layer.getFeatures():
                maybe_yield_to_ui()
                identity = self._feature_identity_key(
                    feature,
                    new_objects_layer,
                    number_field,
                    recording_area_field,
                )
                if identity is None:
                    continue
                if identity in original_objects and identity not in warned_between_layer_keys:
                    warned_between_layer_keys.add(identity)
                    recording_area_id, number = identity
                    recording_area_name = self._get_recording_area_name(
                        recording_areas_layer,
                        recording_area_id,
                    )
                    warnings.append(
                        WarningData(
                            message=self._create_duplicate_warning(
                                recording_area_name,
                                len(original_objects[identity]),
                                number,
                                f"{original_objects_layer.name()} and New Objects",
                            ),
                            recording_area_name=recording_area_name,
                            layer_name=original_objects_layer.name(),
                            filter_expression=(
                                f'"{recording_area_field}" = \'{recording_area_id}\' '
                                f'AND "{number_field}" = {number}'
                            ),
                            object_number=number,
                            second_layer_name="New Objects",
                            second_filter_expression=(
                                f'"{recording_area_field}" = \'{recording_area_id}\' '
                                f'AND "{number_field}" = {number}'
                            ),
                        )
                    )

        except Exception as exc:
            print(f"[DEBUG] Error in _detect_duplicates_between_layers: {exc}")
            import traceback

            traceback.print_exc()

        return warnings

    def _get_recording_area_name(self, recording_areas_layer: Any, recording_area_id: Any) -> str:
        """Get the name of a recording area by its ID."""
        try:
            name_fields = ["name", "title", "label", "description", "comment"]
            for field_name in name_fields:
                field_idx = recording_areas_layer.fields().indexOf(field_name)
                if field_idx >= 0:
                    for feature in recording_areas_layer.getFeatures():
                        maybe_yield_to_ui()
                        if feature.id() == recording_area_id:
                            name_value = feature[field_idx]
                            if name_value and str(name_value) != "NULL":
                                return str(name_value)
            return str(recording_area_id)
        except Exception as exc:
            print(f"Error getting recording area name: {exc}")
            return str(recording_area_id)

    def _create_duplicate_warning(
        self,
        recording_area_name: str,
        count: int,
        number: Any,
        layer_name: str,
    ) -> str:
        """Create a warning message for duplicate objects."""
        try:
            message = self.tr(
                f"Recording Area '{recording_area_name}' has {count} objects with number {number} in {layer_name}"
            )
        except Exception:
            message = (
                f"Recording Area '{recording_area_name}' has {count} objects with number {number} "
                f"in {layer_name}"
            )
        return message
