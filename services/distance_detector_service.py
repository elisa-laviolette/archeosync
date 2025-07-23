"""
Distance Detector Service for ArcheoSync plugin.

This module provides a service that detects when total station points and their related
objects are too far from each other (default 5 cm) and not overlapping. It only checks
when the definitive objects and total station points layers are related.

Key Features:
- Detects total station points and objects that are too far apart (> 5 cm)
- Only checks when layers are related via QGIS relations
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
        translation_service=translation_service
    )
    
    warnings = detector.detect_distance_warnings()
"""

from typing import List, Optional, Any, Union, Dict, Tuple
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea, QgsSpatialIndex

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from ..core.data_structures import WarningData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData


class DistanceDetectorService:
    """
    Service for detecting distance issues between total station points and related objects.
    
    This service analyzes the spatial relationships between total station points and
    their related objects (via QGIS relations). It identifies pairs that are too far
    apart (> 5 cm) and not overlapping.
    """
    
    def __init__(self, settings_manager, layer_service):
        """
        Initialize the service with required dependencies.
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        # Get configurable thresholds from settings with defaults, always as float
        self._max_distance_meters = float(self._settings_manager.get_value('distance_max_distance', 0.05))
    
    def detect_distance_warnings(self) -> List[Union[str, WarningData]]:
        print("[DEBUG] >>> ENTERED detect_distance_warnings <<<")
        """
        Detect distance warnings between total station points and related objects.
        Returns:
            List of warning messages or structured warning data about distance issues
        """
        warnings = []

        # Check if distance warnings are enabled
        if not self._settings_manager.get_value('enable_distance_warnings', True):
            return warnings

        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            objects_layer_id = self._settings_manager.get_value('objects_layer')

            print(f"[DEBUG] total_station_points_layer_id from settings: {total_station_points_layer_id}")
            print(f"[DEBUG] objects_layer_id from settings: {objects_layer_id}")

            # Try to get layers by ID and print their names
            points_layer_by_id = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            objects_layer_by_id = self._layer_service.get_layer_by_id(objects_layer_id)
            print(f"[DEBUG] Layer by ID (total_station_points_layer_id): {getattr(points_layer_by_id, 'name', lambda: None)() if points_layer_by_id else None}")
            print(f"[DEBUG] Layer by ID (objects_layer_id): {getattr(objects_layer_by_id, 'name', lambda: None)() if objects_layer_by_id else None}")

            # Print all loaded layer names
            try:
                from qgis.core import QgsProject
                all_layers = list(QgsProject.instance().mapLayers().values())
                print(f"[DEBUG] All loaded layers: {[layer.name() for layer in all_layers]}")
            except Exception as e:
                print(f"[DEBUG] Could not print all loaded layers: {e}")

            if not total_station_points_layer_id or not objects_layer_id:
                return warnings

            # Get all possible layers
            temp_total_station_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
            temp_objects_layer = self._layer_service.get_layer_by_name("New Objects")
            definitive_total_station_points_layer = points_layer_by_id
            definitive_objects_layer = objects_layer_by_id

            # List of (points_layer, objects_layer, points_layer_type, objects_layer_type)
            layer_combinations = [
                (temp_total_station_points_layer, temp_objects_layer, 'temp', 'temp'),
                (temp_total_station_points_layer, definitive_objects_layer, 'temp', 'definitive'),
                (definitive_total_station_points_layer, temp_objects_layer, 'definitive', 'temp'),
                (definitive_total_station_points_layer, definitive_objects_layer, 'definitive', 'definitive'),
            ]

            for points_layer, objects_layer, points_type, objects_type in layer_combinations:
                if not points_layer or not objects_layer:
                    continue

                # Always use the relation from the definitive layers
                rel_points_layer = definitive_total_station_points_layer
                rel_objects_layer = definitive_objects_layer
                if not rel_points_layer or not rel_objects_layer:
                    continue

                relation = self._get_relation_between_layers(rel_points_layer, rel_objects_layer)
                if not relation:
                    continue

                field_pairs = relation.fieldPairs()
                if not field_pairs:
                    continue

                # Determine which layer is referencing and which is referenced
                if relation.referencingLayer() == rel_points_layer:
                    points_field = list(field_pairs.keys())[0]
                    objects_field = list(field_pairs.values())[0]
                    points_layer_is_referencing = True
                else:
                    objects_field = list(field_pairs.keys())[0]
                    points_field = list(field_pairs.values())[0]
                    points_layer_is_referencing = False

                # Find field indices in the current points_layer and objects_layer (case-insensitive)
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
                    continue

                # Detect distance issues for this combination
                distance_warnings = self._detect_distance_issues(
                    points_layer, objects_layer,
                    points_field_idx, objects_field_idx,
                    points_layer_is_referencing
                )
                if distance_warnings:
                    warnings.extend(distance_warnings)
                    break  # Stop at first successful combination with warnings

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
                relation_value = feature.attribute(points_field_idx)
                if relation_value is not None:
                    relation_value_key = str(relation_value).lower()
                    if relation_value_key not in points_by_relation:
                        points_by_relation[relation_value_key] = []
                    points_by_relation[relation_value_key].append(feature)
            for feature in objects_layer.getFeatures():
                relation_value = feature.attribute(objects_field_idx)
                if relation_value is not None:
                    relation_value_key = str(relation_value).lower()
                    if relation_value_key not in objects_by_relation:
                        objects_by_relation[relation_value_key] = []
                    objects_by_relation[relation_value_key].append(feature)
            # Only check common relation values
            common_relation_values = set(points_by_relation.keys()) & set(objects_by_relation.keys())
            print(f"[DEBUG] points_by_relation keys: {list(points_by_relation.keys())}")
            print(f"[DEBUG] objects_by_relation keys: {list(objects_by_relation.keys())}")
            print(f"[DEBUG] common_relation_values: {list(common_relation_values)}")
            distance_issues = []
            for relation_value in common_relation_values:
                points_features = points_by_relation[relation_value]
                objects_features = objects_by_relation[relation_value]
                print(f"[DEBUG] For relation value {relation_value}: {len(points_features)} point(s), {len(objects_features)} object(s)")
                for pf in points_features:
                    print(f"[DEBUG]   Point feature id: {pf.id()}, geometry: {pf.geometry().asWkt()}")
                for of in objects_features:
                    print(f"[DEBUG]   Object feature id: {of.id()}, geometry: {of.geometry().asWkt()}")
                # All-pairs check for each point/object with the same relation value
                for point_feature in points_features:
                    point_geom = point_feature.geometry()
                    for object_feature in objects_features:
                        object_geom = object_feature.geometry()
                        point_identifier = self._get_feature_identifier(point_feature, "Total Station Point")
                        object_identifier = self._get_feature_identifier(object_feature, "Object")
                        if point_geom.intersects(object_geom):
                            print(f"[DEBUG] Skipping pair {point_identifier} and {object_identifier} (relation value: {relation_value}) because geometries overlap")
                            continue
                        distance = point_geom.distance(object_geom)
                        print(f"[DEBUG] Checking point {point_identifier} and object {object_identifier} (relation value: {relation_value}): distance = {distance}, threshold = {self._max_distance_meters}")
                        if distance > self._max_distance_meters:
                            distance_issues.append({
                                'point_feature': point_feature,
                                'object_feature': object_feature,
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
                    point_identifiers = [issue['point_identifier'] for issue in issues]
                    object_identifiers = [issue['object_identifier'] for issue in issues]
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
    
    def _get_relation_between_layers(self, layer1: Any, layer2: Any) -> Optional[Any]:
        """
        Get the relation between two layers.
        
        Args:
            layer1: First layer
            layer2: Second layer
            
        Returns:
            The relation object if found, None otherwise
        """
        try:
            
            # Get the relation manager
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            # Find relations between the two layers
            for relation_id, relation in relation_manager.relations().items():
                
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                
                # Check if either layer matches either side of the relation
                if ((referencing_layer and referenced_layer) and
                    ((referencing_layer.id() == layer1.id() and referenced_layer.id() == layer2.id()) or
                     (referencing_layer.id() == layer2.id() and referenced_layer.id() == layer1.id()))):
                    return relation
            
            return None
            
        except Exception as e:
            print(f"[DEBUG] Error getting relation between layers: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
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