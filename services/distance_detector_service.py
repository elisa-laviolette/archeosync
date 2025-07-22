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
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea

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
        
        # Get configurable thresholds from settings with defaults
        self._max_distance_meters = self._settings_manager.get_value('distance_max_distance', 0.05)
    
    def detect_distance_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect distance warnings between total station points and related objects.
        
        Returns:
            List of warning messages or structured warning data about distance issues
        """
        warnings = []
        
        # Check if distance warnings are enabled
        if not self._settings_manager.get_value('enable_distance_warnings', True):
            print(f"[DEBUG] Distance warnings are disabled, skipping detection")
            return warnings
        
        print(f"[DEBUG] Starting distance detection with max_distance_meters: {self._max_distance_meters}")
        
        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            objects_layer_id = self._settings_manager.get_value('objects_layer')
            
            print(f"[DEBUG] Layer IDs from settings:")
            print(f"[DEBUG]   total_station_points_layer_id: {total_station_points_layer_id}")
            print(f"[DEBUG]   objects_layer_id: {objects_layer_id}")
            
            # Check if both layers are configured
            if not total_station_points_layer_id or not objects_layer_id:
                print(f"[DEBUG] Missing layer configuration, returning empty warnings")
                print(f"[DEBUG]   total_station_points_layer_id is None: {total_station_points_layer_id is None}")
                print(f"[DEBUG]   objects_layer_id is None: {objects_layer_id is None}")
                return warnings
            
            # Get layers - look for temporary layers first (like out-of-bounds detector)
            print(f"[DEBUG] Looking for layers...")
            
            # Try to find temporary total station points layer first
            temp_total_station_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
            if temp_total_station_points_layer:
                print(f"[DEBUG] Found temporary 'Imported_CSV_Points' layer: {temp_total_station_points_layer.name()}")
                total_station_points_layer = temp_total_station_points_layer
            else:
                print(f"[DEBUG] No temporary 'Imported_CSV_Points' layer found, using configured layer: {total_station_points_layer_id}")
                total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            
            # Try to find temporary objects layer first
            temp_objects_layer = self._layer_service.get_layer_by_name("New Objects")
            if temp_objects_layer:
                print(f"[DEBUG] Found temporary 'New Objects' layer: {temp_objects_layer.name()}")
                objects_layer = temp_objects_layer
            else:
                print(f"[DEBUG] No temporary 'New Objects' layer found, using configured layer: {objects_layer_id}")
                objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
            
            if not total_station_points_layer or not objects_layer:
                print(f"[DEBUG] Could not get one or both layers")
                print(f"[DEBUG]   total_station_points_layer is None: {total_station_points_layer is None}")
                print(f"[DEBUG]   objects_layer is None: {objects_layer is None}")
                return warnings
            
            print(f"[DEBUG] Successfully got layers:")
            print(f"[DEBUG]   Total station points layer: {total_station_points_layer.name()} (ID: {total_station_points_layer.id()})")
            print(f"[DEBUG]   Objects layer: {objects_layer.name()} (ID: {objects_layer.id()})")
            
            # Check if layers are related - handle temporary layers
            print(f"[DEBUG] Checking for relations between layers...")
            
            # For temporary layers, we need to get relation info from definitive layers
            if (total_station_points_layer.name() == "Imported_CSV_Points" or 
                objects_layer.name() == "New Objects"):
                print(f"[DEBUG] Working with temporary layers, getting relation from definitive layers")
                
                # Get definitive layers to find the relation
                definitive_total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
                definitive_objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
                
                if definitive_total_station_points_layer and definitive_objects_layer:
                    print(f"[DEBUG] Got definitive layers:")
                    print(f"[DEBUG]   Definitive total station points: {definitive_total_station_points_layer.name()}")
                    print(f"[DEBUG]   Definitive objects: {definitive_objects_layer.name()}")
                    
                    # Get relation from definitive layers
                    relation = self._get_relation_between_layers(definitive_total_station_points_layer, definitive_objects_layer)
                    if relation:
                        print(f"[DEBUG] Found relation from definitive layers: {relation.name()}")
                        
                        # Get field mappings from the relation
                        field_pairs = relation.fieldPairs()
                        if field_pairs:
                            print(f"[DEBUG] Field pairs from definitive relation: {field_pairs}")
                            
                            # Determine which layer is referencing and which is referenced
                            if relation.referencingLayer() == definitive_total_station_points_layer:
                                # Total station points layer references objects layer
                                points_field = list(field_pairs.keys())[0]  # Field in total station points layer
                                objects_field = list(field_pairs.values())[0]  # Field in objects layer
                                points_layer_is_referencing = True
                            else:
                                # Objects layer references total station points layer
                                objects_field = list(field_pairs.keys())[0]  # Field in objects layer
                                points_field = list(field_pairs.values())[0]  # Field in total station points layer
                                points_layer_is_referencing = False
                            
                            print(f"[DEBUG] Field mapping from definitive layers:")
                            print(f"[DEBUG]   Points field: {points_field}")
                            print(f"[DEBUG]   Objects field: {objects_field}")
                            print(f"[DEBUG]   Points layer is referencing: {points_layer_is_referencing}")
                            
                            # Get field indices in temporary layers - handle case sensitivity
                            points_field_idx = total_station_points_layer.fields().indexOf(points_field)
                            if points_field_idx < 0:
                                # Try case-insensitive search
                                for i, field in enumerate(total_station_points_layer.fields()):
                                    if field.name().lower() == points_field.lower():
                                        points_field_idx = i
                                        print(f"[DEBUG] Found points field '{field.name()}' (case-insensitive match for '{points_field}')")
                                        break
                            
                            objects_field_idx = objects_layer.fields().indexOf(objects_field)
                            if objects_field_idx < 0:
                                # Try case-insensitive search
                                for i, field in enumerate(objects_layer.fields()):
                                    if field.name().lower() == objects_field.lower():
                                        objects_field_idx = i
                                        print(f"[DEBUG] Found objects field '{field.name()}' (case-insensitive match for '{objects_field}')")
                                        break
                            
                            print(f"[DEBUG] Field indices in temporary layers - points: {points_field_idx}, objects: {objects_field_idx}")
                            
                            if points_field_idx < 0 or objects_field_idx < 0:
                                print(f"[DEBUG] Required fields not found in temporary layers")
                                print(f"[DEBUG] Available fields in points layer: {[f.name() for f in total_station_points_layer.fields()]}")
                                print(f"[DEBUG] Available fields in objects layer: {[f.name() for f in objects_layer.fields()]}")
                                return warnings
                        else:
                            print(f"[DEBUG] No field pairs found in definitive relation")
                            return warnings
                    else:
                        print(f"[DEBUG] No relation found between definitive layers")
                        return warnings
                else:
                    print(f"[DEBUG] Could not get definitive layers for relation lookup")
                    return warnings
            else:
                # Working with definitive layers directly
                relation = self._get_relation_between_layers(total_station_points_layer, objects_layer)
                if not relation:
                    print(f"[DEBUG] No relation found between total station points and objects layers")
                    print(f"[DEBUG] Distance detection will not proceed without a relation")
                    return warnings
                
                print(f"[DEBUG] Found relation: {relation.name()}")
                print(f"[DEBUG] Relation ID: {relation.id()}")
                
                # Get field mappings from the relation
                field_pairs = relation.fieldPairs()
                if not field_pairs:
                    print(f"[DEBUG] No field pairs found in relation")
                    return warnings
                
                print(f"[DEBUG] Field pairs: {field_pairs}")
                
                # Determine which layer is referencing and which is referenced
                if relation.referencingLayer() == total_station_points_layer:
                    # Total station points layer references objects layer
                    points_field = list(field_pairs.keys())[0]  # Field in total station points layer
                    objects_field = list(field_pairs.values())[0]  # Field in objects layer
                    points_layer_is_referencing = True
                else:
                    # Objects layer references total station points layer
                    objects_field = list(field_pairs.keys())[0]  # Field in objects layer
                    points_field = list(field_pairs.values())[0]  # Field in total station points layer
                    points_layer_is_referencing = False
                
                print(f"[DEBUG] Field mapping:")
                print(f"[DEBUG]   Points field: {points_field}")
                print(f"[DEBUG]   Objects field: {objects_field}")
                print(f"[DEBUG]   Points layer is referencing: {points_layer_is_referencing}")
                
                # Get field indices - handle case sensitivity
                points_field_idx = total_station_points_layer.fields().indexOf(points_field)
                if points_field_idx < 0:
                    # Try case-insensitive search
                    for i, field in enumerate(total_station_points_layer.fields()):
                        if field.name().lower() == points_field.lower():
                            points_field_idx = i
                            print(f"[DEBUG] Found points field '{field.name()}' (case-insensitive match for '{points_field}')")
                            break
                
                objects_field_idx = objects_layer.fields().indexOf(objects_field)
                if objects_field_idx < 0:
                    # Try case-insensitive search
                    for i, field in enumerate(objects_layer.fields()):
                        if field.name().lower() == objects_field.lower():
                            objects_field_idx = i
                            print(f"[DEBUG] Found objects field '{field.name()}' (case-insensitive match for '{objects_field}')")
                            break
                
                if points_field_idx < 0 or objects_field_idx < 0:
                    print(f"[DEBUG] Required fields not found in layers")
                    print(f"[DEBUG] Available fields in points layer: {[f.name() for f in total_station_points_layer.fields()]}")
                    print(f"[DEBUG] Available fields in objects layer: {[f.name() for f in objects_layer.fields()]}")
                    return warnings
                
                print(f"[DEBUG] Field indices - points: {points_field_idx}, objects: {objects_field_idx}")
            
            # Detect distance issues
            distance_warnings = self._detect_distance_issues(
                total_station_points_layer, objects_layer,
                points_field_idx, objects_field_idx,
                points_layer_is_referencing
            )
            
            warnings.extend(distance_warnings)
            
        except Exception as e:
            print(f"Error in distance detection: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] Distance detection completed, found {len(warnings)} warnings")
        return warnings
    
    def _detect_distance_issues(self, 
                               total_station_points_layer: Any,
                               objects_layer: Any,
                               points_field_idx: int,
                               objects_field_idx: int,
                               points_layer_is_referencing: bool) -> List[Union[str, WarningData]]:
        """
        Detect distance issues between total station points and objects.
        
        Args:
            total_station_points_layer: The total station points layer
            objects_layer: The objects layer
            points_field_idx: Index of the relation field in points layer
            objects_field_idx: Index of the relation field in objects layer
            points_layer_is_referencing: Whether points layer references objects layer
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            print(f"[DEBUG] _detect_distance_issues called")
            
            # Create a distance calculator
            distance_calculator = QgsDistanceArea()
            distance_calculator.setEllipsoid('WGS84')
            
            # Group features by their relation field value
            points_by_relation = {}
            objects_by_relation = {}
            
            # Process total station points
            points_count = 0
            points_with_geometry = 0
            points_with_relation = 0
            
            for feature in total_station_points_layer.getFeatures():
                points_count += 1
                if not feature.geometry() or feature.geometry().isEmpty():
                    continue
                points_with_geometry += 1
                
                relation_value = feature.attribute(points_field_idx)
                print(f"[DEBUG] Point {feature.id()}: relation_value = {relation_value}")
                if relation_value:
                    points_with_relation += 1
                    if relation_value not in points_by_relation:
                        points_by_relation[relation_value] = []
                    points_by_relation[relation_value].append(feature)
            
            # Process objects
            objects_count = 0
            objects_with_geometry = 0
            objects_with_relation = 0
            
            for feature in objects_layer.getFeatures():
                objects_count += 1
                if not feature.geometry() or feature.geometry().isEmpty():
                    continue
                objects_with_geometry += 1
                
                relation_value = feature.attribute(objects_field_idx)
                print(f"[DEBUG] Object {feature.id()}: relation_value = {relation_value}")
                if relation_value:
                    objects_with_relation += 1
                    if relation_value not in objects_by_relation:
                        objects_by_relation[relation_value] = []
                    objects_by_relation[relation_value].append(feature)
            
            print(f"[DEBUG] Points processing summary:")
            print(f"[DEBUG]   Total points: {points_count}")
            print(f"[DEBUG]   Points with geometry: {points_with_geometry}")
            print(f"[DEBUG]   Points with relation value: {points_with_relation}")
            
            print(f"[DEBUG] Objects processing summary:")
            print(f"[DEBUG]   Total objects: {objects_count}")
            print(f"[DEBUG]   Objects with geometry: {objects_with_geometry}")
            print(f"[DEBUG]   Objects with relation value: {objects_with_relation}")
            
            print(f"[DEBUG] Found {len(points_by_relation)} unique relation values in points layer")
            print(f"[DEBUG] Points relation values: {list(points_by_relation.keys())}")
            print(f"[DEBUG] Found {len(objects_by_relation)} unique relation values in objects layer")
            print(f"[DEBUG] Objects relation values: {list(objects_by_relation.keys())}")
            
            # Check for distance issues
            distance_issues = []
            
            # Get all unique relation values that exist in both layers
            common_relation_values = set(points_by_relation.keys()) & set(objects_by_relation.keys())
            
            print(f"[DEBUG] Found {len(common_relation_values)} common relation values")
            print(f"[DEBUG] Common relation values: {list(common_relation_values)}")
            
            for relation_value in common_relation_values:
                points_features = points_by_relation[relation_value]
                objects_features = objects_by_relation[relation_value]
                
                # Check each point-object pair
                for point_feature in points_features:
                    point_geometry = point_feature.geometry()
                    
                    for object_feature in objects_features:
                        object_geometry = object_feature.geometry()
                        
                        # Check if geometries overlap
                        if point_geometry.intersects(object_geometry):
                            # Geometries overlap, no distance issue
                            print(f"[DEBUG] Point {point_feature.id()} intersects object {object_feature.id()}, skipping")
                            continue
                        
                        # Calculate distance between point and polygon boundary
                        # For point to polygon, we need to measure the distance to the polygon boundary
                        distance = point_geometry.distance(object_geometry)
                        
                        print(f"[DEBUG] Distance between point {point_feature.id()} and object {object_feature.id()}: {distance:.3f}m")
                        
                        if distance > self._max_distance_meters:
                            # Get feature identifiers
                            point_identifier = self._get_feature_identifier(point_feature, "Total Station Point")
                            object_identifier = self._get_feature_identifier(object_feature, "Object")
                            
                            distance_issues.append({
                                'point_feature': point_feature,
                                'object_feature': object_feature,
                                'point_identifier': point_identifier,
                                'object_identifier': object_identifier,
                                'distance': distance,
                                'relation_value': relation_value
                            })
            
            print(f"[DEBUG] Found {len(distance_issues)} distance issues")
            
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
                    # Create filter expressions for both layers
                    points_filter = f'"{total_station_points_layer.fields()[points_field_idx].name()}" = \'{relation_value}\''
                    objects_filter = f'"{objects_layer.fields()[objects_field_idx].name()}" = \'{relation_value}\''
                    
                    # Get feature identifiers for the warning message
                    point_identifiers = [issue['point_identifier'] for issue in issues]
                    object_identifiers = [issue['object_identifier'] for issue in issues]
                    max_distance = max(issue['distance'] for issue in issues)
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_distance_warning(
                            point_identifiers, object_identifiers, max_distance
                        ),
                        recording_area_name=f"Relation {relation_value}",  # Use relation value as identifier
                        layer_name=total_station_points_layer.name(),
                        filter_expression=points_filter,
                        second_layer_name=objects_layer.name(),
                        second_filter_expression=objects_filter,
                        distance_issues=issues
                    )
                    warnings.append(warning_data)
                    print(f"[DEBUG] Created distance warning: {warning_data.message}")
            
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
            print(f"[DEBUG] _get_relation_between_layers called for layers: {layer1.name()} and {layer2.name()}")
            print(f"[DEBUG] Layer1 ID: {layer1.id()}, Layer2 ID: {layer2.id()}")
            
            # Get the relation manager
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            print(f"[DEBUG] Found {len(relation_manager.relations())} total relations in project")
            
            # Find relations between the two layers
            for relation_id, relation in relation_manager.relations().items():
                print(f"[DEBUG] Checking relation: {relation.name()} (ID: {relation_id})")
                
                referencing_layer = relation.referencingLayer()
                referenced_layer = relation.referencedLayer()
                
                print(f"[DEBUG]   Referencing layer: {referencing_layer.name() if referencing_layer else 'None'} (ID: {referencing_layer.id() if referencing_layer else 'None'})")
                print(f"[DEBUG]   Referenced layer: {referenced_layer.name() if referenced_layer else 'None'} (ID: {referenced_layer.id() if referenced_layer else 'None'})")
                
                # Check if either layer matches either side of the relation
                if ((referencing_layer and referenced_layer) and
                    ((referencing_layer.id() == layer1.id() and referenced_layer.id() == layer2.id()) or
                     (referencing_layer.id() == layer2.id() and referenced_layer.id() == layer1.id()))):
                    print(f"[DEBUG] Found matching relation: {relation.name()}")
                    return relation
            
            print(f"[DEBUG] No matching relation found")
            print(f"[DEBUG] Available relations:")
            for relation_id, relation in relation_manager.relations().items():
                ref_layer = relation.referencingLayer()
                refd_layer = relation.referencedLayer()
                print(f"[DEBUG]   {relation.name()}: {ref_layer.name() if ref_layer else 'None'} -> {refd_layer.name() if refd_layer else 'None'}")
            
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
                                max_distance: float) -> str:
        """
        Create a warning message for distance issues.
        
        Args:
            point_identifiers: List of point identifiers
            object_identifiers: List of object identifiers
            max_distance: The maximum distance found
        
        Returns:
            The warning message
        """
        try:
            if len(point_identifiers) == 1 and len(object_identifiers) == 1:
                feature_text = f"{point_identifiers[0]} and {object_identifiers[0]}"
            else:
                feature_text = f"{len(point_identifiers)} points and {len(object_identifiers)} objects"
            
            distance_cm = max_distance * 100  # Convert to centimeters
            
            # Fallback: just return the message in English
            return (
                f"{feature_text} are separated by {distance_cm:.1f} cm "
                f"(maximum allowed: {self._max_distance_meters * 100:.1f} cm)"
            )
            
        except Exception as e:
            print(f"Error creating distance warning: {str(e)}")
            return f"{feature_text} are separated by {max_distance * 100:.1f} cm (maximum allowed: {self._max_distance_meters * 100:.1f} cm)" 