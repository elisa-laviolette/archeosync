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
        translation_service=translation_service
    )
    
    warnings = detector.detect_duplicate_objects()
"""

from typing import List, Optional, Any, Union

try:
    from ..core.interfaces import ISettingsManager, ILayerService, ITranslationService
    from ..core.data_structures import WarningData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService, ITranslationService
    from core.data_structures import WarningData


class DuplicateObjectsDetectorService:
    """
    Service for detecting duplicate objects with the same recording area and number.
    
    Detects objects that have the same recording area and number within:
    - The "New Objects" layer (imported objects)
    - The original objects layer (existing objects)
    - Between both layers
    """
    
    def __init__(self, 
                 settings_manager: ISettingsManager,
                 layer_service: ILayerService,
                 translation_service: Optional[ITranslationService] = None):
        """
        Initialize the duplicate objects detector service.
        
        Args:
            settings_manager: Service for accessing settings
            layer_service: Service for accessing layers
            translation_service: Service for translations (optional)
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._translation_service = translation_service
    
    def _find_layer_by_name(self, layer_name: str) -> Optional[Any]:
        """
        Find a layer by name in the current QGIS project.
        
        Args:
            layer_name: The name of the layer to find
            
        Returns:
            The layer if found, None otherwise
        """
        try:
            from qgis.core import QgsProject
            
            project = QgsProject.instance()
            for layer in project.mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
        except Exception as e:
            print(f"Error finding layer by name: {e}")
            return None

    def detect_duplicate_objects(self) -> List[Union[str, WarningData]]:
        """
        Detect duplicate objects with the same recording area and number.
        
        Returns:
            List of warning messages or structured warning data about duplicate objects
        """
        warnings = []
        
        try:
            # Get configuration from settings
            objects_layer_id = self._settings_manager.get_value('objects_layer')
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer')
            number_field = self._settings_manager.get_value('objects_number_field')
            
            if not objects_layer_id or not recording_areas_layer_id or not number_field:
                return warnings
            
            # Get layers
            objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
            recording_areas_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            
            if not objects_layer or not recording_areas_layer:
                return warnings
            
            # Get the recording area field name
            recording_area_field = self._get_recording_area_field(objects_layer, recording_areas_layer)
            if not recording_area_field:
                return warnings
            
            # Check for duplicates within the original objects layer
            original_warnings = self._detect_duplicates_within_layer(
                objects_layer, recording_areas_layer, number_field, recording_area_field, objects_layer.name()
            )
            warnings.extend(original_warnings)
            
            # Check for duplicates within the "New Objects" layer
            new_objects_layer = self._find_layer_by_name("New Objects")
            if new_objects_layer:
                new_warnings = self._detect_duplicates_within_layer(
                    new_objects_layer, recording_areas_layer, number_field, recording_area_field, "New Objects"
                )
                warnings.extend(new_warnings)
                
                # Check for duplicates between original and new objects layers
                between_warnings = self._detect_duplicates_between_layers(
                    objects_layer, new_objects_layer, recording_areas_layer, 
                    number_field, recording_area_field
                )
                warnings.extend(between_warnings)
            
        except Exception as e:
            print(f"Error in duplicate objects detection: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _detect_duplicates_within_layer(self, 
                                      objects_layer: Any, 
                                      recording_areas_layer: Any, 
                                      number_field: str, 
                                      recording_area_field: str, 
                                      layer_name: str) -> List[Union[str, WarningData]]:
        """
        Detect duplicates within a single layer.
        
        Args:
            objects_layer: The objects layer to check
            recording_areas_layer: The recording areas layer
            number_field: The number field name
            recording_area_field: The field name for recording area
            layer_name: The name of the layer for warning messages
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            # Get field indices
            number_field_idx = objects_layer.fields().indexOf(number_field)
            recording_area_field_idx = objects_layer.fields().indexOf(recording_area_field)
            
            if number_field_idx < 0 or recording_area_field_idx < 0:
                return warnings
            
            # Group objects by recording area and number
            duplicates = {}
            for feature in objects_layer.getFeatures():
                recording_area_id = feature[recording_area_field_idx]
                number = feature[number_field_idx]
                
                if recording_area_id and number:
                    key = (recording_area_id, number)
                    if key not in duplicates:
                        duplicates[key] = []
                    duplicates[key].append(feature)
            
            print(f"[DEBUG] Found {len(duplicates)} unique recording area/number combinations in {layer_name}")
            
            # Check for duplicates (more than one object with same recording area and number)
            for (recording_area_id, number), features in duplicates.items():
                if len(features) > 1:
                    # Get recording area name
                    recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_id)
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_duplicate_warning(
                            recording_area_name, len(features), number, layer_name
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=layer_name,
                        filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" = {number}',
                        object_number=number
                    )
                    warnings.append(warning_data)
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_duplicates_within_layer: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _detect_duplicates_between_layers(self, 
                                        original_objects_layer: Any, 
                                        new_objects_layer: Any, 
                                        recording_areas_layer: Any, 
                                        number_field: str, 
                                        recording_area_field: str) -> List[Union[str, WarningData]]:
        """
        Detect duplicates between "New Objects" and original objects layers.
        
        Args:
            original_objects_layer: The original objects layer
            new_objects_layer: The "New Objects" layer
            recording_areas_layer: The recording areas layer
            number_field: The number field name
            recording_area_field: The field name for recording area
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            # Get field indices for both layers
            original_number_field_idx = original_objects_layer.fields().indexOf(number_field)
            new_number_field_idx = new_objects_layer.fields().indexOf(number_field)
            
            if original_number_field_idx < 0 or new_number_field_idx < 0:
                return warnings
            
            # Get recording area field indices
            original_recording_area_field_idx = original_objects_layer.fields().indexOf(recording_area_field)
            new_recording_area_field_idx = new_objects_layer.fields().indexOf(recording_area_field)
            
            if original_recording_area_field_idx < 0 or new_recording_area_field_idx < 0:
                return warnings
            
            # Create lookup dictionaries for original objects
            original_objects = {}
            for feature in original_objects_layer.getFeatures():
                recording_area_id = feature[original_recording_area_field_idx]
                number = feature[original_number_field_idx]
                
                if recording_area_id and number:
                    key = (recording_area_id, number)
                    if key not in original_objects:
                        original_objects[key] = []
                    original_objects[key].append(feature)
            
            # Check new objects against original objects
            for feature in new_objects_layer.getFeatures():
                recording_area_id = feature[new_recording_area_field_idx]
                number = feature[new_number_field_idx]
                
                if recording_area_id and number:
                    key = (recording_area_id, number)
                    if key in original_objects:
                        # Get recording area name
                        recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_id)
                        
                        # Create structured warning data for between-layer duplicates
                        warning_data = WarningData(
                            message=self._create_duplicate_warning(
                                recording_area_name, len(original_objects[key]), number, f"{original_objects_layer.name()} and New Objects"
                            ),
                            recording_area_name=recording_area_name,
                            layer_name=original_objects_layer.name(),
                            filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" = {number}',
                            object_number=number,
                            second_layer_name="New Objects",
                            second_filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" = {number}'
                        )
                        warnings.append(warning_data)
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_duplicates_between_layers: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _get_recording_area_field(self, objects_layer: Any, recording_areas_layer: Any) -> Optional[str]:
        """
        Get the field name in the objects layer that references the recording areas layer.
        
        Args:
            objects_layer: The objects layer
            recording_areas_layer: The recording areas layer
            
        Returns:
            The field name that references the recording areas layer, or None if not found
        """
        try:
            # Get the relation manager
            from qgis.core import QgsProject
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            # Find relations where the objects layer is the referencing layer
            # and the recording areas layer is the referenced layer
            for relation in relation_manager.relations().values():
                if (relation.referencingLayer() == objects_layer and 
                    relation.referencedLayer() == recording_areas_layer):
                    
                    # Get the field pairs
                    field_pairs = relation.fieldPairs()
                    
                    # Return the first referencing field (should be the recording area field)
                    if field_pairs:
                        recording_area_field = list(field_pairs.keys())[0]
                        return recording_area_field
            
            return None
            
        except Exception as e:
            return None
    
    def _get_recording_area_name(self, recording_areas_layer: Any, recording_area_id: Any) -> str:
        """
        Get the name of a recording area by its ID.
        
        Args:
            recording_areas_layer: The recording areas layer
            recording_area_id: The ID of the recording area
            
        Returns:
            The name of the recording area, or the ID as string if name not found
        """
        try:
            # Try to find a name field
            name_fields = ['name', 'title', 'label', 'description', 'comment']
            for field_name in name_fields:
                field_idx = recording_areas_layer.fields().indexOf(field_name)
                if field_idx >= 0:
                    # Find the feature with this ID
                    for feature in recording_areas_layer.getFeatures():
                        if feature.id() == recording_area_id:
                            name_value = feature[field_idx]
                            if name_value and str(name_value) != 'NULL':
                                return str(name_value)
            
            # Fallback to ID if no name found
            return str(recording_area_id)
            
        except Exception as e:
            print(f"Error getting recording area name: {e}")
            return str(recording_area_id)
    
    def _create_duplicate_warning(self, 
                                 recording_area_name: str, 
                                 count: int, 
                                 number: Any, 
                                 layer_name: str) -> str:
        """
        Create a warning message for duplicate objects.
        
        Args:
            recording_area_name: The name of the recording area
            count: The number of duplicate objects
            number: The object number
            layer_name: The name of the layer where duplicates were found
            
        Returns:
            The warning message
        """
        try:
            # Try to translate the message
            message = self._translation_service.translate(
                f"Recording Area '{recording_area_name}' has {count} objects with number {number} in {layer_name}"
            )
        except Exception:
            # Fallback to English if translation fails
            message = f"Recording Area '{recording_area_name}' has {count} objects with number {number} in {layer_name}"
        
        return message 