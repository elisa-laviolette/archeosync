"""
Missing Total Station Detector Service for ArcheoSync plugin.

This module provides a service that detects when objects don't have matching total station points.
It only checks when the definitive objects and total station points layers are related.

Key Features:
- Detects objects that don't have corresponding total station points
- Only checks when layers are related via QGIS relations
- Uses relation field mappings to identify related features
- Provides detailed warnings for each missing total station point
- Integrates with existing layer service and settings
- Supports translation for warning messages
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles missing total station point detection
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection rules

Usage:
    detector = MissingTotalStationDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = detector.detect_missing_total_station_warnings()
"""

from typing import List, Optional, Any, Union, Dict, Tuple
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from ..core.data_structures import WarningData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData


class MissingTotalStationDetectorService:
    """
    Service for detecting objects that don't have matching total station points.
    
    This service analyzes the relationships between objects and total station points
    (via QGIS relations). It identifies objects that don't have corresponding
    total station points.
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
    
    def detect_missing_total_station_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect warnings for objects without matching total station points.
        
        Returns:
            List of warning messages or structured warning data about missing total station points
        """
        # Check if missing total station warnings are enabled
        if not self._settings_manager.get_value('enable_missing_total_station_warnings', True):
            print("[DEBUG] Missing total station warnings are disabled, skipping detection")
            return []
        warnings = []
        
        print(f"[DEBUG] Starting missing total station detection")
        
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
            
            # Get layers - look for temporary layers first (like distance detector)
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
                            
                            if points_field_idx < 0 or objects_field_idx < 0:
                                print(f"[DEBUG] Required fields not found in temporary layers")
                                print(f"[DEBUG] Available fields in points layer: {[f.name() for f in total_station_points_layer.fields()]}")
                                print(f"[DEBUG] Available fields in objects layer: {[f.name() for f in objects_layer.fields()]}")
                                return warnings
                            
                            print(f"[DEBUG] Field indices in temporary layers - points: {points_field_idx}, objects: {objects_field_idx}")
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
                    print(f"[DEBUG] Missing total station detection will not proceed without a relation")
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
            
            # Detect missing total station issues
            missing_warnings = self._detect_missing_total_station_issues(
                total_station_points_layer, objects_layer,
                points_field_idx, objects_field_idx,
                points_layer_is_referencing
            )
            
            warnings.extend(missing_warnings)
            
        except Exception as e:
            print(f"Error in missing total station detection: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] Missing total station detection completed, found {len(warnings)} warnings")
        return warnings
    
    def _get_recording_area_name(self, recording_areas_layer: Any, recording_area_id: Any) -> str:
        """
        Get the name of a recording area by its ID, using the display expression if available.
        Args:
            recording_areas_layer: The recording areas layer
            recording_area_id: The ID of the recording area
        Returns:
            The name of the recording area, or the ID as string if name not found
        """
        try:
            # Find the feature with the given ID or field value
            target_feature = None
            for feature in recording_areas_layer.getFeatures():
                if feature.id() == recording_area_id or any(feature[field_idx] == recording_area_id for field_idx in range(feature.fields().count())):
                    target_feature = feature
                    break
            if target_feature:
                # Try display expression first
                display_expression = recording_areas_layer.displayExpression()
                if display_expression:
                    try:
                        from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
                        context = QgsExpressionContext()
                        context.appendScope(QgsExpressionContextUtils.layerScope(recording_areas_layer))
                        context.setFeature(target_feature)
                        expression = QgsExpression(display_expression)
                        result = expression.evaluate(context)
                        if result and str(result) != 'NULL':
                            return str(result)
                    except Exception as e:
                        print(f"Error evaluating display expression: {e}")
                # Fallback: Try to get a name field if available
                name_fields = ['name', 'title', 'label', 'description', 'comment']
                for field_name in name_fields:
                    field_idx = recording_areas_layer.fields().indexOf(field_name)
                    if field_idx >= 0:
                        name_value = target_feature[field_idx]
                        if name_value and str(name_value) != 'NULL':
                            return str(name_value)
                # Final fallback to ID
                return str(target_feature.id())
            return str(recording_area_id)
        except Exception as e:
            print(f"Error getting recording area name: {e}")
            return str(recording_area_id)
    
    def _detect_missing_total_station_issues(self, 
                                           total_station_points_layer: Any,
                                           objects_layer: Any,
                                           points_field_idx: int,
                                           objects_field_idx: int,
                                           points_layer_is_referencing: bool) -> List[Union[str, WarningData]]:
        """
        Detect objects that don't have matching total station points.
        
        Args:
            total_station_points_layer: The total station points layer (temporary if present)
            objects_layer: The objects layer (should be temporary)
            points_field_idx: Index of the relation field in points layer
            objects_field_idx: Index of the relation field in objects layer
            points_layer_is_referencing: Whether points layer references objects layer
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        try:
            # Fetch the recording areas layer from settings
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer')
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id) if recording_areas_layer_id else None
            # Also fetch the definitive points layer for union
            definitive_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            definitive_points_layer = self._layer_service.get_layer_by_id(definitive_points_layer_id) if definitive_points_layer_id else None
            # Build points_by_relation from both temporary and definitive points layers
            points_by_relation = {}
            def add_points_from_layer(layer, field_idx):
                if not layer or field_idx is None:
                    return
                for feature in layer.getFeatures():
                    relation_value = feature.attribute(field_idx)
                    if relation_value is not None and relation_value != '':
                        norm_value = str(relation_value).strip().lower()
                        if norm_value not in points_by_relation:
                            points_by_relation[norm_value] = []
                        points_by_relation[norm_value].append(feature)
            # Add from temporary points layer
            add_points_from_layer(total_station_points_layer, points_field_idx)
            # If definitive points layer is different, add from it as well
            if definitive_points_layer and definitive_points_layer != total_station_points_layer:
                # Find the correct field index in the definitive layer (by name, case-insensitive)
                temp_field_name = total_station_points_layer.fields()[points_field_idx].name()
                def_field_idx = definitive_points_layer.fields().indexOf(temp_field_name)
                if def_field_idx < 0:
                    # Try case-insensitive
                    for i, field in enumerate(definitive_points_layer.fields()):
                        if field.name().lower() == temp_field_name.lower():
                            def_field_idx = i
                            break
                add_points_from_layer(definitive_points_layer, def_field_idx)
            # Process objects (only from the temporary objects layer)
            objects_by_relation = {}
            objects_count = 0
            objects_with_relation = 0
            for feature in objects_layer.getFeatures():
                objects_count += 1
                relation_value = feature.attribute(objects_field_idx)
                if relation_value is not None and relation_value != '':
                    objects_with_relation += 1
                    norm_value = str(relation_value).strip().lower()
                    if norm_value not in objects_by_relation:
                        objects_by_relation[norm_value] = []
                    objects_by_relation[norm_value].append(feature)
            print(f"[DEBUG] Points relation values (union): {list(points_by_relation.keys())}")
            print(f"[DEBUG] Objects relation values: {list(objects_by_relation.keys())}")
            # Find objects that don't have matching total station points
            missing_total_station_issues = []
            for norm_value, objects_features in objects_by_relation.items():
                if norm_value not in points_by_relation:
                    for object_feature in objects_features:
                        object_identifier = self._get_feature_identifier(object_feature, "Object")
                        missing_total_station_issues.append({
                            'object_feature': object_feature,
                            'object_identifier': object_identifier,
                            'relation_value': object_feature.attribute(objects_field_idx)
                        })
            print(f"[DEBUG] Found {len(missing_total_station_issues)} missing total station issues")
            # Create warnings for missing total station issues
            if missing_total_station_issues:
                by_recording_area = {}
                for issue in missing_total_station_issues:
                    object_feature = issue['object_feature']
                    # Get the recording area value from the object feature
                    recording_area_value = None
                    if recording_areas_layer:
                        # Try to get the relation field from the definitive object layer and recording area layer
                        objects_layer_id = self._settings_manager.get_value('objects_layer')
                        definitive_objects_layer = self._layer_service.get_layer_by_id(objects_layer_id) if objects_layer_id else None
                        if definitive_objects_layer and recording_areas_layer:
                            # Find the relation
                            from qgis.core import QgsProject
                            project = QgsProject.instance()
                            relation_manager = project.relationManager()
                            for relation in relation_manager.relations().values():
                                if (relation.referencingLayer() == definitive_objects_layer and 
                                    relation.referencedLayer() == recording_areas_layer):
                                    field_pairs = relation.fieldPairs()
                                    if field_pairs:
                                        recording_area_field = list(field_pairs.keys())[0]
                                        recording_area_value = object_feature.attribute(recording_area_field)
                                        print(f"[DEBUG] Using relation field '{recording_area_field}' with value '{recording_area_value}' for object {object_feature.id()}")
                                        break
                    # Fallback: try common field names if not found
                    if recording_area_value is None:
                        for fallback_field in ['recording_area', 'recording_area_id', 'area_id', 'area']:
                            idx = object_feature.fields().indexOf(fallback_field)
                            if idx >= 0:
                                recording_area_value = object_feature.attribute(idx)
                                if recording_area_value:
                                    print(f"[DEBUG] Using fallback field '{fallback_field}' with value '{recording_area_value}' for object {object_feature.id()}")
                                    break
                    # Get the human-readable name
                    if recording_area_value is not None and recording_areas_layer:
                        recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_value)
                        print(f"[DEBUG] Found recording area name '{recording_area_name}' for value '{recording_area_value}' (object {object_feature.id()})")
                    else:
                        recording_area_name = str(recording_area_value) if recording_area_value is not None else "Unknown"
                        print(f"[DEBUG] Could not find recording area name for value '{recording_area_value}' (object {object_feature.id()})")
                    if recording_area_name not in by_recording_area:
                        by_recording_area[recording_area_name] = []
                    by_recording_area[recording_area_name].append(issue)
                for recording_area_name, issues in by_recording_area.items():
                    # Use the first relation value for filter expressions
                    relation_value = issues[0]['relation_value']
                    points_filter = f'"{total_station_points_layer.fields()[points_field_idx].name()}" = \'{relation_value}\''
                    objects_filter = f'"{objects_layer.fields()[objects_field_idx].name()}" = \'{relation_value}\''
                    object_identifiers = [issue['object_identifier'] for issue in issues]
                    warning_data = WarningData(
                        message=self._create_missing_total_station_warning(object_identifiers),
                        recording_area_name=recording_area_name,
                        layer_name=objects_layer.name(),
                        filter_expression=objects_filter,
                        second_layer_name=total_station_points_layer.name(),
                        second_filter_expression=points_filter,
                        missing_total_station_issues=issues
                    )
                    print(f"[DEBUG] Created warning for recording_area_name='{recording_area_name}' with {len(issues)} issues.")
                    warnings.append(warning_data)
        except Exception as e:
            print(f"Error detecting missing total station issues: {str(e)}")
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
            The relation if found, None otherwise
        """
        try:
            from qgis.core import QgsProject
            
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            print(f"[DEBUG] Looking for relation between layers:")
            print(f"[DEBUG]   Layer 1: {layer1.name()} (ID: {layer1.id()})")
            print(f"[DEBUG]   Layer 2: {layer2.name()} (ID: {layer2.id()})")
            
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
    
    def _get_feature_identifier(self, feature: Any, feature_type: str) -> str:
        """
        Get a human-readable identifier for a feature.
        
        Args:
            feature: The feature to get an identifier for
            feature_type: The type of feature (for fallback)
            
        Returns:
            A human-readable identifier
        """
        try:
            # Try to get the number field from settings for objects
            if feature_type == "Object":
                number_field = self._settings_manager.get_value('objects_number_field', '')
                if number_field:
                    number_value = feature.attribute(number_field)
                    if number_value is not None and number_value != '':
                        return f"Object {number_value}"
            
            # Fallback to feature ID
            return f"{feature_type} {feature.id()}"
            
        except Exception as e:
            print(f"Error getting feature identifier: {str(e)}")
            return f"{feature_type} {feature.id()}"
    
    def _create_missing_total_station_warning(self, object_identifiers: List[str]) -> str:
        """
        Create a warning message for missing total station points.
        
        Args:
            object_identifiers: List of object identifiers
        
        Returns:
            The warning message
        """
        try:
            if len(object_identifiers) == 1:
                feature_text = object_identifiers[0]
            else:
                feature_text = f"{len(object_identifiers)} objects"
            
            # Fallback: just return the message in English
            return f"{feature_text} have no matching total station points"
        except Exception as e:
            print(f"Error creating missing total station warning: {str(e)}")
            return f"{feature_text} have no matching total station points" 