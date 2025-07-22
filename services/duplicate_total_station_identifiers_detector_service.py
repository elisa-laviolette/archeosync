"""
Duplicate Total Station Identifiers Detector Service for ArcheoSync plugin.

This module provides a service that detects duplicate identifiers in total station points.
It checks for duplicates both within the temporary Imported_CSV_points layer and between
that layer and the definitive total station points layer.

Key Features:
- Detects duplicate identifiers in total station points
- Guesses identifier field by looking for "id" in field names and string fields
- Checks within temporary Imported_CSV_points layer
- Checks between temporary and definitive total station points layers
- Provides detailed warnings for each duplicate found
- Integrates with existing layer service and settings
- Supports translation for warning messages
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles duplicate identifier detection in total station points
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection rules

Usage:
    detector = DuplicateTotalStationIdentifiersDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = detector.detect_duplicate_identifiers_warnings()
"""

from typing import List, Optional, Any, Union, Dict, Tuple
from qgis.PyQt.QtCore import QObject

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from ..core.data_structures import WarningData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData


class DuplicateTotalStationIdentifiersDetectorService(QObject):
    """
    Service for detecting duplicate identifiers in total station points.
    
    Detects total station points that have the same identifier within:
    - The "Imported_CSV_Points" layer (imported total station points)
    - The definitive total station points layer (existing total station points)
    - Between both layers
    """
    
    def __init__(self, settings_manager: ISettingsManager, layer_service: ILayerService):
        super().__init__()
        """
        Initialize the duplicate total station identifiers detector service.
        
        Args:
            settings_manager: Service for accessing settings
            layer_service: Service for accessing layers
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
    
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
            
            print(f"[DEBUG] _find_layer_by_name called with layer_name: {layer_name}")
            project = QgsProject.instance()
            all_layers = project.mapLayers().values()
            print(f"[DEBUG] Found {len(all_layers)} total layers in project")
            
            for layer in all_layers:
                print(f"[DEBUG] Checking layer: '{layer.name()}' against '{layer_name}'")
                if layer.name() == layer_name:
                    print(f"[DEBUG] Found matching layer: {layer.name()}")
                    return layer
            
            print(f"[DEBUG] No layer found with name: {layer_name}")
            return None
        except Exception as e:
            print(f"Error finding layer by name: {e}")
            return None

    def detect_duplicate_identifiers_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect duplicate identifiers in total station points.
        
        Returns:
            List of warning messages or structured warning data about duplicate identifiers
        """
        # Check if duplicate total station identifiers warnings are enabled
        if not self._settings_manager.get_value('enable_duplicate_total_station_identifiers_warnings', True):
            print("[DEBUG] Duplicate total station identifiers warnings are disabled, skipping detection")
            return []
        print("=" * 50)
        print("DUPLICATE TOTAL STATION IDENTIFIERS DETECTION STARTED")
        print("=" * 50)
        warnings = []
        
        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            
            if not total_station_points_layer_id:
                return warnings
            
            # Get the definitive total station points layer
            definitive_total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            if not definitive_total_station_points_layer:
                return warnings
            
            # Find the temporary total station points layer
            print("[DEBUG] About to find temporary layer by name 'Imported_CSV_Points'")
            temp_total_station_points_layer = self._find_layer_by_name("Imported_CSV_Points")
            print(f"[DEBUG] Temporary layer found: {temp_total_station_points_layer is not None}")
            if temp_total_station_points_layer:
                print(f"[DEBUG] Temporary layer name: {temp_total_station_points_layer.name()}")
                print(f"[DEBUG] Temporary layer fields: {[f.name() for f in temp_total_station_points_layer.fields()]}")
            else:
                print("[DEBUG] Temporary layer NOT found")
            
            # Find a common identifier field between both layers
            common_identifier_field = self._find_common_identifier_field(
                definitive_total_station_points_layer, temp_total_station_points_layer
            )
            
            if not common_identifier_field:
                print("[DEBUG] Could not find common identifier field between definitive and temporary total station points layers")
                return warnings
            
            print(f"[DEBUG] Using common identifier field: {common_identifier_field}")
            
            # Check for duplicates within the temporary total station points layer
            print(f"[DEBUG] About to check temporary layer, temp_total_station_points_layer: {temp_total_station_points_layer}")
            if temp_total_station_points_layer:
                print(f"[DEBUG] Checking temporary layer: {temp_total_station_points_layer.name()}")
                temp_warnings = self._detect_duplicates_within_layer(
                    temp_total_station_points_layer, common_identifier_field, "Imported_CSV_Points"
                )
                print(f"[DEBUG] Temporary layer warnings: {len(temp_warnings)}")
                warnings.extend(temp_warnings)
                
                # Check for duplicates between temporary and definitive total station points layers
                print(f"[DEBUG] Checking for duplicates between layers")
                between_warnings = self._detect_duplicates_between_layers(
                    definitive_total_station_points_layer, temp_total_station_points_layer,
                    common_identifier_field, common_identifier_field
                )
                print(f"[DEBUG] Between layers warnings: {len(between_warnings)}")
                warnings.extend(between_warnings)
            else:
                # If no temporary layer, only check the definitive layer
                print(f"[DEBUG] No temporary layer found, only checking definitive layer: {definitive_total_station_points_layer.name()}")
            
        except Exception as e:
            print(f"Error in duplicate total station identifiers detection: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] Duplicate total station identifiers detection completed, found {len(warnings)} warnings")
        return warnings
    
    def _find_common_identifier_field(self, definitive_layer: Any, temp_layer: Any) -> Optional[str]:
        """
        Find a common identifier field between the definitive and temporary layers.
        Only considers fields that are present in both layers, ignoring case.
        
        Args:
            definitive_layer: The definitive total station points layer
            temp_layer: The temporary total station points layer (can be None)
            
        Returns:
            The common identifier field name, or None if not found
        """
        try:
            # If no temporary layer, just use the definitive layer
            if not temp_layer:
                return self._guess_identifier_field(definitive_layer)
            
            # Get all string fields from both layers
            definitive_string_fields = []
            temp_string_fields = []
            
            for field in definitive_layer.fields():
                if field.typeName().lower() == "string":
                    definitive_string_fields.append(field.name().lower())
            
            for field in temp_layer.fields():
                if field.typeName().lower() == "string":
                    temp_string_fields.append(field.name().lower())
            
            print(f"[DEBUG] Definitive layer string fields: {definitive_string_fields}")
            print(f"[DEBUG] Temporary layer string fields: {temp_string_fields}")
            
            # Find common string fields (case-insensitive)
            common_string_fields = set(definitive_string_fields) & set(temp_string_fields)
            print(f"[DEBUG] Common string fields: {common_string_fields}")
            
            if not common_string_fields:
                print("[DEBUG] No common string fields found between layers")
                return None
            
            # Look for fields containing "id" (case-insensitive) in common fields
            id_candidates = [field for field in common_string_fields if "id" in field]
            
            if id_candidates:
                # Get the actual field name from the definitive layer (preserve original case)
                for field in definitive_layer.fields():
                    if field.name().lower() in id_candidates:
                        print(f"[DEBUG] Found common identifier field with 'id': {field.name()}")
                        return field.name()
                
                # If not found in definitive layer, try temp layer
                if temp_layer:
                    for field in temp_layer.fields():
                        if field.name().lower() in id_candidates:
                            print(f"[DEBUG] Found common identifier field with 'id' in temp layer: {field.name()}")
                            return field.name()
                
                # If still not found, try case-insensitive search in both layers
                for field in definitive_layer.fields():
                    if field.name().lower() in [candidate.lower() for candidate in id_candidates]:
                        print(f"[DEBUG] Found common identifier field with 'id' (case-insensitive): {field.name()}")
                        return field.name()
                
                if temp_layer:
                    for field in temp_layer.fields():
                        if field.name().lower() in [candidate.lower() for candidate in id_candidates]:
                            print(f"[DEBUG] Found common identifier field with 'id' in temp layer (case-insensitive): {field.name()}")
                            return field.name()
            
            # If no "id" fields found, try common identifier patterns
            pattern_candidates = []
            for field in common_string_fields:
                if (field in ["identifier", "identifiant", "code", "name", "nom"] or
                    field.endswith("_id") or field.endswith("_code")):
                    pattern_candidates.append(field)
            
            if pattern_candidates:
                # Get the actual field name from the definitive layer (preserve original case)
                for field in definitive_layer.fields():
                    if field.name().lower() in pattern_candidates:
                        print(f"[DEBUG] Found common identifier field from pattern: {field.name()}")
                        return field.name()
            
            # If still no candidates, return the first common string field
            for field in definitive_layer.fields():
                if field.name().lower() in common_string_fields:
                    print(f"[DEBUG] Using first common string field as identifier: {field.name()}")
                    return field.name()
            
            print("[DEBUG] No suitable common identifier field found")
            return None
            
        except Exception as e:
            print(f"Error finding common identifier field: {e}")
            return None
    
    def _guess_identifier_field(self, layer: Any) -> Optional[str]:
        """
        Guess which field corresponds to the identifier by looking for "id" in field names
        and only considering string fields.
        
        Args:
            layer: The layer to analyze
            
        Returns:
            The guessed identifier field name, or None if not found
        """
        try:
            # Look for fields containing "id" (case-insensitive) that are string fields
            candidate_fields = []
            
            for field in layer.fields():
                field_name = field.name().lower()
                field_type = field.typeName().lower()
                
                # Check if field name contains "id" and is a string field
                if "id" in field_name and field_type == "string":
                    candidate_fields.append(field.name())
            
            # If we found candidates, return the first one
            if candidate_fields:
                print(f"[DEBUG] Guessed identifier field: {candidate_fields[0]} from candidates: {candidate_fields}")
                return candidate_fields[0]
            
            # If no candidates found, try to find any string field that might be an identifier
            for field in layer.fields():
                field_name = field.name().lower()
                field_type = field.typeName().lower()
                
                # Look for common identifier patterns in string fields
                if (field_type == "string" and 
                    (field_name in ["identifier", "identifiant", "code", "name", "nom"] or
                     field_name.endswith("_id") or field_name.endswith("_code"))):
                    print(f"[DEBUG] Guessed identifier field from common pattern: {field.name()}")
                    return field.name()
            
            print(f"[DEBUG] Could not guess identifier field for layer: {layer.name()}")
            print(f"[DEBUG] Available string fields: {[f.name() for f in layer.fields() if f.typeName().lower() == 'string']}")
            return None
            
        except Exception as e:
            print(f"Error guessing identifier field: {e}")
            return None
    
    def _detect_duplicates_within_layer(self, 
                                      layer: Any, 
                                      identifier_field: str, 
                                      layer_name: str) -> List[Union[str, WarningData]]:
        """
        Detect duplicates within a single layer.
        
        Args:
            layer: The layer to check
            identifier_field: The identifier field name
            layer_name: The name of the layer for warning messages
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            print(f"[DEBUG] _detect_duplicates_within_layer called for {layer_name} with field: {identifier_field}")
            
            # Get field index
            identifier_field_idx = layer.fields().indexOf(identifier_field)
            print(f"[DEBUG] Field index for {identifier_field}: {identifier_field_idx}")
            
            if identifier_field_idx < 0:
                # Try case-insensitive search
                print(f"[DEBUG] Field {identifier_field} not found in {layer_name}, trying case-insensitive search")
                for i, field in enumerate(layer.fields()):
                    if field.name().lower() == identifier_field.lower():
                        identifier_field_idx = i
                        print(f"[DEBUG] Found field '{field.name()}' (case-insensitive match for '{identifier_field}')")
                        break
                
                if identifier_field_idx < 0:
                    print(f"[DEBUG] Field {identifier_field} not found in {layer_name}")
                    print(f"[DEBUG] Available fields: {[f.name() for f in layer.fields()]}")
                    return warnings
            
            # Group features by identifier
            duplicates = {}
            feature_count = 0
            for feature in layer.getFeatures():
                feature_count += 1
                identifier = feature[identifier_field_idx]
                print(f"[DEBUG] Feature {feature_count} in {layer_name}: identifier = {identifier}")
                
                if identifier:
                    if identifier not in duplicates:
                        duplicates[identifier] = []
                    duplicates[identifier].append(feature)
            
            print(f"[DEBUG] Found {len(duplicates)} unique identifiers in {layer_name}")
            print(f"[DEBUG] Identifiers in {layer_name}: {list(duplicates.keys())}")
            
            # Check for duplicates (more than one feature with same identifier)
            duplicate_count = 0
            for identifier, features in duplicates.items():
                if len(features) > 1:
                    duplicate_count += 1
                    print(f"[DEBUG] Found duplicate in {layer_name}: {len(features)} features with identifier '{identifier}'")
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_duplicate_warning(
                            len(features), identifier, layer_name
                        ),
                        recording_area_name="",  # Not applicable for total station points
                        layer_name=layer_name,
                        filter_expression=f'"{identifier_field}" = \'{identifier}\'',
                        object_number=None  # Not applicable for total station points
                    )
                    warnings.append(warning_data)
            
            print(f"[DEBUG] Created {duplicate_count} duplicate warnings for {layer_name}")
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_duplicates_within_layer: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _detect_duplicates_between_layers(self, 
                                        definitive_layer: Any, 
                                        temp_layer: Any, 
                                        definitive_identifier_field: str, 
                                        temp_identifier_field: str) -> List[Union[str, WarningData]]:
        """
        Detect duplicates between definitive and temporary total station points layers.
        
        Optimized to only check entities in the definitive layer that have the same 
        identifiers as those in the temporary layer, rather than processing all entities.
        
        Args:
            definitive_layer: The definitive total station points layer
            temp_layer: The temporary total station points layer
            definitive_identifier_field: The identifier field name in definitive layer
            temp_identifier_field: The identifier field name in temporary layer
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            # Get field indices for both layers
            definitive_identifier_field_idx = definitive_layer.fields().indexOf(definitive_identifier_field)
            temp_identifier_field_idx = temp_layer.fields().indexOf(temp_identifier_field)
            
            if definitive_identifier_field_idx < 0 or temp_identifier_field_idx < 0:
                return warnings
            
            # First, collect all identifiers from the temporary layer
            temp_identifiers = set()
            for feature in temp_layer.getFeatures():
                identifier = feature[temp_identifier_field_idx]
                if identifier:
                    temp_identifiers.add(identifier)
            
            print(f"[DEBUG] Found {len(temp_identifiers)} unique identifiers in temporary layer")
            
            if not temp_identifiers:
                print("[DEBUG] No identifiers found in temporary layer, skipping between-layers check")
                return warnings
            
            # Now only check entities in the definitive layer that have matching identifiers
            definitive_identifiers = set()
            for feature in definitive_layer.getFeatures():
                identifier = feature[definitive_identifier_field_idx]
                if identifier and identifier in temp_identifiers:
                    definitive_identifiers.add(identifier)
            
            # Find common identifiers (duplicates between layers)
            common_identifiers = definitive_identifiers & temp_identifiers
            
            print(f"[DEBUG] Found {len(common_identifiers)} common identifiers between layers")
            
            # Create warnings for each common identifier
            for identifier in common_identifiers:
                # Create structured warning data
                warning_data = WarningData(
                    message=self._create_between_layers_duplicate_warning(identifier),
                    recording_area_name="",  # Not applicable for total station points
                    layer_name=definitive_layer.name(),
                    filter_expression=f'"{definitive_identifier_field}" = \'{identifier}\'',
                    object_number=None,  # Not applicable for total station points
                    second_layer_name="Imported_CSV_Points",
                    second_filter_expression=f'"{temp_identifier_field}" = \'{identifier}\''
                )
                warnings.append(warning_data)
            
        except Exception as e:
            print(f"[DEBUG] Error in _detect_duplicates_between_layers: {e}")
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _create_duplicate_warning(self, count: int, identifier: Any, layer_name: str) -> str:
        """
        Create a warning message for duplicate identifiers within a layer.
        
        Args:
            count: Number of features with the same identifier
            identifier: The duplicate identifier
            layer_name: The name of the layer
            
        Returns:
            The warning message
        """
        return self.tr(f"Found {count} total station points with the same identifier '{identifier}' in layer '{layer_name}'")
    
    def _create_between_layers_duplicate_warning(self, identifier: Any) -> str:
        """
        Create a warning message for duplicate identifiers between layers.
        
        Args:
            identifier: The duplicate identifier
            
        Returns:
            The warning message
        """
        return self.tr(f"Found total station point with identifier '{identifier}' in both imported and definitive layers") 