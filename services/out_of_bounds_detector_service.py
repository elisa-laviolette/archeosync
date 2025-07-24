"""
Out of Bounds Detector Service for ArcheoSync plugin.

This module provides a service to detect objects, features, and small finds that are
located outside their recording areas by more than a specified distance (default 20 cm).
It analyzes the spatial relationships between features and their associated recording areas
and identifies those that are positioned outside the expected boundaries.

Key Features:
- Detects features located outside recording areas by more than 20 cm
- Supports objects, features, and small finds layers
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

from typing import List, Dict, Any, Optional, Union, Tuple

try:
    from ..core.data_structures import WarningData
except ImportError:
    from core.data_structures import WarningData

from qgis.core import QgsProject, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import QObject


class OutOfBoundsDetectorService(QObject):
    """
    Service for detecting features located outside their recording areas.
    
    This service analyzes the spatial relationships between features (objects, features, 
    small finds) and their associated recording areas. It identifies features that are 
    positioned outside the expected boundaries by more than a specified distance.
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
            objects_layer_id = self._settings_manager.get_value('objects_layer')
            features_layer_id = self._settings_manager.get_value('features_layer')
            small_finds_layer_id = self._settings_manager.get_value('small_finds_layer')
            
            print(f"[DEBUG] Layer IDs from settings:")
            print(f"[DEBUG]   recording_areas_layer_id: {recording_areas_layer_id}")
            print(f"[DEBUG]   objects_layer_id: {objects_layer_id}")
            print(f"[DEBUG]   features_layer_id: {features_layer_id}")
            print(f"[DEBUG]   small_finds_layer_id: {small_finds_layer_id}")
            
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
            
            # Check objects layer - look for temporary layer first
            if objects_layer_id:
                print(f"[DEBUG] Checking objects layer...")
                # Try to find the temporary "New Objects" layer first
                temp_objects_layer = self._layer_service.get_layer_by_name("New Objects")
                if temp_objects_layer:
                    print(f"[DEBUG] Found temporary 'New Objects' layer: {temp_objects_layer.name()}")
                    objects_warnings = self._detect_out_of_bounds_in_layer(
                        temp_objects_layer.id(), recording_areas_layer, "Objects"
                    )
                else:
                    print(f"[DEBUG] No temporary 'New Objects' layer found, using configured layer: {objects_layer_id}")
                    objects_warnings = self._detect_out_of_bounds_in_layer(
                        objects_layer_id, recording_areas_layer, "Objects"
                    )
                print(f"[DEBUG] Objects layer returned {len(objects_warnings)} warnings")
                warnings.extend(objects_warnings)
            
            # Check features layer - look for temporary layer first
            if features_layer_id:
                print(f"[DEBUG] Checking features layer...")
                # Try to find the temporary "New Features" layer first
                temp_features_layer = self._layer_service.get_layer_by_name("New Features")
                if temp_features_layer:
                    print(f"[DEBUG] Found temporary 'New Features' layer: {temp_features_layer.name()}")
                    features_warnings = self._detect_out_of_bounds_in_layer(
                        temp_features_layer.id(), recording_areas_layer, "Features"
                    )
                else:
                    print(f"[DEBUG] No temporary 'New Features' layer found, using configured layer: {features_layer_id}")
                    features_warnings = self._detect_out_of_bounds_in_layer(
                        features_layer_id, recording_areas_layer, "Features"
                    )
                print(f"[DEBUG] Features layer returned {len(features_warnings)} warnings")
                warnings.extend(features_warnings)
            
            # Check small finds layer - look for temporary layer first
            if small_finds_layer_id:
                print(f"[DEBUG] Checking small finds layer...")
                # Try to find the temporary "New Small Finds" layer first
                temp_small_finds_layer = self._layer_service.get_layer_by_name("New Small Finds")
                if temp_small_finds_layer:
                    print(f"[DEBUG] Found temporary 'New Small Finds' layer: {temp_small_finds_layer.name()}")
                    small_finds_warnings = self._detect_out_of_bounds_in_layer(
                        temp_small_finds_layer.id(), recording_areas_layer, "Small Finds"
                    )
                else:
                    print(f"[DEBUG] No temporary 'New Small Finds' layer found, using configured layer: {small_finds_layer_id}")
                    small_finds_warnings = self._detect_out_of_bounds_in_layer(
                        small_finds_layer_id, recording_areas_layer, "Small Finds"
                    )
                print(f"[DEBUG] Small finds layer returned {len(small_finds_warnings)} warnings")
                warnings.extend(small_finds_warnings)
            
            print(f"[DEBUG] Total out-of-bounds warnings found: {len(warnings)}")
            
        except Exception as e:
            print(f"[DEBUG] Error in out-of-bounds detection: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
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
            
            # We don't need to pre-load all recording area geometries
            # We'll get them on-demand when needed
            
            # Check each feature in the layer
            out_of_bounds_features = []
            feature_count = 0
            max_features = 10000  # Safety limit
            processed_features = 0
            features_with_geometry = 0
            features_with_recording_area = 0
            features_outside = 0
            
            print(f"[DEBUG] Starting feature processing...")
            
            for feature in layer.getFeatures():
                feature_count += 1
                if feature_count > max_features:
                    print(f"[DEBUG] Warning: Too many features ({feature_count}), limiting to {max_features}")
                    break
                    
                if not feature.geometry() or feature.geometry().isEmpty():
                    continue
                
                features_with_geometry += 1
                
                # Get the recording area value from the feature
                recording_area_value = feature.attribute(recording_area_field_idx)
                if not recording_area_value:
                    continue
                
                features_with_recording_area += 1
                
                # Find the recording area feature that matches this value
                recording_area_feature = None
                recording_area_geometry = None
                
                # Use the stored field mapping to find the recording area feature
                for ra_feature in recording_areas_layer.getFeatures():
                    ra_value = ra_feature.attribute(referenced_field_idx)
                    if ra_value == recording_area_value:
                        recording_area_feature = ra_feature
                        recording_area_geometry = ra_feature.geometry()
                        print(f"[DEBUG] Found recording area feature: {recording_area_value} -> {ra_value}")
                        break
                
                if not recording_area_geometry or recording_area_geometry.isEmpty():
                    print(f"[DEBUG] No recording area geometry found for value: {recording_area_value}")
                    continue
                
                feature_geometry = feature.geometry()
                
                # Check if feature is outside the recording area
                if not recording_area_geometry.contains(feature_geometry):
                    features_outside += 1
                    # Calculate the distance to the recording area boundary
                    distance = recording_area_geometry.distance(feature_geometry)
                    
                    print(f"[DEBUG] Feature outside recording area: distance = {distance:.3f}m")
                    
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
            print(f"[DEBUG]   Total features: {feature_count}")
            print(f"[DEBUG]   Features with geometry: {features_with_geometry}")
            print(f"[DEBUG]   Features with recording area: {features_with_recording_area}")
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
                    # Use the feature's unique identifier (Label) instead of FID which can change
                    feature_labels = []
                    for item in items:
                        feature = item['feature']
                        # Get the Label field value (or another unique identifier)
                        label_field_idx = feature.fields().indexOf('Label')
                        if label_field_idx >= 0:
                            label_value = feature.attribute(label_field_idx)
                            if label_value:
                                feature_labels.append(f"'{label_value}'")
                    
                    if feature_labels:
                        filter_expression = f'"Label" IN ({",".join(feature_labels)})'
                    else:
                        # Fallback to FID if no Label field
                        feature_ids = [str(item['feature_id']) for item in items]
                        filter_expression = f'"fid" IN ({",".join(feature_ids)})'
                    
                    # Debug: Verify filter expression
                    print(f"[DEBUG] Creating filter expression: {filter_expression}")
                    print(f"[DEBUG] Feature labels from detection: {feature_labels}")
                    
                    # Check actual labels in the layer
                    actual_labels = []
                    label_field_idx = layer.fields().indexOf('Label')
                    if label_field_idx >= 0:
                        for feature in layer.getFeatures():
                            label_value = feature.attribute(label_field_idx)
                            if label_value:
                                actual_labels.append(str(label_value))
                    print(f"[DEBUG] Actual labels in layer: {actual_labels}")
                    
                    # Check if our detected labels match actual labels
                    missing_labels = [label.strip("'") for label in feature_labels if label.strip("'") not in actual_labels]
                    if missing_labels:
                        print(f"[DEBUG] WARNING: Labels {missing_labels} not found in layer!")
                    
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