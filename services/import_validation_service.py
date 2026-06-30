"""
Batched, UI-friendly copy of temporary import layers onto definitive project layers.

Validation keeps definitive layers in edit mode, applies QGIS default value expressions
via ``QgsVectorLayerUtils.createFeature``, and re-applies imported attributes so
self-referencing defaults cannot overwrite source values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    from ..core.ui_responsiveness import maybe_yield_to_ui
except ImportError:
    from core.ui_responsiveness import maybe_yield_to_ui


# One feature per Qt timer tick so the progress bar can repaint between copies.
DEFAULT_COPY_BATCH_SIZE = 1

# Yield to Qt while loading source features from disk.
FEATURE_LOAD_YIELD_EVERY = 25

IMPORT_LAYER_MAPPINGS: Dict[str, str] = {
    "New Objects": "objects_layer",
    "New Features": "features_layer",
    "New Small Finds": "small_finds_layer",
    "Imported_CSV_Points": "total_station_points_layer",
}

TEMPORARY_IMPORT_LAYER_NAMES = tuple(IMPORT_LAYER_MAPPINGS.keys())

_FID_FIELD_NAMES = frozenset({"fid", "id", "gid", "objectid", "featureid"})


def _feature_id(feature: Any) -> Optional[int]:
    """
    Return a QgsFeature id across QGIS API and test-mock variants.

    Uncommitted features in an edit buffer use negative temporary FIDs; these
    must be kept for post-validation selection. Only unassigned sentinels are
    rejected (``None``, ``0``, ``-1``).
    """
    fid: Any = None
    try:
        fid = feature.id()
    except TypeError:
        fid = getattr(feature, "id", None)
        if callable(fid):
            try:
                fid = fid()
            except Exception:
                return None
    except Exception:
        return None

    if fid is None or fid in (0, -1):
        return None
    if isinstance(fid, int):
        return fid
    return None


@dataclass
class LayerFieldMapping:
    """Precomputed field mapping for a source/target layer pair."""

    attribute_field_pairs: List[Tuple[int, int]]


@dataclass
class CopyBatchResult:
    """Outcome of copying one batch of features."""

    next_index: int
    copied_count: int
    error_count: int
    added_feature_ids: List[int] = field(default_factory=list)


@dataclass
class LayerCopyJob:
    """Work item: copy all features from a temporary layer to a definitive layer."""

    temp_layer_name: str
    definitive_layer_key: str
    source_layer: Any
    target_layer: Any
    field_mapping: LayerFieldMapping
    feature_count: int
    source_features: Optional[List[Any]] = None
    feature_index: int = 0
    copied_count: int = 0
    added_feature_ids: List[int] = field(default_factory=list)
    load_complete: bool = False
    load_iterator: Any = field(default=None, repr=False, compare=False)
    expression_context: Any = field(default=None, repr=False, compare=False)
    target_signals_blocked: bool = False


class ImportFeatureCopier:
    """
    Copy features from temporary import layers to definitive layers in batches.

    Uses ``QgsVectorLayerUtils.createFeature`` per feature so layer default
    expressions match interactive digitizing. Features are added with
    ``addFeature`` one at a time so sequential aggregate defaults (e.g.
    ``maximum("sequence") + 1``) see entities already in the edit buffer.
    Work is still chunked so the Qt event loop can stay responsive.
    """

    def __init__(self, batch_size: int = DEFAULT_COPY_BATCH_SIZE) -> None:
        self._batch_size = max(1, batch_size)

    @staticmethod
    def is_missing_attribute_value(value: Any) -> bool:
        """Return True when a field value should be considered empty for default injection."""
        if value is None:
            return True
        try:
            if hasattr(value, "isNull") and callable(value.isNull) and value.isNull():
                return True
        except Exception:
            pass
        if isinstance(value, str):
            stripped = value.strip()
            return stripped == "" or stripped.lower() == "null"
        try:
            if str(value) == "NULL":
                return True
        except Exception:
            pass
        return False

    def build_field_mapping(self, source_fields: Any, target_layer: Any) -> LayerFieldMapping:
        """Precompute source/target field index pairs for a layer copy job."""
        source_field_name_to_index = {
            source_fields.at(i).name().lower(): i for i in range(source_fields.count())
        }
        target_fields = target_layer.fields()
        pairs: List[Tuple[int, int]] = []

        for field_index in range(target_fields.count()):
            field_name = target_fields.at(field_index).name()
            if field_name.lower() in _FID_FIELD_NAMES:
                continue
            source_field_idx = source_field_name_to_index.get(field_name.lower(), -1)
            if source_field_idx < 0:
                continue
            pairs.append((field_index, source_field_idx))

        return LayerFieldMapping(attribute_field_pairs=pairs)

    def create_feature_with_target_structure(
        self,
        source_feature: Any,
        target_layer: Any,
        field_mapping: LayerFieldMapping,
        expression_context: Any = None,
    ) -> Optional[Any]:
        """
        Build a target-layer feature with default expressions applied.

        Imported attributes are re-applied after ``QgsVectorLayerUtils.createFeature``
        so self-referencing defaults cannot replace valid source values.
        """
        try:
            from qgis.core import QgsGeometry, QgsVectorLayerUtils

            geometry = (
                source_feature.geometry()
                if source_feature.geometry() and not source_feature.geometry().isEmpty()
                else QgsGeometry()
            )

            attribute_map: Dict[int, Any] = {}
            for target_idx, source_idx in field_mapping.attribute_field_pairs:
                source_value = source_feature[source_idx]
                if self.is_missing_attribute_value(source_value):
                    continue
                attribute_map[target_idx] = source_value

            context = expression_context
            if context is None and hasattr(target_layer, "createExpressionContext"):
                try:
                    context = target_layer.createExpressionContext()
                except Exception:
                    context = None

            new_feature = QgsVectorLayerUtils.createFeature(
                target_layer,
                geometry,
                attribute_map,
                context,
            )

            for field_index, source_value in attribute_map.items():
                new_feature.setAttribute(field_index, source_value)

            return new_feature
        except Exception as exc:
            print(f"Error creating feature with target structure: {exc}")
            return None

    def copy_features_batch(
        self,
        source_features: Sequence[Any],
        target_layer: Any,
        start_index: int,
        field_mapping: LayerFieldMapping,
        expression_context: Any = None,
    ) -> CopyBatchResult:
        """
        Copy up to ``batch_size`` features starting at ``start_index``.

        The target layer is put into edit mode when needed. Each batch yields to the
        Qt event loop so the QGIS UI stays responsive during validation.
        """
        if not target_layer.isEditable():
            target_layer.startEditing()

        end_index = min(start_index + self._batch_size, len(source_features))
        error_count = 0
        copied_count = 0
        added_feature_ids: List[int] = []

        for index in range(start_index, end_index):
            source_feature = source_features[index]
            try:
                new_feature = self.create_feature_with_target_structure(
                    source_feature,
                    target_layer,
                    field_mapping,
                    expression_context=expression_context,
                )
                if new_feature is None:
                    error_count += 1
                    continue

                # Create and insert immediately so aggregate default expressions
                # (e.g. maximum("sequence") + 1) see entities already in the buffer.
                success = target_layer.addFeature(new_feature)
                if not success:
                    error_count += 1
                    if hasattr(target_layer, "lastError"):
                        print(
                            f"Failed to add feature {index + 1} to {target_layer.name()}: "
                            f"{target_layer.lastError()}"
                        )
                    continue

                copied_count += 1
                feature_id = _feature_id(new_feature)
                if feature_id is not None and feature_id >= 0:
                    added_feature_ids.append(feature_id)
            except Exception as exc:
                error_count += 1
                print(f"Error processing feature {index + 1}: {exc}")

            maybe_yield_to_ui(force=True)

        return CopyBatchResult(
            next_index=end_index,
            copied_count=copied_count,
            error_count=error_count,
            added_feature_ids=added_feature_ids,
        )

    @staticmethod
    def select_copied_features(target_layer: Any, feature_ids: Sequence[int]) -> None:
        """Select newly copied features (including uncommitted edit-buffer FIDs)."""
        ids = [feature_id for feature_id in feature_ids if feature_id not in (None, 0, -1)]
        if not ids:
            return
        try:
            target_layer.removeSelection()
            if hasattr(target_layer, "selectByIds"):
                set_selection = ImportFeatureCopier._select_behavior_set_selection()
                if set_selection is not None:
                    target_layer.selectByIds(ids, set_selection)
                else:
                    target_layer.selectByIds(ids)
            else:
                for feature_id in ids:
                    target_layer.select(feature_id)
        except Exception as exc:
            print(f"Warning: Could not select newly added features: {exc}")

    @staticmethod
    def _select_behavior_set_selection() -> Any:
        """Return QgsVectorLayer.SetSelection for QGIS 3 and QGIS 4."""
        try:
            from qgis.core import QgsVectorLayer

            if hasattr(QgsVectorLayer, "SetSelection"):
                return QgsVectorLayer.SetSelection
            select_behavior = getattr(QgsVectorLayer, "SelectBehavior", None)
            if select_behavior is not None and hasattr(select_behavior, "SetSelection"):
                return select_behavior.SetSelection
        except ImportError:
            pass
        return None


def load_job_source_features_chunk(
    job: LayerCopyJob,
    chunk_size: int = FEATURE_LOAD_YIELD_EVERY,
) -> bool:
    """
    Load up to ``chunk_size`` temporary-layer features, then return control to Qt.

    Returns:
        True when every feature for the job has been read from the source layer.
    """
    if job.load_complete:
        return True

    if job.source_features is None:
        job.source_features = []

    if job.load_iterator is None:
        job.load_iterator = iter(job.source_layer.getFeatures())

    loaded_this_chunk = 0
    while loaded_this_chunk < chunk_size:
        try:
            job.source_features.append(next(job.load_iterator))
            loaded_this_chunk += 1
        except StopIteration:
            job.load_iterator = None
            job.load_complete = True
            job.feature_count = len(job.source_features)
            maybe_yield_to_ui(force=True)
            return True

    maybe_yield_to_ui(force=True)
    return False


def load_job_source_features(job: LayerCopyJob) -> List[Any]:
    """
    Load every temporary-layer feature (synchronous path for unit tests).

    Production validation uses :func:`load_job_source_features_chunk` so the UI
    can repaint between chunks.
    """
    while not load_job_source_features_chunk(job, chunk_size=FEATURE_LOAD_YIELD_EVERY):
        pass
    return job.source_features or []


def block_job_target_signals(job: LayerCopyJob) -> None:
    """Suppress per-feature layer signals that trigger map redraws during validation."""
    if job.target_signals_blocked:
        return
    try:
        job.target_layer.blockSignals(True)
        job.target_signals_blocked = True
    except Exception:
        pass


def unblock_job_target_signals(job: LayerCopyJob) -> None:
    """Re-enable target-layer signals after validation."""
    if not job.target_signals_blocked:
        return
    try:
        job.target_layer.blockSignals(False)
        job.target_signals_blocked = False
    except Exception:
        pass


def ensure_job_expression_context(job: LayerCopyJob) -> None:
    """Create and cache the QgsExpressionContext for a copy job."""
    if job.expression_context is not None:
        return
    if not hasattr(job.target_layer, "createExpressionContext"):
        return
    try:
        job.expression_context = job.target_layer.createExpressionContext()
    except Exception:
        job.expression_context = None


def build_layer_copy_jobs(
    project_layers: Dict[str, Any],
    get_setting: Callable[[str, Any], Any],
    layer_mappings: Optional[Dict[str, str]] = None,
) -> List[LayerCopyJob]:
    """
    Resolve temporary import layers and their configured definitive targets.

    Args:
        project_layers: ``QgsProject.instance().mapLayers()`` value.
        get_setting: Callable returning a definitive layer id for a settings key.
        layer_mappings: Optional override of ``IMPORT_LAYER_MAPPINGS``.

    Returns:
        Copy jobs for every temporary layer that exists and has a configured target.
    """
    mappings = layer_mappings or IMPORT_LAYER_MAPPINGS
    copier = ImportFeatureCopier()
    jobs: List[LayerCopyJob] = []

    layers_by_name: Dict[str, Any] = {}
    layers_by_id: Dict[str, Any] = {}
    for layer in project_layers.values():
        layers_by_name[layer.name()] = layer
        layers_by_id[layer.id()] = layer

    for temp_layer_name, definitive_layer_key in mappings.items():
        source_layer = layers_by_name.get(temp_layer_name)
        if source_layer is None:
            continue

        definitive_layer_id = get_setting(definitive_layer_key, "")
        if not definitive_layer_id:
            continue

        target_layer = layers_by_id.get(definitive_layer_id)
        if target_layer is None:
            continue

        feature_count = source_layer.featureCount()
        if feature_count <= 0:
            continue

        field_mapping = copier.build_field_mapping(source_layer.fields(), target_layer)

        jobs.append(
            LayerCopyJob(
                temp_layer_name=temp_layer_name,
                definitive_layer_key=definitive_layer_key,
                source_layer=source_layer,
                target_layer=target_layer,
                field_mapping=field_mapping,
                feature_count=feature_count,
            )
        )

    return jobs


def remove_pending_import_layers(
    project: Any,
    layer_service: Optional[Any] = None,
    get_setting: Optional[Callable[[str, Any], Any]] = None,
) -> int:
    """
    Remove temporary import layers and related relation clones from the project.

    Called before a new import and when the user cancels a pending import so stale
    memory layers are never reused after source files change on disk.

    Args:
        project: QgsProject instance
        layer_service: Optional layer service for relation cleanup
        get_setting: Optional settings lookup for peer layer replacement mapping

    Returns:
        Number of map layers removed
    """
    if project is None:
        return 0

    try:
        layers_to_remove: List[str] = []
        for layer in project.mapLayers().values():
            if layer.name() in TEMPORARY_IMPORT_LAYER_NAMES:
                layers_to_remove.append(layer.id())
                print(f"Found temporary layer to delete: {layer.name()}")

        # Relation repair walks and rebuilds project relations in C++; only run it
        # when temporary import layers are actually present and about to be removed.
        if (
            layers_to_remove
            and layer_service is not None
            and get_setting is not None
            and hasattr(layer_service, "repair_definitive_project_relations")
        ):
            peer_replacements = build_peer_temp_layer_replacements(
                project.mapLayers(),
                get_setting,
            )
            repaired = layer_service.repair_definitive_project_relations(
                project,
                peer_layer_replacements=peer_replacements,
            )
            if repaired:
                print(
                    f"Repaired {repaired} definitive project relation(s) "
                    "before import cleanup"
                )

        if layer_service is not None and hasattr(
            layer_service, "remove_import_clone_relations"
        ):
            removed = layer_service.remove_import_clone_relations(project)
            if removed:
                print(
                    f"Removed {removed} temporary import relation clone(s) "
                    "before deleting temp layers"
                )

        if layer_service is not None and hasattr(layer_service, "invalidate_layer_cache"):
            for layer_id in layers_to_remove:
                layer_service.invalidate_layer_cache(layer_id)
        elif layer_service is not None and hasattr(layer_service, "clear_caches"):
            layer_service.clear_caches()

        for layer_id in layers_to_remove:
            project.removeMapLayer(layer_id)
            print(f"Deleted temporary layer: {layer_id}")

        if layers_to_remove:
            print(f"Successfully deleted {len(layers_to_remove)} temporary layer(s)")
        else:
            print("No temporary layers found to delete")

        return len(layers_to_remove)
    except Exception as exc:
        print(f"Error deleting temporary import layers: {exc}")
        import traceback

        traceback.print_exc()
        return 0


def reset_import_session_tracking(
    csv_import_service: Optional[Any] = None,
    field_project_import_service: Optional[Any] = None,
    layer_service: Optional[Any] = None,
) -> None:
    """
    Clear pending archive paths and in-memory layer caches after import cancellation.

    Ensures a subsequent import does not reuse bookkeeping or metadata from a
    cancelled session.
    """
    if csv_import_service is not None and hasattr(csv_import_service, "clear_last_imported_files"):
        csv_import_service.clear_last_imported_files()
    if field_project_import_service is not None and hasattr(
        field_project_import_service, "clear_last_imported_projects"
    ):
        field_project_import_service.clear_last_imported_projects()
    if layer_service is not None and hasattr(layer_service, "clear_caches"):
        layer_service.clear_caches()


def build_peer_temp_layer_replacements(
    project_layers: Dict[str, Any],
    get_setting: Callable[[str, Any], Any],
    layer_mappings: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Map definitive layer ids to active temporary import layer ids in the project.

    Used when cloning QGIS relations so inter-definitive relations (e.g. Objects to
    Features) are reproduced on their temporary counterparts during import.
    """
    mappings = layer_mappings or IMPORT_LAYER_MAPPINGS
    replacements: Dict[str, str] = {}

    layers_by_name: Dict[str, Any] = {}
    layers_by_id: Dict[str, Any] = {}
    for layer in project_layers.values():
        layers_by_name[layer.name()] = layer
        layers_by_id[layer.id()] = layer

    for temp_layer_name, definitive_layer_key in mappings.items():
        temp_layer = layers_by_name.get(temp_layer_name)
        if temp_layer is None:
            continue
        definitive_layer_id = get_setting(definitive_layer_key, "")
        if not definitive_layer_id:
            continue
        definitive_layer = layers_by_id.get(definitive_layer_id)
        if definitive_layer is None:
            continue
        replacements[definitive_layer.id()] = temp_layer.id()

    return replacements
