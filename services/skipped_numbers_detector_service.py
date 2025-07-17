"""
Skipped Numbers Detector Service for ArcheoSync plugin.

This module provides a service to detect skipped numbers in recording areas.
It analyzes the numbering sequence of objects within each recording area and
identifies gaps in the numbering sequence.

Key Features:
- Detects gaps in object numbering within recording areas
- Provides detailed warnings about skipped numbers
- Supports translation for warning messages
- Integrates with existing warning display system

Architecture Benefits:
- Single Responsibility: Only handles skipped number detection
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection logic

Usage:
    service = SkippedNumbersDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = service.detect_skipped_numbers()
"""

from typing import List, Dict, Any, Optional
from qgis.core import QgsProject


class SkippedNumbersDetectorService:
    """
    Service for detecting skipped numbers in recording areas.
    
    This service analyzes the numbering sequence of objects within each recording area
    and identifies gaps in the numbering sequence. It provides detailed warnings about
    skipped numbers to help users identify potential data entry issues.
    """
    
    def __init__(self, settings_manager, layer_service, translation_service):
        """
        Initialize the service with required dependencies.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            translation_service: Service for translations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._translation_service = translation_service
    
    def detect_skipped_numbers(self) -> List[str]:
        """
        Detect skipped numbers in recording areas.
        
        Returns:
            List of warning messages about skipped numbers
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
            
            # Check for skipped numbers within the "New Objects" layer only
            new_objects_layer = self._find_layer_by_name("New Objects")
            if new_objects_layer:
                # Check for gaps between original objects and new objects layers
                # This will catch all gaps including those within New Objects layer
                between_warnings = self._detect_skipped_numbers_between_layers(
                    objects_layer, new_objects_layer, recording_areas_layer, 
                    number_field, recording_area_field
                )
                warnings.extend(between_warnings)
            
        except Exception as e:
            print(f"Error in skipped numbers detection: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _detect_skipped_numbers_within_layer(self, 
                                           objects_layer: Any, 
                                           recording_areas_layer: Any, 
                                           number_field: str, 
                                           recording_area_field: str, 
                                           layer_name: str) -> List[str]:
        """
        Detect skipped numbers within a single layer.
        
        Args:
            objects_layer: The objects layer to check
            recording_areas_layer: The recording areas layer
            number_field: The number field name
            recording_area_field: The field name for recording area
            layer_name: The name of the layer for warning messages
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        try:
            print(f"[DEBUG] _detect_skipped_numbers_within_layer called for {layer_name}")
            
            # Get field indices
            number_field_idx = objects_layer.fields().indexOf(number_field)
            recording_area_field_idx = objects_layer.fields().indexOf(recording_area_field)
            
            if number_field_idx < 0 or recording_area_field_idx < 0:
                print(f"[DEBUG] Required fields not found in {layer_name} layer")
                return warnings
            
            print(f"[DEBUG] Field indices for {layer_name} - number: {number_field_idx}, recording area: {recording_area_field_idx}")
            
            # Group objects by recording area
            recording_area_objects = {}
            for feature in objects_layer.getFeatures():
                recording_area_id = feature.attribute(recording_area_field_idx)
                number = feature.attribute(number_field_idx)
                
                if recording_area_id and number:
                    if recording_area_id not in recording_area_objects:
                        recording_area_objects[recording_area_id] = []
                    
                    try:
                        number_int = int(number)
                        recording_area_objects[recording_area_id].append(number_int)
                    except (ValueError, TypeError):
                        # Skip non-numeric numbers
                        pass
            
            print(f"[DEBUG] Found {len(recording_area_objects)} recording areas with objects in {layer_name}")
            
            # Check for skipped numbers in each recording area
            for recording_area_id, numbers in recording_area_objects.items():
                if len(numbers) < 2:
                    # Need at least 2 numbers to detect gaps
                    continue
                
                # Sort numbers and find gaps
                numbers.sort()
                gaps = self._find_gaps_in_sequence(numbers)
                
                if gaps:
                    # Get recording area name
                    recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_id)
                    
                    warning = self._create_skipped_numbers_warning(
                        recording_area_name, gaps, layer_name
                    )
                    warnings.append(warning)
                    print(f"[DEBUG] Found skipped numbers in {layer_name}: {warning}")
            
            print(f"[DEBUG] Found {len(warnings)} skipped number warnings within {layer_name}")
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_skipped_numbers_within_layer: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _find_gaps_in_sequence(self, numbers: List[int]) -> List[int]:
        """
        Find gaps in a sequence of numbers.
        
        Args:
            numbers: List of sorted integers
            
        Returns:
            List of missing numbers (gaps)
        """
        gaps = []
        
        if len(numbers) < 2:
            return gaps
        
        # Find gaps in the sequence
        for i in range(len(numbers) - 1):
            current = numbers[i]
            next_num = numbers[i + 1]
            
            # Check for gaps (missing numbers between current and next)
            for missing in range(current + 1, next_num):
                gaps.append(missing)
        
        return gaps
    
    def _detect_skipped_numbers_between_layers(self, 
                                             original_objects_layer: Any, 
                                             new_objects_layer: Any, 
                                             recording_areas_layer: Any, 
                                             number_field: str, 
                                             recording_area_field: str) -> List[str]:
        """
        Detect skipped numbers between original objects and new objects layers.
        
        Args:
            original_objects_layer: The original objects layer
            new_objects_layer: The new objects layer
            recording_areas_layer: The recording areas layer
            number_field: The number field name
            recording_area_field: The field name for recording area
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        try:
            print(f"[DEBUG] _detect_skipped_numbers_between_layers called")
            
            # Get field indices for both layers
            original_number_field_idx = original_objects_layer.fields().indexOf(number_field)
            new_number_field_idx = new_objects_layer.fields().indexOf(number_field)
            
            if original_number_field_idx < 0 or new_number_field_idx < 0:
                print(f"[DEBUG] Number field '{number_field}' not found in one or both layers")
                return warnings
            
            # Get recording area field indices
            original_recording_area_field_idx = original_objects_layer.fields().indexOf(recording_area_field)
            new_recording_area_field_idx = new_objects_layer.fields().indexOf(recording_area_field)
            
            if original_recording_area_field_idx < 0 or new_recording_area_field_idx < 0:
                print(f"[DEBUG] Recording area field '{recording_area_field}' not found in one or both layers")
                return warnings
            
            print(f"[DEBUG] Field indices - original number: {original_number_field_idx}, new number: {new_number_field_idx}")
            print(f"[DEBUG] Field indices - original recording area: {original_recording_area_field_idx}, new recording area: {new_recording_area_field_idx}")
            
            # Collect all numbers by recording area from both layers
            combined_recording_area_objects = {}
            
            # Add numbers from original objects layer
            for feature in original_objects_layer.getFeatures():
                recording_area_id = feature.attribute(original_recording_area_field_idx)
                number = feature.attribute(original_number_field_idx)
                
                if recording_area_id and number:
                    if recording_area_id not in combined_recording_area_objects:
                        combined_recording_area_objects[recording_area_id] = []
                    
                    try:
                        number_int = int(number)
                        combined_recording_area_objects[recording_area_id].append(number_int)
                    except (ValueError, TypeError):
                        # Skip non-numeric numbers
                        pass
            
            # Add numbers from new objects layer
            for feature in new_objects_layer.getFeatures():
                recording_area_id = feature.attribute(new_recording_area_field_idx)
                number = feature.attribute(new_number_field_idx)
                
                if recording_area_id and number:
                    if recording_area_id not in combined_recording_area_objects:
                        combined_recording_area_objects[recording_area_id] = []
                    
                    try:
                        number_int = int(number)
                        combined_recording_area_objects[recording_area_id].append(number_int)
                    except (ValueError, TypeError):
                        # Skip non-numeric numbers
                        pass
            
            print(f"[DEBUG] Found {len(combined_recording_area_objects)} recording areas with combined objects")
            
            # Check for skipped numbers in each recording area
            for recording_area_id, numbers in combined_recording_area_objects.items():
                if len(numbers) < 2:
                    # Need at least 2 numbers to detect gaps
                    continue
                
                # Sort numbers and find gaps
                numbers.sort()
                gaps = self._find_gaps_in_sequence(numbers)
                
                if gaps:
                    # Get recording area name
                    recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_id)
                    
                    warning = self._create_skipped_numbers_warning(
                        recording_area_name, gaps, "Objects and New Objects"
                    )
                    warnings.append(warning)
                    print(f"[DEBUG] Found skipped numbers between layers: {warning}")
            
            print(f"[DEBUG] Found {len(warnings)} skipped number warnings between layers")
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_skipped_numbers_between_layers: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _get_recording_area_field(self, objects_layer: Any, recording_areas_layer: Any) -> Optional[str]:
        """
        Get the recording area field name from the relation between objects and recording areas layers.
        
        Args:
            objects_layer: The objects layer
            recording_areas_layer: The recording areas layer
            
        Returns:
            The recording area field name, or None if not found
        """
        try:
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            # Find relations where the objects layer is the referencing layer
            # and the recording areas layer is the referenced layer
            for relation in relation_manager.relations().values():
                print(f"[DEBUG] Checking relation: {relation.name()}")
                print(f"[DEBUG]   Referencing layer: {relation.referencingLayer().name() if relation.referencingLayer() else 'None'}")
                print(f"[DEBUG]   Referenced layer: {relation.referencedLayer().name() if relation.referencedLayer() else 'None'}")
                
                if (relation.referencingLayer() == objects_layer and 
                    relation.referencedLayer() == recording_areas_layer):
                    
                    # Get the field pairs
                    field_pairs = relation.fieldPairs()
                    print(f"[DEBUG]   Field pairs: {field_pairs}")
                    
                    # Return the first referencing field (should be the recording area field)
                    if field_pairs:
                        recording_area_field = list(field_pairs.keys())[0]
                        print(f"[DEBUG]   Found recording area field: {recording_area_field}")
                        return recording_area_field
            
            print(f"[DEBUG] No relation found between objects and recording areas layers")
            return None
            
        except Exception as e:
            print(f"[DEBUG] Error getting recording area field: {str(e)}")
            return None
    
    def _get_recording_area_name(self, recording_areas_layer: Any, recording_area_id: Any) -> str:
        """
        Get the name of a recording area by its ID.
        
        Args:
            recording_areas_layer: The recording areas layer
            recording_area_id: The ID of the recording area
            
        Returns:
            The name of the recording area, or the ID as string if not found
        """
        try:
            # Try to find the recording area by ID
            for feature in recording_areas_layer.getFeatures():
                if feature.id() == recording_area_id:
                    # Try to get a name field (common field names for names)
                    for field_name in ['name', 'Name', 'NAME', 'label', 'Label', 'LABEL']:
                        field_idx = recording_areas_layer.fields().indexOf(field_name)
                        if field_idx >= 0:
                            name = feature.attribute(field_idx)
                            if name:
                                return str(name)
                    
                    # If no name field found, return the ID
                    return str(recording_area_id)
            
            # If not found, return the ID as string
            return str(recording_area_id)
            
        except Exception as e:
            print(f"[DEBUG] Error getting recording area name: {e}")
            return str(recording_area_id)
    
    def _find_layer_by_name(self, layer_name: str) -> Optional[Any]:
        """
        Find a layer by name.
        
        Args:
            layer_name: The name of the layer to find
            
        Returns:
            The layer if found, None otherwise
        """
        try:
            project = QgsProject.instance()
            layers = project.mapLayersByName(layer_name)
            return layers[0] if layers else None
        except Exception as e:
            print(f"[DEBUG] Error finding layer by name: {e}")
            return None
    
    def _create_skipped_numbers_warning(self, 
                                       recording_area_name: str, 
                                       gaps: List[int], 
                                       layer_name: str) -> str:
        """
        Create a warning message for skipped numbers.
        
        Args:
            recording_area_name: The name of the recording area
            gaps: List of missing numbers
            layer_name: The name of the layer where gaps were found
            
        Returns:
            The warning message
        """
        try:
            # Format the gaps list
            if len(gaps) == 1:
                gaps_text = str(gaps[0])
            else:
                gaps_text = ", ".join(map(str, gaps))
            
            # Try to translate the message
            message = self._translation_service.tr(
                "Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
            ).format(
                recording_area_name=recording_area_name,
                gaps=gaps_text,
                layer_name=layer_name
            )
        except Exception:
            # Fallback to English if translation fails
            message = f"Recording Area '{recording_area_name}' has skipped numbers: {gaps_text} in {layer_name}"
        
        return message 