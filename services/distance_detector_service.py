"""
Distance Detector Service for ArcheoSync plugin.

This module provides a service that detects when total station points and their related
objects are too far from each other (default 5 cm) and not overlapping. It only checks
when the definitive objects and total station points layers are related.

Key Features:
- Detects total station points and objects that are too far apart (> 5 cm)
- Only checks when layers are related via QGIS relations (direct), or via the shortest
  multi-hop chain of project relations through intermediate layers when no direct relation exists
- Uses relation field mappings to identify related features
- Provides detailed warnings for each distance issue found
- Integrates with existing layer service and settings
- Supports translation for warning messages
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles distance detection between related features
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection rules

Usage:
    detector = DistanceDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
    )
    
    warnings = detector.detect_distance_warnings()
"""

from collections import defaultdict, deque
from typing import List, Optional, Any, Union, Dict, Tuple, AbstractSet
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea, QgsSpatialIndex

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from ..core.data_structures import WarningData
    from ..core.ui_responsiveness import maybe_yield_to_ui
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData
    from core.ui_responsiveness import maybe_yield_to_ui


class DistanceDetectorService:
    """
    Service for detecting distance issues between total station points and related objects.
    
    This service analyzes the spatial relationships between total station points and
    their related objects (via QGIS relations). It identifies pairs that are too far
    apart (> 5 cm) and not overlapping.
    """

    # Relation field names for which we allow alternate column names on layers (CSV often uses PtID vs identifier).
    _STANDARD_RELATION_FIELD_NAMES = frozenset({
        'identifier', 'identifiant', 'id', 'code', 'label', 'label_court', 'label_long',
        'object_number', 'number', 'numero', 'ptid', 'pt_id', 'num', 'no',
    })
    # Relation keys shared by more points than this are treated as non-unique (e.g. recording area id).
    _MAX_POINTS_PER_RELATION_KEY = 20
    _MAX_POINT_OBJECT_PAIRINGS = 100
    _EXACT_TOPO_FIRST_FIELD_NAMES = frozenset({
        'first_identifier', 'first_identifiant', 'premier_identifiant',
        'first_ptid', 'first_pt_id',
    })
    _EXACT_TOPO_LAST_FIELD_NAMES = frozenset({
        'last_identifier', 'last_identifiant', 'dernier_identifiant',
        'last_ptid', 'last_pt_id',
    })
    
    def __init__(self, settings_manager, layer_service, import_context=None):
        """
        Initialize the service with required dependencies.
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            import_context: Optional dict with current import summary counters
                (``csv_points_count``, ``objects_count``) so stale temporary layers
                from a previous session are not used for distance checks.
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._import_context = import_context or {}
        # Get configurable thresholds from settings with defaults, always as float
        self._max_distance_meters = float(self._settings_manager.get_value('distance_max_distance', 0.05))
    
    def detect_distance_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect distance warnings between total station points and related objects.
        Returns:
            List of warning messages or structured warning data about distance issues
        """
        warnings = []

        # Check if distance warnings are enabled
        if not self._settings_manager.get_value('enable_distance_warnings', True):
            print("[DEBUG] Distance detection: feature disabled in settings")
            return warnings

        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            objects_layer_id = self._settings_manager.get_value('objects_layer')

            if not total_station_points_layer_id or not objects_layer_id:
                print("[DEBUG] Distance detection: missing points/objects layer ids in settings")
                return warnings

            # Get all possible layers
            temp_total_station_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
            temp_objects_layer = self._layer_service.get_layer_by_name("New Objects")
            csv_points_count = self._import_context.get('csv_points_count')
            if csv_points_count is not None and int(csv_points_count) == 0:
                if temp_total_station_points_layer is not None:
                    print(
                        "[DEBUG] Distance detection: ignoring stale Imported_CSV_Points layer "
                        "(current import has no CSV points)"
                    )
                temp_total_station_points_layer = None
            definitive_total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            definitive_objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
            print(
                "[DEBUG] Distance detection: layer presence "
                f"(temp_points={bool(temp_total_station_points_layer)}, "
                f"temp_objects={bool(temp_objects_layer)}, "
                f"def_points={bool(definitive_total_station_points_layer)}, "
                f"def_objects={bool(definitive_objects_layer)})"
            )

            # Object-only import: never run QGIS relation / recording-area pairing without CSV points.
            if temp_objects_layer and not temp_total_station_points_layer:
                print("[DEBUG] Distance detection: object-only import (no Imported_CSV_Points)")
                if self._objects_layer_has_topo_identifier_fields(temp_objects_layer):
                    warnings.extend(
                        self._detect_distance_by_topo_identifiers(
                            temp_objects_layer,
                            primary_points_layer=None,
                            definitive_points_layer=definitive_total_station_points_layer,
                        )
                    )
                else:
                    print(
                        "[DEBUG] Distance detection: skipped — no topo link fields on objects "
                        "and no pending CSV points layer"
                    )
                return warnings

            # List of (points_layer, objects_layer, points_layer_type, objects_layer_type)
            # We avoid definitive-definitive checks while temporary import layers exist, because
            # distance warnings in the import workflow must target pending imported data first.
            layer_combinations = [
                (temp_total_station_points_layer, temp_objects_layer, 'temp', 'temp'),
                (temp_total_station_points_layer, definitive_objects_layer, 'temp', 'definitive'),
            ]
            if not temp_total_station_points_layer and not temp_objects_layer:
                layer_combinations.append(
                    (definitive_total_station_points_layer, definitive_objects_layer, 'definitive', 'definitive')
                )
            processed_combinations = 0

            for points_layer, objects_layer, points_type, objects_type in layer_combinations:
                maybe_yield_to_ui()
                if not points_layer or not objects_layer:
                    continue
                processed_combinations += 1
                print(
                    "[DEBUG] Distance detection: evaluating combination "
                    f"points='{points_layer.name()}' ({points_type}) -> "
                    f"objects='{objects_layer.name()}' ({objects_type})"
                )

                if not definitive_total_station_points_layer or not definitive_objects_layer:
                    print("[DEBUG] Distance detection: missing definitive points or objects layer from settings")
                    continue

                if self._objects_layer_has_topo_identifier_fields(objects_layer):
                    topo_warnings = self._detect_distance_by_topo_identifiers(
                        objects_layer,
                        primary_points_layer=points_layer if self._layer_has_features(points_layer) else None,
                        definitive_points_layer=definitive_total_station_points_layer,
                    )
                    print(
                        "[DEBUG] Distance detection: topo identifier check completed "
                        f"(warnings={len(topo_warnings)})"
                    )
                    warnings.extend(topo_warnings)
                    continue

                if not self._layer_has_features(points_layer):
                    print(
                        "[DEBUG] Distance detection: skipping relation check — "
                        f"points layer '{points_layer.name()}' has no features"
                    )
                    continue

                recording_area_link_fields = self._collect_recording_area_link_field_names(
                    definitive_total_station_points_layer,
                    definitive_objects_layer,
                )

                # Never pair pending objects with definitive points via direct relation fields
                # (e.g. recording-area id). Indirect mobilier paths are handled below.
                skip_direct_relation = points_type == 'definitive' and objects_type == 'temp'

                recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer')
                forbidden_layer_ids: Optional[AbstractSet[str]] = None
                if recording_areas_layer_id:
                    forbidden_layer_ids = frozenset({str(recording_areas_layer_id)})

                # Direct relations between the two definitive layers, plus a path for multi-hop
                # detection. BFS skips direct point<->object relations so a useless or CSV-incompatible
                # direct link does not hide a valid longer path (e.g. points -> mobilier -> objects).
                relations = self._collect_relations_between_layers(
                    definitive_total_station_points_layer, definitive_objects_layer
                )
                print(f"[DEBUG] Distance detection: direct relations found = {len(relations)}")
                forbidden_relation_ids: Optional[AbstractSet[str]] = None
                if relations:
                    forbidden_relation_ids = frozenset(
                        self._relation_project_id(r) for r in relations
                    )
                    print(
                        "[DEBUG] Distance detection: direct relation ids ignored for indirect path = "
                        f"{sorted(forbidden_relation_ids)}"
                    )
                indirect_path = self._find_shortest_relation_path(
                    definitive_total_station_points_layer,
                    definitive_objects_layer,
                    forbidden_relation_ids=forbidden_relation_ids,
                    forbidden_layer_ids=forbidden_layer_ids,
                )
                if indirect_path:
                    print(f"[DEBUG] Distance detection: indirect path hops = {len(indirect_path)}")
                else:
                    print("[DEBUG] Distance detection: no indirect path found")

                if not relations and not indirect_path:
                    print(
                        "[DEBUG] Distance detection: no QGIS relation (direct or indirect) "
                        "between definitive points and objects layers"
                    )
                    continue

                ordered_relations = self._ordered_relations_for_distance(
                    relations, definitive_total_station_points_layer
                ) if relations else []

                matched_relation = False
                direct_warnings_count = 0
                if not skip_direct_relation:
                    for relation in ordered_relations:
                        field_pairs = relation.fieldPairs()
                        if not field_pairs:
                            print("[DEBUG] Distance detection: skipping relation without field pairs")
                            continue

                        # Determine which layer is referencing and which is referenced in this relation
                        if relation.referencingLayer() == definitive_total_station_points_layer:
                            def_points_field = list(field_pairs.keys())[0]
                            def_objects_field = list(field_pairs.values())[0]
                            points_layer_is_referencing = True
                        else:
                            def_objects_field = list(field_pairs.keys())[0]
                            def_points_field = list(field_pairs.values())[0]
                            points_layer_is_referencing = False

                        points_field = self._find_relation_field_on_layer(
                            points_layer, def_points_field, is_point_layer=True
                        )
                        objects_field = self._find_relation_field_on_layer(
                            objects_layer, def_objects_field, is_point_layer=False
                        )
                        if points_field is None or objects_field is None:
                            p_names = [f.name() for f in points_layer.fields()]
                            o_names = [f.name() for f in objects_layer.fields()]
                            print(
                                "[DEBUG] Distance detection: relation fields not resolved on current layers "
                                f"(relation expects points='{def_points_field}', objects='{def_objects_field}'; "
                                f"resolved points_field={points_field!r}, objects_field={objects_field!r}; "
                                f"points fields={p_names}; objects fields={o_names}); trying next relation"
                            )
                            continue

                        if (
                            self._is_recording_area_link_field(points_field, recording_area_link_fields)
                            or self._is_recording_area_link_field(objects_field, recording_area_link_fields)
                        ):
                            print(
                                "[DEBUG] Distance detection: skipping relation using recording-area fields "
                                f"(points='{points_field}', objects='{objects_field}')"
                            )
                            continue

                        points_field_idx = points_layer.fields().indexOf(points_field)
                        if points_field_idx < 0:
                            for i, field in enumerate(points_layer.fields()):
                                if field.name().lower() == points_field.lower():
                                    points_field_idx = i
                                    break

                        objects_field_idx = objects_layer.fields().indexOf(objects_field)
                        if objects_field_idx < 0:
                            for i, field in enumerate(objects_layer.fields()):
                                if field.name().lower() == objects_field.lower():
                                    objects_field_idx = i
                                    break

                        if points_field_idx < 0 or objects_field_idx < 0:
                            print(
                                "[DEBUG] Distance detection: resolved fields but invalid indexes "
                                f"(points_idx={points_field_idx}, objects_idx={objects_field_idx})"
                            )
                            continue

                        matched_relation = True
                        print(
                            "[DEBUG] Distance detection: running direct check with fields "
                            f"points='{points_field}' (idx={points_field_idx}) and "
                            f"objects='{objects_field}' (idx={objects_field_idx})"
                        )
                        distance_warnings = self._detect_distance_issues(
                            points_layer, objects_layer,
                            points_field_idx, objects_field_idx,
                            points_layer_is_referencing
                        )
                        direct_warnings_count = len(distance_warnings)
                        print(
                            "[DEBUG] Distance detection: direct check completed "
                            f"(warnings={direct_warnings_count})"
                        )
                        warnings.extend(distance_warnings)
                        # Use the first relation whose field mapping exists on both current layers
                        break

                # If direct mapping was unusable, or usable but yielded no warnings,
                # try the indirect chain as a fallback.
                if (not skip_direct_relation and (not matched_relation or direct_warnings_count == 0) and indirect_path) or (
                    skip_direct_relation and indirect_path
                ):
                    print(
                        "[DEBUG] Distance detection: running indirect fallback "
                        f"(matched_relation={matched_relation}, direct_warnings={direct_warnings_count})"
                    )
                    indirect_result = self._detect_distance_issues_via_relation_path(
                        points_layer,
                        objects_layer,
                        definitive_total_station_points_layer,
                        definitive_objects_layer,
                        indirect_path,
                    )
                    if indirect_result is not None:
                        matched_relation = True
                        print(
                            "[DEBUG] Distance detection: indirect check completed "
                            f"(warnings={len(indirect_result)})"
                        )
                        warnings.extend(indirect_result)
                    else:
                        print("[DEBUG] Distance detection: indirect check could not be applied")

                if not matched_relation:
                    print(
                        "[DEBUG] Distance detection: no relation had usable field pairs on "
                        f"points layer '{points_layer.name()}' and objects layer '{objects_layer.name()}'"
                    )
                    if relations and indirect_path is None:
                        print(
                            "[DEBUG] Distance detection: hint — a direct points↔objects relation exists "
                            "but no alternate multi-hop path was found; remove or fix the direct relation "
                            "if you rely on an intermediate layer."
                        )
            if processed_combinations == 0:
                print(
                    "[DEBUG] Distance detection: no valid points/objects layer combination available "
                    "(temporary and definitive layers missing)."
                )
            else:
                print(
                    "[DEBUG] Distance detection: done "
                    f"(processed_combinations={processed_combinations}, total_warnings={len(warnings)})"
                )

        except Exception as e:
            print(f"Error in distance detection: {e}")
            import traceback
            traceback.print_exc()

        return warnings
    
    def _detect_distance_issues(self, 
                               total_station_points_layer: Any,
                               objects_layer: Any,
                               points_field_idx: int,
                               objects_field_idx: int,
                               points_layer_is_referencing: bool) -> List[Union[str, WarningData]]:
        """
        Optimized: Uses QgsSpatialIndex for objects per relation value.
        """
        warnings = []
        try:
            distance_calculator = QgsDistanceArea()
            distance_calculator.setEllipsoid('WGS84')
            # Group features by their relation field value (case-insensitive)
            points_by_relation = {}
            objects_by_relation = {}
            for feature in total_station_points_layer.getFeatures():
                maybe_yield_to_ui()
                relation_value = feature.attribute(points_field_idx)
                if self._is_valid_relation_value(relation_value):
                    relation_value_key = self._relation_value_key(relation_value)
                    if relation_value_key not in points_by_relation:
                        points_by_relation[relation_value_key] = []
                    points_by_relation[relation_value_key].append(feature)
            for feature in objects_layer.getFeatures():
                maybe_yield_to_ui()
                if not self._object_feature_has_point_association(feature, objects_layer):
                    continue
                relation_value = feature.attribute(objects_field_idx)
                if self._is_valid_relation_value(relation_value):
                    relation_value_key = self._relation_value_key(relation_value)
                    if relation_value_key not in objects_by_relation:
                        objects_by_relation[relation_value_key] = []
                    objects_by_relation[relation_value_key].append(feature)
            # Only check common relation values (same link attribute on both sides)
            common_relation_values = set(points_by_relation.keys()) & set(objects_by_relation.keys())
            if not common_relation_values and (points_by_relation or objects_by_relation):
                pk = set(points_by_relation.keys())
                ok = set(objects_by_relation.keys())
                print(
                    "[DEBUG] Distance detection: no overlapping link values between points and objects "
                    f"(unique keys on points: {len(pk)}, on objects: {len(ok)}; "
                    f"sample only-on-points: {sorted(pk - ok)[:8]}; "
                    f"sample only-on-objects: {sorted(ok - pk)[:8]})"
                )
            distance_issues = []
            for relation_value in common_relation_values:
                points_features = points_by_relation[relation_value]
                objects_features = objects_by_relation[relation_value]
                if len(points_features) > self._MAX_POINTS_PER_RELATION_KEY:
                    print(
                        "[DEBUG] Distance detection: skipping non-unique relation key "
                        f"'{relation_value}' ({len(points_features)} points)"
                    )
                    continue
                pairing_count = len(points_features) * len(objects_features)
                if pairing_count > self._MAX_POINT_OBJECT_PAIRINGS:
                    print(
                        "[DEBUG] Distance detection: skipping relation key "
                        f"'{relation_value}' (too many pairings: {pairing_count})"
                    )
                    continue
                for pf in points_features:
                    for of in objects_features:
                        maybe_yield_to_ui(every=10)
                        point_geom = pf.geometry()
                        object_geom = of.geometry()
                        point_identifier = self._get_feature_identifier(pf, "Total Station Point")
                        object_identifier = self._get_feature_identifier(of, "Object")
                        if point_geom.intersects(object_geom):
                            continue
                        distance = point_geom.distance(object_geom)
                        if distance > self._max_distance_meters:
                            distance_issues.append({
                                'point_feature': pf,
                                'object_feature': of,
                                'point_identifier': point_identifier,
                                'object_identifier': object_identifier,
                                'distance': distance,
                                'relation_value': relation_value
                            })
            # Create warnings for distance issues
            if distance_issues:
                # Group by relation value for better organization
                by_relation_value = {}
                for issue in distance_issues:
                    relation_value = issue['relation_value']
                    if relation_value not in by_relation_value:
                        by_relation_value[relation_value] = []
                    by_relation_value[relation_value].append(issue)
                
                for relation_value, issues in by_relation_value.items():
                    # Create filter expressions for both layers (use original case from first feature)
                    points_filter_value = issues[0]['point_feature'].attribute(points_field_idx)
                    objects_filter_value = issues[0]['object_feature'].attribute(objects_field_idx)
                    points_filter = f'"{total_station_points_layer.fields()[points_field_idx].name()}" = \'{points_filter_value}\''
                    objects_filter = f'"{objects_layer.fields()[objects_field_idx].name()}" = \'{objects_filter_value}\''
                    
                    # Get feature identifiers for the warning message
                    point_identifiers = sorted({issue['point_identifier'] for issue in issues})
                    object_identifiers = sorted({issue['object_identifier'] for issue in issues})
                    max_distance = max(issue['distance'] for issue in issues)
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_distance_warning(
                            point_identifiers, object_identifiers, max_distance, relation_value
                        ),
                        recording_area_name=f"Relation {relation_value}",  # Use relation value as identifier
                        layer_name=total_station_points_layer.name(),
                        filter_expression=points_filter,
                        second_layer_name=objects_layer.name(),
                        second_filter_expression=objects_filter,
                        distance_issues=issues
                    )
                    warnings.append(warning_data)
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_distance_issues: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _collect_relations_between_layers(self, layer1: Any, layer2: Any) -> List[Any]:
        """
        Return all QGIS relations that connect layer1 and layer2 (either referencing direction).

        Args:
            layer1: First layer (must not be None)
            layer2: Second layer (must not be None)

        Returns:
            List of QgsRelation instances (possibly empty).
        """
        found: List[Any] = []
        try:
            if not layer1 or not layer2:
                return found
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            for relation_id, relation in relation_manager.relations().items():
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                if not (referencing_layer and referenced_layer):
                    continue
                if ((referencing_layer.id() == layer1.id() and referenced_layer.id() == layer2.id()) or
                        (referencing_layer.id() == layer2.id() and referenced_layer.id() == layer1.id())):
                    found.append(relation)
            return found
        except Exception as e:
            print(f"[DEBUG] Error collecting relations between layers: {str(e)}")
            import traceback
            traceback.print_exc()
            return found

    def _ordered_relations_for_distance(self, relations: List[Any], definitive_points_layer: Any) -> List[Any]:
        """
        Prefer the relation whose referencing layer is the total station points layer (child / FK side).

        When users create two relations (one in each direction), iteration order alone can pick a
        relation whose field mapping does not match the temporary import layer; trying the other
        direction next fixes that. Preferring points-as-referencing matches the usual topo->object link.
        """
        if not relations or not definitive_points_layer:
            return relations or []
        preferred: List[Any] = []
        other: List[Any] = []
        pid = definitive_points_layer.id()
        for relation in relations:
            rl = relation.referencingLayer()
            if rl and rl.id() == pid:
                preferred.append(relation)
            else:
                other.append(relation)
        return preferred + other

    def _relation_project_id(self, relation: Any, dict_key: Any = None) -> str:
        """
        Stable string id for a QgsRelation, for comparing relations across calls.

        Uses :meth:`QgsRelation.id` when available, otherwise the relation manager dict key
        or Python ``id`` as last resort (tests may use plain mocks).
        """
        try:
            rid = relation.id()
            if rid:
                return str(rid)
        except Exception:
            pass
        if dict_key is not None:
            return str(dict_key)
        return str(id(relation))

    def _other_layer_in_relation(self, current_layer: Any, relation: Any) -> Optional[Any]:
        """Return the layer at the other end of ``relation`` from ``current_layer``."""
        try:
            ref = relation.referencingLayer()
            rec = relation.referencedLayer()
            if not ref or not rec or not current_layer:
                return None
            cid = current_layer.id()
            if ref.id() == cid:
                return rec
            if rec.id() == cid:
                return ref
        except Exception:
            return None
        return None

    def _find_shortest_relation_path(
        self,
        layer_start: Any,
        layer_end: Any,
        max_hops: int = 8,
        forbidden_relation_ids: Optional[AbstractSet[str]] = None,
        forbidden_layer_ids: Optional[AbstractSet[str]] = None,
    ) -> Optional[List[Any]]:
        """
        Shortest chain of QgsRelation instances connecting ``layer_start`` to ``layer_end``.

        Used when no direct relation exists between the two layers. Each relation in the list
        links consecutive layers on the path (BFS on the undirected relation graph).

        Args:
            layer_start: First endpoint (e.g. definitive total station points layer).
            layer_end: Second endpoint (e.g. definitive objects layer).
            max_hops: Maximum number of relations in the path (prevents runaway search).
            forbidden_relation_ids: Relations whose ids must not appear on the path (typically
                all direct point↔object relations so a longer path through an intermediate layer
                can still be found).
            forbidden_layer_ids: Layer ids that must not appear on the path (e.g. recording areas).

        Returns:
            Ordered list of relations, or None if no path exists within ``max_hops``.
        """
        try:
            if not layer_start or not layer_end or layer_start.id() == layer_end.id():
                return None
            queue = deque([(layer_start, [])])
            visited = {layer_start.id()}
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            while queue:
                current, path = queue.popleft()
                if len(path) >= max_hops:
                    continue
                for rel_key, relation in relation_manager.relations().items():
                    if forbidden_relation_ids:
                        rid = self._relation_project_id(relation, rel_key)
                        if rid in forbidden_relation_ids:
                            continue
                    nxt = self._other_layer_in_relation(current, relation)
                    if not nxt:
                        continue
                    nid = nxt.id()
                    if forbidden_layer_ids and str(nid) in forbidden_layer_ids:
                        continue
                    new_path = path + [relation]
                    if nid == layer_end.id():
                        return new_path
                    if nid in visited:
                        continue
                    visited.add(nid)
                    queue.append((nxt, new_path))
            return None
        except Exception as e:
            print(f"[DEBUG] Error finding indirect relation path: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _ordered_layers_along_path(
        self,
        layer_start: Any,
        relations_path: List[Any],
    ) -> Optional[List[Any]]:
        """
        Reconstruct [L0, L1, ..., Ln] where L0 is ``layer_start`` and each relation connects Li to Li+1.
        """
        layers = [layer_start]
        current = layer_start
        for relation in relations_path:
            nxt = self._other_layer_in_relation(current, relation)
            if not nxt:
                return None
            layers.append(nxt)
            current = nxt
        return layers

    def _resolve_combo_layer_for_path_node(
        self,
        path_node: Any,
        definitive_points: Any,
        definitive_objects: Any,
        points_combo: Any,
        objects_combo: Any,
    ) -> Any:
        """Map a definitive path endpoint to the combo (temp/def) layer used for detection."""
        if path_node.id() == definitive_points.id():
            return points_combo
        if path_node.id() == definitive_objects.id():
            return objects_combo
        return path_node

    def _field_names_for_relation_hop(self, relation: Any, from_layer: Any) -> Optional[Tuple[str, str]]:
        """
        For a hop from ``from_layer`` to the other layer in ``relation``, return
        (field_name_on_from, field_name_on_to) using the relation's single field pair.
        """
        fp = relation.fieldPairs()
        if not fp:
            return None
        ref_field, rec_field = next(iter(fp.items()))
        ref_lyr = relation.referencingLayer()
        rec_lyr = relation.referencedLayer()
        if not ref_lyr or not rec_lyr:
            return None
        if from_layer.id() == ref_lyr.id():
            return ref_field, rec_field
        if from_layer.id() == rec_lyr.id():
            return rec_field, ref_field
        return None

    def _field_index_on_layer_for_path(
        self,
        combo_layer: Any,
        relation_field_name: str,
        *,
        path_def_layer: Any,
        definitive_points: Any,
        definitive_objects: Any,
    ) -> int:
        """Resolve a relation field name to a field index on ``combo_layer`` for path traversal."""
        if path_def_layer.id() == definitive_points.id():
            is_pt = True
        elif path_def_layer.id() == definitive_objects.id():
            is_pt = False
        else:
            is_pt = False
        fname = self._find_relation_field_on_layer(
            combo_layer, relation_field_name, is_point_layer=is_pt
        )
        if not fname:
            return -1
        idx = combo_layer.fields().indexOf(fname)
        if idx >= 0:
            return idx
        for i, field in enumerate(combo_layer.fields()):
            if field.name().lower() == fname.lower():
                return i
        return -1

    def _detect_distance_issues_via_relation_path(
        self,
        points_combo: Any,
        objects_combo: Any,
        definitive_points: Any,
        definitive_objects: Any,
        relations_path: List[Any],
    ) -> Optional[List[Union[str, WarningData]]]:
        """
        Pair points with objects by following a multi-hop QGIS relation path, then apply the same
        distance / overlap rules as :meth:`_detect_distance_issues`.

        Returns:
            ``None`` if the path could not be applied (invalid path, unresolved fields).
            An empty list if the path applied but no distance warnings were produced.
            Otherwise the list of warnings.
        """
        warnings: List[Union[str, WarningData]] = []
        try:
            ordered_def = self._ordered_layers_along_path(definitive_points, relations_path)
            if (
                not ordered_def
                or ordered_def[-1].id() != definitive_objects.id()
                or ordered_def[0].id() != definitive_points.id()
            ):
                print("[DEBUG] Distance detection (indirect): path does not connect points to objects")
                return None

            combo_layers = [
                self._resolve_combo_layer_for_path_node(
                    d, definitive_points, definitive_objects, points_combo, objects_combo
                )
                for d in ordered_def
            ]
            print(
                "[DEBUG] Distance detection (indirect): resolved path layers = "
                f"{[layer.name() if layer else '<none>' for layer in combo_layers]}"
            )

            hops: List[Tuple[int, int]] = []
            for i, relation in enumerate(relations_path):
                from_def = ordered_def[i]
                to_def = ordered_def[i + 1]
                names = self._field_names_for_relation_hop(relation, from_def)
                if not names:
                    print("[DEBUG] Distance detection (indirect): relation has no field pairs")
                    return None
                from_name, to_name = names
                from_idx = self._field_index_on_layer_for_path(
                    combo_layers[i],
                    from_name,
                    path_def_layer=from_def,
                    definitive_points=definitive_points,
                    definitive_objects=definitive_objects,
                )
                to_idx = self._field_index_on_layer_for_path(
                    combo_layers[i + 1],
                    to_name,
                    path_def_layer=to_def,
                    definitive_points=definitive_points,
                    definitive_objects=definitive_objects,
                )
                if from_idx < 0 or to_idx < 0:
                    print(
                        "[DEBUG] Distance detection (indirect): could not resolve hop fields "
                        f"(hop {i}: from_idx={from_idx}, to_idx={to_idx})"
                    )
                    return None
                print(
                    "[DEBUG] Distance detection (indirect): hop mapping "
                    f"{i}: '{combo_layers[i].name()}'.'{from_name}'[{from_idx}] -> "
                    f"'{combo_layers[i + 1].name()}'.'{to_name}'[{to_idx}]"
                )
                hops.append((from_idx, to_idx))

            feats = []
            for layer in combo_layers:
                feature_list = []
                for feature in layer.getFeatures():
                    maybe_yield_to_ui()
                    feature_list.append(feature)
                feats.append(feature_list)
            print(
                "[DEBUG] Distance detection (indirect): feature counts by layer = "
                f"{[len(fset) for fset in feats]}"
            )
            if not feats[0] or not feats[-1]:
                return []

            indices: List[Dict[str, List[Any]]] = []
            for i in range(len(hops)):
                to_idx = hops[i][1]
                bucket: Dict[str, List[Any]] = defaultdict(list)
                for feature in feats[i + 1]:
                    maybe_yield_to_ui()
                    if i + 1 == len(feats) - 1 and not self._object_feature_has_point_association(
                        feature, combo_layers[i + 1]
                    ):
                        continue
                    val = feature.attribute(to_idx)
                    if not self._is_valid_relation_value(val):
                        continue
                    bucket[self._relation_value_key(val)].append(feature)
                indices.append(dict(bucket))

            distance_issues: List[Dict[str, Any]] = []
            for point_feature in feats[0]:
                maybe_yield_to_ui()
                v0 = point_feature.attribute(hops[0][0])
                if not self._is_valid_relation_value(v0):
                    continue
                current_matches = indices[0].get(self._relation_value_key(v0), [])
                for hi in range(1, len(hops)):
                    nxt: List[Any] = []
                    from_idx = hops[hi][0]
                    idx_map = indices[hi]
                    for candidate in current_matches:
                        vk = candidate.attribute(from_idx)
                        if not self._is_valid_relation_value(vk):
                            continue
                        nxt.extend(idx_map.get(self._relation_value_key(vk), []))
                    current_matches = nxt
                for object_feature in current_matches:
                    maybe_yield_to_ui(every=10)
                    point_geom = point_feature.geometry()
                    object_geom = object_feature.geometry()
                    point_identifier = self._get_feature_identifier(point_feature, "Total Station Point")
                    object_identifier = self._get_feature_identifier(object_feature, "Object")
                    if point_geom.intersects(object_geom):
                        continue
                    distance = point_geom.distance(object_geom)
                    if distance > self._max_distance_meters:
                        chain_key = self._relation_value_key(v0)
                        distance_issues.append({
                            'point_feature': point_feature,
                            'object_feature': object_feature,
                            'point_identifier': point_identifier,
                            'object_identifier': object_identifier,
                            'distance': distance,
                            'relation_value': chain_key,
                        })
            print(
                "[DEBUG] Distance detection (indirect): pairing result "
                f"(distance_issues={len(distance_issues)})"
            )

            if not distance_issues:
                return []

            by_relation_value: Dict[str, List[Dict[str, Any]]] = {}
            for issue in distance_issues:
                key = issue['relation_value']
                if key not in by_relation_value:
                    by_relation_value[key] = []
                by_relation_value[key].append(issue)

            points_field_idx = hops[0][0]
            objects_field_idx = hops[-1][1]
            for relation_value, issues in by_relation_value.items():
                unique_point_ids = {issue['point_feature'].id() for issue in issues}
                unique_object_ids = {issue['object_feature'].id() for issue in issues}
                if len(unique_point_ids) > self._MAX_POINTS_PER_RELATION_KEY:
                    print(
                        "[DEBUG] Distance detection (indirect): skipping non-unique key "
                        f"'{relation_value}' ({len(unique_point_ids)} points)"
                    )
                    continue
                if len(unique_point_ids) * len(unique_object_ids) > self._MAX_POINT_OBJECT_PAIRINGS:
                    print(
                        "[DEBUG] Distance detection (indirect): skipping key "
                        f"'{relation_value}' (too many pairings)"
                    )
                    continue
                points_filter_value = issues[0]['point_feature'].attribute(points_field_idx)
                objects_filter_value = issues[0]['object_feature'].attribute(objects_field_idx)
                points_filter = (
                    f'"{points_combo.fields()[points_field_idx].name()}" = \'{points_filter_value}\''
                )
                objects_filter = (
                    f'"{objects_combo.fields()[objects_field_idx].name()}" = \'{objects_filter_value}\''
                )
                point_identifiers = sorted({issue['point_identifier'] for issue in issues})
                object_identifiers = sorted({issue['object_identifier'] for issue in issues})
                max_distance = max(issue['distance'] for issue in issues)
                warning_data = WarningData(
                    message=self._create_distance_warning(
                        point_identifiers, object_identifiers, max_distance, relation_value
                    ),
                    recording_area_name=f"Indirect relation {relation_value}",
                    layer_name=points_combo.name(),
                    filter_expression=points_filter,
                    second_layer_name=objects_combo.name(),
                    second_filter_expression=objects_filter,
                    distance_issues=issues,
                )
                warnings.append(warning_data)

        except Exception as e:
            print(f"[DEBUG] Error in _detect_distance_issues_via_relation_path: {e}")
            import traceback
            traceback.print_exc()
            return None

        return warnings

    def _get_relation_between_layers(self, layer1: Any, layer2: Any) -> Optional[Any]:
        """
        Return one relation between two layers, preferring layer1 as the referencing layer when
        several relations exist (see _ordered_relations_for_distance).

        Args:
            layer1: Typically the definitive total station points layer when called from tests/tools
            layer2: The other definitive layer

        Returns:
            A relation object if found, None otherwise
        """
        relations = self._collect_relations_between_layers(layer1, layer2)
        if not relations:
            return None
        ordered = self._ordered_relations_for_distance(relations, layer1)
        return ordered[0] if ordered else None
    
    def _get_feature_identifier(self, feature: Any, layer_type: str) -> str:
        """
        Get a human-readable identifier for a feature.
        
        Args:
            feature: The feature to get identifier for
            layer_type: The type of layer (for context)
            
        Returns:
            A string identifier for the feature
        """
        try:
            # Try to get a meaningful identifier field
            if layer_type == "Total Station Point":
                # Look for common point identifier fields
                for field_name in ['point_id', 'station_id', 'point_number', 'id', 'fid']:
                    field_idx = feature.fields().indexOf(field_name)
                    if field_idx >= 0:
                        value = feature.attribute(field_idx)
                        if value:
                            return f"Point {value}"
            elif layer_type == "Object":
                # Look for common object identifier fields
                for field_name in ['object_number', 'number', 'object_id', 'id', 'fid']:
                    field_idx = feature.fields().indexOf(field_name)
                    if field_idx >= 0:
                        value = feature.attribute(field_idx)
                        if value:
                            return f"Object {value}"
            
            # Fallback to feature ID
            return f"{layer_type} {feature.id()}"
            
        except Exception as e:
            print(f"Error getting feature identifier: {e}")
            return f"{layer_type} {feature.id()}"
    
    def _create_distance_warning(self, 
                                point_identifiers: List[str], 
                                object_identifiers: List[str], 
                                max_distance: float,
                                relation_value: str = None) -> str:
        """
        Create a warning message for distance issues.
        Args:
            point_identifiers: List of point identifiers
            object_identifiers: List of object identifiers
            max_distance: The maximum distance found
            relation_value: The matched identifier (relation value)
        Returns:
            The warning message
        """
        try:
            if len(point_identifiers) == 1 and len(object_identifiers) == 1:
                feature_text = f"{point_identifiers[0]} and {object_identifiers[0]}"
            else:
                feature_text = f"{len(point_identifiers)} points and {len(object_identifiers)} objects"
            distance_cm = max_distance * 100  # Convert to centimeters
            identifier_text = f" [Identifier: {relation_value}]" if relation_value else ""
            # Fallback: just return the message in English
            return (
                f"{feature_text} are separated by {distance_cm:.1f} cm (maximum allowed: {self._max_distance_meters * 100:.1f} cm){identifier_text}"
            )
        except Exception as e:
            print(f"Error creating distance warning: {str(e)}")
            return f"{feature_text} are separated by {max_distance * 100:.1f} cm (maximum allowed: {self._max_distance_meters * 100:.1f} cm)" 

    def _find_identifier_field(self, layer, is_point_layer: bool) -> Optional[str]:
        """
        Try to find a likely identifier field for points or objects.
        """
        # For points, try common names
        if is_point_layer:
            candidates = ["ptid", "PtID", "point_id", "station_id", "point_number", "id", "fid", "Label_court"]
        else:
            candidates = ["Label_court", "label_court", "object_number", "number", "object_id", "id", "fid"]
        field_names = [f.name().lower() for f in layer.fields()]
        for candidate in candidates:
            if candidate.lower() in field_names:
                # Return the actual field name (case-sensitive)
                for f in layer.fields():
                    if f.name().lower() == candidate.lower():
                        return f.name()
        return None 

    def _is_valid_relation_value(self, relation_value: Any) -> bool:
        """
        Return whether a relation value can safely link points and objects.

        Empty strings and common textual null markers are treated as missing.
        This avoids false matches where many features share an "empty" identifier.
        """
        if relation_value is None:
            return False
        text_value = str(relation_value).strip()
        if not text_value:
            return False
        if text_value.lower() in {"null", "none", "nan"}:
            return False
        return True

    def _relation_value_key(self, relation_value: Any) -> str:
        """Normalize a relation value to a stable case-insensitive key."""
        return str(relation_value).strip().lower()

    def _layer_has_features(self, layer: Any) -> bool:
        """Return whether a vector layer contains at least one feature."""
        if not layer:
            return False
        try:
            for _feature in layer.getFeatures():
                return True
        except Exception:
            return False
        return False

    def _find_topo_link_field_indices(self, objects_layer: Any) -> Tuple[int, int]:
        """
        Locate object-layer columns that store topo point identifiers (first/last).

        Supports common English and French field names used in field-survey schemas.
        """
        if not objects_layer:
            return -1, -1
        first_idx = -1
        last_idx = -1
        for i, field in enumerate(objects_layer.fields()):
            name = field.name().strip().lower()
            if name in self._EXACT_TOPO_FIRST_FIELD_NAMES:
                first_idx = i
            elif name in self._EXACT_TOPO_LAST_FIELD_NAMES:
                last_idx = i
        if first_idx >= 0 or last_idx >= 0:
            return first_idx, last_idx
        for i, field in enumerate(objects_layer.fields()):
            name = field.name().strip().lower()
            if first_idx < 0 and ('first' in name or 'premier' in name):
                if 'identif' in name or 'ptid' in name or 'pt_id' in name:
                    first_idx = i
            if last_idx < 0 and ('last' in name or 'dernier' in name):
                if 'identif' in name or 'ptid' in name or 'pt_id' in name:
                    last_idx = i
        return first_idx, last_idx

    def _collect_recording_area_link_field_names(
        self,
        definitive_points_layer: Any,
        definitive_objects_layer: Any,
    ) -> frozenset:
        """
        Return lower-case field names that reference recording areas, not topo point ids.

        These fields must never be used to pair points with objects for distance checks.
        """
        names: set = set()
        recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer')
        recording_areas_layer = (
            self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_areas_layer_id
            else None
        )
        try:
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            for relation in relation_manager.relations().values():
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                if not referencing_layer or not referenced_layer or not recording_areas_layer:
                    continue
                if referenced_layer.id() != recording_areas_layer.id():
                    continue
                field_pairs = relation.fieldPairs()
                if not field_pairs:
                    continue
                if definitive_objects_layer and referencing_layer.id() == definitive_objects_layer.id():
                    names.update(field_pairs.keys())
                if definitive_points_layer and referencing_layer.id() == definitive_points_layer.id():
                    names.update(field_pairs.keys())
        except Exception as e:
            print(f"[DEBUG] Distance detection: could not collect recording-area fields: {e}")

        for setting_key in (
            'objects_recording_area_field',
            'alternative_objects_recording_area_field',
        ):
            configured = self._settings_manager.get_value(setting_key, '')
            if configured:
                names.add(str(configured).strip().lower())

        return frozenset(str(name).strip().lower() for name in names if name)

    def _is_recording_area_link_field(
        self,
        field_name: Optional[str],
        recording_area_link_fields: AbstractSet[str],
    ) -> bool:
        """Return whether ``field_name`` is a recording-area foreign key."""
        if not field_name or not recording_area_link_fields:
            return False
        return field_name.strip().lower() in recording_area_link_fields

    def _objects_layer_has_topo_identifier_fields(self, objects_layer: Any) -> bool:
        """Return whether the objects layer stores topo point links in first/last columns."""
        first_idx, last_idx = self._find_topo_link_field_indices(objects_layer)
        return first_idx >= 0 or last_idx >= 0

    def _index_points_layers_by_topo_identifier(
        self,
        *points_layers: Any,
    ) -> Dict[str, List[Tuple[Any, Any]]]:
        """
        Build a case-insensitive index of topo points keyed by their identifier field value.

        When several layers are provided (temporary CSV + definitive), all are merged into one
        index so imported objects can be checked against either source.
        """
        index: Dict[str, List[Tuple[Any, Any]]] = {}
        for layer in points_layers:
            if not layer:
                continue
            identifier_field = self._find_identifier_field(layer, is_point_layer=True)
            if not identifier_field:
                print(
                    "[DEBUG] Distance detection (topo ids): no identifier field on "
                    f"layer '{layer.name()}'"
                )
                continue
            field_idx = layer.fields().indexOf(identifier_field)
            if field_idx < 0:
                for i, field in enumerate(layer.fields()):
                    if field.name().lower() == identifier_field.lower():
                        field_idx = i
                        break
            if field_idx < 0:
                continue
            for feature in layer.getFeatures():
                maybe_yield_to_ui()
                relation_value = feature.attribute(field_idx)
                if not self._is_valid_relation_value(relation_value):
                    continue
                key = self._relation_value_key(relation_value)
                if key not in index:
                    index[key] = []
                index[key].append((layer, feature))
        return index

    def _get_object_topo_identifier_keys(self, feature: Any, objects_layer: Any) -> List[str]:
        """Return normalized first/last topo identifiers declared on an object feature."""
        if not feature or not objects_layer:
            return []
        first_idx, last_idx = self._find_topo_link_field_indices(objects_layer)
        keys: List[str] = []
        for field_idx in (first_idx, last_idx):
            if field_idx < 0:
                continue
            value = feature.attribute(field_idx)
            if self._is_valid_relation_value(value):
                key = self._relation_value_key(value)
                if key not in keys:
                    keys.append(key)
        return keys

    def _detect_distance_by_topo_identifiers(
        self,
        objects_layer: Any,
        primary_points_layer: Any = None,
        definitive_points_layer: Any = None,
    ) -> List[Union[str, WarningData]]:
        """
        Pair objects with topo points via ``first_identifier`` / ``last_identifier``.

        This avoids false positives when QGIS relations (or indirect paths through recording
        areas) use non-unique keys such as a recording-area id.
        """
        warnings: List[Union[str, WarningData]] = []
        try:
            points_index = self._index_points_layers_by_topo_identifier(
                primary_points_layer,
                definitive_points_layer
                if definitive_points_layer is not primary_points_layer
                else None,
            )
            if not points_index:
                print("[DEBUG] Distance detection (topo ids): no indexed topo points")
                return warnings

            first_idx, last_idx = self._find_topo_link_field_indices(objects_layer)
            distance_issues: List[Dict[str, Any]] = []
            seen_pairings: AbstractSet[Tuple[int, int]] = set()

            for object_feature in objects_layer.getFeatures():
                maybe_yield_to_ui()
                if not self._object_feature_has_point_association(object_feature, objects_layer):
                    continue
                topo_keys = self._get_object_topo_identifier_keys(object_feature, objects_layer)
                if not topo_keys:
                    continue

                matched_points: List[Tuple[Any, Any]] = []
                for topo_key in topo_keys:
                    matched_points.extend(points_index.get(topo_key, []))

                if not matched_points:
                    continue

                unique_points: Dict[Tuple[str, int], Tuple[Any, Any]] = {}
                for point_layer, point_feature in matched_points:
                    unique_points[(point_layer.id(), point_feature.id())] = (
                        point_layer,
                        point_feature,
                    )

                for point_layer, point_feature in unique_points.values():
                    pairing_key = (object_feature.id(), point_feature.id())
                    if pairing_key in seen_pairings:
                        continue
                    seen_pairings.add(pairing_key)

                    point_geom = point_feature.geometry()
                    object_geom = object_feature.geometry()
                    if point_geom.intersects(object_geom):
                        continue
                    distance = point_geom.distance(object_geom)
                    if distance <= self._max_distance_meters:
                        continue

                    relation_value = topo_keys[0]
                    distance_issues.append({
                        'point_feature': point_feature,
                        'object_feature': object_feature,
                        'point_layer': point_layer,
                        'point_identifier': self._get_feature_identifier(point_feature, "Total Station Point"),
                        'object_identifier': self._get_feature_identifier(object_feature, "Object"),
                        'distance': distance,
                        'relation_value': relation_value,
                    })

            if not distance_issues:
                return warnings

            by_topo_key: Dict[str, List[Dict[str, Any]]] = {}
            for issue in distance_issues:
                key = issue['relation_value']
                if key not in by_topo_key:
                    by_topo_key[key] = []
                by_topo_key[key].append(issue)

            for relation_value, issues in by_topo_key.items():
                point_layer = issues[0]['point_layer']
                point_feature = issues[0]['point_feature']
                object_feature = issues[0]['object_feature']
                identifier_field = self._find_identifier_field(point_layer, is_point_layer=True)
                points_filter = ""
                if identifier_field:
                    field_idx = point_layer.fields().indexOf(identifier_field)
                    if field_idx >= 0:
                        filter_value = point_feature.attribute(field_idx)
                        points_filter = (
                            f'"{identifier_field}" = \'{filter_value}\''
                        )
                if not points_filter:
                    points_filter = f"$id = {point_feature.id()}"

                objects_filter_parts = []
                for field_name, field_idx in (
                    ("first_identifier", first_idx),
                    ("last_identifier", last_idx),
                ):
                    if field_idx < 0:
                        continue
                    fields = objects_layer.fields()
                    actual_name = fields[field_idx].name()
                    value = object_feature.attribute(field_idx)
                    if self._is_valid_relation_value(value):
                        objects_filter_parts.append(f'"{actual_name}" = \'{value}\'')
                objects_filter = (
                    " OR ".join(objects_filter_parts)
                    if objects_filter_parts
                    else f"$id = {object_feature.id()}"
                )

                point_identifiers = sorted({issue['point_identifier'] for issue in issues})
                object_identifiers = sorted({issue['object_identifier'] for issue in issues})
                max_distance = max(issue['distance'] for issue in issues)
                warnings.append(WarningData(
                    message=self._create_distance_warning(
                        point_identifiers, object_identifiers, max_distance, relation_value
                    ),
                    recording_area_name=f"Topo {relation_value}",
                    layer_name=point_layer.name(),
                    filter_expression=points_filter,
                    second_layer_name=objects_layer.name(),
                    second_filter_expression=objects_filter,
                    distance_issues=issues,
                ))
        except Exception as e:
            print(f"[DEBUG] Error in _detect_distance_by_topo_identifiers: {e}")
            import traceback
            traceback.print_exc()

        return warnings

    def _object_feature_has_point_association(self, feature: Any, objects_layer: Any) -> bool:
        """
        Return whether an object feature has an explicit point association.

        When `first_identifier` / `last_identifier` fields exist, they must contain at
        least one non-empty value. This prevents distance warnings on imported objects
        that are not linked to points yet.
        """
        if not feature or not objects_layer:
            return False
        first_idx, last_idx = self._find_topo_link_field_indices(objects_layer)
        if first_idx < 0 and last_idx < 0:
            return True
        first_val = feature.attribute(first_idx) if first_idx >= 0 else None
        last_val = feature.attribute(last_idx) if last_idx >= 0 else None
        return self._is_valid_relation_value(first_val) or self._is_valid_relation_value(last_val)

    def _find_matching_field(self, layer, target_field_name: str) -> Optional[str]:
        """
        Find a field in the given layer whose name matches target_field_name (case-insensitive).
        """
        for f in layer.fields():
            if f.name().lower() == target_field_name.lower():
                return f.name()
        return None

    def _find_relation_field_on_layer(
        self,
        layer: Any,
        relation_field_name: str,
        *,
        is_point_layer: bool,
    ) -> Optional[str]:
        """
        Resolve a relation field on a layer, including common naming mismatches.

        Definitive layers often use ``identifier`` while CSV imports create ``ptid`` / ``pt_id``.
        Objects may use ``label_court`` or ``identifiant`` instead of ``identifier``. Synonyms are
        only tried when the relation field name is a known "standard" link name, to avoid mapping
        an unrelated attribute (e.g. a custom ``ref_site``) to ``id``.
        """
        if not relation_field_name or not layer:
            return None
        direct = self._find_matching_field(layer, relation_field_name)
        if direct:
            return direct
        key = str(relation_field_name).strip().lower()
        if key not in self._STANDARD_RELATION_FIELD_NAMES:
            return None
        if is_point_layer:
            alternates = (
                'ptid', 'pt_id', 'label_court', 'label', 'identifiant', 'identifier',
                'code', 'numero', 'number', 'object_number',
            )
        else:
            alternates = (
                'label_court', 'label', 'object_number', 'number', 'identifiant', 'identifier',
                'code', 'numero', 'ptid', 'pt_id',
            )
        # Only allow id-like fallback when the relation itself explicitly targets id/fid.
        if key in {'id', 'fid'}:
            alternates = alternates + ('id', 'fid')
        seen = {key}
        for alt in alternates:
            al = alt.lower()
            if al in seen:
                continue
            seen.add(al)
            match = self._find_matching_field(layer, alt)
            if match:
                return match
        return None