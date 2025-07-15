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
from qgis.core import (QgsRasterLayer, QgsGeometry, QgsProject, QgsVectorLayer, 
                       QgsFeature, QgsFields, QgsField, QgsCoordinateTransform, 
                       QgsRectangle, QgsVectorFileWriter)

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
        Uses direct GDAL command approach that matches the working manual command.
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
            
            # Buffer geometry if needed
            if offset_meters > 0:
                buffered_geometry = feature_geometry.buffer(offset_meters, 5)
            else:
                buffered_geometry = feature_geometry
            
            print(f"[DEBUG] Using direct GDAL command approach for raster clipping")
            print(f"[DEBUG] Raster source: {raster_source}")
            print(f"[DEBUG] Raster CRS: {raster_layer.crs().description()}")
            print(f"[DEBUG] Output path: {output_path}")
            
            # Use direct GDAL command approach (similar to working manual command)
            return self._clip_raster_with_gdal_command(raster_layer, buffered_geometry, output_path)
        except Exception as e:
            print(f"Error clipping raster: {str(e)}")
            return None
    
    def clip_raster_to_geometry(self, 
                               raster_layer_id: str,
                               geometry_wkt: str,
                               output_path: Optional[str] = None,
                               offset_meters: float = 0.2) -> bool:
        """
        Clip a raster layer to a geometry defined by WKT string with an offset.
        
        This method clips a raster layer to the boundary of a polygon defined by
        a WKT (Well-Known Text) string, optionally adding a buffer zone around
        the geometry. The clipped raster is saved as a GeoTIFF file.
        
        Args:
            raster_layer_id: ID of the raster layer to clip (must exist in QGIS project)
            geometry_wkt: WKT string defining the polygon geometry to clip to
            output_path: Optional output path for the clipped raster (auto-generated if None)
            offset_meters: Offset in meters to expand the clipping area (default: 0.2)
            
        Returns:
            True if clipping was successful, False otherwise
            
        Example:
            >>> service = QGISRasterProcessingService()
            >>> success = service.clip_raster_to_geometry(
            ...     raster_layer_id='background_image',
            ...     geometry_wkt='POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            ...     offset_meters=0.5
            ... )
        """
        try:
            # Parse WKT to QgsGeometry
            geometry = QgsGeometry.fromWkt(geometry_wkt)
            if not geometry or geometry.isNull():
                print("Error: Invalid WKT geometry")
                return False
            
            # Use the existing clip_raster_to_feature method
            clipped_path = self.clip_raster_to_feature(
                raster_layer_id=raster_layer_id,
                feature_geometry=geometry,
                offset_meters=offset_meters,
                output_path=output_path
            )
            
            return clipped_path is not None
            
        except Exception as e:
            print(f"Error clipping raster to geometry: {str(e)}")
            return False
    
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
            print(f"[DEBUG] Starting _create_temp_shapefile with geometry type: {type(geometry)}")
            print(f"[DEBUG] offset_meters type: {type(offset_meters)}, value: {offset_meters}")
            
            # Ensure offset_meters is a float
            try:
                offset_meters = float(offset_meters)
                print(f"[DEBUG] Converted offset_meters to float: {offset_meters}")
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error converting offset_meters to float: {e}, using 0.0")
                offset_meters = 0.0
            
            # Create buffered geometry if offset is specified
            if offset_meters > 0:
                buffered_geometry = geometry.buffer(offset_meters, 5)  # 5 segments for smooth buffer
                print(f"[DEBUG] Created buffered geometry: {type(buffered_geometry)}")
            else:
                buffered_geometry = geometry
                print(f"[DEBUG] Using original geometry: {type(buffered_geometry)}")
            
            print(f"[DEBUG] Checking if geometry is multipart...")
            # Ensure the polygon is explicitly closed
            if buffered_geometry.isMultipart():
                print(f"[DEBUG] Processing multipart geometry...")
                try:
                    polygons = buffered_geometry.asMultiPolygon()
                    print(f"[DEBUG] Got multipolygon data: {type(polygons)}, length: {len(polygons) if hasattr(polygons, '__len__') else 'no len'}")
                    
                    for i, poly in enumerate(polygons):
                        print(f"[DEBUG] Processing polygon {i}: {type(poly)}")
                        # Safety check: ensure poly is a list/tuple and has content
                        if isinstance(poly, (list, tuple)) and len(poly) > 0:
                            print(f"[DEBUG] Polygon {i} has {len(poly)} rings")
                            # Check if the first ring has enough points
                            if len(poly[0]) >= 2:
                                print(f"[DEBUG] Polygon {i} ring 0 has {len(poly[0])} points")
                                # Compare coordinates properly by converting to strings or using QgsPointXY methods
                                first_point = poly[0][0]
                                last_point = poly[0][-1]
                                print(f"[DEBUG] Polygon {i} - first_point type: {type(first_point)}, last_point type: {type(last_point)}")
                                if hasattr(first_point, 'x') and hasattr(last_point, 'x'):
                                    if (first_point.x() != last_point.x() or first_point.y() != last_point.y()):
                                        poly[0].append(first_point)
                                        polygons[i] = poly
                                        print(f"[DEBUG] Polygon {i} - closed the ring")
                            else:
                                print(f"[DEBUG] Polygon {i} ring 0 has insufficient points: {len(poly[0])}")
                        else:
                            print(f"[DEBUG] Polygon {i} is not a valid list/tuple or is empty")
                    
                    closed_geometry = QgsGeometry.fromMultiPolygonXY(polygons)
                    print(f"[DEBUG] Created multipolygon geometry successfully")
                except Exception as e:
                    print(f"[DEBUG] Error processing multipart geometry: {str(e)}")
                    raise
            else:
                print(f"[DEBUG] Processing single polygon...")
                try:
                    poly = buffered_geometry.asPolygon()
                    print(f"[DEBUG] Got polygon data: {type(poly)}, length: {len(poly) if hasattr(poly, '__len__') else 'no len'}")
                    
                    if isinstance(poly, (list, tuple)) and len(poly) > 0 and len(poly[0]) >= 2:
                        print(f"[DEBUG] Single polygon has {len(poly)} rings, first ring has {len(poly[0])} points")
                        first_point = poly[0][0]
                        last_point = poly[0][-1]
                        print(f"[DEBUG] Single polygon - first_point type: {type(first_point)}, last_point type: {type(last_point)}")
                        if hasattr(first_point, 'x') and hasattr(last_point, 'x'):
                            if (first_point.x() != last_point.x() or first_point.y() != last_point.y()):
                                poly[0].append(first_point)
                                print(f"[DEBUG] Single polygon - closed the ring")
                    else:
                        print(f"[DEBUG] Single polygon is not valid or has insufficient points")
                    
                    closed_geometry = QgsGeometry.fromPolygonXY(poly)
                    print(f"[DEBUG] Created single polygon geometry successfully")
                except Exception as e:
                    print(f"[DEBUG] Error processing single polygon: {str(e)}")
                    raise
            
            # Create temporary shapefile using QGIS native methods
            temp_fd, temp_path = tempfile.mkstemp(suffix='.shp', prefix='clip_')
            os.close(temp_fd)
            
            # Remove the .shp extension
            temp_base = temp_path[:-4]
            
            # Create a temporary vector layer
            from PyQt5.QtCore import QVariant
            
            # Create fields
            fields = QgsFields()
            fields.append(QgsField("id", QVariant.Int))
            
            # Create vector layer
            layer = QgsVectorLayer(f"Polygon?crs={crs.toWkt()}", "temp_clip", "memory")
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

    def _clip_raster_with_masklayer(self, raster_layer, mask_layer, output_path):
        """
        Clip raster using QGIS processing 'gdal:cliprasterbymasklayer'.
        Returns True if successful, False otherwise.
        """
        try:
            import processing
            print(f"[DEBUG] Starting QGIS processing.cliprasterbymasklayer")
            print(f"[DEBUG] Raster layer: {raster_layer.name()}, source: {raster_layer.source()}")
            print(f"[DEBUG] Raster CRS: {raster_layer.crs().description()}")
            print(f"[DEBUG] Raster extent: {raster_layer.extent().toString()}")
            print(f"[DEBUG] Mask layer: {mask_layer.name()}, feature count: {mask_layer.featureCount()}")
            print(f"[DEBUG] Mask CRS: {mask_layer.crs().description()}")
            print(f"[DEBUG] Mask extent: {mask_layer.extent().toString()}")
            
            # Get the first feature from mask layer and show its geometry details
            mask_features = list(mask_layer.getFeatures())
            if mask_features:
                feature = mask_features[0]
                geom = feature.geometry()
                print(f"[DEBUG] Mask geometry type: {geom.type()}")
                print(f"[DEBUG] Mask geometry WKT: {geom.asWkt()[:200]}...")  # First 200 chars
                print(f"[DEBUG] Mask geometry area: {geom.area()}")
                print(f"[DEBUG] Mask geometry bounds: {geom.boundingBox().toString()}")
            
            print(f"[DEBUG] Output path: {output_path}")
            
            # Try with additional parameters that might help
            params = {
                'INPUT': raster_layer,
                'MASK': mask_layer,
                'CROP_TO_CUTLINE': True,
                'KEEP_RESOLUTION': True,
                'OUTPUT': output_path,
                'NODATA': None,  # Don't set nodata
                'ALPHA_BAND': False,  # Don't create alpha band
                'CROP_TO_CUTLINE': True,
                'KEEP_RESOLUTION': True,
                'SET_RESOLUTION': False,
                'X_RESOLUTION': None,
                'Y_RESOLUTION': None,
                'MULTITHREADING': True,
                'OPTIONS': '',
                'DATA_TYPE': 0,  # Use input data type
                'EXTRA': ''
            }
            
            print(f"[DEBUG] Processing parameters: {params}")
            result = processing.run('gdal:cliprasterbymasklayer', params)
            print(f"[DEBUG] Processing result: {result}")
            
            if result and 'OUTPUT' in result:
                output_file = result['OUTPUT']
                print(f"[DEBUG] Processing returned output: {output_file}")
                
                # Check if file exists and has content
                import os
                print(f"[DEBUG] Checking if output file exists: {os.path.exists(output_file)}")
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    print(f"[DEBUG] Output file exists, size: {file_size} bytes")
                    
                    # Try to load the output as a layer to check if it's valid
                    test_layer = QgsRasterLayer(output_file, "test_clipped")
                    if test_layer.isValid():
                        print(f"[DEBUG] Output layer is valid, extent: {test_layer.extent().toString()}")
                        print(f"[DEBUG] Output layer band count: {test_layer.bandCount()}")
                        if test_layer.bandCount() > 0:
                            try:
                                stats = test_layer.dataProvider().bandStatistics(1)
                                print(f"[DEBUG] Output layer band 1 stats: min={stats.minimumValue}, max={stats.maximumValue}, mean={stats.mean}, stdDev={stats.stdDev}")
                                if stats.minimumValue == stats.maximumValue:
                                    print(f"[DEBUG] WARNING: All pixel values are the same ({stats.minimumValue}) - likely black or white")
                                elif stats.minimumValue == 0 and stats.maximumValue == 0:
                                    print(f"[DEBUG] WARNING: All pixel values are 0 - completely black")
                                else:
                                    print(f"[DEBUG] Output appears to have valid data range")
                            except Exception as stats_error:
                                print(f"[DEBUG] Could not get band statistics: {stats_error}")
                    else:
                        print(f"[DEBUG] Output layer is NOT valid: {test_layer.error().summary()}")
                    
                    if file_size > 1000:  # More than 1KB
                        print(f"[DEBUG] QGIS processing.cliprasterbymasklayer succeeded: {output_file}")
                        return True
                    else:
                        print(f"[DEBUG] QGIS processing.cliprasterbymasklayer produced small file: {output_file}")
                        return False
                else:
                    print(f"[DEBUG] QGIS processing.cliprasterbymasklayer did not create output file")
                    print(f"[DEBUG] Expected file path: {output_file}")
                    print(f"[DEBUG] Directory exists: {os.path.exists(os.path.dirname(output_file))}")
                    return False
            else:
                print(f"[DEBUG] QGIS processing.cliprasterbymasklayer did not produce output: {result}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] QGIS processing.cliprasterbymasklayer failed: {str(e)}")
            return False

    def _clip_raster_with_warp(self, raster_layer, mask_layer, output_path):
        """
        Alternative clipping method using gdal:warpreproject with mask.
        Returns True if successful, False otherwise.
        """
        try:
            import processing
            print(f"[DEBUG] Trying alternative clipping with gdal:warpreproject")
            
            # Create a temporary mask file
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.shp', delete=False) as tmp_file:
                temp_mask_path = tmp_file.name
            
            # Save mask layer to temporary shapefile
            error = QgsVectorFileWriter.writeAsVectorFormat(
                mask_layer, temp_mask_path, "UTF-8", mask_layer.crs(), "ESRI Shapefile"
            )
            
            if error[0] != QgsVectorFileWriter.NoError:
                print(f"[DEBUG] Failed to save temporary mask: {error}")
                os.unlink(temp_mask_path)
                return False
            
            # Try warping with mask
            params = {
                'INPUT': raster_layer,
                'SOURCE_CRS': raster_layer.crs(),
                'TARGET_CRS': raster_layer.crs(),  # Same CRS
                'RESAMPLING': 0,  # Nearest neighbor
                'NODATA': None,
                'TARGET_RESOLUTION': None,
                'OPTIONS': '',
                'DATA_TYPE': 0,
                'TARGET_EXTENT': mask_layer.extent(),
                'TARGET_EXTENT_CRS': mask_layer.crs(),
                'MULTITHREADING': True,
                'EXTRA': f'-cutline {temp_mask_path} -crop_to_cutline',
                'OUTPUT': output_path
            }
            
            print(f"[DEBUG] Warp parameters: {params}")
            result = processing.run('gdal:warpreproject', params)
            print(f"[DEBUG] Warp result: {result}")
            
            # Clean up temporary file
            try:
                os.unlink(temp_mask_path)
            except:
                pass
            
            if result and 'OUTPUT' in result:
                output_file = result['OUTPUT']
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    print(f"[DEBUG] Alternative warping succeeded: {output_file}")
                    
                    # Add detailed output validation
                    print(f"[DEBUG] Validating warped output file...")
                    test_layer = QgsRasterLayer(output_file, "test_warped")
                    if test_layer.isValid():
                        print(f"[DEBUG] Warped output layer is valid, extent: {test_layer.extent().toString()}")
                        print(f"[DEBUG] Warped output layer band count: {test_layer.bandCount()}")
                        if test_layer.bandCount() > 0:
                            try:
                                stats = test_layer.dataProvider().bandStatistics(1)
                                print(f"[DEBUG] Warped output band 1 stats: min={stats.minimumValue}, max={stats.maximumValue}, mean={stats.mean}, stdDev={stats.stdDev}")
                                if stats.minimumValue == stats.maximumValue:
                                    print(f"[DEBUG] WARNING: All pixel values are the same ({stats.minimumValue}) - likely black or white")
                                elif stats.minimumValue == 0 and stats.maximumValue == 0:
                                    print(f"[DEBUG] WARNING: All pixel values are 0 - completely black")
                                    print(f"[DEBUG] Warping produced black output - trying next method")
                                    return False
                                else:
                                    print(f"[DEBUG] Warped output appears to have valid data range")
                            except Exception as stats_error:
                                print(f"[DEBUG] Could not get warped output band statistics: {stats_error}")
                    else:
                        print(f"[DEBUG] Warped output layer is NOT valid: {test_layer.error().summary()}")
                    
                    return True
                else:
                    print(f"[DEBUG] Warped output file is too small or doesn't exist: {output_file}")
                    if os.path.exists(output_file):
                        print(f"[DEBUG] Warped output file size: {os.path.getsize(output_file)} bytes")
                    return False
            else:
                print(f"[DEBUG] Warp processing did not produce valid output: {result}")
                return False
            
        except Exception as e:
            print(f"[DEBUG] Alternative warping failed: {str(e)}")
            return False

    def _clip_raster_with_extent(self, raster_layer, mask_layer, output_path):
        """
        Alternative clipping method using gdal:cliprasterbyextent.
        Returns True if successful, False otherwise.
        """
        try:
            import processing
            print(f"[DEBUG] Trying alternative clipping with gdal:cliprasterbyextent")
            
            # Get the extent from the mask layer
            mask_extent = mask_layer.extent()
            print(f"[DEBUG] Using mask extent for clipping: {mask_extent.toString()}")
            
            # Try clipping by extent
            params = {
                'INPUT': raster_layer,
                'PROJWIN': f"{mask_extent.xMinimum()},{mask_extent.xMaximum()},{mask_extent.yMinimum()},{mask_extent.yMaximum()}",
                'NODATA': None,
                'OPTIONS': '',
                'DATA_TYPE': 0,
                'OUTPUT': output_path
            }
            
            print(f"[DEBUG] Extent clipping parameters: {params}")
            result = processing.run('gdal:cliprasterbyextent', params)
            print(f"[DEBUG] Extent clipping result: {result}")
            
            if result and 'OUTPUT' in result:
                output_file = result['OUTPUT']
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    print(f"[DEBUG] Extent clipping succeeded: {output_file}")
                    
                    # Add detailed output validation
                    print(f"[DEBUG] Validating extent-clipped output file...")
                    test_layer = QgsRasterLayer(output_file, "test_extent_clipped")
                    if test_layer.isValid():
                        print(f"[DEBUG] Extent-clipped output layer is valid, extent: {test_layer.extent().toString()}")
                        print(f"[DEBUG] Extent-clipped output layer band count: {test_layer.bandCount()}")
                        if test_layer.bandCount() > 0:
                            try:
                                stats = test_layer.dataProvider().bandStatistics(1)
                                print(f"[DEBUG] Extent-clipped output band 1 stats: min={stats.minimumValue}, max={stats.maximumValue}, mean={stats.mean}, stdDev={stats.stdDev}")
                                if stats.minimumValue == stats.maximumValue:
                                    print(f"[DEBUG] WARNING: All pixel values are the same ({stats.minimumValue}) - likely black or white")
                                elif stats.minimumValue == 0 and stats.maximumValue == 0:
                                    print(f"[DEBUG] WARNING: All pixel values are 0 - completely black")
                                else:
                                    print(f"[DEBUG] Extent-clipped output appears to have valid data range")
                            except Exception as stats_error:
                                print(f"[DEBUG] Could not get extent-clipped output band statistics: {stats_error}")
                    else:
                        print(f"[DEBUG] Extent-clipped output layer is NOT valid: {test_layer.error().summary()}")
                    
                    return True
                else:
                    print(f"[DEBUG] Extent-clipped output file is too small or doesn't exist: {output_file}")
                    if os.path.exists(output_file):
                        print(f"[DEBUG] Extent-clipped output file size: {os.path.getsize(output_file)} bytes")
                    return False
            else:
                print(f"[DEBUG] Extent clipping did not produce valid output: {result}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] Extent clipping failed: {str(e)}")
            return False

    def _get_crs_string(self, crs):
        """Get CRS string representation, handling custom CRS properly."""
        try:
            # Try to get authid first
            authid = crs.authid()
            if authid and authid != '':
                return authid
            
            # For custom CRS, use WKT
            wkt = crs.toWkt()
            if wkt and wkt != '':
                return wkt
            
            # Fallback to proj4 string
            proj4 = crs.toProj4()
            if proj4 and proj4 != '':
                return proj4
            
            # Last resort - use EPSG:4326
            print("Warning: Could not determine CRS, using EPSG:4326 as fallback")
            return "EPSG:4326"
        except Exception as e:
            print(f"Error getting CRS string: {str(e)}, using EPSG:4326 as fallback")
            return "EPSG:4326"

    def _clip_raster_with_gdal_command(self, raster_layer, geometry, output_path):
        """
        Clip raster using direct GDAL command approach (similar to working manual command).
        This method creates a temporary shapefile and uses gdalwarp with the exact same
        CRS for source and target, matching the working manual command.
        
        Args:
            raster_layer: QgsRasterLayer to clip
            geometry: QgsGeometry to use as clipping mask
            output_path: Path for output raster
            
        Returns:
            str: Path to clipped raster if successful, None otherwise
        """
        try:
            print(f"[DEBUG] Starting direct GDAL command clipping")
            print(f"[DEBUG] Raster source: {raster_layer.source()}")
            print(f"[DEBUG] Raster CRS: {raster_layer.crs().description()}")
            print(f"[DEBUG] Output path: {output_path}")
            
            # Get raster CRS WKT (same as working command)
            raster_crs_wkt = raster_layer.crs().toWkt()
            print(f"[DEBUG] Raster CRS WKT (full): {raster_crs_wkt}")
            
            # Create temporary shapefile from geometry
            temp_shapefile = self._create_temp_shapefile_from_geometry(geometry, raster_layer.crs())
            if not temp_shapefile:
                print(f"[DEBUG] Failed to create temporary shapefile")
                return None
            prj_path = f"{temp_shapefile}.prj"
            shp_path = f"{temp_shapefile}.shp"
            print(f"[DEBUG] Temp shapefile: {shp_path}")
            print(f"[DEBUG] Temp .prj file: {prj_path}")
            print(f"[DEBUG] .shp exists: {os.path.exists(shp_path)}")
            print(f"[DEBUG] .prj exists: {os.path.exists(prj_path)}")
            if os.path.exists(prj_path):
                with open(prj_path, 'r') as f:
                    prj_contents = f.read()
                print(f"[DEBUG] .prj file contents:\n{prj_contents}")
            
            try:
                # Get gdalwarp path
                gdalwarp_path = self._get_gdal_tool_path('gdalwarp')
                if not gdalwarp_path:
                    print(f"[DEBUG] gdalwarp not found")
                    return None
                
                # Build command similar to working manual command
                # For custom CRS like affine projections, use WKT format without extra quotes
                cmd = [
                    gdalwarp_path,
                    '-overwrite',
                    '-s_srs', raster_crs_wkt,
                    '-t_srs', raster_crs_wkt,
                    '-of', 'GTiff',
                    '-cutline', f"{temp_shapefile}.shp",
                    '-crop_to_cutline',
                    '-dstalpha',
                    raster_layer.source(),
                    output_path
                ]
                
                print(f"[DEBUG] GDAL command: {' '.join(cmd)}")
                print(f"[DEBUG] (copy-paste this command to test manually)")
                
                # Also print a shell-ready version with proper quoting
                shell_cmd = f'gdalwarp -overwrite -s_srs "{raster_crs_wkt}" -t_srs "{raster_crs_wkt}" -of GTiff -cutline "{temp_shapefile}.shp" -crop_to_cutline -dstalpha "{raster_layer.source()}" "{output_path}"'
                print(f"[DEBUG] Shell-ready command (copy-paste this):")
                print(f"[DEBUG] {shell_cmd}")
                
                # Execute command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=300  # 5 minute timeout
                )
                
                print(f"[DEBUG] GDAL command return code: {result.returncode}")
                print(f"[DEBUG] GDAL stdout (full):\n{result.stdout}")
                print(f"[DEBUG] GDAL stderr (full):\n{result.stderr}")
                
                if result.returncode != 0:
                    print(f"[DEBUG] GDAL command failed with return code {result.returncode}")
                    return None
                
                # Check if output file was created and has content
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"[DEBUG] Output file created, size: {file_size} bytes")
                    
                    if file_size > 1000:  # More than 1KB
                        # Validate the output
                        test_layer = QgsRasterLayer(output_path, "test_gdal_clipped")
                        if test_layer.isValid():
                            print(f"[DEBUG] GDAL-clipped output is valid, extent: {test_layer.extent().toString()}")
                            print(f"[DEBUG] GDAL-clipped output band count: {test_layer.bandCount()}")
                            
                            if test_layer.bandCount() > 0:
                                try:
                                    stats = test_layer.dataProvider().bandStatistics(1)
                                    print(f"[DEBUG] GDAL-clipped output band 1 stats: min={stats.minimumValue}, max={stats.maximumValue}, mean={stats.mean}, stdDev={stats.stdDev}")
                                    if stats.minimumValue == stats.maximumValue:
                                        print(f"[DEBUG] WARNING: All pixel values are the same ({stats.minimumValue})")
                                    elif stats.minimumValue == 0 and stats.maximumValue == 0:
                                        print(f"[DEBUG] WARNING: All pixel values are 0 - completely black")
                                        return None
                                    else:
                                        print(f"[DEBUG] GDAL-clipped output has valid data range")
                                        return output_path
                                except Exception as stats_error:
                                    print(f"[DEBUG] Could not get GDAL-clipped output band statistics: {stats_error}")
                                    return output_path
                            else:
                                print(f"[DEBUG] GDAL-clipped output has no bands")
                                return None
                        else:
                            print(f"[DEBUG] GDAL-clipped output is NOT valid: {test_layer.error().summary()}")
                            return None
                    else:
                        print(f"[DEBUG] Output file is too small: {file_size} bytes")
                        return None
                else:
                    print(f"[DEBUG] Output file was not created")
                    return None
                    
            finally:
                # Clean up temporary shapefile
                self._cleanup_temp_shapefile(temp_shapefile)
                
        except subprocess.TimeoutExpired:
            print(f"[DEBUG] GDAL command timed out")
            return None
        except Exception as e:
            print(f"[DEBUG] Error in direct GDAL command clipping: {str(e)}")
            return None

    def _create_temp_shapefile_from_geometry(self, geometry, crs):
        """
        Create a temporary shapefile from a QgsGeometry with the specified CRS.
        
        Args:
            geometry: QgsGeometry to save
            crs: QgsCoordinateReferenceSystem for the shapefile
            
        Returns:
            str: Path to temporary shapefile (without .shp extension) or None if failed
        """
        try:
            # Create temporary file path
            temp_fd, temp_path = tempfile.mkstemp(suffix='.shp', prefix='temp_clip_')
            os.close(temp_fd)
            temp_path = temp_path[:-4]  # Remove .shp extension
            
            print(f"[DEBUG] Creating temporary shapefile: {temp_path}")
            
            # Create fields
            from PyQt5.QtCore import QVariant
            fields = QgsFields()
            fields.append(QgsField("id", QVariant.Int))
            
            # Create vector layer
            layer = QgsVectorLayer(f"Polygon?crs={crs.toWkt()}", "temp_clip", "memory")
            layer.dataProvider().addAttributes(fields)
            layer.updateFields()
            
            # Create feature
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([1])
            
            # Add feature to layer
            layer.dataProvider().addFeatures([feature])
            layer.updateExtents()
            
            # Save to shapefile
            error = QgsVectorFileWriter.writeAsVectorFormat(
                layer, temp_path, "UTF-8", crs, "ESRI Shapefile"
            )
            
            if error[0] != QgsVectorFileWriter.NoError:
                print(f"[DEBUG] Failed to save shapefile: {error}")
                return None
            
            # Overwrite the .prj file with the exact WKT from the raster to ensure CRS match
            prj_path = f"{temp_path}.prj"
            try:
                with open(prj_path, 'w') as f:
                    f.write(crs.toWkt())
                print(f"[DEBUG] Overwrote .prj file with exact raster WKT")
            except Exception as e:
                print(f"[DEBUG] Warning: Could not overwrite .prj file: {e}")
            
            print(f"[DEBUG] Successfully created temporary shapefile: {temp_path}.shp")
            return temp_path
            
        except Exception as e:
            print(f"[DEBUG] Error creating temporary shapefile: {str(e)}")
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