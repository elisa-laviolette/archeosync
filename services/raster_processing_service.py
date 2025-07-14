"""
Raster processing service implementation for ArcheoSync plugin.

This module provides a service for processing raster layers, specifically for
clipping background images to recording areas with configurable offsets.

The service integrates with QGIS and uses GDAL for raster processing operations.
It provides functionality to clip raster layers to polygon geometries with
configurable buffer offsets, making it ideal for archaeological recording
scenarios where background imagery needs to be limited to specific areas.

Key Features:
- GDAL-based raster clipping operations
- Configurable offset support for buffer zones
- Automatic coordinate system handling
- Temporary file management and cleanup
- Comprehensive error handling and validation
- QGIS layer integration

Usage:
    raster_service = QGISRasterProcessingService()
    clipped_path = raster_service.clip_raster_to_feature(
        raster_layer_id='raster_id',
        feature_geometry=feature.geometry(),
        offset_meters=0.2,
        output_path='/path/to/output.tif'
    )

Dependencies:
- QGIS with GDAL support
- GDAL command-line tools (gdalwarp, ogr2ogr)
- PyQt5 for QGIS integration

The service automatically:
- Validates input parameters and geometries
- Creates temporary shapefiles for clipping operations
- Handles coordinate system transformations
- Manages temporary file cleanup
- Provides detailed error messages for troubleshooting
"""

import os
import tempfile
import subprocess
from typing import Optional, Any, List
from qgis.core import QgsRasterLayer, QgsGeometry, QgsProject

try:
    from ..core.interfaces import IRasterProcessingService
except ImportError:
    from core.interfaces import IRasterProcessingService


class QGISRasterProcessingService(IRasterProcessingService):
    """
    QGIS-specific implementation of raster processing operations.
    
    This class provides functionality to process raster layers using GDAL,
    specifically for clipping operations with configurable offsets. It is designed
    for archaeological recording scenarios where background imagery needs to be
    limited to specific recording areas.
    
    The service handles:
    - Raster layer validation and lookup
    - Geometry validation and buffering
    - Coordinate system management
    - Temporary file creation and cleanup
    - GDAL command execution
    - Error handling and reporting
    
    Dependencies:
    - QGIS environment with GDAL support
    - GDAL command-line tools (gdalwarp, ogr2ogr)
    """
    
    def __init__(self):
        """Initialize the raster processing service."""
        pass
    
    def clip_raster_to_feature(self, 
                              raster_layer_id: str,
                              feature_geometry: Any,
                              offset_meters: float = 0.2,
                              output_path: Optional[str] = None) -> Optional[str]:
        """
        Clip a raster layer to a feature geometry with an offset.
        
        This method clips a raster layer to the boundary of a polygon feature,
        optionally adding a buffer zone around the feature. The clipped raster
        is saved as a GeoTIFF file and can be used as background imagery in
        archaeological recording projects.
        
        Args:
            raster_layer_id: ID of the raster layer to clip (must exist in QGIS project)
            feature_geometry: QgsGeometry of the polygon feature to clip to
            offset_meters: Offset in meters to expand the clipping area (default: 0.2)
            output_path: Optional output path for the clipped raster (auto-generated if None)
            
        Returns:
            Path to the clipped raster file (GeoTIFF), or None if operation failed
            
        Raises:
            No explicit exceptions, but returns None for any errors encountered
            
        Example:
            >>> service = QGISRasterProcessingService()
            >>> clipped_path = service.clip_raster_to_feature(
            ...     raster_layer_id='background_image',
            ...     feature_geometry=recording_area.geometry(),
            ...     offset_meters=0.5
            ... )
            >>> if clipped_path:
            ...     print(f"Clipped raster saved to: {clipped_path}")
        """
        try:
            # Get the raster layer
            raster_layer = QgsProject.instance().mapLayer(raster_layer_id)
            if not raster_layer or not isinstance(raster_layer, QgsRasterLayer):
                print(f"Error: Invalid raster layer ID: {raster_layer_id}")
                return None
            
            # Validate feature geometry
            if not feature_geometry or feature_geometry.isNull():
                print("Error: Invalid feature geometry")
                return None
            
            # Get raster source path
            raster_source = raster_layer.source()
            if not raster_source or not os.path.exists(raster_source):
                print(f"Error: Raster source not found: {raster_source}")
                return None
            
            # Create output path if not provided
            if not output_path:
                output_path = self._create_temp_output_path(raster_source)
            
            # Create temporary shapefile for the clipping geometry
            raster_crs = raster_layer.crs()
            
            temp_shapefile = self._create_temp_shapefile(feature_geometry, offset_meters, raster_crs)
            if not temp_shapefile:
                print("Error: Failed to create temporary shapefile")
                return None
            
            try:
                # Pass raster_crs.authid() to _execute_gdalwarp
                success = self._execute_gdalwarp(
                    input_raster=raster_source,
                    output_raster=output_path,
                    cutline_shapefile=temp_shapefile,
                    raster_crs_authid=raster_crs.authid()
                )
                
                if success and os.path.exists(output_path):
                    return output_path
                else:
                    print("Error: GDAL warp operation failed")
                    return None
                    
            finally:
                # Clean up temporary shapefile
                self._cleanup_temp_shapefile(temp_shapefile)
                
        except Exception as e:
            print(f"Error clipping raster: {str(e)}")
            return None
    
    def _create_temp_output_path(self, input_raster_path: str) -> str:
        """
        Create a temporary output path for the clipped raster.
        
        Creates a temporary file path with .tif extension for the clipped raster.
        The file is created in the system's temporary directory with a unique name.
        
        Args:
            input_raster_path: Path to the input raster (used for context)
            
        Returns:
            Path to the temporary output file (GeoTIFF format)
        """
        # Always use GeoTIFF for output as it's more reliable for clipping operations
        temp_fd, temp_path = tempfile.mkstemp(suffix='.tif', prefix='clipped_')
        os.close(temp_fd)
        
        return temp_path
    
    def _create_temp_shapefile(self, geometry: Any, offset_meters: float, crs: Any) -> Optional[str]:
        """
        Create a temporary shapefile from geometry with offset.
        
        Creates a temporary shapefile from a QgsGeometry, optionally applying
        a buffer offset. The shapefile is created with the specified coordinate
        reference system and includes proper projection files.
        
        Args:
            geometry: QgsGeometry to create shapefile from (must be valid polygon)
            offset_meters: Offset in meters to expand the geometry (0 for no buffer)
            crs: Coordinate reference system to use for the shapefile
            
        Returns:
            Path to the temporary shapefile (.shp), or None if creation failed
            
        Note:
            The shapefile is created in the system's temporary directory and
            should be cleaned up after use.
        """
        try:
            # Create buffered geometry if offset is specified
            if offset_meters > 0:
                buffered_geometry = geometry.buffer(offset_meters, 5)  # 5 segments for smooth buffer
            else:
                buffered_geometry = geometry
            
            # Ensure the polygon is explicitly closed
            if buffered_geometry.isMultipart():
                polygons = buffered_geometry.asMultiPolygon()
                print(f"[DEBUG] Multipart geometry - polygons count: {len(polygons)}")
                for i, poly in enumerate(polygons):
                    print(f"[DEBUG] Polygon {i} - poly type: {type(poly)}, poly length: {len(poly) if poly else 0}")
                    # Safety check: ensure poly[0] exists and has at least 2 points
                    if poly and len(poly) > 0 and len(poly[0]) >= 2:
                        print(f"[DEBUG] Polygon {i} - poly[0] length: {len(poly[0])}")
                        # Compare coordinates properly by converting to strings or using QgsPointXY methods
                        first_point = poly[0][0]
                        last_point = poly[0][-1]
                        print(f"[DEBUG] Polygon {i} - first_point type: {type(first_point)}, last_point type: {type(last_point)}")
                        if (first_point.x() != last_point.x() or first_point.y() != last_point.y()):
                            poly[0].append(first_point)
                            polygons[i] = poly
                closed_geometry = QgsGeometry.fromMultiPolygonXY(polygons)
            else:
                poly = buffered_geometry.asPolygon()
                print(f"[DEBUG] Single polygon - poly type: {type(poly)}, poly length: {len(poly) if poly else 0}")
                if poly and len(poly) > 0 and len(poly[0]) >= 2:
                    print(f"[DEBUG] Single polygon - poly[0] length: {len(poly[0])}")
                    first_point = poly[0][0]
                    last_point = poly[0][-1]
                    print(f"[DEBUG] Single polygon - first_point type: {type(first_point)}, last_point type: {type(last_point)}")
                    if (first_point.x() != last_point.x() or first_point.y() != last_point.y()):
                        poly[0].append(first_point)
                closed_geometry = QgsGeometry.fromPolygonXY(poly)
            
            # Create temporary shapefile using QGIS native methods
            temp_fd, temp_path = tempfile.mkstemp(suffix='.shp', prefix='clip_')
            os.close(temp_fd)
            
            # Remove the .shp extension
            temp_base = temp_path[:-4]
            
            # Create a temporary vector layer
            from qgis.core import QgsVectorLayer, QgsFeature, QgsFields, QgsField, QgsVectorFileWriter
            from PyQt5.QtCore import QVariant
            
            # Create fields
            fields = QgsFields()
            fields.append(QgsField("id", QVariant.Int))
            
            # Create vector layer
            layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "temp_clip", "memory")
            layer.dataProvider().addAttributes(fields)
            layer.updateFields()
            
            # Create feature
            feature = QgsFeature(fields)
            feature.setGeometry(closed_geometry)
            feature.setAttributes([1])
            
            # Add feature to layer
            layer.dataProvider().addFeatures([feature])
            
            # Save as shapefile
            success = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                temp_base,
                "UTF-8",
                crs,
                "ESRI Shapefile"
            )
            
            if success[0] == QgsVectorFileWriter.NoError:
                
                return temp_base + '.shp'
            else:
                print(f"Failed to create shapefile: {success}")
                return None
                
        except Exception as e:
            print(f"Error creating temporary shapefile: {str(e)}")
            print(f"Geometry type: {type(geometry)}")
            print(f"Geometry is null: {geometry.isNull() if hasattr(geometry, 'isNull') else 'N/A'}")
            print(f"Geometry is valid: {geometry.isValid() if hasattr(geometry, 'isValid') else 'N/A'}")
            if hasattr(geometry, 'asWkt'):
                print(f"Geometry WKT: {geometry.asWkt()[:100]}...")  # First 100 chars
            return None
    
    def _execute_gdalwarp(self, 
                         input_raster: str,
                         output_raster: str,
                         cutline_shapefile: str,
                         raster_crs_authid: str) -> bool:
        """
        Execute GDAL warp command to clip raster.
        
        Uses gdalwarp to clip a raster using a shapefile as a cutline. The
        operation maintains the original coordinate reference system and
        automatically detects the layer name in the shapefile.
        
        Args:
            input_raster: Path to input raster file
            output_raster: Path to output raster file (GeoTIFF)
            cutline_shapefile: Path to shapefile used for clipping
            raster_crs_authid: Auth ID of the raster's coordinate reference system
            
        Returns:
            True if operation was successful, False otherwise
            
        Note:
            Requires gdalwarp command-line tool to be available in the system PATH.
        """
        try:
            # Check if shapefile exists and has projection
            if not os.path.exists(cutline_shapefile):
                print(f"Cutline shapefile does not exist: {cutline_shapefile}")
                return False
            
            prj_file = cutline_shapefile[:-4] + '.prj'
            if not os.path.exists(prj_file):
                print(f"Cutline projection file does not exist: {prj_file}")
                return False
            
            # Detect actual layer name in shapefile
            try:
                from osgeo import ogr
                driver = ogr.GetDriverByName('ESRI Shapefile')
                ds = driver.Open(cutline_shapefile, 0)
                layer_name = ds.GetLayer(0).GetName()
            except Exception as e:
                print(f"Could not detect cutline layer name, defaulting to 'temp_clip': {e}")
                layer_name = 'temp_clip'
            
            # Get gdalwarp path
            gdalwarp_path = self._get_gdal_tool_path('gdalwarp')
            if not gdalwarp_path:
                print("Error: gdalwarp not found")
                return False
            
            # Build gdalwarp command with explicit SRS and detected cutline layer name
            cmd = [
                gdalwarp_path,
                '-s_srs', raster_crs_authid,
                '-t_srs', raster_crs_authid,
                '-cutline', cutline_shapefile,
                '-cl', layer_name,
                '-crop_to_cutline',
                input_raster,
                output_raster
            ]
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                print(f"GDAL warp error: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            print("GDAL warp operation timed out")
            return False
        except Exception as e:
            print(f"Error executing gdalwarp: {str(e)}")
            return False
    
    def _execute_ogr2ogr(self, 
                        output_shapefile: str,
                        wkt_geometry: str,
                        crs: str) -> bool:
        """
        Execute ogr2ogr command to create shapefile from WKT.
        
        Creates a shapefile from WKT geometry using ogr2ogr. The method
        converts the WKT to GeoJSON format and then uses ogr2ogr to create
        a proper shapefile with projection information.
        
        Args:
            output_shapefile: Path to output shapefile (without .shp extension)
            wkt_geometry: WKT representation of polygon geometry
            crs: Coordinate reference system (EPSG code or auth ID)
            
        Returns:
            True if operation was successful, False otherwise
            
        Note:
            Requires ogr2ogr command-line tool to be available in the system PATH.
        """
        try:
            # Get ogr2ogr path
            ogr2ogr_path = self._get_gdal_tool_path('ogr2ogr')
            if not ogr2ogr_path:
                print("Error: ogr2ogr not found")
                return False
            
            # Create GeoJSON content
            geojson_content = f'''{{
                "type": "FeatureCollection",
                "features": [
                    {{
                        "type": "Feature",
                        "geometry": {{
                            "type": "Polygon",
                            "coordinates": [[{self._wkt_to_coordinates(wkt_geometry)}]]
                        }},
                        "properties": {{}}
                    }}
                ]
            }}'''
            
            # Create temporary GeoJSON file
            temp_fd, temp_geojson = tempfile.mkstemp(suffix='.geojson', prefix='temp_')
            os.close(temp_fd)
            
            try:
                # Write GeoJSON content
                with open(temp_geojson, 'w') as f:
                    f.write(geojson_content)
                
                # Build ogr2ogr command
                cmd = [
                    ogr2ogr_path,
                    '-f', 'ESRI Shapefile',
                    '-t_srs', crs,
                    output_shapefile,
                    temp_geojson
                ]
                
                # Execute command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60  # 1 minute timeout
                )
                
                if result.returncode != 0:
                    print(f"ogr2ogr error: {result.stderr}")
                    return False
                
                return True
                
            finally:
                # Clean up temporary GeoJSON file
                if os.path.exists(temp_geojson):
                    os.remove(temp_geojson)
                    
        except subprocess.TimeoutExpired:
            print("ogr2ogr operation timed out")
            return False
        except Exception as e:
            print(f"Error executing ogr2ogr: {str(e)}")
            return False
    
    def _wkt_to_coordinates(self, wkt: str) -> str:
        """
        Convert WKT polygon to coordinate string for GeoJSON.
        
        Extracts coordinates from a WKT polygon string and converts them to
        GeoJSON format. Ignores Z coordinates (3D) and focuses on X,Y coordinates.
        
        Args:
            wkt: WKT representation of polygon (e.g., "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
            
        Returns:
            Coordinate string for GeoJSON (e.g., "[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]")
            
        Note:
            Returns empty string if parsing fails.
        """
        try:
            # Extract coordinates from WKT POLYGON((x1 y1 z1, x2 y2 z2, ...))
            start = wkt.find('((') + 2
            end = wkt.find('))')
            coord_string = wkt[start:end]
            
            # Convert to GeoJSON format (ignore Z coordinates)
            coords = []
            for coord_pair in coord_string.split(','):
                parts = coord_pair.strip().split()
                if len(parts) >= 2:
                    x, y = parts[0], parts[1]  # Take only X and Y, ignore Z
                    coords.append(f"[{x}, {y}]")
            
            return ', '.join(coords)
            
        except Exception as e:
            print(f"Error converting WKT to coordinates: {str(e)}")
            return ""
    
    def _cleanup_temp_shapefile(self, shapefile_path: str) -> None:
        """
        Clean up temporary shapefile and associated files.
        
        Removes a shapefile and all its associated files (.shp, .shx, .dbf, .prj, etc.)
        from the filesystem. This is used to clean up temporary files created
        during raster clipping operations.
        
        Args:
            shapefile_path: Path to the shapefile to clean up (with .shp extension)
            
        Note:
            Silently ignores errors if files don't exist or can't be removed.
        """
        try:
            base_path = shapefile_path[:-4]  # Remove .shp extension
            
            # Remove all related files
            extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg']
            for ext in extensions:
                file_path = base_path + ext
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
        except Exception as e:
            print(f"Error cleaning up temporary shapefile: {str(e)}")
    
    def is_gdal_available(self) -> bool:
        """
        Check if GDAL command line tools are available.
        
        Verifies that both gdalwarp and ogr2ogr command-line tools are available.
        This method searches for GDAL tools in common QGIS installation paths
        and falls back to system PATH.
        
        Returns:
            True if both gdalwarp and ogr2ogr are available, False otherwise
            
        Note:
            This method attempts to run version commands for both tools to verify
            their availability and proper installation.
        """
        try:
            # Get potential GDAL tool paths
            gdal_paths = self._get_gdal_tool_paths()
            
            # Check gdalwarp
            gdalwarp_available = self._check_gdal_tool('gdalwarp', gdal_paths)
            if not gdalwarp_available:
                print("Warning: gdalwarp not found in any of the searched paths")
                return False
            
            # Check ogr2ogr
            ogr2ogr_available = self._check_gdal_tool('ogr2ogr', gdal_paths)
            if not ogr2ogr_available:
                print("Warning: ogr2ogr not found in any of the searched paths")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error checking GDAL availability: {str(e)}")
            return False
    
    def _get_gdal_tool_paths(self) -> List[str]:
        """
        Get potential paths where GDAL tools might be located.
        
        Returns:
            List of potential paths to search for GDAL tools
        """
        paths = []
        
        # Add current PATH
        paths.extend(os.environ.get('PATH', '').split(os.pathsep))
        
        # Platform-specific paths
        import platform
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # Common QGIS installation paths on macOS
            qgis_paths = [
                '/Applications/QGIS.app/Contents/MacOS',
                '/Applications/QGIS.app/Contents/Frameworks',
                '/Applications/QGIS.app/Contents/Resources',
                '/Applications/QGIS.app/Contents/MacOS/bin',
                '/Applications/QGIS.app/Contents/Frameworks/bin',
                '/Applications/QGIS.app/Contents/Resources/bin',
            ]
            
            # Common GDAL installation paths on macOS
            gdal_paths = [
                '/Applications/Postgres.app/Contents/Versions/latest/bin',
                '/usr/local/bin',
                '/opt/homebrew/bin',
                '/opt/local/bin',
                '/usr/bin',
            ]
            
        elif system == "Windows":
            # Common QGIS installation paths on Windows
            qgis_paths = [
                'C:\\Program Files\\QGIS*/apps\\qgis\\bin',
                'C:\\Program Files\\QGIS*/apps\\qgis-ltr\\bin',
                'C:\\OSGeo4W*/bin',
                'C:\\OSGeo4W*/apps\\qgis\\bin',
            ]
            
            # Common GDAL installation paths on Windows
            gdal_paths = [
                'C:\\Program Files\\GDAL\\bin',
                'C:\\OSGeo4W*/bin',
            ]
            
        else:  # Linux
            # Common QGIS installation paths on Linux
            qgis_paths = [
                '/usr/bin',
                '/usr/local/bin',
                '/opt/qgis/bin',
                '/usr/share/qgis/bin',
            ]
            
            # Common GDAL installation paths on Linux
            gdal_paths = [
                '/usr/bin',
                '/usr/local/bin',
                '/opt/gdal/bin',
            ]
        
        # Add QGIS and GDAL paths
        paths.extend(qgis_paths)
        paths.extend(gdal_paths)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in paths:
            if path and path not in seen:
                seen.add(path)
                unique_paths.append(path)
        
        return unique_paths
    
    def _check_gdal_tool(self, tool_name: str, search_paths: List[str]) -> bool:
        """
        Check if a specific GDAL tool is available in the given paths.
        
        Args:
            tool_name: Name of the GDAL tool (e.g., 'gdalwarp', 'ogr2ogr')
            search_paths: List of paths to search for the tool
            
        Returns:
            True if the tool is available and working, False otherwise
        """
        # First try the tool name directly (uses PATH)
        try:
            result = subprocess.run(
                [tool_name, '--version'],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Try specific paths
        for path in search_paths:
            if not path or not os.path.exists(path):
                continue
                
            tool_path = os.path.join(path, tool_name)
            if os.path.exists(tool_path) and os.access(tool_path, os.X_OK):
                try:
                    result = subprocess.run(
                        [tool_path, '--version'],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10
                    )
                    if result.returncode == 0:
                        print(f"Found {tool_name} at: {tool_path}")
                        return True
                except (subprocess.TimeoutExpired, OSError):
                    continue
        
        return False 
    
    def _get_gdal_tool_path(self, tool_name: str) -> Optional[str]:
        """
        Get the full path to a GDAL tool.
        
        Args:
            tool_name: Name of the GDAL tool (e.g., 'gdalwarp', 'ogr2ogr')
            
        Returns:
            Full path to the tool if found, None otherwise
        """
        # First try the tool name directly (uses PATH)
        try:
            result = subprocess.run(
                [tool_name, '--version'],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            if result.returncode == 0:
                return tool_name
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Try specific paths
        gdal_paths = self._get_gdal_tool_paths()
        for path in gdal_paths:
            if not path or not os.path.exists(path):
                continue
                
            tool_path = os.path.join(path, tool_name)
            if os.path.exists(tool_path) and os.access(tool_path, os.X_OK):
                try:
                    result = subprocess.run(
                        [tool_path, '--version'],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10
                    )
                    if result.returncode == 0:
                        return tool_path
                except (subprocess.TimeoutExpired, OSError):
                    continue
        
        return None 
    
    def get_gdal_debug_info(self) -> str:
        """
        Get detailed debugging information about GDAL tool availability.
        
        Returns:
            String containing detailed information about GDAL tool locations and availability
        """
        info = []
        info.append("=== GDAL Tool Debug Information ===")
        
        # Check PATH
        path_env = os.environ.get('PATH', '')
        info.append(f"PATH environment variable: {path_env}")
        
        # Get all potential paths
        gdal_paths = self._get_gdal_tool_paths()
        info.append(f"Total paths to search: {len(gdal_paths)}")
        
        # Check each tool
        for tool_name in ['gdalwarp', 'ogr2ogr']:
            info.append(f"\n--- {tool_name} ---")
            
            # Check direct PATH access
            try:
                result = subprocess.run(
                    [tool_name, '--version'],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5
                )
                if result.returncode == 0:
                    info.append(f"✓ Found in PATH: {tool_name}")
                    info.append(f"  Version output: {result.stdout.strip()}")
                else:
                    info.append(f"✗ Not found in PATH: {tool_name}")
            except Exception as e:
                info.append(f"✗ Error checking PATH for {tool_name}: {str(e)}")
            
            # Check specific paths
            found_in_paths = []
            for path in gdal_paths:
                if not path or not os.path.exists(path):
                    continue
                    
                tool_path = os.path.join(path, tool_name)
                if os.path.exists(tool_path):
                    if os.access(tool_path, os.X_OK):
                        try:
                            result = subprocess.run(
                                [tool_path, '--version'],
                                capture_output=True,
                                text=True,
                                check=False,
                                timeout=5
                            )
                            if result.returncode == 0:
                                found_in_paths.append(f"  ✓ {tool_path}")
                            else:
                                found_in_paths.append(f"  ✗ {tool_path} (execution failed)")
                        except Exception as e:
                            found_in_paths.append(f"  ✗ {tool_path} (error: {str(e)})")
                    else:
                        found_in_paths.append(f"  ✗ {tool_path} (not executable)")
            
            if found_in_paths:
                info.append("Found in specific paths:")
                info.extend(found_in_paths)
            else:
                info.append("Not found in any specific paths")
        
        return "\n".join(info) 