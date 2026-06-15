"""
Out of Bounds Detector Service for ArcheoSync plugin.

This module provides a service to detect objects, features, small finds, and total-station
(topo) points that are located outside their recording areas by more than a specified
distance (default 20 cm). It analyzes the spatial relationships between features and their
associated recording areas and identifies those that are positioned outside the expected boundaries.

Key Features:
- Detects features located outside recording areas by more than 20 cm
- Supports objects, features, small finds layers, and imported CSV / total-station point layers
- Uses QGIS relations to determine field mappings
- Provides detailed warnings about out-of-bounds features
- Supports translation for warning messages
- Integrates with existing warning display system
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles out-of-bounds detection
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection logic

Usage:
    service = OutOfBoundsDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = service.detect_out_of_bounds_features()
"""

from collections import defaultdict, deque
from typing import List, Dict, Any, Optional, Union, Tuple, AbstractSet

try:
    from ..core.data_structures import WarningData
    from ..core.ui_responsiveness import maybe_yield_to_ui
except ImportError:
    from core.data_structures import WarningData
    from core.ui_responsiveness import maybe_yield_to_ui

from qgis.core import QgsProject, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import QObject

# Temporary import layers created during field-data import (see import_validation_service).
_TEMP_IMPORT_LAYER_NAMES = {
    "objects_layer": "New Objects",
    "features_layer": "New Features",
    "small_finds_layer": "New Small Finds",
}

_LAYER_TYPE_LABELS = {
    "objects_layer": "Objects",
    "features_layer": "Features",
    "small_finds_layer": "Small Finds",
}

_TEMP_TOPO_LAYER_NAME = "Imported_CSV_Points"

_ALL_TEMP_IMPORT_LAYER_NAMES = tuple(_TEMP_IMPORT_LAYER_NAMES.values()) + (_TEMP_TOPO_LAYER_NAME,)

_STANDARD_RELATION_FIELD_NAMES = frozenset({
    'identifier', 'identifiant', 'id', 'code', 'label', 'label_court', 'label_long',
    'object_number', 'number', 'numero', 'ptid', 'pt_id', 'num', 'no',
})


class OutOfBoundsDetectorService(QObject):
    """
    Service for detecting features located outside their recording areas.
    
    This service analyzes the spatial relationships between features (objects, features,
    small finds, total-station points) and their associated recording areas. It identifies
    features that are positioned outside the expected boundaries by more than a specified distance.
    """
    
    def __init__(self, settings_manager, layer_service):
        super().__init__()
        """
        Initialize the service with required dependencies.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        
        # Get configurable thresholds from settings with defaults
        self._max_distance_meters = float(self._settings_manager.get_value('bounds_max_distance', 0.2))
    
    def detect_out_of_bounds_features(self) -> List[Union[str, WarningData]]:
        """
        Detect features located outside their recording areas.

        Only pending temporary import layers are scanned (``New Objects``,
        ``New Features``, ``New Small Finds``, ``Imported_CSV_Points``).
        
        Returns:
            List of warning messages or structured warning data about out-of-bounds features
        """
        warnings = []
        
        # Check if out of bounds warnings are enabled
        if not self._settings_manager.get_value('enable_bounds_warnings', True):
            print(f"[DEBUG] Out of bounds warnings are disabled, skipping detection")
            return warnings
        
        print(f"[DEBUG] Starting out-of-bounds detection with max_distance_meters: {self._max_distance_meters}")
        
        try:
            # Get configuration from settings
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer')
            
            print(f"[DEBUG] Layer IDs from settings:")
            print(f"[DEBUG]   recording_areas_layer_id: {recording_areas_layer_id}")
            for setting_key, temp_name in _TEMP_IMPORT_LAYER_NAMES.items():
                print(
                    f"[DEBUG]   {setting_key}: "
                    f"{self._settings_manager.get_value(setting_key)} "
                    f"(temp: {temp_name})"
                )
            
            if not recording_areas_layer_id:
                print(f"[DEBUG] No recording areas layer configured, returning empty warnings")
                return warnings
            
            # Get recording areas layer
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if not recording_areas_layer:
                print(f"[DEBUG] Could not get recording areas layer with ID: {recording_areas_layer_id}")
                return warnings
            
            print(f"[DEBUG] Successfully got recording areas layer: {recording_areas_layer.name()}")
            print(f"[DEBUG] Recording areas layer feature count: {recording_areas_layer.featureCount()}")

            if not self._has_temporary_import_layers():
                print("[DEBUG] No temporary import layers present, skipping out-of-bounds detection")
                return warnings

            layers_to_check = self._resolve_layers_to_check()
            for layer_id, layer_type in layers_to_check:
                print(f"[DEBUG] Checking {layer_type} layer ({layer_id})...")
                layer_warnings = self._detect_out_of_bounds_in_layer(
                    layer_id, recording_areas_layer, layer_type
                )
                print(f"[DEBUG] {layer_type} layer returned {len(layer_warnings)} warnings")
                warnings.extend(layer_warnings)

            topo_warnings = self._detect_topo_points_out_of_bounds(recording_areas_layer)
            print(f"[DEBUG] Total station points layer returned {len(topo_warnings)} warnings")
            warnings.extend(topo_warnings)
            
            print(f"[DEBUG] Total out-of-bounds warnings found: {len(warnings)}")
            
        except Exception as e:
            print(f"[DEBUG] Error in out-of-bounds detection: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings

    def _has_temporary_import_layers(self) -> bool:
        """Return whether any pending ArcheoSync import layer exists in the project."""
        return any(
            self._layer_service.get_layer_by_name(layer_name)
            for layer_name in _ALL_TEMP_IMPORT_LAYER_NAMES
        )

    def _resolve_layers_to_check(self) -> List[Tuple[str, str]]:
        """
        Resolve which object/feature/small-find layers should be scanned.

        Only existing temporary ``New *`` import layers are checked. Definitive
        project layers are never scanned by this service.
        """
        layers_to_check: List[Tuple[str, str]] = []
        for setting_key, temp_layer_name in _TEMP_IMPORT_LAYER_NAMES.items():
            if not self._settings_manager.get_value(setting_key):
                continue

            temp_layer = self._layer_service.get_layer_by_name(temp_layer_name)
            if temp_layer:
                layers_to_check.append((temp_layer.id(), _LAYER_TYPE_LABELS[setting_key]))

        return layers_to_check

    def _detect_topo_points_out_of_bounds(self, recording_areas_layer: Any) -> List[Union[str, WarningData]]:
        """
        Detect out-of-bounds total-station (topo) points in ``Imported_CSV_Points``.

        Supports direct and multi-hop QGIS relations to recording areas. Definitive
        topo layers are used only to resolve relation metadata, not for spatial checks.
        """
        warnings: List[Union[str, WarningData]] = []
        temp_topo = self._layer_service.get_layer_by_name(_TEMP_TOPO_LAYER_NAME)
        if not temp_topo:
            print("[DEBUG] No temporary topo import layer, skipping topo out-of-bounds check")
            return warnings

        definitive_topo_id = self._settings_manager.get_value('total_station_points_layer')
        if not definitive_topo_id:
            print("[DEBUG] No total station points layer configured")
            return warnings

        definitive_topo = self._layer_service.get_layer_by_id(definitive_topo_id)
        if not definitive_topo:
            print(f"[DEBUG] Could not get definitive topo layer with ID: {definitive_topo_id}")
            return warnings

        check_layer = temp_topo
        print(
            f"[DEBUG] Checking temporary topo points layer '{check_layer.name()}'"
        )

        direct_relation = self._get_relation_for_layer(definitive_topo, recording_areas_layer)
        if direct_relation:
            print("[DEBUG] Topo out-of-bounds: using direct relation to recording areas")
            return self._detect_out_of_bounds_in_layer(
                check_layer.id(), recording_areas_layer, "Total Station Points"
            )

        indirect_path = self._find_shortest_relation_path(definitive_topo, recording_areas_layer)
        if not indirect_path:
            print("[DEBUG] No direct or indirect relation between topo points and recording areas")
            return warnings

        print(f"[DEBUG] Topo out-of-bounds: indirect path hops = {len(indirect_path)}")
        return self._detect_out_of_bounds_via_relation_path(
            check_layer, definitive_topo, recording_areas_layer, indirect_path
        )
    
    def _detect_out_of_bounds_in_layer(self,
                                     layer_id: str, 
                                     recording_areas_layer: Any, 
                                     layer_type: str) -> List[Union[str, WarningData]]:
        """
        Detect out-of-bounds features in a specific layer.
        
        Args:
            layer_id: The layer ID to check
            recording_areas_layer: The recording areas layer
            layer_type: The type of layer (Objects, Features, Small Finds)
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        print(f"[DEBUG] _detect_out_of_bounds_in_layer called for layer_id: {layer_id}, layer_type: {layer_type}")
        
        try:
            # Get the layer
            layer = self._layer_service.get_layer_by_id(layer_id)
            if not layer:
                print(f"[DEBUG] Could not get layer with ID: {layer_id}")
                return warnings
            
            print(f"[DEBUG] Successfully got layer: {layer.name()}")
            print(f"[DEBUG] Layer feature count: {layer.featureCount()}")
            print(f"[DEBUG] Layer fields: {[field.name() for field in layer.fields()]}")
            
            # Get the recording area field name from relations
            recording_area_field = self._get_recording_area_field(layer, recording_areas_layer)
            print(f"[DEBUG] Recording area field found: {recording_area_field}")
            
            if not recording_area_field:
                print(f"[DEBUG] No recording area field found, trying fallback for temporary layers...")
                # For temporary layers, try to get the field name from the corresponding definitive layer
                if layer.name().startswith("New "):
                    print(f"[DEBUG] Layer is temporary: {layer.name()}")
                    # Map temporary layer names to definitive layer types
                    layer_type_mapping = {
                        "New Objects": "objects_layer",
                        "New Features": "features_layer",
                        "New Small Finds": "small_finds_layer"
                    }

                    definitive_layer_key = layer_type_mapping.get(layer.name())
                    print(f"[DEBUG] Definitive layer key: {definitive_layer_key}")
                    if definitive_layer_key:
                        definitive_layer_id = self._settings_manager.get_value(definitive_layer_key)
                        print(f"[DEBUG] Definitive layer ID: {definitive_layer_id}")
                        if definitive_layer_id:
                            definitive_layer = self._layer_service.get_layer_by_id(definitive_layer_id)
                            if definitive_layer:
                                print(f"[DEBUG] Got definitive layer: {definitive_layer.name()}")
                                # Get the field name from the definitive layer's relation
                                definitive_field = self._get_recording_area_field(definitive_layer, recording_areas_layer)
                                print(f"[DEBUG] Definitive field: {definitive_field}")
                                if definitive_field:
                                    # Check if the temporary layer has the same field
                                    field_idx = layer.fields().indexOf(definitive_field)
                                    print(f"[DEBUG] Field index in temporary layer: {field_idx}")
                                    if field_idx >= 0:
                                        recording_area_field = definitive_field
                                        print(f"[DEBUG] Using definitive field: {recording_area_field}")
                elif layer.name() == _TEMP_TOPO_LAYER_NAME:
                    print(f"[DEBUG] Layer is temporary topo import: {layer.name()}")
                    definitive_layer_id = self._settings_manager.get_value('total_station_points_layer')
                    if definitive_layer_id:
                        definitive_layer = self._layer_service.get_layer_by_id(definitive_layer_id)
                        if definitive_layer:
                            definitive_field = self._get_recording_area_field(
                                definitive_layer, recording_areas_layer
                            )
                            if definitive_field:
                                resolved_field = self._find_relation_field_on_layer(
                                    layer, definitive_field, is_point_layer=True
                                )
                                if resolved_field:
                                    recording_area_field = resolved_field
                                    print(
                                        f"[DEBUG] Using topo field from definitive layer: "
                                        f"{recording_area_field}"
                                    )
                    
                    if not recording_area_field:
                        print(f"[DEBUG] Still no recording area field found for temporary layer")
                        return warnings
                else:
                    print(f"[DEBUG] Layer is not temporary and no recording area field found")
                    return warnings
            
            # Get field indices
            recording_area_field_idx = layer.fields().indexOf(recording_area_field)
            print(f"[DEBUG] Recording area field index: {recording_area_field_idx}")
            if recording_area_field_idx < 0:
                print(f"[DEBUG] Recording area field not found in layer")
                return warnings
            
            # Get the field mapping information for finding recording area features
            referenced_field_name = None
            if layer.name().startswith("New "):
                # For temporary layers, we need to get the field mapping from the definitive layer
                layer_type_mapping = {
                    "New Objects": "objects_layer",
                    "New Features": "features_layer",
                    "New Small Finds": "small_finds_layer"
                }

                definitive_layer_key = layer_type_mapping.get(layer.name())
                if definitive_layer_key:
                    definitive_layer_id = self._settings_manager.get_value(definitive_layer_key)
                    if definitive_layer_id:
                        definitive_layer = self._layer_service.get_layer_by_id(definitive_layer_id)
                        if definitive_layer:
                            # Get the relation from the definitive layer
                            relation = self._get_relation_for_layer(definitive_layer, recording_areas_layer)
                            if relation:
                                field_pairs = relation.fieldPairs()
                                if field_pairs:
                                    # Get the referenced field name (the field in the recording areas layer)
                                    referenced_field_name = list(field_pairs.values())[0]
                                    print(f"[DEBUG] Using field mapping from definitive layer: {recording_area_field} -> {referenced_field_name}")
            elif layer.name() == _TEMP_TOPO_LAYER_NAME:
                definitive_layer_id = self._settings_manager.get_value('total_station_points_layer')
                if definitive_layer_id:
                    definitive_layer = self._layer_service.get_layer_by_id(definitive_layer_id)
                    if definitive_layer:
                        relation = self._get_relation_for_layer(definitive_layer, recording_areas_layer)
                        if relation:
                            field_pairs = relation.fieldPairs()
                            if field_pairs:
                                referenced_field_name = list(field_pairs.values())[0]
                                print(
                                    f"[DEBUG] Using topo field mapping from definitive layer: "
                                    f"{recording_area_field} -> {referenced_field_name}"
                                )
            else:
                # For definitive layers, get the relation directly
                relation = self._get_relation_for_layer(layer, recording_areas_layer)
                if relation:
                    field_pairs = relation.fieldPairs()
                    if field_pairs:
                        # Get the referenced field name (the field in the recording areas layer)
                        referenced_field_name = list(field_pairs.values())[0]
                        print(f"[DEBUG] Using field mapping from layer relation: {recording_area_field} -> {referenced_field_name}")
            
            if not referenced_field_name:
                print(f"[DEBUG] Could not determine field mapping for recording area lookup")
                return warnings
            
            # Get the referenced field index in the recording areas layer
            referenced_field_idx = recording_areas_layer.fields().indexOf(referenced_field_name)
            if referenced_field_idx < 0:
                print(f"[DEBUG] Referenced field '{referenced_field_name}' not found in recording areas layer")
                return warnings
            
            print(f"[DEBUG] Recording area lookup field: {referenced_field_name} (index: {referenced_field_idx})")

            # Collect only features that have geometry and a recording area reference.
            features_to_check = []
            feature_count = 0
            max_features = 10000  # Safety limit

            print(f"[DEBUG] Collecting features with geometry...")
            for feature in layer.getFeatures():
                maybe_yield_to_ui(every=50)
                feature_count += 1
                if feature_count > max_features:
                    print(f"[DEBUG] Warning: Too many features ({feature_count}), limiting to {max_features}")
                    break

                if not feature.geometry() or feature.geometry().isEmpty():
                    continue

                recording_area_value = feature.attribute(recording_area_field_idx)
                if not recording_area_value:
                    continue

                features_to_check.append((feature, recording_area_value))

            print(f"[DEBUG] Features with geometry and recording area: {len(features_to_check)}")
            if not features_to_check:
                print(f"[DEBUG] No features to check, skipping recording-area lookup")
                return warnings

            needed_recording_area_values = {value for _, value in features_to_check}
            recording_areas_by_value = {}
            for ra_feature in recording_areas_layer.getFeatures():
                maybe_yield_to_ui(every=50)
                ra_value = ra_feature.attribute(referenced_field_idx)
                if ra_value in needed_recording_area_values:
                    recording_areas_by_value[ra_value] = ra_feature
            
            # Check each feature with geometry
            out_of_bounds_features = []
            processed_features = 0
            features_with_recording_area = 0
            features_outside = 0
            
            print(f"[DEBUG] Starting feature processing...")
            
            for feature, recording_area_value in features_to_check:
                maybe_yield_to_ui(every=50)
                features_with_recording_area += 1
                
                # Find the recording area feature that matches this value
                recording_area_feature = recording_areas_by_value.get(recording_area_value)
                recording_area_geometry = (
                    recording_area_feature.geometry()
                    if recording_area_feature is not None
                    else None
                )
                
                if not recording_area_geometry or recording_area_geometry.isEmpty():
                    continue
                
                feature_geometry = feature.geometry()
                
                # Check if feature is outside the recording area
                if not recording_area_geometry.contains(feature_geometry):
                    features_outside += 1
                    # Calculate the distance to the recording area boundary
                    distance = recording_area_geometry.distance(feature_geometry)
                    maybe_yield_to_ui(every=50)
                    
                    if distance > self._max_distance_meters:
                        # Get recording area name
                        recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_feature)
                        
                        # Get feature identifier (number field if available)
                        feature_identifier = self._get_feature_identifier(feature, layer_type)
                        
                        print(f"[DEBUG] Found out-of-bounds feature: {feature_identifier} in {recording_area_name}, distance: {distance:.3f}m")
                        
                        out_of_bounds_features.append({
                            'feature': feature,
                            'feature_id': feature.id(),  # Store the FID directly
                            'recording_area_name': recording_area_name,
                            'recording_area_id': recording_area_value,
                            'distance': distance,
                            'feature_identifier': feature_identifier
                        })
                
                processed_features += 1
                if processed_features % 100 == 0:
                    print(f"[DEBUG] Processed {processed_features} features...")
            
            print(f"[DEBUG] Feature processing complete:")
            print(f"[DEBUG]   Total features scanned: {feature_count}")
            print(f"[DEBUG]   Features with geometry and recording area: {features_with_recording_area}")
            print(f"[DEBUG]   Features outside recording areas: {features_outside}")
            print(f"[DEBUG]   Out-of-bounds features (beyond {self._max_distance_meters}m): {len(out_of_bounds_features)}")
            
            # Create warnings for out-of-bounds features
            if out_of_bounds_features:
                print(f"[DEBUG] Creating warnings for {len(out_of_bounds_features)} out-of-bounds features")
                # Group by recording area for better organization
                by_recording_area = {}
                for item in out_of_bounds_features:
                    recording_area_id = item['recording_area_id']
                    if recording_area_id not in by_recording_area:
                        by_recording_area[recording_area_id] = []
                    by_recording_area[recording_area_id].append(item)
                
                for recording_area_id, items in by_recording_area.items():
                    recording_area_name = items[0]['recording_area_name']
                    feature_identifiers = [item['feature_identifier'] for item in items]
                    max_distance = max(item['distance'] for item in items)
                    
                    # Create filter expression to select only the out-of-bounds features
                    filter_expression = self._build_out_of_bounds_filter_expression(
                        layer, items, layer_type
                    )
                    
                    # Debug: Verify filter expression
                    print(f"[DEBUG] Creating filter expression: {filter_expression}")
                    
                    print(f"[DEBUG] Creating warning for {recording_area_name}: {len(items)} features, max distance: {max_distance:.3f}m")
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_out_of_bounds_warning(
                            recording_area_name, layer_type, feature_identifiers, max_distance
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=layer.name(),  # Use actual layer name instead of layer type
                        filter_expression=filter_expression,
                        out_of_bounds_features=items
                    )
                    warnings.append(warning_data)
                    print(f"[DEBUG] Created warning: {warning_data.message}")
            else:
                print(f"[DEBUG] No out-of-bounds features found")
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_out_of_bounds_in_layer: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] _detect_out_of_bounds_in_layer returning {len(warnings)} warnings")
        return warnings

    def _detect_out_of_bounds_via_relation_path(
        self,
        check_layer: Any,
        definitive_start_layer: Any,
        recording_areas_layer: Any,
        relations_path: List[Any],
    ) -> List[Union[str, WarningData]]:
        """
        Detect out-of-bounds features by following a multi-hop QGIS relation path to recording areas.

        Used for topo points when no direct relation links them to recording areas (for example
        points → link table → recording areas).
        """
        warnings: List[Union[str, WarningData]] = []
        try:
            ordered_def = self._ordered_layers_along_path(definitive_start_layer, relations_path)
            if (
                not ordered_def
                or ordered_def[-1].id() != recording_areas_layer.id()
                or ordered_def[0].id() != definitive_start_layer.id()
            ):
                print("[DEBUG] Topo out-of-bounds (indirect): path does not connect layers")
                return warnings

            combo_layers: List[Any] = []
            for index, def_layer in enumerate(ordered_def):
                if index == 0 and check_layer and check_layer.id() != def_layer.id():
                    combo_layers.append(check_layer)
                else:
                    combo_layers.append(def_layer)

            print(
                "[DEBUG] Topo out-of-bounds (indirect): resolved path layers = "
                f"{[layer.name() if layer else '<none>' for layer in combo_layers]}"
            )

            hops: List[Tuple[int, int]] = []
            for hop_index, relation in enumerate(relations_path):
                from_def = ordered_def[hop_index]
                names = self._field_names_for_relation_hop(relation, from_def)
                if not names:
                    print("[DEBUG] Topo out-of-bounds (indirect): relation has no field pairs")
                    return warnings
                from_name, to_name = names
                from_idx = self._field_index_on_path_layer(
                    combo_layers[hop_index], from_name, from_def, definitive_start_layer
                )
                to_idx = self._field_index_on_path_layer(
                    combo_layers[hop_index + 1], to_name, ordered_def[hop_index + 1],
                    definitive_start_layer,
                )
                if from_idx < 0 or to_idx < 0:
                    print(
                        "[DEBUG] Topo out-of-bounds (indirect): could not resolve hop fields "
                        f"(hop {hop_index}: from_idx={from_idx}, to_idx={to_idx})"
                    )
                    return warnings
                hops.append((from_idx, to_idx))

            features_by_layer: List[List[Any]] = []
            for layer in combo_layers:
                layer_features = []
                for feature in layer.getFeatures():
                    maybe_yield_to_ui()
                    layer_features.append(feature)
                features_by_layer.append(layer_features)

            if not features_by_layer[0]:
                return warnings

            indices: List[Dict[str, List[Any]]] = []
            for hop_index in range(len(hops)):
                to_idx = hops[hop_index][1]
                bucket: Dict[str, List[Any]] = defaultdict(list)
                for feature in features_by_layer[hop_index + 1]:
                    maybe_yield_to_ui()
                    value = feature.attribute(to_idx)
                    if not self._is_valid_relation_value(value):
                        continue
                    bucket[self._relation_value_key(value)].append(feature)
                indices.append(dict(bucket))

            out_of_bounds_features: List[Dict[str, Any]] = []
            for point_feature in features_by_layer[0]:
                maybe_yield_to_ui()
                if not point_feature.geometry() or point_feature.geometry().isEmpty():
                    continue

                start_value = point_feature.attribute(hops[0][0])
                if not self._is_valid_relation_value(start_value):
                    continue

                current_matches = indices[0].get(self._relation_value_key(start_value), [])
                for hop_index in range(1, len(hops)):
                    next_matches: List[Any] = []
                    from_idx = hops[hop_index][0]
                    index_map = indices[hop_index]
                    for candidate in current_matches:
                        link_value = candidate.attribute(from_idx)
                        if not self._is_valid_relation_value(link_value):
                            continue
                        next_matches.extend(
                            index_map.get(self._relation_value_key(link_value), [])
                        )
                    current_matches = next_matches

                point_geometry = point_feature.geometry()
                for recording_area_feature in current_matches:
                    maybe_yield_to_ui()
                    recording_area_geometry = recording_area_feature.geometry()
                    if not recording_area_geometry or recording_area_geometry.isEmpty():
                        continue
                    if recording_area_geometry.contains(point_geometry):
                        continue
                    distance = recording_area_geometry.distance(point_geometry)
                    if distance <= self._max_distance_meters:
                        continue

                    recording_area_name = self._get_recording_area_name(
                        recording_areas_layer, recording_area_feature
                    )
                    feature_identifier = self._get_feature_identifier(
                        point_feature, "Total Station Points"
                    )
                    out_of_bounds_features.append({
                        'feature': point_feature,
                        'feature_id': point_feature.id(),
                        'recording_area_name': recording_area_name,
                        'recording_area_id': recording_area_feature.id(),
                        'distance': distance,
                        'feature_identifier': feature_identifier,
                    })

            if not out_of_bounds_features:
                return warnings

            by_recording_area: Dict[Any, List[Dict[str, Any]]] = {}
            for item in out_of_bounds_features:
                recording_area_id = item['recording_area_id']
                if recording_area_id not in by_recording_area:
                    by_recording_area[recording_area_id] = []
                by_recording_area[recording_area_id].append(item)

            for recording_area_id, items in by_recording_area.items():
                recording_area_name = items[0]['recording_area_name']
                feature_identifiers = [item['feature_identifier'] for item in items]
                max_distance = max(item['distance'] for item in items)
                filter_expression = self._build_out_of_bounds_filter_expression(
                    check_layer, items, "Total Station Points"
                )
                warning_data = WarningData(
                    message=self._create_out_of_bounds_warning(
                        recording_area_name, "Total Station Points", feature_identifiers, max_distance
                    ),
                    recording_area_name=recording_area_name,
                    layer_name=check_layer.name(),
                    filter_expression=filter_expression,
                    out_of_bounds_features=items,
                )
                warnings.append(warning_data)

        except Exception as e:
            print(f"[DEBUG] Error in _detect_out_of_bounds_via_relation_path: {e}")
            import traceback
            traceback.print_exc()

        return warnings

    def _build_out_of_bounds_filter_expression(
        self,
        layer: Any,
        items: List[Dict[str, Any]],
        layer_type: str,
    ) -> str:
        """Build a QGIS expression to select out-of-bounds features in the attribute table."""
        if layer_type == "Total Station Points":
            for field_name in ('identifier', 'PtID', 'ptid', 'point_id', 'Label'):
                field_idx = layer.fields().indexOf(field_name)
                if field_idx < 0:
                    continue
                values = []
                for item in items:
                    value = item['feature'].attribute(field_idx)
                    if value is not None and str(value).strip():
                        values.append(f"'{value}'")
                if values:
                    return f'"{field_name}" IN ({",".join(values)})'

        label_field_idx = layer.fields().indexOf('Label')
        if label_field_idx >= 0:
            feature_labels = []
            for item in items:
                label_value = item['feature'].attribute(label_field_idx)
                if label_value:
                    feature_labels.append(f"'{label_value}'")
            if feature_labels:
                return f'"Label" IN ({",".join(feature_labels)})'

        feature_ids = [str(item['feature_id']) for item in items]
        return f"$id IN ({','.join(feature_ids)})"

    def _other_layer_in_relation(self, current_layer: Any, relation: Any) -> Optional[Any]:
        """Return the layer at the other end of ``relation`` from ``current_layer``."""
        try:
            ref = relation.referencingLayer()
            rec = relation.referencedLayer()
            if not ref or not rec or not current_layer:
                return None
            current_id = current_layer.id()
            if ref.id() == current_id:
                return rec
            if rec.id() == current_id:
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
    ) -> Optional[List[Any]]:
        """Shortest chain of QgsRelation instances connecting two layers (BFS)."""
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
                        relation_id = self._relation_project_id(relation, rel_key)
                        if relation_id in forbidden_relation_ids:
                            continue
                    nxt = self._other_layer_in_relation(current, relation)
                    if not nxt:
                        continue
                    new_path = path + [relation]
                    if nxt.id() == layer_end.id():
                        return new_path
                    if nxt.id() in visited:
                        continue
                    visited.add(nxt.id())
                    queue.append((nxt, new_path))
            return None
        except Exception as e:
            print(f"[DEBUG] Error finding indirect relation path: {e}")
            return None

    def _relation_project_id(self, relation: Any, dict_key: Any = None) -> str:
        """Stable string id for a QgsRelation."""
        try:
            relation_id = relation.id()
            if relation_id:
                return str(relation_id)
        except Exception:
            pass
        if dict_key is not None:
            return str(dict_key)
        return str(id(relation))

    def _ordered_layers_along_path(
        self,
        layer_start: Any,
        relations_path: List[Any],
    ) -> Optional[List[Any]]:
        """Reconstruct [L0, L1, ..., Ln] where each relation connects consecutive layers."""
        layers = [layer_start]
        current = layer_start
        for relation in relations_path:
            nxt = self._other_layer_in_relation(current, relation)
            if not nxt:
                return None
            layers.append(nxt)
            current = nxt
        return layers

    def _field_names_for_relation_hop(self, relation: Any, from_layer: Any) -> Optional[Tuple[str, str]]:
        """Return (field_on_from_layer, field_on_to_layer) for one relation hop."""
        field_pairs = relation.fieldPairs()
        if not field_pairs:
            return None
        ref_field, rec_field = next(iter(field_pairs.items()))
        ref_layer = relation.referencingLayer()
        rec_layer = relation.referencedLayer()
        if not ref_layer or not rec_layer:
            return None
        if from_layer.id() == ref_layer.id():
            return ref_field, rec_field
        if from_layer.id() == rec_layer.id():
            return rec_field, ref_field
        return None

    def _field_index_on_path_layer(
        self,
        combo_layer: Any,
        relation_field_name: str,
        path_def_layer: Any,
        definitive_topo_layer: Any,
    ) -> int:
        """Resolve a relation field name to a field index on a path layer."""
        is_point_layer = path_def_layer.id() == definitive_topo_layer.id()
        field_name = self._find_relation_field_on_layer(
            combo_layer, relation_field_name, is_point_layer=is_point_layer
        )
        if not field_name:
            return -1
        field_idx = combo_layer.fields().indexOf(field_name)
        if field_idx >= 0:
            return field_idx
        for index, field in enumerate(combo_layer.fields()):
            if field.name().lower() == field_name.lower():
                return index
        return -1

    def _find_matching_field(self, layer: Any, target_field_name: str) -> Optional[str]:
        """Find a field whose name matches ``target_field_name`` (case-insensitive)."""
        for field in layer.fields():
            if field.name().lower() == target_field_name.lower():
                return field.name()
        return None

    def _find_relation_field_on_layer(
        self,
        layer: Any,
        relation_field_name: str,
        *,
        is_point_layer: bool,
    ) -> Optional[str]:
        """Resolve a relation field on a layer, including common naming mismatches."""
        if not relation_field_name or not layer:
            return None
        direct = self._find_matching_field(layer, relation_field_name)
        if direct:
            return direct
        key = str(relation_field_name).strip().lower()
        if key not in _STANDARD_RELATION_FIELD_NAMES:
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
        if key in {'id', 'fid'}:
            alternates = alternates + ('id', 'fid')
        seen = {key}
        for alternate in alternates:
            alternate_lower = alternate.lower()
            if alternate_lower in seen:
                continue
            seen.add(alternate_lower)
            match = self._find_matching_field(layer, alternate)
            if match:
                return match
        return None

    def _is_valid_relation_value(self, relation_value: Any) -> bool:
        """Return whether a relation value can safely link features."""
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
    
    def _get_relation_for_layer(self, layer: Any, recording_areas_layer: Any) -> Optional[Any]:
        """
        Get the relation between a layer and the recording areas layer.
        
        Args:
            layer: The layer to check
            recording_areas_layer: The recording areas layer
            
        Returns:
            The relation object if found, None otherwise
        """
        try:
            print(f"[DEBUG] _get_relation_for_layer called for layer: {layer.name()}")
            
            # Get the relation manager
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            print(f"[DEBUG] Found {len(relation_manager.relations())} total relations in project")
            
            # Find relations where the layer is the referencing layer
            # and the recording areas layer is the referenced layer
            for relation in relation_manager.relations().values():
                print(f"[DEBUG] Checking relation: {relation.name()}")
                print(f"[DEBUG]   Referencing layer: {relation.referencingLayer().name() if relation.referencingLayer() else 'None'}")
                print(f"[DEBUG]   Referenced layer: {relation.referencedLayer().name() if relation.referencedLayer() else 'None'}")
                
                if (relation.referencingLayer() == layer and 
                    relation.referencedLayer() == recording_areas_layer):
                    print(f"[DEBUG] Found matching relation: {relation.name()}")
                    return relation
            
            print(f"[DEBUG] No matching relation found")
            return None
            
        except Exception as e:
            print(f"[DEBUG] Error getting relation for layer: {str(e)}")
            return None
    
    def _get_recording_area_field(self, layer: Any, recording_areas_layer: Any) -> Optional[str]:
        """
        Get the field name in the layer that references the recording areas layer.
        
        Args:
            layer: The layer to check
            recording_areas_layer: The recording areas layer
            
        Returns:
            The field name that references the recording areas layer, or None if not found
        """
        try:
            print(f"[DEBUG] _get_recording_area_field called for layer: {layer.name()}")
            
            relation = self._get_relation_for_layer(layer, recording_areas_layer)
            if relation:
                field_pairs = relation.fieldPairs()
                print(f"[DEBUG] Field pairs in relation: {field_pairs}")
                if field_pairs:
                    # Return the first referencing field (should be the recording area field)
                    recording_area_field = list(field_pairs.keys())[0]
                    print(f"[DEBUG] Found recording area field: {recording_area_field}")
                    return recording_area_field
                else:
                    print(f"[DEBUG] No field pairs found in relation")
            else:
                print(f"[DEBUG] No relation found")
            
            return None
            
        except Exception as e:
            print(f"[DEBUG] Error getting recording area field: {str(e)}")
            return None
    
    def _get_recording_area_name(self, recording_areas_layer: Any, recording_area_feature: Any) -> str:
        """
        Get the name of a recording area from its feature.
        
        Args:
            recording_areas_layer: The recording areas layer
            recording_area_feature: The recording area feature
            
        Returns:
            The recording area name, or the ID as string if name not found
        """
        try:
            if recording_area_feature and recording_area_feature.isValid():
                # Try to use the layer's display expression first
                display_expression = recording_areas_layer.displayExpression()
                if display_expression:
                    try:
                        from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
                        
                        # Create expression context
                        context = QgsExpressionContext()
                        context.appendScope(QgsExpressionContextUtils.layerScope(recording_areas_layer))
                        context.setFeature(recording_area_feature)
                        
                        # Evaluate the display expression
                        expression = QgsExpression(display_expression)
                        result = expression.evaluate(context)
                        
                        if result and str(result) != 'NULL':
                            return str(result)
                    except Exception as e:
                        print(f"Error evaluating display expression: {e}")
                
                # Fallback: Try to get a name field if available
                name_field_idx = recording_areas_layer.fields().indexOf('name')
                if name_field_idx >= 0:
                    name = recording_area_feature.attribute(name_field_idx)
                    if name:
                        return str(name)
                
                # Final fallback to ID
                return str(recording_area_feature.id())
            
            return "Unknown"
            
        except Exception as e:
            print(f"Error getting recording area name: {str(e)}")
            return "Unknown"
    
    def _get_feature_identifier(self, feature: Any, layer_type: str) -> str:
        """
        Get a human-readable identifier for a feature.
        
        Args:
            feature: The feature to get identifier for
            layer_type: The type of layer (Objects, Features, Small Finds)
            
        Returns:
            A string identifier for the feature
        """
        try:
            # Try to get a number field based on layer type
            if layer_type == "Objects":
                number_field = self._settings_manager.get_value('objects_number_field')
                if number_field:
                    number_idx = feature.fields().indexOf(number_field)
                    if number_idx >= 0:
                        number = feature.attribute(number_idx)
                        if number:
                            return f"Object {number}"
            elif layer_type == "Total Station Points":
                for field_name in ('identifier', 'PtID', 'ptid', 'point_id', 'station_id'):
                    field_idx = feature.fields().indexOf(field_name)
                    if field_idx >= 0:
                        value = feature.attribute(field_idx)
                        if value:
                            return f"Point {value}"
            
            # Fallback to feature ID
            return f"{layer_type} {feature.id()}"
            
        except Exception as e:
            print(f"Error getting feature identifier: {str(e)}")
            return f"{layer_type} {feature.id()}"
    
    def _create_out_of_bounds_warning(self, recording_area_name: str, layer_type: str, feature_identifiers: List[str], max_distance: float) -> str:
        """
        Create a warning message for out-of-bounds features.
        
        Args:
            recording_area_name: The name of the recording area
            layer_type: The type of layer (Objects, Features, Small Finds)
            feature_identifiers: List of feature identifiers
            max_distance: The maximum distance found
            
        Returns:
            A formatted warning message
        """
        try:
            if len(feature_identifiers) == 1:
                feature_text = feature_identifiers[0]
            else:
                feature_text = f"{len(feature_identifiers)} features"
            distance_cm = max_distance * 100
            return self.tr(f"{feature_text} in recording area '{recording_area_name}' is located {distance_cm:.1f} cm outside the recording area boundary (maximum allowed: {self._max_distance_meters * 100:.1f} cm)")
        except Exception as e:
            print(f"Error creating out-of-bounds warning: {str(e)}")
            return f"{feature_text} in recording area '{recording_area_name}' is located outside the recording area boundary" 