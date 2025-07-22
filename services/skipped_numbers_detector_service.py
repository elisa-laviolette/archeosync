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
- Returns structured warning data for attribute table filtering

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

from typing import List, Dict, Any, Optional, Union

try:
    from ..core.data_structures import WarningData
except ImportError:
    from core.data_structures import WarningData

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QObject


class SkippedNumbersDetectorService(QObject):
    """
    Service for detecting skipped numbers in recording areas.
    
    This service analyzes the numbering sequence of objects within each recording area
    and identifies gaps in the numbering sequence. It provides detailed warnings about
    skipped numbers to help users identify potential data entry issues.
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
    
    def detect_skipped_numbers(self) -> List[Union[str, WarningData]]:
        """
        Detect skipped numbers in recording areas.
        
        Returns:
            List of warning messages or structured warning data about skipped numbers
        """
        # Check if skipped numbers warnings are enabled
        if not self._settings_manager.get_value('enable_skipped_numbers_warnings', True):
            print("[DEBUG] Skipped numbers warnings are disabled, skipping detection")
            return []
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
                                           layer_name: str) -> List[Union[str, WarningData]]:
        """
        Detect skipped numbers within a single layer.
        
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
                    
                    # Get context numbers (gaps + before/after)
                    context_numbers = self._get_context_numbers_for_gaps(numbers, gaps)
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_skipped_numbers_warning(
                            recording_area_name, gaps, layer_name
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=layer_name,
                        filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" IN ({",".join(map(str, context_numbers))})',
                        skipped_numbers=gaps
                    )
                    warnings.append(warning_data)
            
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
            
            # Check for gaps between current and next number
            for missing in range(current + 1, next_num):
                gaps.append(missing)
        
        return gaps
    
    def _get_context_numbers_for_gaps(self, numbers: List[int], gaps: List[int]) -> List[int]:
        """
        Get the numbers before and after gaps to provide context.
        
        Args:
            numbers: List of sorted integers
            gaps: List of missing numbers (gaps)
            
        Returns:
            List of numbers including gaps and their context (before/after)
        """
        if not gaps or not numbers:
            return gaps
        
        context_numbers = set(gaps)  # Start with the gaps
        
        # Find numbers before and after each gap
        for gap in gaps:
            # Find the number before the gap
            for num in numbers:
                if num < gap:
                    context_numbers.add(num)
                else:
                    break
            
            # Find the number after the gap
            for num in numbers:
                if num > gap:
                    context_numbers.add(num)
                    break
        
        return sorted(list(context_numbers))
    
    def _detect_skipped_numbers_between_layers(self, 
                                             original_objects_layer: Any, 
                                             new_objects_layer: Any, 
                                             recording_areas_layer: Any, 
                                             number_field: str, 
                                             recording_area_field: str) -> List[Union[str, WarningData]]:
        """
        Detect skipped numbers between original and new objects layers.
        
        Args:
            original_objects_layer: The original objects layer
            new_objects_layer: The new objects layer
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
            
            # Group objects by recording area for both layers
            original_recording_area_objects = {}
            new_recording_area_objects = {}
            
            # Process original objects
            for feature in original_objects_layer.getFeatures():
                recording_area_id = feature.attribute(original_recording_area_field_idx)
                number = feature.attribute(original_number_field_idx)
                
                if recording_area_id and number:
                    if recording_area_id not in original_recording_area_objects:
                        original_recording_area_objects[recording_area_id] = []
                    
                    try:
                        number_int = int(number)
                        original_recording_area_objects[recording_area_id].append(number_int)
                    except (ValueError, TypeError):
                        pass
            
            # Process new objects
            for feature in new_objects_layer.getFeatures():
                recording_area_id = feature.attribute(new_recording_area_field_idx)
                number = feature.attribute(new_number_field_idx)
                
                if recording_area_id and number:
                    if recording_area_id not in new_recording_area_objects:
                        new_recording_area_objects[recording_area_id] = []
                    
                    try:
                        number_int = int(number)
                        new_recording_area_objects[recording_area_id].append(number_int)
                    except (ValueError, TypeError):
                        pass
            
            # Check for gaps in each recording area
            all_recording_areas = set(original_recording_area_objects.keys()) | set(new_recording_area_objects.keys())
            
            for recording_area_id in all_recording_areas:
                original_numbers = original_recording_area_objects.get(recording_area_id, [])
                new_numbers = new_recording_area_objects.get(recording_area_id, [])
                
                # Combine all numbers for this recording area
                all_numbers = original_numbers + new_numbers
                
                if len(all_numbers) < 2:
                    continue
                
                # Sort and find gaps
                all_numbers.sort()
                gaps = self._find_gaps_in_sequence(all_numbers)
                
                if gaps:
                    # Get recording area name
                    recording_area_name = self._get_recording_area_name(recording_areas_layer, recording_area_id)
                    
                    # Get context numbers (gaps + before/after)
                    context_numbers = self._get_context_numbers_for_gaps(all_numbers, gaps)
                    
                    # Create structured warning data for between-layer skipped numbers
                    warning_data = WarningData(
                        message=self._create_skipped_numbers_warning(
                            recording_area_name, gaps, f"{original_objects_layer.name()} and New Objects"
                        ),
                        recording_area_name=recording_area_name,
                        layer_name=original_objects_layer.name(),
                        filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" IN ({",".join(map(str, context_numbers))})',
                        skipped_numbers=gaps,
                        second_layer_name="New Objects",
                        second_filter_expression=f'"{recording_area_field}" = \'{recording_area_id}\' AND "{number_field}" IN ({",".join(map(str, context_numbers))})'
                    )
                    warnings.append(warning_data)
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_skipped_numbers_between_layers: {e}")
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
    
    def _find_layer_by_name(self, layer_name: str) -> Optional[Any]:
        """
        Find a layer by name in the current QGIS project.
        
        Args:
            layer_name: The name of the layer to find
            
        Returns:
            The layer if found, None otherwise
        """
        try:
            project = QgsProject.instance()
            for layer in project.mapLayers().values():
                if layer.name() == layer_name:
                    return layer
            return None
        except Exception as e:
            print(f"Error finding layer by name: {e}")
            return None
    
    def _create_skipped_numbers_warning(self, recording_area_name: str, gaps: List[int], layer_name: str) -> str:
        """
        Create a warning message for skipped numbers.
        
        Args:
            recording_area_name: The name of the recording area
            gaps: List of skipped numbers
            layer_name: The name of the layer where gaps were found
            
        Returns:
            The warning message
        """
        try:
            message = self.tr(f"Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}")
        except Exception:
            message = f"Recording Area '{recording_area_name}' has skipped numbers: {gaps} in {layer_name}"
        return message 