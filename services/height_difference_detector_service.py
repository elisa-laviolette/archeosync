"""
Height Difference Detector Service for ArcheoSync plugin.

This module provides a service that detects when total station points that are relatively
close (a meter or less of distance) have a significant difference in height (Z field),
say more than 20 cm.

Key Features:
- Detects total station points that are close but have significant height differences
- Configurable distance threshold (default 1 meter) and height difference threshold (default 20 cm)
- Uses Z field from total station points for height comparison
- Provides detailed warnings for each height difference issue found
- Integrates with existing layer service and settings
- Supports translation for warning messages
- Returns structured warning data for attribute table filtering

Architecture Benefits:
- Single Responsibility: Only handles height difference detection between close points
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new detection rules

Usage:
    detector = HeightDifferenceDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = detector.detect_height_difference_warnings()
"""

from typing import List, Optional, Any, Union, Dict, Tuple
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea, QgsSpatialIndex

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from core.interfaces import ITranslationService
    from ..core.data_structures import WarningData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData


class HeightDifferenceDetectorService:
    """
    Service for detecting height differences between close total station points.
    
    This service analyzes total station points to find pairs that are close in distance
    but have significant height differences, which could indicate measurement errors
    or data quality issues.
    """
    
    def __init__(self, settings_manager: ISettingsManager, 
                 layer_service: ILayerService):
        """
        Initialize the height difference detector service.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        
        # Get configurable thresholds from settings with defaults
        self._max_distance_meters = float(self._settings_manager.get_value('height_max_distance', 1.0))
        self._max_height_difference_meters = float(self._settings_manager.get_value('height_max_difference', 0.2))
    
    def detect_height_difference_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect height difference warnings between close total station points.
        
        Returns:
            List of warning messages or structured warning data about height difference issues
        """
        warnings = []
        
        # Check if height difference warnings are enabled
        if not self._settings_manager.get_value('enable_height_warnings', True):
            return warnings
        
        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            
            # Check if layer is configured
            if not total_station_points_layer_id:
                return warnings
            
            # Get layers - look for temporary layers first
            
            # Try to find temporary total station points layer first
            temp_total_station_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
            if temp_total_station_points_layer:
                total_station_points_layer = temp_total_station_points_layer
            else:
                total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            
            if not total_station_points_layer:
                return warnings
            
            # Find Z field index
            z_field_idx = self._find_z_field_index(total_station_points_layer)
            if z_field_idx < 0:
                return warnings
            
            # Detect height difference issues
            height_difference_warnings = self._detect_height_difference_issues(
                total_station_points_layer, z_field_idx
            )
            
            warnings.extend(height_difference_warnings)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _find_z_field_index(self, layer: Any) -> int:
        """
        Find the Z field index in the layer.
        
        Args:
            layer: The layer to search for Z field
            
        Returns:
            Index of Z field or -1 if not found
        """
        # Try exact match first
        z_field_idx = layer.fields().indexOf("Z")
        if z_field_idx >= 0:
            return z_field_idx
        
        # Try case-insensitive search
        for i, field in enumerate(layer.fields()):
            if field.name().lower() == "z":
                return i
        
        # Try common variations
        z_variations = ["z", "height", "elevation", "altitude", "z_coord", "z_coordinate"]
        for i, field in enumerate(layer.fields()):
            if field.name().lower() in z_variations:
                return i
        
        return -1
    
    def _detect_height_difference_issues(self, 
                                       total_station_points_layer: Any,
                                       z_field_idx: int) -> List[Union[str, WarningData]]:
        """
        Detect height difference issues between close total station points.
        Optimized: Uses QgsSpatialIndex to only check pairs within max distance.
        """
        warnings = []
        try:
            # Create a distance calculator
            distance_calculator = QgsDistanceArea()
            layer_crs = total_station_points_layer.crs()
            if layer_crs.isValid():
                distance_calculator.setSourceCrs(layer_crs, QgsProject.instance().transformContext())
            else:
                distance_calculator.setEllipsoid('WGS84')

            # Collect features with valid geometry and Z
            features = []
            feature_geoms = []
            for feature in total_station_points_layer.getFeatures():
                if not feature.geometry() or feature.geometry().isEmpty():
                    continue
                z_value = feature.attribute(z_field_idx)
                if z_value is None or z_value == "":
                    continue
                try:
                    z_float = float(z_value)
                except (ValueError, TypeError):
                    continue
                features.append({'feature': feature, 'geometry': feature.geometry(), 'z': z_float})
                feature_geoms.append(feature.geometry())

            if len(features) < 2:
                return warnings

            # Build spatial index
            spatial_index = QgsSpatialIndex()
            for f in features:
                spatial_index.insertFeature(f['feature'])

            checked_pairs = set()
            height_difference_issues = []
            for i, f1 in enumerate(features):
                geom1 = f1['geometry']
                z1 = f1['z']
                id1 = f1['feature'].id()
                # Use bounding box grow for candidate search
                bbox = geom1.boundingBox()
                bbox.grow(self._max_distance_meters)
                candidate_ids = spatial_index.intersects(bbox)
                for cid in candidate_ids:
                    if cid == id1:
                        continue
                    # Ensure each pair is only checked once
                    pair = tuple(sorted((id1, cid)))
                    if pair in checked_pairs:
                        continue
                    checked_pairs.add(pair)
                    # Get candidate feature
                    f2 = next((f for f in features if f['feature'].id() == cid), None)
                    if not f2:
                        continue
                    geom2 = f2['geometry']
                    z2 = f2['z']
                    # Calculate distance
                    point1 = geom1.asPoint()
                    point2 = geom2.asPoint()
                    point1_2d = QgsPointXY(point1.x(), point1.y())
                    point2_2d = QgsPointXY(point2.x(), point2.y())
                    try:
                        distance = distance_calculator.measureLine(point1_2d, point2_2d)
                    except Exception:
                        dx = point2.x() - point1.x()
                        dy = point2.y() - point1.y()
                        distance = (dx * dx + dy * dy) ** 0.5
                    if distance is None or distance != distance:
                        continue
                    if distance <= float(self._max_distance_meters):
                        height_difference = abs(z1 - z2)
                        if height_difference > self._max_height_difference_meters:
                            feature1_identifier = self._get_feature_identifier(f1['feature'], "Total Station Point")
                            feature2_identifier = self._get_feature_identifier(f2['feature'], "Total Station Point")
                            height_difference_issues.append({
                                'feature1': f1['feature'],
                                'feature2': f2['feature'],
                                'feature1_identifier': feature1_identifier,
                                'feature2_identifier': feature2_identifier,
                                'distance': distance,
                                'height_difference': height_difference,
                                'z1': z1,
                                'z2': z2
                            })
            # Create warnings for height difference issues
            if height_difference_issues:
                # Group by distance range for better organization
                by_distance_range = {}
                for issue in height_difference_issues:
                    distance_range = self._get_distance_range(issue['distance'])
                    if distance_range not in by_distance_range:
                        by_distance_range[distance_range] = []
                    by_distance_range[distance_range].append(issue)
                
                for distance_range, issues in by_distance_range.items():
                    # Create filter expressions for the layer using dynamic identifier field
                    identifier_field = self._find_identifier_field(total_station_points_layer)
                    feature_identifiers = []
                    feature_ids = []
                    
                    for issue in issues:
                        feature1 = issue['feature1']
                        feature2 = issue['feature2']
                        
                        if identifier_field:
                            # Use the dynamic identifier field
                            identifier_field_idx = feature1.fields().indexOf(identifier_field)
                            
                            if identifier_field_idx >= 0:
                                identifier1 = feature1.attribute(identifier_field_idx)
                                identifier2 = feature2.attribute(identifier_field_idx)
                                
                                if identifier1 is not None:
                                    feature_identifiers.append(f"'{identifier1}'")
                                if identifier2 is not None:
                                    feature_identifiers.append(f"'{identifier2}'")
                            else:
                                # Fallback to feature IDs
                                feature_ids.extend([feature1.id(), feature2.id()])
                        else:
                            # Fallback to feature IDs
                            feature_ids.extend([feature1.id(), feature2.id()])
                    
                    # Remove duplicates and create filter expression
                    if feature_identifiers:
                        unique_identifiers = list(set(feature_identifiers))
                        
                        if len(unique_identifiers) == 1:
                            filter_expression = f'"{identifier_field}" = {unique_identifiers[0]}'
                        else:
                            identifiers_list = ",".join(unique_identifiers)
                            filter_expression = f'"{identifier_field}" IN ({identifiers_list})'
                    else:
                        # Use feature IDs as fallback
                        unique_ids = list(set(feature_ids))
                        
                        if len(unique_ids) == 1:
                            filter_expression = f'"fid" = {unique_ids[0]}'
                        else:
                            id_list = ",".join(str(id) for id in unique_ids)
                            filter_expression = f'"fid" IN ({id_list})'
                    
                    # Get feature identifiers for the warning message
                    feature1_identifiers = [issue['feature1_identifier'] for issue in issues]
                    feature2_identifiers = [issue['feature2_identifier'] for issue in issues]
                    max_height_difference = max(issue['height_difference'] for issue in issues)
                    max_distance = max(issue['distance'] for issue in issues)
                    
                    # Create structured warning data
                    warning_data = WarningData(
                        message=self._create_height_difference_warning(
                            feature1_identifiers, feature2_identifiers, 
                            max_distance, max_height_difference
                        ),
                        recording_area_name=f"Height Difference {distance_range}",
                        layer_name=total_station_points_layer.name(),
                        filter_expression=filter_expression,
                        height_difference_issues=issues
                    )
                    
                    warnings.append(warning_data)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return warnings
    
    def _find_identifier_field(self, layer: Any) -> Optional[str]:
        """
        Find the identifier field for the layer using the same logic as the duplicate detector.
        
        Args:
            layer: The layer to analyze
            
        Returns:
            The identifier field name, or None if not found
        """
        try:
            # First try to find a common identifier field
            identifier_field = self._find_common_identifier_field(layer)
            if identifier_field:
                return identifier_field
            
            # If not found, try to guess the identifier field
            return self._guess_identifier_field(layer)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _find_common_identifier_field(self, layer: Any) -> Optional[str]:
        """
        Find a common identifier field by looking for common identifier field names.
        
        Args:
            layer: The layer to analyze
            
        Returns:
            The identifier field name, or None if not found
        """
        try:
            # Common identifier field names
            common_fields = ["identifier", "identifiant", "id", "code", "name", "nom", "label"]
            
            for field in layer.fields():
                if field.name().lower() in common_fields:
                    return field.name()
            
            return None
            
        except Exception as e:
            import traceback
            traceback.print_exc()
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
                return candidate_fields[0]
            
            # If no candidates found, try to find any string field that might be an identifier
            for field in layer.fields():
                field_name = field.name().lower()
                field_type = field.typeName().lower()
                
                # Look for common identifier patterns in string fields
                if (field_type == "string" and 
                    (field_name in ["identifier", "identifiant", "code", "name", "nom"] or
                     field_name.endswith("_id") or field_name.endswith("_code"))):
                    return field.name()
            
            return None
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _get_distance_range(self, distance: float) -> str:
        """
        Get a human-readable distance range string.
        
        Args:
            distance: Distance in meters
            
        Returns:
            Distance range string
        """
        if distance < 0.1:
            return "0-10cm"
        elif distance < 0.5:
            return "10-50cm"
        else:
            return "50cm-1m"
    
    def _get_feature_identifier(self, feature: Any, feature_type: str) -> str:
        """
        Get a human-readable identifier for a feature.
        
        Args:
            feature: The feature to get identifier for
            feature_type: Type of feature for context
            
        Returns:
            Feature identifier string
        """
        try:
            # Try to get an ID field first
            id_field_idx = feature.fields().indexOf("id")
            if id_field_idx >= 0:
                id_value = feature.attribute(id_field_idx)
                if id_value is not None:
                    return f"{feature_type} {id_value}"
            
            # Try common identifier fields
            identifier_fields = ["identifier", "name", "number", "point_id", "station_id"]
            for field_name in identifier_fields:
                field_idx = feature.fields().indexOf(field_name)
                if field_idx >= 0:
                    field_value = feature.attribute(field_idx)
                    if field_value is not None:
                        return f"{feature_type} {field_value}"
            
            # Fallback to feature ID
            return f"{feature_type} {feature.id()}"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"{feature_type} {feature.id()}"
    
    def _create_height_difference_warning(self, 
                                        feature1_identifiers: List[str], 
                                        feature2_identifiers: List[str], 
                                        max_distance: float,
                                        max_height_difference: float) -> str:
        """
        Create a warning message for height difference issues.
        
        Args:
            feature1_identifiers: List of first feature identifiers
            feature2_identifiers: List of second feature identifiers
            max_distance: The maximum distance found
            max_height_difference: The maximum height difference found
        
        Returns:
            The warning message
        """
        try:
            if len(feature1_identifiers) == 1 and len(feature2_identifiers) == 1:
                feature_text = f"{feature1_identifiers[0]} and {feature2_identifiers[0]}"
            else:
                feature_text = f"{len(feature1_identifiers)} point pairs"
            
            distance_cm = max_distance * 100  # Convert to centimeters
            height_difference_cm = max_height_difference * 100  # Convert to centimeters
            
            # Fallback: just return the message in English
            return (
                f"{feature_text} are separated by {distance_cm:.1f} cm but have a height difference of {height_difference_cm:.1f} cm "
                f"(maximum allowed: {self._max_height_difference_meters * 100:.1f} cm)"
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            distance_cm = max_distance * 100
            height_difference_cm = max_height_difference * 100
            return f"{feature_text} are separated by {distance_cm:.1f} cm but have a height difference of {height_difference_cm:.1f} cm (maximum allowed: {self._max_height_difference_meters * 100:.1f} cm)" 