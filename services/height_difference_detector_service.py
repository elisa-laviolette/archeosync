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
from qgis.core import QgsProject, QgsGeometry, QgsPointXY, QgsDistanceArea

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
        self._max_distance_meters = self._settings_manager.get_value('height_max_distance', 1.0)
        self._max_height_difference_meters = self._settings_manager.get_value('height_max_difference', 0.2)
    
    def detect_height_difference_warnings(self) -> List[Union[str, WarningData]]:
        """
        Detect height difference warnings between close total station points.
        
        Returns:
            List of warning messages or structured warning data about height difference issues
        """
        warnings = []
        
        # Check if height difference warnings are enabled
        if not self._settings_manager.get_value('enable_height_warnings', True):
            print(f"[DEBUG] Height difference warnings are disabled, skipping detection")
            return warnings
        
        print(f"[DEBUG] Starting height difference detection with max_distance_meters: {self._max_distance_meters}, max_height_difference_meters: {self._max_height_difference_meters}")
        
        try:
            # Get configuration from settings
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer')
            
            print(f"[DEBUG] Layer ID from settings:")
            print(f"[DEBUG]   total_station_points_layer_id: {total_station_points_layer_id}")
            
            # Check if layer is configured
            if not total_station_points_layer_id:
                print(f"[DEBUG] Missing layer configuration, returning empty warnings")
                return warnings
            
            # Get layers - look for temporary layers first
            print(f"[DEBUG] Looking for layers...")
            
            # Try to find temporary total station points layer first
            temp_total_station_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
            if temp_total_station_points_layer:
                print(f"[DEBUG] Found temporary 'Imported_CSV_Points' layer: {temp_total_station_points_layer.name()}")
                total_station_points_layer = temp_total_station_points_layer
            else:
                print(f"[DEBUG] No temporary 'Imported_CSV_Points' layer found, using configured layer: {total_station_points_layer_id}")
                total_station_points_layer = self._layer_service.get_layer_by_id(total_station_points_layer_id)
            
            if not total_station_points_layer:
                print(f"[DEBUG] Could not get total station points layer")
                return warnings
            
            print(f"[DEBUG] Successfully got layer:")
            print(f"[DEBUG]   Total station points layer: {total_station_points_layer.name()} (ID: {total_station_points_layer.id()})")
            
            # Find Z field index
            z_field_idx = self._find_z_field_index(total_station_points_layer)
            if z_field_idx < 0:
                print(f"[DEBUG] Z field not found in total station points layer")
                print(f"[DEBUG] Available fields: {[f.name() for f in total_station_points_layer.fields()]}")
                return warnings
            
            print(f"[DEBUG] Found Z field at index: {z_field_idx}")
            
            # Detect height difference issues
            height_difference_warnings = self._detect_height_difference_issues(
                total_station_points_layer, z_field_idx
            )
            
            warnings.extend(height_difference_warnings)
            
        except Exception as e:
            print(f"Error in height difference detection: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[DEBUG] Height difference detection completed, found {len(warnings)} warnings")
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
                print(f"[DEBUG] Found Z field '{field.name()}' (case-insensitive match)")
                return i
        
        # Try common variations
        z_variations = ["z", "height", "elevation", "altitude", "z_coord", "z_coordinate"]
        for i, field in enumerate(layer.fields()):
            if field.name().lower() in z_variations:
                print(f"[DEBUG] Found Z field '{field.name()}' (variation match)")
                return i
        
        return -1
    
    def _detect_height_difference_issues(self, 
                                       total_station_points_layer: Any,
                                       z_field_idx: int) -> List[Union[str, WarningData]]:
        """
        Detect height difference issues between close total station points.
        
        Args:
            total_station_points_layer: The total station points layer
            z_field_idx: Index of the Z field in the layer
            
        Returns:
            List of warning messages or structured warning data
        """
        warnings = []
        
        try:
            print(f"[DEBUG] ===== _detect_height_difference_issues METHOD STARTED =====")
            print(f"[DEBUG] This is the NEW version of the method with detailed debugging")
            print(f"[DEBUG] _detect_height_difference_issues called")
            
            # Create a distance calculator
            distance_calculator = QgsDistanceArea()
            
            # Set the coordinate reference system from the layer
            layer_crs = total_station_points_layer.crs()
            print(f"[DEBUG] Layer CRS: {layer_crs.description()}")
            print(f"[DEBUG] Layer CRS is valid: {layer_crs.isValid()}")
            print(f"[DEBUG] Layer CRS authid: {layer_crs.authid()}")
            
            if layer_crs.isValid():
                distance_calculator.setSourceCrs(layer_crs, QgsProject.instance().transformContext())
                print(f"[DEBUG] Using layer CRS: {layer_crs.description()}")
            else:
                # Fallback to WGS84 if no valid CRS
                distance_calculator.setEllipsoid('WGS84')
                print(f"[DEBUG] Using fallback WGS84 CRS")
            
                        # Get all features with valid geometry and Z values
            features = []
            feature_count = 0
            print(f"[DEBUG] Starting feature processing loop...")
            try:
                for feature in total_station_points_layer.getFeatures():
                    feature_count += 1
                    print(f"[DEBUG] Processing feature {feature_count}: id={feature.id()}")
                    
                    if not feature.geometry():
                        print(f"[DEBUG] Feature {feature_count}: No geometry")
                        continue
                    
                    if feature.geometry().isEmpty():
                        print(f"[DEBUG] Feature {feature_count}: Empty geometry")
                        continue
                    
                    z_value = feature.attribute(z_field_idx)
                    if z_value is None or z_value == "":
                        print(f"[DEBUG] Feature {feature_count}: No Z value")
                        continue
                    
                    try:
                        z_float = float(z_value)
                        print(f"[DEBUG] Feature {feature_count}: Z value = {z_float}")
                        
                        # Debug the geometry before adding
                        geom = feature.geometry()
                        print(f"[DEBUG] Feature {feature_count} geometry type: {geom.type()}")
                        print(f"[DEBUG] Feature {feature_count} geometry WKT: {geom.asWkt()}")
                        print(f"[DEBUG] Feature {feature_count} geometry JSON: {geom.asJson()}")
                        
                        # Try to get coordinates directly
                        try:
                            point = geom.asPoint()
                            print(f"[DEBUG] Feature {feature_count} asPoint: x={point.x()}, y={point.y()}")
                            print(f"[DEBUG] Feature {feature_count} point type: {type(point)}")
                            print(f"[DEBUG] Feature {feature_count} x valid: {point.x() == point.x()}")
                            print(f"[DEBUG] Feature {feature_count} y valid: {point.y() == point.y()}")
                        except Exception as e:
                            print(f"[DEBUG] Feature {feature_count} asPoint failed: {e}")
                        
                        features.append({
                            'feature': feature,
                            'geometry': geom,
                            'z': z_float
                        })
                        print(f"[DEBUG] Feature {feature_count}: Added to features list")
                        
                    except (ValueError, TypeError) as e:
                        print(f"[DEBUG] Feature {feature_count}: Z value conversion failed: {e}")
                        continue
                        
            except Exception as e:
                print(f"[DEBUG] Exception during feature processing: {e}")
                import traceback
                traceback.print_exc()
                return warnings
            
            print(f"[DEBUG] Found {len(features)} features with valid geometry and Z values")
            print(f"[DEBUG] Features list length: {len(features)}")
            print(f"[DEBUG] Features list type: {type(features)}")
            
            if len(features) == 0:
                print(f"[DEBUG] No features found, returning early")
                return warnings
            
            if len(features) < 2:
                print(f"[DEBUG] Not enough features for height difference detection (need at least 2)")
                return warnings
            
            # Debug: Print the first few features to see what we're working with
            print(f"[DEBUG] Starting detailed feature debugging...")
            print(f"[DEBUG] Will process {len(features)} features")
            for i, feature in enumerate(features[:3]):
                try:
                    point = feature['geometry'].asPoint()
                    print(f"[DEBUG] Feature {i}: x={point.x()}, y={point.y()}, z={feature['z']}")
                    print(f"[DEBUG] Feature {i} geometry type: {feature['geometry'].type()}")
                    print(f"[DEBUG] Feature {i} geometry is empty: {feature['geometry'].isEmpty()}")
                    print(f"[DEBUG] Feature {i} geometry is valid: {feature['geometry'].isGeosValid()}")
                    print(f"[DEBUG] Feature {i} geometry as text: {feature['geometry'].asWkt()}")
                    print(f"[DEBUG] Feature {i} geometry as JSON: {feature['geometry'].asJson()}")
                    print(f"[DEBUG] Feature {i} geometry as point: {feature['geometry'].asPoint()}")
                    print(f"[DEBUG] Feature {i} geometry as point XY: {feature['geometry'].asPointXY()}")
                    
                    # Check if point coordinates are valid numbers
                    print(f"[DEBUG] Feature {i} x is finite: {point.x() == point.x() and point.x() != float('inf')}")
                    print(f"[DEBUG] Feature {i} y is finite: {point.y() == point.y() and point.y() != float('inf')}")
                    print(f"[DEBUG] Feature {i} x type: {type(point.x())}")
                    print(f"[DEBUG] Feature {i} y type: {type(point.y())}")
                    
                    # Try to get raw coordinates
                    try:
                        raw_point = feature['geometry'].vertexAt(0)
                        print(f"[DEBUG] Feature {i} raw vertex: {raw_point}")
                    except Exception as e:
                        print(f"[DEBUG] Feature {i} could not get raw vertex: {e}")
                        
                except Exception as e:
                    print(f"[DEBUG] Feature {i} error getting geometry info: {e}")
                    print(f"[DEBUG] Feature {i} geometry object: {feature['geometry']}")
                    print(f"[DEBUG] Feature {i} geometry type: {type(feature['geometry'])}")
            
            if len(features) < 2:
                print(f"[DEBUG] Not enough features for height difference detection")
                return warnings
            
            # Check all pairs of features for distance and height differences
            height_difference_issues = []
            
            print(f"[DEBUG] Starting distance calculation loop...")
            print(f"[DEBUG] Number of features to process: {len(features)}")
            print(f"[DEBUG] Expected number of pairs: {len(features) * (len(features) - 1) // 2}")
            
            # Initialize distance calculator
            print(f"[DEBUG] Initializing distance calculator...")
            try:
                distance_calculator = QgsDistanceArea()
                print(f"[DEBUG] Distance calculator initialized successfully")
            except Exception as e:
                print(f"[DEBUG] Error initializing distance calculator: {e}")
                distance_calculator = None
            
            # Simple test to see if we can access the features
            print(f"[DEBUG] Testing feature access...")
            if len(features) > 0:
                test_feature = features[0]
                print(f"[DEBUG] First feature type: {type(test_feature)}")
                print(f"[DEBUG] First feature keys: {test_feature.keys() if hasattr(test_feature, 'keys') else 'No keys'}")
                print(f"[DEBUG] First feature has geometry: {'geometry' in test_feature}")
                print(f"[DEBUG] First feature has z: {'z' in test_feature}")
            
            pair_count = 0
            print(f"[DEBUG] ABOUT TO START DISTANCE CALCULATION LOOP")
            print(f"[DEBUG] Features list length: {len(features)}")
            print(f"[DEBUG] Features list type: {type(features)}")
            print(f"[DEBUG] First feature type: {type(features[0]) if features else 'No features'}")
            
            for i, feature1 in enumerate(features):
                print(f"[DEBUG] Processing feature {i+1}/{len(features)}")
                for j, feature2 in enumerate(features[i+1:], i+1):
                    pair_count += 1
                    print(f"[DEBUG] Processing pair {pair_count}: feature {i+1} vs feature {j+1}")
                    print(f"[DEBUG] === PAIR {pair_count} COORDINATE DEBUG ===")
                    try:
                        print(f"[DEBUG] Getting geometry for feature1...")
                        geom1 = feature1['geometry']
                        print(f"[DEBUG] Feature1 geometry type: {type(geom1)}")
                        print(f"[DEBUG] Feature1 geometry WKT: {geom1.asWkt()}")
                        
                        print(f"[DEBUG] Getting geometry for feature2...")
                        geom2 = feature2['geometry']
                        print(f"[DEBUG] Feature2 geometry type: {type(geom2)}")
                        print(f"[DEBUG] Feature2 geometry WKT: {geom2.asWkt()}")
                        
                        point1 = geom1.asPoint()
                        point2 = geom2.asPoint()
                        
                        # Debug geometry coordinates
                        print(f"[DEBUG] Point1: x={point1.x()}, y={point1.y()}")
                        print(f"[DEBUG] Point2: x={point2.x()}, y={point2.y()}")
                        print(f"[DEBUG] Point1 type: {type(point1)}")
                        print(f"[DEBUG] Point2 type: {type(point2)}")
                        print(f"[DEBUG] Point1 x is NaN: {point1.x() != point1.x()}")
                        print(f"[DEBUG] Point1 y is NaN: {point1.y() != point1.y()}")
                        print(f"[DEBUG] Point2 x is NaN: {point2.x() != point2.x()}")
                        print(f"[DEBUG] Point2 y is NaN: {point2.y() != point2.y()}")
                        print(f"[DEBUG] === END PAIR {pair_count} COORDINATE DEBUG ===")
                        
                        # Check if coordinates are valid
                        if (point1.x() == 0 and point1.y() == 0) or (point2.x() == 0 and point2.y() == 0):
                            print(f"[DEBUG] Warning: One or both points have zero coordinates")
                        
                        # Check for NaN coordinates
                        if (point1.x() != point1.x()) or (point1.y() != point1.y()) or (point2.x() != point2.x()) or (point2.y() != point2.y()):
                            print(f"[DEBUG] Warning: One or both points have NaN coordinates")
                            print(f"[DEBUG] Point1 NaN check: x={point1.x() != point1.x()}, y={point1.y() != point1.y()}")
                            print(f"[DEBUG] Point2 NaN check: x={point2.x() != point2.x()}, y={point2.y() != point2.y()}")
                            print(f"[DEBUG] Point1 raw values: x={point1.x()}, y={point1.y()}")
                            print(f"[DEBUG] Point2 raw values: x={point2.x()}, y={point2.y()}")
                            print(f"[DEBUG] Point1 type: {type(point1)}")
                            print(f"[DEBUG] Point2 type: {type(point2)}")
                            
                            # Try alternative methods to get coordinates
                            try:
                                print(f"[DEBUG] Trying alternative coordinate extraction...")
                                print(f"[DEBUG] Feature1 geometry WKT: {feature1['geometry'].asWkt()}")
                                print(f"[DEBUG] Feature2 geometry WKT: {feature2['geometry'].asWkt()}")
                                
                                # Try to get coordinates from WKT
                                wkt1 = feature1['geometry'].asWkt()
                                wkt2 = feature2['geometry'].asWkt()
                                
                                if 'POINT(' in wkt1 and 'POINT(' in wkt2:
                                    # Extract coordinates from WKT
                                    coords1 = wkt1.replace('POINT(', '').replace(')', '').split()
                                    coords2 = wkt2.replace('POINT(', '').replace(')', '').split()
                                    
                                    if len(coords1) >= 2 and len(coords2) >= 2:
                                        x1, y1 = float(coords1[0]), float(coords1[1])
                                        x2, y2 = float(coords2[0]), float(coords2[1])
                                        
                                        print(f"[DEBUG] Extracted from WKT - Point1: x={x1}, y={y1}")
                                        print(f"[DEBUG] Extracted from WKT - Point2: x={x2}, y={y2}")
                                        
                                        # Use these coordinates instead
                                        point1 = QgsPointXY(x1, y1)
                                        point2 = QgsPointXY(x2, y2)
                                    else:
                                        print(f"[DEBUG] Could not extract coordinates from WKT")
                                        continue
                                else:
                                    print(f"[DEBUG] WKT does not contain POINT format")
                                    continue
                                    
                            except Exception as e:
                                print(f"[DEBUG] Alternative coordinate extraction failed: {e}")
                                continue
                    except Exception as e:
                        print(f"[DEBUG] Error getting point coordinates: {e}")
                        continue
                    
                    # Create 2D points for distance calculation
                    print(f"[DEBUG] Creating 2D points for distance calculation")
                    print(f"[DEBUG] Point1 coordinates: x={point1.x()}, y={point1.y()}")
                    print(f"[DEBUG] Point2 coordinates: x={point2.x()}, y={point2.y()}")
                    
                    point1_2d = QgsPointXY(point1.x(), point1.y())
                    point2_2d = QgsPointXY(point2.x(), point2.y())
                    
                    print(f"[DEBUG] Created QgsPointXY objects:")
                    print(f"[DEBUG] Point1_2d: x={point1_2d.x()}, y={point1_2d.y()}")
                    print(f"[DEBUG] Point2_2d: x={point2_2d.x()}, y={point2_2d.y()}")
                    
                    # Try to calculate distance using QGIS first, then fallback to Euclidean
                    distance = None
                    try:
                        print(f"[DEBUG] Attempting QGIS distance calculation...")
                        if distance_calculator is None:
                            print(f"[DEBUG] Distance calculator is None, using Euclidean")
                            raise ValueError("Distance calculator is None")
                        qgis_distance = distance_calculator.measureLine(point1_2d, point2_2d)
                        print(f"[DEBUG] QGIS distance: {qgis_distance}")
                        print(f"[DEBUG] QGIS distance type: {type(qgis_distance)}")
                        print(f"[DEBUG] QGIS distance is NaN: {qgis_distance != qgis_distance}")
                        print(f"[DEBUG] QGIS distance is inf: {qgis_distance == float('inf')}")
                        
                        # Check if distance is valid (not nan or inf)
                        if qgis_distance == qgis_distance and qgis_distance != float('inf'):  # Valid number check
                            distance = qgis_distance
                            print(f"[DEBUG] Using QGIS distance: {distance}")
                        else:
                            print(f"[DEBUG] QGIS distance is NaN or inf, using Euclidean")
                            raise ValueError("QGIS distance is NaN or inf")
                            
                    except Exception as e:
                        print(f"[DEBUG] QGIS distance calculation failed: {e}, using Euclidean")
                        # Fallback to simple Euclidean distance
                        dx = point2.x() - point1.x()
                        dy = point2.y() - point1.y()
                        print(f"[DEBUG] Euclidean calculation: dx={dx}, dy={dy}")
                        print(f"[DEBUG] Euclidean calculation: dx^2={dx*dx}, dy^2={dy*dy}")
                        distance = (dx * dx + dy * dy) ** 0.5
                        print(f"[DEBUG] Euclidean distance: {distance}")
                        print(f"[DEBUG] Euclidean distance type: {type(distance)}")
                        print(f"[DEBUG] Euclidean distance is NaN: {distance != distance}")
                    
                    # Additional check for NaN in Euclidean distance
                    if distance is None or distance != distance:  # NaN check
                        print(f"[DEBUG] Euclidean distance is also NaN, skipping")
                        print(f"[DEBUG] Distance value: {distance}")
                        print(f"[DEBUG] Distance type: {type(distance)}")
                        continue
                    
                    # Convert to meters - assume distance is already in meters for archaeological projects
                    distance_meters = distance
                    print(f"[DEBUG] Distance in meters: {distance_meters}")
                    
                    # Check if features are close enough
                    print(f"[DEBUG] Distance: {distance_meters}m, max: {self._max_distance_meters}m")
                    print(f"[DEBUG] Z values: {feature1['z']} vs {feature2['z']}")
                    if distance_meters <= self._max_distance_meters:
                        # Calculate height difference
                        height_difference = abs(feature1['z'] - feature2['z'])
                        print(f"[DEBUG] Height difference: {height_difference}m, max: {self._max_height_difference_meters}m")
                        
                        # Check if height difference is significant
                        if height_difference > self._max_height_difference_meters:
                            # Get feature identifiers
                            feature1_identifier = self._get_feature_identifier(feature1['feature'], "Total Station Point")
                            feature2_identifier = self._get_feature_identifier(feature2['feature'], "Total Station Point")
                            
                            height_difference_issues.append({
                                'feature1': feature1['feature'],
                                'feature2': feature2['feature'],
                                'feature1_identifier': feature1_identifier,
                                'feature2_identifier': feature2_identifier,
                                'distance': distance_meters,
                                'height_difference': height_difference,
                                'z1': feature1['z'],
                                'z2': feature2['z']
                            })
            
            print(f"[DEBUG] Found {len(height_difference_issues)} height difference issues")
            
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
                    
                    print(f"[DEBUG] Found identifier field: {identifier_field}")
                    
                    for issue in issues:
                        feature1 = issue['feature1']
                        feature2 = issue['feature2']
                        
                        if identifier_field:
                            # Use the dynamic identifier field
                            identifier_field_idx = feature1.fields().indexOf(identifier_field)
                            print(f"[DEBUG] Identifier field index for {identifier_field}: {identifier_field_idx}")
                            
                            if identifier_field_idx >= 0:
                                identifier1 = feature1.attribute(identifier_field_idx)
                                identifier2 = feature2.attribute(identifier_field_idx)
                                print(f"[DEBUG] Feature1 {identifier_field}: {identifier1}")
                                print(f"[DEBUG] Feature2 {identifier_field}: {identifier2}")
                                
                                if identifier1 is not None:
                                    feature_identifiers.append(f"'{identifier1}'")
                                if identifier2 is not None:
                                    feature_identifiers.append(f"'{identifier2}'")
                            else:
                                # Fallback to feature IDs
                                feature_ids.extend([feature1.id(), feature2.id()])
                                print(f"[DEBUG] Using feature IDs as fallback: {feature1.id()}, {feature2.id()}")
                        else:
                            # Fallback to feature IDs
                            feature_ids.extend([feature1.id(), feature2.id()])
                            print(f"[DEBUG] No identifier field found, using feature IDs: {feature1.id()}, {feature2.id()}")
                    
                    # Remove duplicates and create filter expression
                    if feature_identifiers:
                        unique_identifiers = list(set(feature_identifiers))
                        print(f"[DEBUG] Unique identifiers: {unique_identifiers}")
                        
                        if len(unique_identifiers) == 1:
                            filter_expression = f'"{identifier_field}" = {unique_identifiers[0]}'
                        else:
                            identifiers_list = ",".join(unique_identifiers)
                            filter_expression = f'"{identifier_field}" IN ({identifiers_list})'
                    else:
                        # Use feature IDs as fallback
                        unique_ids = list(set(feature_ids))
                        print(f"[DEBUG] Unique feature IDs: {unique_ids}")
                        
                        if len(unique_ids) == 1:
                            filter_expression = f'"fid" = {unique_ids[0]}'
                        else:
                            id_list = ",".join(str(id) for id in unique_ids)
                            filter_expression = f'"fid" IN ({id_list})'
                    
                    # Debug: Print filter expression details
                    print(f"[DEBUG] Final filter expression: {filter_expression}")
                    if feature_identifiers:
                        print(f"[DEBUG] Using {identifier_field} field with values: {feature_identifiers}")
                    else:
                        print(f"[DEBUG] Using fid field with values: {feature_ids}")
                    
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
            print(f"Error in height difference detection: {str(e)}")
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
            print(f"Error finding identifier field: {e}")
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
                    print(f"[DEBUG] Found common identifier field: {field.name()}")
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
            print(f"Error getting feature identifier: {str(e)}")
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
            print(f"Error creating height difference warning: {str(e)}")
            distance_cm = max_distance * 100
            height_difference_cm = max_height_difference * 100
            return f"{feature_text} are separated by {distance_cm:.1f} cm but have a height difference of {height_difference_cm:.1f} cm (maximum allowed: {self._max_height_difference_meters * 100:.1f} cm)" 