"""
Project creation service implementation for ArcheoSync plugin.

This module provides a service for creating QGIS projects for field work,
replacing the QField dependency with direct QGIS project creation.

Key Features:
- Create QGIS projects (.qgs) for selected recording areas
- Copy layers as Geopackage files with preserved styling and forms
- Filter layers to contain only relevant data for each recording area
- Create clipped background raster layers
- Set project variables for field preparation
- Handle layer relationships and data filtering

Usage:
    project_service = QGISProjectCreationService(
        settings_manager, layer_service, file_system_service, raster_processing_service
    )
    
    success = project_service.create_field_project(
        feature_data=feature_info,
        recording_areas_layer_id='layer_id',
        objects_layer_id='objects_layer_id',
        features_layer_id='features_layer_id',
        background_layer_id='background_layer_id',
        extra_layers=['extra_layer_1', 'extra_layer_2'],
        destination_folder='/path/to/destination',
        project_name='Recording_Area_1',
        next_values={'first_number': '1', 'level': 'A1'}
    )

The service provides:
- Automatic folder creation with proper naming
- QGIS project file creation
- Layer copying as Geopackage files
- Data filtering based on recording area relationships
- Background raster clipping and integration
- Project variable injection
- Comprehensive error handling
"""

import os
import re
from typing import Optional, Any, Dict, List
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry, QgsWkbTypes, QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsBookmark, QgsReferencedRectangle
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QObject

try:
    from ..core.interfaces import ISettingsManager, ILayerService, IFileSystemService, IRasterProcessingService
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService, IFileSystemService, IRasterProcessingService


class QGISProjectCreationService(QObject):
    """
    QGIS-specific implementation for creating field projects.
    
    This service creates QGIS projects for field work by:
    1. Creating a new folder for each recording area
    2. Creating a QGIS project file (.qgs)
    3. Copying layers as Geopackage files with data filtering
    4. Adding clipped background raster layers
    5. Setting project variables for field preparation
    """
    
    def __init__(self, settings_manager: ISettingsManager, layer_service: ILayerService, file_system_service: IFileSystemService, raster_processing_service: IRasterProcessingService):
        QObject.__init__(self)
        """
        Initialize the project creation service.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            file_system_service: Service for file system operations
            raster_processing_service: Service for raster processing operations
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._file_system_service = file_system_service
        self._raster_processing_service = raster_processing_service
    
    def create_field_project(self,
                           feature_data: Dict[str, Any],
                           recording_areas_layer_id: str,
                           objects_layer_id: str,
                           features_layer_id: Optional[str],
                           small_finds_layer_id: Optional[str],
                           background_layer_id: Optional[str],
                           extra_layers: Optional[List[str]] = None,
                           destination_folder: str = "",
                           project_name: str = "",
                           next_values: Dict[str, str] = None) -> bool:
        """
        Create a QGIS field project for a specific recording area.
        
        Args:
            feature_data: Dictionary containing feature data (id, geometry_wkt, attributes, display_name)
            recording_areas_layer_id: ID of the recording areas layer
            objects_layer_id: ID of the objects layer
            features_layer_id: ID of the features layer (optional)
            background_layer_id: ID of the background image layer (optional)
            extra_layers: List of additional layer IDs to include (optional)
            destination_folder: Folder where to save the field project
            project_name: Name for the field project
            next_values: Dictionary containing first_number, level values (optional)
            
        Returns:
            True if project creation was successful, False otherwise
        """
        try:
            if not feature_data or not recording_areas_layer_id or not objects_layer_id:
                raise ValueError("Required parameters are missing")
            if not destination_folder or not project_name:
                raise ValueError("Destination folder and project name are required")

            # Create project directory
            project_dir = os.path.join(destination_folder, project_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            # Create a new QGIS project
            project = QgsProject()
            
            # Set project CRS to match the recording areas layer
            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_layer:
                project.setCrs(recording_layer.crs())
                print(f"Set project CRS to: {self._get_crs_string(recording_layer.crs())}")

            # Process background raster first (so it appears at the bottom of the layer tree)
            if background_layer_id:
                raster_offset = self._settings_manager.get_value('raster_clipping_offset', 0.0)
                success = self._create_clipped_raster(
                    raster_layer_id=background_layer_id,
                    recording_area_geometry=feature_data['geometry_wkt'],
                    output_path=os.path.join(project_dir, "background.tif"),
                    project=project,
                    offset_meters=raster_offset
                )
                if not success:
                    print(f"Warning: Failed to create clipped background raster")

            # Create recording areas layer with only the selected feature
            recording_layer_info = self._layer_service.get_layer_info(recording_areas_layer_id)
            recording_layer_name = recording_layer_info['name'] if recording_layer_info else "Recording Areas"
            recording_gpkg_path = os.path.join(project_dir, f"{recording_layer_name}.gpkg")
            success = self._create_filtered_layer(
                source_layer_id=recording_areas_layer_id,
                output_path=recording_gpkg_path,
                layer_name=recording_layer_name,
                filter_expression=f"id = {feature_data['id']}",
                project=project
            )
            if not success:
                raise RuntimeError(f"Failed to create recording areas layer: {recording_gpkg_path}")

            # Create objects layer (empty)
            objects_layer_info = self._layer_service.get_layer_info(objects_layer_id)
            objects_layer_name = objects_layer_info['name'] if objects_layer_info else "Objects"
            objects_gpkg_path = os.path.join(project_dir, f"{objects_layer_name}.gpkg")
            success = self._create_empty_layer_copy(
                source_layer_id=objects_layer_id,
                output_path=objects_gpkg_path,
                layer_name=objects_layer_name,
                project=project
            )
            if not success:
                raise RuntimeError(f"Failed to create objects layer: {objects_gpkg_path}")

            # Create features layer (empty) if configured
            if features_layer_id:
                features_layer_info = self._layer_service.get_layer_info(features_layer_id)
                features_layer_name = features_layer_info['name'] if features_layer_info else "Features"
                features_gpkg_path = os.path.join(project_dir, f"{features_layer_name}.gpkg")
                success = self._create_empty_layer_copy(
                    source_layer_id=features_layer_id,
                    output_path=features_gpkg_path,
                    layer_name=features_layer_name,
                    project=project
                )
                if not success:
                    raise RuntimeError(f"Failed to create features layer: {features_gpkg_path}")

            # Create small finds layer (empty) if configured
            if small_finds_layer_id:
                small_finds_layer_info = self._layer_service.get_layer_info(small_finds_layer_id)
                default_name = "Small Finds"
                small_finds_layer_name = small_finds_layer_info['name'] if small_finds_layer_info else default_name
                small_finds_gpkg_path = os.path.join(project_dir, f"{small_finds_layer_name}.gpkg")
                success = self._create_empty_layer_copy(
                    source_layer_id=small_finds_layer_id,
                    output_path=small_finds_gpkg_path,
                    layer_name=small_finds_layer_name,
                    project=project
                )
                if not success:
                    raise RuntimeError(f"Failed to create small finds layer: {small_finds_gpkg_path}")

            # Process extra layers
            if extra_layers:
                for layer_id in extra_layers:
                    if layer_id != recording_areas_layer_id:  # Skip recording areas layer
                        layer_info = self._layer_service.get_layer_info(layer_id)
                        if layer_info:
                            layer_name = layer_info['name']
                            print(f"[DEBUG] Processing extra layer: {layer_name} (ID: {layer_id})")
                            # Check if layer has relationship with recording areas
                            if self._has_relationship_with_recording_areas(layer_id, recording_areas_layer_id):
                                print(f"[DEBUG] Layer {layer_name} has relationship - will filter")
                                # Filter to only related features
                                filter_expression = self._get_relationship_filter_expression(layer_id, recording_areas_layer_id, feature_data['id'])
                                if filter_expression:
                                    success = self._create_filtered_layer(
                                        source_layer_id=layer_id,
                                        output_path=os.path.join(project_dir, f"{layer_name}.gpkg"),
                                        layer_name=layer_name,
                                        filter_expression=filter_expression,
                                        project=project
                                    )
                                else:
                                    print(f"[DEBUG] No filter expression found for {layer_name} - copying all features")
                                    # Fallback to copying all features if no specific filter expression found
                                    success = self._create_layer_copy(
                                        source_layer_id=layer_id,
                                        output_path=os.path.join(project_dir, f"{layer_name}.gpkg"),
                                        layer_name=layer_name,
                                        project=project
                                    )
                            else:
                                print(f"[DEBUG] Layer {layer_name} has no relationship - copying all features")
                                # Copy all features
                                success = self._create_layer_copy(
                                    source_layer_id=layer_id,
                                    output_path=os.path.join(project_dir, f"{layer_name}.gpkg"),
                                    layer_name=layer_name,
                                    project=project
                                )
                            if not success:
                                print(f"Warning: Failed to process extra layer {layer_name}")

            # Set project variables
            if next_values:
                self._set_project_variables(project, next_values, feature_data['display_name'])

            # Create bookmark for recording area
            self._create_recording_area_bookmark(project, feature_data, feature_data['display_name'])

            # Ensure all layers are properly refreshed before saving
            print("[DEBUG] Refreshing all layers before saving project")
            for layer in project.mapLayers().values():
                if hasattr(layer, 'triggerRepaint'):
                    layer.triggerRepaint()
                if hasattr(layer, 'updateExtents'):
                    layer.updateExtents()

            # Save the project
            project_path = os.path.join(project_dir, f"{project_name}.qgs")
            print(f"[DEBUG] Saving project to: {project_path}")
            success = project.write(project_path)
            if not success:
                raise RuntimeError(f"Failed to save project: {project_path}")

            print(f"Successfully created field project: {project_path}")
            return True

        except Exception as e:
            print(f"Error creating field project: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _create_filtered_layer(self, source_layer_id: str, output_path: str, layer_name: str, 
                             filter_expression: str, project: QgsProject) -> bool:
        """Create a filtered copy of a layer."""
        try:
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer:
                return False

            # Apply filter
            source_layer.setSubsetString(filter_expression)

            # Debug output - count features manually to get accurate count
            filtered_count = 0
            for feature in source_layer.getFeatures():
                filtered_count += 1
            print(f"[DEBUG] Filtering layer '{layer_name}' with expression: {filter_expression}")
            print(f"[DEBUG] Number of features after filtering: {filtered_count}")
            
            # Copy layer
            success = self._copy_layer_to_geopackage(source_layer, output_path, layer_name)
            
            # Reset filter
            source_layer.setSubsetString("")
            
            if success:
                # Add to project
                layer = QgsVectorLayer(output_path, layer_name, "ogr")
                if layer.isValid():
                    # Force the layer to reload its style
                    layer.triggerRepaint()
                    project.addMapLayer(layer)
                    return True
            
            return False
        except Exception as e:
            print(f"Error creating filtered layer: {str(e)}")
            return False

    def _create_empty_layer_copy(self, source_layer_id: str, output_path: str, layer_name: str, 
                                project: QgsProject) -> bool:
        """Create an empty copy of a layer with the same structure."""
        try:
            print(f"[DEBUG] _create_empty_layer_copy called for layer: {layer_name}")
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer:
                print(f"[DEBUG] Could not get source layer for ID: {source_layer_id}")
                return False

            print(f"[DEBUG] Source layer has {source_layer.fields().count()} fields")
            # Create empty layer with same structure
            success = self._copy_layer_structure_to_geopackage(source_layer, output_path, layer_name)
            
            if success:
                # Add to project
                layer = QgsVectorLayer(output_path, layer_name, "ogr")
                if layer.isValid():
                    # Force the layer to reload its style
                    layer.triggerRepaint()
                    project.addMapLayer(layer)
                    return True
            
            return False
        except Exception as e:
            print(f"[DEBUG] Exception in _create_empty_layer_copy: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _create_layer_copy(self, source_layer_id: str, output_path: str, layer_name: str, 
                          project: QgsProject) -> bool:
        """Create a complete copy of a layer."""
        try:
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer:
                return False

            # Copy layer
            success = self._copy_layer_to_geopackage(source_layer, output_path, layer_name)
            
            if success:
                # Add to project
                layer = QgsVectorLayer(output_path, layer_name, "ogr")
                if layer.isValid():
                    # Force the layer to reload its style
                    layer.triggerRepaint()
                    project.addMapLayer(layer)
                    return True
            
            return False
        except Exception as e:
            print(f"Error creating layer copy: {str(e)}")
            return False

    def _copy_layer_to_geopackage(self, source_layer, output_path, layer_name):
        """Copy a layer to a Geopackage file with preserved forms, styles, and field configurations."""
        try:
            print(f"[DEBUG] _copy_layer_to_geopackage called for layer: {layer_name}")
            from qgis.core import QgsVectorFileWriter
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name

            # Try V2 API if available and compatible
            if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV2"):
                try:
                    error = QgsVectorFileWriter.writeAsVectorFormatV2(source_layer, output_path, options)
                    if error[0] != QgsVectorFileWriter.NoError:
                        print(f"Error writing layer to Geopackage: {error[1]}")
                        return False
                    
                    # After successful data copy, copy forms, styles, and field configurations
                    self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
                    return True
                except TypeError:
                    # Fallback to classic API
                    pass

            # Classic API (older QGIS)
            error = QgsVectorFileWriter.writeAsVectorFormat(
                source_layer, output_path, "UTF-8", source_layer.crs(), "GPKG", False, ["layerName=" + layer_name]
            )
            # Accept both int and tuple return types
            if (isinstance(error, int) and error != QgsVectorFileWriter.NoError) or \
               (isinstance(error, tuple) and error[0] != QgsVectorFileWriter.NoError):
                print(f"Error writing layer to Geopackage (classic): {error}")
                return False
            
            # After successful data copy, copy forms, styles, and field configurations
            self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
            return True
        except Exception as e:
            print(f"Error copying layer to Geopackage: {str(e)}")
            return False

    def _copy_layer_structure_to_geopackage(self, source_layer, output_path, layer_name):
        """Copy only the structure of a layer to a Geopackage file (no features) with preserved forms and styles."""
        try:
            print(f"[DEBUG] _copy_layer_structure_to_geopackage called for layer: {layer_name}")
            from qgis.core import QgsVectorFileWriter, QgsWkbTypes
            # Determine geometry type from source layer
            geom_type = source_layer.geometryType()
            if geom_type == QgsWkbTypes.PolygonGeometry:
                geom_string = "Polygon"
            elif geom_type == QgsWkbTypes.LineGeometry:
                geom_string = "LineString"
            else:
                geom_string = "Point"
            
            # Handle custom CRS properly
            crs_string = self._get_crs_string(source_layer.crs())
            temp_layer = QgsVectorLayer(f"{geom_string}?crs={crs_string}", "temp", "memory")
            
            # Copy all fields (including virtual fields)
            temp_layer.startEditing()
            for field in source_layer.fields():
                temp_layer.addAttribute(field)
            temp_layer.commitChanges()

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name

            # Try V2 API if available and compatible
            if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV2"):
                try:
                    error = QgsVectorFileWriter.writeAsVectorFormatV2(temp_layer, output_path, options)
                    if error[0] != QgsVectorFileWriter.NoError:
                        print(f"Error writing layer structure to Geopackage: {error[1]}")
                        return False
                    
                    # After successful structure copy, copy forms, styles, and field configurations
                    self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
                    return True
                except TypeError:
                    # Fallback to classic API
                    pass

            # Classic API (older QGIS)
            error = QgsVectorFileWriter.writeAsVectorFormat(
                temp_layer, output_path, "UTF-8", source_layer.crs(), "GPKG", False, ["layerName=" + layer_name]
            )
            # Accept both int and tuple return types
            if (isinstance(error, int) and error != QgsVectorFileWriter.NoError) or \
               (isinstance(error, tuple) and error[0] != QgsVectorFileWriter.NoError):
                print(f"Error writing layer structure to Geopackage (classic): {error}")
                return False
            
            # After successful structure copy, copy forms, styles, and field configurations
            self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
            return True
        except Exception as e:
            print(f"[DEBUG] Exception in _copy_layer_structure_to_geopackage: {str(e)}")
            import traceback
            traceback.print_exc()
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

    def _copy_layer_properties_to_geopackage(self, source_layer, output_path, layer_name):
        """Copy forms, styles, and field configurations to the Geopackage layer."""
        try:
            # Load the target layer from the Geopackage
            target_layer = QgsVectorLayer(output_path, layer_name, "ogr")
            if not target_layer.isValid():
                print(f"Warning: Could not load target layer for property copying: {output_path}")
                return False
            
            print(f"[DEBUG] Copying properties from {source_layer.name()} to {target_layer.name()}")
            print(f"[DEBUG] Source layer style URI: {source_layer.styleURI()}")
            print(f"[DEBUG] Target layer style URI: {target_layer.styleURI()}")
            
            # Copy layer properties using the layer service methods
            self._layer_service._copy_layer_properties(source_layer, target_layer)
            
            # Try to copy QML style
            qml_success = self._layer_service._copy_qml_style(source_layer, target_layer)
            
            # If QML style copying failed, use renderer fallback
            if not qml_success:
                print(f"QML style copying failed for {layer_name}, using renderer clone as fallback")
                self._layer_service._copy_renderer_fallback(source_layer, target_layer)
            
            # Force the layer to save its style to the Geopackage
            try:
                # Try to save the style directly to the Geopackage
                # Use a more robust approach for Geopackage style saving
                style_result = target_layer.saveStyleToDatabase(layer_name, "", True, "")
                if style_result[0]:
                    print(f"[DEBUG] Successfully saved style to Geopackage database for {layer_name}")
                else:
                    print(f"[DEBUG] Failed to save style to Geopackage database for {layer_name}: {style_result[1]}")
                    # Try alternative approach
                    try:
                        # Save as QML and then load it back
                        temp_qml = target_layer.saveNamedStyle("")
                        if temp_qml[0]:
                            target_layer.loadNamedStyle(temp_qml[1])
                            print(f"[DEBUG] Used alternative style saving method for {layer_name}")
                    except Exception as alt_e:
                        print(f"[DEBUG] Alternative style saving also failed: {str(alt_e)}")
            except Exception as e:
                print(f"[DEBUG] Error saving style to Geopackage database: {str(e)}")
                # Try alternative approach
                try:
                    # Save as QML and then load it back
                    temp_qml = target_layer.saveNamedStyle("")
                    if temp_qml[0]:
                        target_layer.loadNamedStyle(temp_qml[1])
                        print(f"[DEBUG] Used alternative style saving method for {layer_name}")
                except Exception as alt_e:
                    print(f"[DEBUG] Alternative style saving also failed: {str(alt_e)}")
            
            # Also try to save the style as a QML file in the same directory as the Geopackage
            try:
                import os
                qml_path = os.path.splitext(output_path)[0] + ".qml"
                if target_layer.saveNamedStyle(qml_path)[0]:
                    print(f"[DEBUG] Saved QML style file: {qml_path}")
                else:
                    print(f"[DEBUG] Failed to save QML style file: {qml_path}")
            except Exception as e:
                print(f"[DEBUG] Error saving QML style file: {str(e)}")
            
            print(f"Successfully copied forms, styles, and field configurations to {layer_name}")
            return True
            
        except Exception as e:
            print(f"Error copying layer properties to Geopackage: {str(e)}")
            return False

    def _has_relationship_with_recording_areas(self, layer_id: str, recording_areas_layer_id: str) -> bool:
        """Check if a layer has a relationship with the recording areas layer using QGIS relations."""
        try:
            from qgis.core import QgsProject
            
            # Get QGIS project and relation manager
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            # Check for relations where the extra layer references the recording areas layer
            for relation in relation_manager.relations().values():
                if (relation.referencingLayerId() == layer_id and 
                    relation.referencedLayerId() == recording_areas_layer_id):
                    print(f"[DEBUG] Found relationship: {relation.referencingLayerId()} -> {relation.referencedLayerId()}")
                    return True
            
            print(f"[DEBUG] No relationship found for layer {layer_id} with recording areas layer {recording_areas_layer_id}")
            return False
        except Exception as e:
            print(f"Error checking layer relationship: {str(e)}")
            return False

    def _get_relationship_filter_expression(self, layer_id: str, recording_areas_layer_id: str, 
                                          selected_feature_id: int) -> Optional[str]:
        """Get the filter expression for filtering related features based on QGIS relations."""
        try:
            from qgis.core import QgsProject
            
            # Get QGIS project and relation manager
            project = QgsProject.instance()
            relation_manager = project.relationManager()
            
            # Get the recording area layer and the selected feature
            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if not recording_layer:
                print(f"[DEBUG] Recording area layer not found: {recording_areas_layer_id}")
                return None
            
            # Find the selected feature
            selected_feature = None
            for feature in recording_layer.getFeatures():
                if feature.id() == selected_feature_id:
                    selected_feature = feature
                    break
            
            if not selected_feature:
                print(f"[DEBUG] Selected feature not found: {selected_feature_id}")
                return None
            
            # Find the relation where the extra layer references the recording areas layer
            for relation in relation_manager.relations().values():
                if (relation.referencingLayerId() == layer_id and 
                    relation.referencedLayerId() == recording_areas_layer_id):
                    
                    # Get the field pairs for this relation
                    field_pairs = relation.fieldPairs()
                    if field_pairs:
                        # Get the referencing field (the field in the extra layer that references recording areas)
                        referencing_field = list(field_pairs.keys())[0]
                        # Get the referenced field (the field in the recording areas layer)
                        referenced_field = list(field_pairs.values())[0]
                        
                        # Get the value from the referenced field in the selected feature
                        field_idx = recording_layer.fields().indexOf(referenced_field)
                        if field_idx >= 0:
                            referenced_value = selected_feature.attribute(field_idx)
                            print(f"[DEBUG] Using field '{referenced_field}' with value '{referenced_value}' for filtering")
                            filter_expr = f'"{referencing_field}" = \'{referenced_value}\''
                            print(f"[DEBUG] Generated filter expression: {filter_expr}")
                            return filter_expr
                        else:
                            print(f"[DEBUG] Referenced field '{referenced_field}' not found in recording area layer")
            
            print(f"[DEBUG] No filter expression generated for layer {layer_id}")
            return None
        except Exception as e:
            print(f"Error getting relationship filter expression: {str(e)}")
            return None

    def _create_clipped_raster(self, raster_layer_id: str, recording_area_geometry: str, 
                              output_path: str, project: QgsProject, offset_meters: float = 0.0) -> bool:
        """Create a clipped raster layer with enhancement settings applied."""
        try:
            # Use the raster processing service to clip the raster
            success = self._raster_processing_service.clip_raster_to_geometry(
                raster_layer_id=raster_layer_id,
                geometry_wkt=recording_area_geometry,
                output_path=output_path,
                offset_meters=offset_meters
            )
            
            if success:
                # Add to project
                layer = QgsRasterLayer(output_path, "Background", "gdal")
                if layer.isValid():
                    # Apply raster enhancement settings
                    enhancement_applied = self._apply_raster_enhancement(layer)
                    
                    # Force the layer to update its style after enhancement
                    layer.triggerRepaint()
                    
                    # Save raster style as QML with enhancement values
                    import os
                    qml_path = os.path.splitext(output_path)[0] + ".qml"
                    
                    if enhancement_applied:
                        # Save the style with enhancement values
                        self._save_raster_style_with_enhancement(layer, qml_path)
                    else:
                        # Save the style without enhancement
                        style_result = layer.saveNamedStyle(qml_path)
                        if style_result[0]:
                            print(f"[DEBUG] Saved raster QML style file: {qml_path}")
                        else:
                            print(f"[DEBUG] Failed to save raster QML style file: {qml_path}")
                    
                    # Load the style back to ensure it's associated
                    load_result = layer.loadNamedStyle(qml_path)
                    if load_result[0]:
                        print(f"[DEBUG] Loaded raster QML style file: {qml_path}")
                    else:
                        print(f"[DEBUG] Failed to load raster QML style file: {qml_path}")
                    
                    project.addMapLayer(layer)
                    return True
            
            return False
        except Exception as e:
            print(f"Error creating clipped raster: {str(e)}")
            return False

    def _save_raster_style_with_enhancement(self, layer: QgsRasterLayer, qml_path: str) -> bool:
        """Save raster style to QML file with enhancement values explicitly included, using XML parsing for correct structure."""
        try:
            import xml.etree.ElementTree as ET
            # Get enhancement settings
            brightness = self._settings_manager.get_value('raster_brightness', 0)
            contrast = self._settings_manager.get_value('raster_contrast', 0)
            saturation = self._settings_manager.get_value('raster_saturation', 0)

            # First save the basic style
            style_result = layer.saveNamedStyle(qml_path)
            if not style_result[0]:
                print(f"[DEBUG] Failed to save basic raster style: {qml_path}")
                return False

            # Parse the QML file as XML
            tree = ET.parse(qml_path)
            root = tree.getroot()

            # Find the <pipe> element
            pipe = root.find('pipe')
            if pipe is None:
                print(f"[DEBUG] No <pipe> element found in QML: {qml_path}")
                return False

            # Remove any existing <brightnesscontrast> and <huesaturation> elements
            for tag in ['brightnesscontrast', 'huesaturation']:
                for elem in pipe.findall(tag):
                    pipe.remove(elem)

            # Prepare new enhancement elements
            brightness_elem = ET.Element('brightnesscontrast', {
                'gamma': '1',
                'brightness': str(brightness),
                'contrast': str(contrast)
            })
            hue_elem = ET.Element('huesaturation', {
                'colorizeOn': '0',
                'invertColors': '0',
                'colorizeRed': '255',
                'colorizeGreen': '128',
                'colorizeStrength': '100',
                'grayscaleMode': '0',
                'saturation': str(saturation),
                'colorizeBlue': '128'
            })

            # Find the <rasterrenderer> element to insert after
            renderer = pipe.find('rasterrenderer')
            insert_index = 0
            for idx, child in enumerate(pipe):
                if child.tag == 'rasterrenderer':
                    insert_index = idx + 1
                    break
            # Insert enhancements after <rasterrenderer>
            pipe.insert(insert_index, brightness_elem)
            pipe.insert(insert_index + 1, hue_elem)

            # Write the updated QML content back
            tree.write(qml_path, encoding='utf-8', xml_declaration=False)

            print(f"[DEBUG] Saved raster QML style file with enhancement (XML) - Brightness: {brightness}, Contrast: {contrast}, Saturation: {saturation}")
            return True
        except Exception as e:
            print(f"Error saving raster style with enhancement (XML): {str(e)}")
            return False

    def _apply_raster_enhancement(self, raster_layer: QgsRasterLayer) -> bool:
        """
        Apply brightness, contrast, and saturation settings to a raster layer.
        
        Args:
            raster_layer: The raster layer to enhance
            
        Returns:
            True if enhancement was applied successfully, False otherwise
        """
        try:
            if not raster_layer or not raster_layer.isValid():
                print("[DEBUG] Raster layer is invalid or None.")
                return False
            
            # Get the renderer
            renderer = raster_layer.renderer()
            if not renderer:
                print("[DEBUG] No renderer found for raster layer.")
                return False
            
            print(f"[DEBUG] Renderer type: {type(renderer)}")
            print(f"[DEBUG] Renderer has setBrightness: {hasattr(renderer, 'setBrightness')}")
            print(f"[DEBUG] Renderer has setContrast: {hasattr(renderer, 'setContrast')}")
            print(f"[DEBUG] Renderer has setSaturation: {hasattr(renderer, 'setSaturation')}")
            
            # Get enhancement settings from settings manager
            brightness = self._settings_manager.get_value('raster_brightness', 0)
            contrast = self._settings_manager.get_value('raster_contrast', 0)
            saturation = self._settings_manager.get_value('raster_saturation', 0)
            
            print(f"[DEBUG] Applying raster enhancement - Brightness: {brightness}, Contrast: {contrast}, Saturation: {saturation}")
            
            # Apply brightness and contrast
            if hasattr(renderer, 'setBrightness'):
                renderer.setBrightness(brightness)
                print(f"[DEBUG] Set brightness to: {brightness}")
            else:
                print("[DEBUG] Renderer does not support setBrightness.")
            if hasattr(renderer, 'setContrast'):
                renderer.setContrast(contrast)
                print(f"[DEBUG] Set contrast to: {contrast}")
            else:
                print("[DEBUG] Renderer does not support setContrast.")
            
            # Apply saturation (hue/saturation)
            if hasattr(renderer, 'setSaturation'):
                renderer.setSaturation(saturation)
                print(f"[DEBUG] Set saturation to: {saturation}")
            else:
                print("[DEBUG] Renderer does not support setSaturation.")
            
            # Trigger repaint to apply changes
            raster_layer.triggerRepaint()
            
            return True
            
        except Exception as e:
            print(f"Error applying raster enhancement: {str(e)}")
            return False

    def _is_virtual_field(self, field, layer=None) -> bool:
        """
        Check if a field is a virtual/computed field that should be excluded from copying.
        
        Args:
            field: QgsField object to check
            layer: Optional QgsVectorLayer to check for QML style file
            
        Returns:
            True if the field appears to be virtual/computed
        """
        try:
            print(f"[DEBUG] _is_virtual_field called for field: {field.name()}")
            # Method 1: Check if it's a virtual field (computed field)
            if hasattr(field, 'isVirtual') and field.isVirtual():
                print(f"[DEBUG] Field {field.name()} detected as virtual via isVirtual()")
                return True
            
            # Method 2: Check if it's a computed field (QVariant.Invalid type)
            if hasattr(field, 'type') and field.type() == 100:  # QVariant.Invalid
                print(f"[DEBUG] Field {field.name()} detected as virtual via type() == 100")
                return True
            
            # Method 3: Check if the field has an expression (computed field)
            if hasattr(field, 'expression') and field.expression():
                print(f"[DEBUG] Field {field.name()} detected as virtual via expression()")
                return True
            
            # Method 4: Check if the field has a default value expression
            if hasattr(field, 'defaultValueDefinition') and field.defaultValueDefinition():
                default_def = field.defaultValueDefinition()
                if hasattr(default_def, 'expression') and default_def.expression():
                    print(f"[DEBUG] Field {field.name()} detected as virtual via defaultValueDefinition().expression()")
                    return True
            
            # Method 5: Check QML style file for expression fields (most reliable)
            if layer and hasattr(layer, 'styleURI'):
                qml_path = layer.styleURI()
                if qml_path and qml_path.endswith('.qml'):
                    virtual_fields = self._parse_qml_expression_fields(qml_path)
                    if field.name() in virtual_fields:
                        print(f"[DEBUG] Field {field.name()} detected as virtual via QML expression fields")
                        return True
            
            # Method 6: Check if the field has a comment indicating it's computed
            if hasattr(field, 'comment') and field.comment():
                comment = field.comment().lower()
                if any(keyword in comment for keyword in ['computed', 'virtual', 'expression', 'calculated']):
                    print(f"[DEBUG] Field {field.name()} detected as virtual via comment: {comment}")
                    return True
            
            # Method 7: Check if the field has an alias that suggests it's computed
            if hasattr(field, 'alias') and field.alias():
                alias = field.alias().lower()
                if any(keyword in alias for keyword in ['computed', 'virtual', 'expression', 'calculated']):
                    print(f"[DEBUG] Field {field.name()} detected as virtual via alias: {alias}")
                    return True
            
            print(f"[DEBUG] Field {field.name()} not detected as virtual")
            return False
        except Exception as e:
            # If we can't determine, assume it's not virtual
            print(f"[DEBUG] Exception in _is_virtual_field for {field.name()}: {str(e)}")
            return False
    
    def _parse_qml_expression_fields(self, qml_path):
        """Parse QML file to extract expression fields."""
        import xml.etree.ElementTree as ET
        
        try:
            tree = ET.parse(qml_path)
            root = tree.getroot()
            
            # Find expressionfields section
            expressionfields = root.find('.//expressionfields')
            if expressionfields is None:
                return {}
            
            virtual_fields = {}
            for field in expressionfields.findall('field'):
                name = field.get('name')
                expression = field.get('expression')
                if name and expression:
                    virtual_fields[name] = expression
            
            return virtual_fields
            
        except Exception as e:
            print(f"Error parsing QML file {qml_path}: {str(e)}")
            return {}



    def _set_project_variables(self, project: QgsProject, next_values: Dict[str, str], recording_area: str) -> None:
        """Set project variables for field preparation."""
        try:
            # Set recording area name
            project.setCustomVariables({
                'recording_area': recording_area,
                'first_number': next_values.get('first_number', ''),
                'level': next_values.get('level', ''),
                'auto_zoom_bookmark': recording_area
            })
        except Exception as e:
            print(f"Error setting project variables: {str(e)}") 

    def _create_recording_area_bookmark(self, project: QgsProject, feature_data: Dict[str, Any], recording_area_name: str) -> None:
        """
        Create a bookmark for the recording area that zooms to the feature's geometry.
        """
        try:
            # Get the geometry as a QgsGeometry object
            geometry_wkt = feature_data['geometry_wkt']
            geom = QgsGeometry.fromWkt(geometry_wkt)

            # Get the project CRS
            project_crs = project.crs()
            
            # Create a referenced rectangle with the project CRS
            bounding_box = geom.boundingBox()
            referenced_rect = QgsReferencedRectangle(bounding_box, project_crs)

            # Create a new bookmark
            bookmark = QgsBookmark()
            bookmark.setName(recording_area_name)
            bookmark.setExtent(referenced_rect)
            # Add the bookmark to the project's bookmark manager
            project.bookmarkManager().addBookmark(bookmark)
            print(f"Created bookmark for {recording_area_name} with extent: {bounding_box}")
        except Exception as e:
            print(f"Error creating recording area bookmark: {str(e)}")

 