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

import copy
import os
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Optional, Any, Dict, List
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsDefaultValue,
)
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QObject

try:
    from ..core.interfaces import ISettingsManager, ILayerService, IFileSystemService, IRasterProcessingService
    from .field_project_metadata import (
        PROJECT_KIND_GLOBAL,
        write_project_metadata,
    )
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService, IFileSystemService, IRasterProcessingService
    from services.field_project_metadata import (
        PROJECT_KIND_GLOBAL,
        write_project_metadata,
    )


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
                           next_values: Dict[str, str] = None,
                           source_map_rotation: Optional[float] = None) -> bool:
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
            source_map_rotation: Map canvas rotation (degrees) from the main project (optional)
            
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

            # Keep a mapping from source layer IDs (in the main project) to the
            # corresponding layer IDs in the generated field project. This is
            # required to recreate QGIS relations in the field project, since
            # layer IDs change when layers are copied/loaded.
            source_to_target_layer_ids: Dict[str, str] = {}
            
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
            self._try_register_created_layer_id_mapping(
                project=project,
                source_layer_id=recording_areas_layer_id,
                created_layer_name=recording_layer_name,
                created_layer_source_path=recording_gpkg_path,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )

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
            self._apply_defaults_to_created_layer(project, objects_gpkg_path, objects_layer_name, "objects")
            self._try_register_created_layer_id_mapping(
                project=project,
                source_layer_id=objects_layer_id,
                created_layer_name=objects_layer_name,
                created_layer_source_path=objects_gpkg_path,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )

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
                self._apply_defaults_to_created_layer(project, features_gpkg_path, features_layer_name, "features")
                self._try_register_created_layer_id_mapping(
                    project=project,
                    source_layer_id=features_layer_id,
                    created_layer_name=features_layer_name,
                    created_layer_source_path=features_gpkg_path,
                    source_to_target_layer_ids=source_to_target_layer_ids,
                )

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
                self._apply_defaults_to_created_layer(project, small_finds_gpkg_path, small_finds_layer_name, "small_finds")
                self._try_register_created_layer_id_mapping(
                    project=project,
                    source_layer_id=small_finds_layer_id,
                    created_layer_name=small_finds_layer_name,
                    created_layer_source_path=small_finds_gpkg_path,
                    source_to_target_layer_ids=source_to_target_layer_ids,
                )

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
                            else:
                                self._try_register_created_layer_id_mapping(
                                    project=project,
                                    source_layer_id=layer_id,
                                    created_layer_name=layer_name,
                                    created_layer_source_path=os.path.join(project_dir, f"{layer_name}.gpkg"),
                                    source_to_target_layer_ids=source_to_target_layer_ids,
                                )

            # Set project variables
            recording_area_variable_value = feature_data.get('recording_area_variable_value', feature_data['display_name'])
            if next_values:
                self._set_project_variables(project, next_values, recording_area_variable_value)

            # Create bookmark and initial map view for recording area
            map_view_payload = self._create_recording_area_bookmark(
                project,
                feature_data,
                feature_data['display_name'],
                map_rotation=source_map_rotation if source_map_rotation is not None else 0.0,
            )

            # Recreate QGIS relations from the main project into the field project.
            # This is necessary so Relation widgets in forms remain valid after export.
            self._copy_project_relations_to_field_project(
                source_project=QgsProject.instance(),
                target_project=project,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )

            # Fix ValueRelation layer references for all layers
            for layer in project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    self._layer_service._fix_valuerelation_layer_references(layer, project)

            # Ensure all layers are properly refreshed before saving
            for layer in project.mapLayers().values():
                if hasattr(layer, 'triggerRepaint'):
                    layer.triggerRepaint()
                if hasattr(layer, 'updateExtents'):
                    layer.updateExtents()

            # Save the project
            project_path = os.path.join(project_dir, f"{project_name}.qgs")
            success = project.write(project_path)
            if not success:
                raise RuntimeError(f"Failed to save project: {project_path}")

            # Fallback persistence for relations:
            # In some QGIS runtime combinations, relationManager.addRelation() rejects
            # valid relations during project build because of project-instance context.
            # To guarantee relation availability in the generated recording project, we
            # inject mapped relations directly into the .qgs XML.
            self._inject_relations_into_qgs_xml(
                qgs_path=project_path,
                source_project=QgsProject.instance(),
                target_project=project,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )
            if map_view_payload:
                self._inject_map_view_into_qgs_xml(project_path, map_view_payload)

            print(f"Successfully created field project: {project_path}")
            return True

        except Exception as e:
            print(f"Error creating field project: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def create_global_field_project(self,
                                    extent_geometry_wkt: str,
                                    destination_folder: str,
                                    project_name: str,
                                    background_layer_id: Optional[str] = None,
                                    extent_crs_authid: Optional[str] = None) -> bool:
        """
        Create a global field project with empty editable layers for the extent.

        Recording areas and extra layers are exported as read-only context clipped
        or filtered to the extent. Objects, features, small finds, and alternative
        objects are created as empty layers (same structure as the source project).
        No project variables or form default expressions are applied.
        """
        try:
            if not extent_geometry_wkt or not destination_folder or not project_name:
                raise ValueError("Extent, destination folder, and project name are required")

            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
            objects_layer_id = self._settings_manager.get_value('objects_layer', '')
            if not recording_areas_layer_id or not objects_layer_id:
                raise ValueError("Recording areas and objects layers must be configured")

            extent_geometry = QgsGeometry.fromWkt(extent_geometry_wkt)
            if not extent_geometry or extent_geometry.isNull() or extent_geometry.isEmpty():
                raise ValueError("Invalid extent geometry")

            project_dir = os.path.join(destination_folder, project_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            project = QgsProject()
            source_to_target_layer_ids: Dict[str, str] = {}
            readonly_layer_ids: List[str] = []

            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_layer:
                project.setCrs(recording_layer.crs())

            recording_area_ids = self._layer_service.get_recording_area_ids_intersecting_geometry(
                recording_areas_layer_id,
                extent_geometry,
                extent_crs_authid,
            )
            extra_layers = self._settings_manager.get_value('extra_field_layers', []) or []

            if background_layer_id:
                raster_offset = self._settings_manager.get_value('raster_clipping_offset', 0.0)
                self._create_clipped_raster(
                    raster_layer_id=background_layer_id,
                    recording_area_geometry=extent_geometry_wkt,
                    output_path=os.path.join(project_dir, "background.tif"),
                    project=project,
                    offset_meters=raster_offset,
                )

            import_layer_names: Dict[str, str] = {}

            layer_exports = [
                (recording_areas_layer_id, True),
                (objects_layer_id, False),
            ]
            features_layer_id = self._settings_manager.get_value('features_layer', '')
            if features_layer_id:
                layer_exports.append((features_layer_id, False))
            small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
            if small_finds_layer_id:
                layer_exports.append((small_finds_layer_id, False))

            for layer_id, is_readonly in layer_exports:
                layer_info = self._layer_service.get_layer_info(layer_id)
                if not layer_info:
                    continue
                layer_name = layer_info['name']
                output_path = os.path.join(project_dir, f"{layer_name}.gpkg")
                if layer_id == recording_areas_layer_id:
                    success = self._create_global_recording_areas_layer_copy(
                        recording_areas_layer_id=layer_id,
                        recording_area_ids=recording_area_ids,
                        output_path=output_path,
                        layer_name=layer_name,
                        extent_geometry=extent_geometry,
                        project=project,
                        extent_crs_authid=extent_crs_authid,
                    )
                else:
                    success = self._create_empty_layer_copy(
                        source_layer_id=layer_id,
                        output_path=output_path,
                        layer_name=layer_name,
                        project=project,
                    )
                if not success:
                    print(f"Warning: Failed to export layer {layer_name} for global project")
                else:
                    if layer_id == objects_layer_id:
                        import_layer_names["objects"] = layer_name
                    elif layer_id == features_layer_id:
                        import_layer_names["features"] = layer_name
                    elif layer_id == small_finds_layer_id:
                        import_layer_names["small_finds"] = layer_name
                    self._try_register_created_layer_id_mapping(
                        project=project,
                        source_layer_id=layer_id,
                        created_layer_name=layer_name,
                        created_layer_source_path=output_path,
                        source_to_target_layer_ids=source_to_target_layer_ids,
                    )
                    if is_readonly:
                        readonly_layer_ids.append(layer_id)

            alternative_objects_layer_id = self._settings_manager.get_value('alternative_objects_layer', '')
            if alternative_objects_layer_id:
                alt_info = self._layer_service.get_layer_info(alternative_objects_layer_id)
                if alt_info:
                    alt_name = alt_info['name']
                    alt_path = os.path.join(project_dir, f"{alt_name}.gpkg")
                    if self._create_empty_layer_copy(
                        source_layer_id=alternative_objects_layer_id,
                        output_path=alt_path,
                        layer_name=alt_name,
                        project=project,
                    ):
                        import_layer_names["alternative_objects"] = alt_name
                        self._try_register_created_layer_id_mapping(
                            project=project,
                            source_layer_id=alternative_objects_layer_id,
                            created_layer_name=alt_name,
                            created_layer_source_path=alt_path,
                            source_to_target_layer_ids=source_to_target_layer_ids,
                        )

            for extra_layer_id in extra_layers:
                if extra_layer_id == recording_areas_layer_id:
                    continue
                extra_info = self._layer_service.get_layer_info(extra_layer_id)
                if not extra_info:
                    continue
                extra_name = extra_info['name']
                extra_path = os.path.join(project_dir, f"{extra_name}.gpkg")
                if self._has_relationship_with_recording_areas(extra_layer_id, recording_areas_layer_id):
                    filter_expression = self._get_relationship_filter_expression_for_ids(
                        extra_layer_id,
                        recording_areas_layer_id,
                        recording_area_ids,
                    )
                    if filter_expression:
                        success = self._create_filtered_layer(
                            source_layer_id=extra_layer_id,
                            output_path=extra_path,
                            layer_name=extra_name,
                            filter_expression=filter_expression,
                            project=project,
                        )
                    else:
                        success = self._export_extra_layer_for_global_project(
                            extra_layer_id=extra_layer_id,
                            output_path=extra_path,
                            layer_name=extra_name,
                            extent_geometry=extent_geometry,
                            project=project,
                            extent_crs_authid=extent_crs_authid,
                        )
                else:
                    success = self._export_extra_layer_for_global_project(
                        extra_layer_id=extra_layer_id,
                        output_path=extra_path,
                        layer_name=extra_name,
                        extent_geometry=extent_geometry,
                        project=project,
                        extent_crs_authid=extent_crs_authid,
                    )
                if success:
                    self._try_register_created_layer_id_mapping(
                        project=project,
                        source_layer_id=extra_layer_id,
                        created_layer_name=extra_name,
                        created_layer_source_path=extra_path,
                        source_to_target_layer_ids=source_to_target_layer_ids,
                    )
                    readonly_layer_ids.append(extra_layer_id)

            self._apply_readonly_layers_in_project(project, readonly_layer_ids, source_to_target_layer_ids)

            self._copy_project_relations_to_field_project(
                source_project=QgsProject.instance(),
                target_project=project,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )

            for layer in project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    self._layer_service._fix_valuerelation_layer_references(layer, project)

            project_path = os.path.join(project_dir, f"{project_name}.qgs")
            if not project.write(project_path):
                raise RuntimeError(f"Failed to save project: {project_path}")

            self._inject_relations_into_qgs_xml(
                qgs_path=project_path,
                source_project=QgsProject.instance(),
                target_project=project,
                source_to_target_layer_ids=source_to_target_layer_ids,
            )

            crs_string = self._get_crs_string(project.crs()) if project.crs() else ""
            write_project_metadata(
                project_dir,
                PROJECT_KIND_GLOBAL,
                extent_geometry_wkt,
                crs_string,
                import_layers=import_layer_names,
            )

            print(f"Successfully created global field project: {project_path}")
            return True
        except Exception as e:
            print(f"Error creating global field project: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _apply_defaults_to_created_layer(self, project: QgsProject, output_path: str, layer_name: str, layer_key: str) -> None:
        """Apply configured form defaults on a newly copied layer."""
        try:
            normalized_output_path = os.path.normpath(output_path)
            for layer in project.mapLayers().values():
                if not isinstance(layer, QgsVectorLayer):
                    continue
                if layer.name() != layer_name:
                    continue
                source_path = os.path.normpath(layer.source().split("|")[0])
                if source_path != normalized_output_path:
                    continue
                self._apply_configured_field_defaults(layer, layer_key)
                break
        except Exception as e:
            print(f"Warning: failed to apply configured defaults for {layer_name}: {str(e)}")

    def _apply_configured_field_defaults(self, layer: QgsVectorLayer, layer_key: str) -> None:
        """Apply default expressions to fields configured in settings."""
        objects_number_field = self._settings_manager.get_value('objects_number_field', '')
        escaped_objects_number_field = str(objects_number_field).replace('"', '""') if objects_number_field else ''
        objects_number_expression = (
            f"with_variable('first', coalesce(to_int(@first_number), 1), "
            f"with_variable('current_max', coalesce(maximum(\"{escaped_objects_number_field}\"), @first - 1), "
            f"if(@current_max > @first - 1, @current_max, @first - 1) + 1))"
            if escaped_objects_number_field else "@first_number"
        )
        layer_field_map = {
            "objects": [
                ("objects_number_field", objects_number_expression),
                ("objects_recording_area_field", "@recording_area"),
                ("objects_level_field", "@level"),
            ],
            "features": [
                ("features_recording_area_field", "@recording_area"),
                ("features_level_field", "@level"),
            ],
            "small_finds": [
                ("small_finds_recording_area_field", "@recording_area"),
                ("small_finds_level_field", "@level"),
            ],
        }
        field_definitions = layer_field_map.get(layer_key, [])
        for setting_key, expression in field_definitions:
            field_name = self._settings_manager.get_value(setting_key, '')
            if not field_name:
                continue
            field_idx = layer.fields().indexOf(field_name)
            if field_idx < 0:
                continue
            layer.setDefaultValueDefinition(field_idx, QgsDefaultValue(expression))

    def _try_register_created_layer_id_mapping(
        self,
        project: QgsProject,
        source_layer_id: str,
        created_layer_name: str,
        created_layer_source_path: str,
        source_to_target_layer_ids: Dict[str, str],
    ) -> None:
        """
        Best-effort mapping between a source layer ID and the copied layer ID in the field project.

        We need this mapping to rebuild QGIS relations (which are layer-ID based) in the
        generated project. This uses layer names as a lookup key inside the generated project.
        """
        try:
            if not project or not source_layer_id or not created_layer_name:
                return
            # Prefer matching by data source path (most reliable), then fall back to name.
            target_layer = None
            expected_path = str(created_layer_source_path or "")
            if expected_path:
                for lyr in project.mapLayers().values():
                    try:
                        src = lyr.source() if hasattr(lyr, "source") else ""
                        # GPKG sources often look like: "/path/file.gpkg|layername=Layer"
                        if src and src.startswith(expected_path):
                            target_layer = lyr
                            break
                    except Exception:
                        continue

            if target_layer is None and hasattr(project, "mapLayersByName"):
                matches = project.mapLayersByName(created_layer_name)
                if matches:
                    target_layer = matches[0]

            if target_layer is not None and hasattr(target_layer, "id"):
                source_to_target_layer_ids[source_layer_id] = target_layer.id()
        except Exception as e:
            print(f"[DEBUG] Failed to register layer ID mapping for {created_layer_name}: {str(e)}")

    def _copy_project_relations_to_field_project(
        self,
        source_project: QgsProject,
        target_project: QgsProject,
        source_to_target_layer_ids: Dict[str, str],
    ) -> None:
        """
        Copy QGIS relation definitions from the source project to the generated field project.

        QGIS relations reference layers by their internal layer IDs. Since we copy layers into
        a new project, the IDs change, and we must remap them so the relation widgets in forms
        stay valid.
        """
        try:
            if not source_project or not target_project:
                return
            if not source_to_target_layer_ids:
                return

            source_relation_manager = source_project.relationManager()
            target_relation_manager = target_project.relationManager()

            if not source_relation_manager or not target_relation_manager:
                return

            from qgis.core import QgsRelation

            # Defensive: sometimes the mapping collected during export can miss layers
            # or keep stale IDs. Before copying relations, ensure every mapped target
            # layer ID actually exists in the target project. If not, try to remap
            # by matching layer names between projects.
            try:
                fixed = 0
                for src_id, tgt_id in list(source_to_target_layer_ids.items()):
                    if not tgt_id or target_project.mapLayer(tgt_id) is not None:
                        continue
                    src_layer = source_project.mapLayer(src_id)
                    src_name = src_layer.name() if src_layer is not None and hasattr(src_layer, "name") else None
                    if not src_name:
                        continue
                    if hasattr(target_project, "mapLayersByName"):
                        matches = target_project.mapLayersByName(src_name)
                        if matches:
                            source_to_target_layer_ids[src_id] = matches[0].id()
                            fixed += 1
                if fixed:
                    print(f"[DEBUG] Fixed {fixed} layer-id mapping(s) by name")
            except Exception as e:
                print(f"[DEBUG] Failed to fix layer-id mappings: {str(e)}")

            def _resolve_target_layer_id(src_layer_id: str) -> Optional[str]:
                """
                Resolve a source layer ID to an existing target-project layer ID.

                Prefer explicit mapping; if missing/stale, fallback to name-based lookup.
                """
                if not src_layer_id:
                    return None

                mapped = source_to_target_layer_ids.get(src_layer_id)
                if mapped and target_project.mapLayer(mapped) is not None:
                    return mapped

                src_layer = source_project.mapLayer(src_layer_id)
                if src_layer is None or not hasattr(src_layer, "name"):
                    return None

                src_name = src_layer.name()
                if hasattr(target_project, "mapLayersByName"):
                    matches = target_project.mapLayersByName(src_name)
                    if matches:
                        resolved = matches[0].id()
                        source_to_target_layer_ids[src_layer_id] = resolved
                        return resolved
                return None

            copied = 0
            prepared_relations: Dict[str, Any] = {}
            for rel in source_relation_manager.relations().values():
                try:
                    src_referencing_id = rel.referencingLayerId()
                    src_referenced_id = rel.referencedLayerId()

                    # Debug: print basic source relation info to understand what's present.
                    try:
                        src_rel_id_dbg = rel.id() if hasattr(rel, "id") else ""
                        src_rel_name_dbg = rel.name() if hasattr(rel, "name") else ""
                        src_ref_layer_dbg = source_project.mapLayer(src_referenced_id)
                        src_ing_layer_dbg = source_project.mapLayer(src_referencing_id)
                        print(
                            "[DEBUG] Relation candidate:"
                            f" id='{src_rel_id_dbg}'"
                            f" name='{src_rel_name_dbg}'"
                            f" referencing='{src_ing_layer_dbg.name() if src_ing_layer_dbg else src_referencing_id}'"
                            f" referenced='{src_ref_layer_dbg.name() if src_ref_layer_dbg else src_referenced_id}'"
                        )
                    except Exception:
                        pass

                    tgt_referencing_id = _resolve_target_layer_id(src_referencing_id)
                    tgt_referenced_id = _resolve_target_layer_id(src_referenced_id)
                    if not tgt_referencing_id or not tgt_referenced_id:
                        continue
                    tgt_referencing_layer = target_project.mapLayer(tgt_referencing_id)
                    tgt_referenced_layer = target_project.mapLayer(tgt_referenced_id)
                    if tgt_referencing_layer is None or tgt_referenced_layer is None:
                        continue

                    new_rel = QgsRelation()

                    # Preserve name when available (helpful for debugging and form configs)
                    rel_name = rel.name() if hasattr(rel, "name") else ""
                    if hasattr(new_rel, "setName") and rel_name:
                        new_rel.setName(rel_name)

                    # Relation IDs must be unique within the target project. If the source id
                    # is empty or duplicates something in the target manager, generate a new one.
                    src_rel_id = rel.id() if hasattr(rel, "id") else ""
                    target_ids = set(target_relation_manager.relations().keys()) if hasattr(target_relation_manager, "relations") else set()
                    final_rel_id = src_rel_id if src_rel_id and src_rel_id not in target_ids else f"archeosync_{uuid.uuid4().hex[:12]}"
                    if hasattr(new_rel, "setId"):
                        new_rel.setId(final_rel_id)

                    # QGIS bindings vary across versions:
                    # - some expect layer IDs
                    # - others expect layer objects
                    # We try both forms and verify the final stored IDs.
                    try:
                        if hasattr(new_rel, "setReferencingLayerId"):
                            new_rel.setReferencingLayerId(tgt_referencing_id)
                        else:
                            new_rel.setReferencingLayer(tgt_referencing_id)
                    except Exception:
                        try:
                            new_rel.setReferencingLayer(tgt_referencing_layer)
                        except Exception:
                            pass

                    try:
                        if hasattr(new_rel, "setReferencedLayerId"):
                            new_rel.setReferencedLayerId(tgt_referenced_id)
                        else:
                            new_rel.setReferencedLayer(tgt_referenced_id)
                    except Exception:
                        try:
                            new_rel.setReferencedLayer(tgt_referenced_layer)
                        except Exception:
                            pass

                    # Last-resort retry with layer objects when IDs did not stick.
                    if new_rel.referencingLayerId() != tgt_referencing_id:
                        try:
                            new_rel.setReferencingLayer(tgt_referencing_layer)
                        except Exception:
                            pass
                    if new_rel.referencedLayerId() != tgt_referenced_id:
                        try:
                            new_rel.setReferencedLayer(tgt_referenced_layer)
                        except Exception:
                            pass

                    if new_rel.referencingLayerId() != tgt_referencing_id or new_rel.referencedLayerId() != tgt_referenced_id:
                        print(
                            "[DEBUG] Could not bind relation to target layers:"
                            f" got referencing='{new_rel.referencingLayerId()}', referenced='{new_rel.referencedLayerId()}'"
                            f" expected referencing='{tgt_referencing_id}', referenced='{tgt_referenced_id}'"
                        )
                        continue

                    # Extra defensive check: if either mapped ID is still missing in target project,
                    # log and skip early with a clear reason.
                    try:
                        mapped_ref_ing = tgt_referencing_id
                        mapped_ref_ed = tgt_referenced_id
                        if target_project.mapLayer(mapped_ref_ing) is None:
                            print(f"[DEBUG] Skipping relation '{rel_name}': mapped referencing layer missing in target (id='{mapped_ref_ing}')")
                            continue
                        if target_project.mapLayer(mapped_ref_ed) is None:
                            print(f"[DEBUG] Skipping relation '{rel_name}': mapped referenced layer missing in target (id='{mapped_ref_ed}')")
                            continue
                    except Exception:
                        pass

                    # PyQGIS can expose fieldPairs as a Python dict, or as a Qt map-like
                    # object depending on QGIS version/bindings. Normalize it to an
                    # iterable of (referencing_field, referenced_field).
                    field_pairs_obj = rel.fieldPairs() if hasattr(rel, "fieldPairs") else None
                    field_pairs_list: List[tuple] = []
                    if field_pairs_obj:
                        try:
                            # Most Pythonic case
                            if hasattr(field_pairs_obj, "items"):
                                field_pairs_list = [(k, v) for k, v in field_pairs_obj.items()]
                            # Qt map-like case (keys()/values())
                            elif hasattr(field_pairs_obj, "keys") and hasattr(field_pairs_obj, "values"):
                                keys = list(field_pairs_obj.keys())
                                values = list(field_pairs_obj.values())
                                field_pairs_list = list(zip(keys, values))
                            # Some bindings allow iteration yielding keys
                            elif hasattr(field_pairs_obj, "__iter__"):
                                keys = list(field_pairs_obj)
                                try:
                                    values = list(field_pairs_obj.values()) if hasattr(field_pairs_obj, "values") else []
                                except Exception:
                                    values = []
                                if keys and values and len(keys) == len(values):
                                    field_pairs_list = list(zip(keys, values))
                        except Exception:
                            field_pairs_list = []

                    if not field_pairs_list:
                        try:
                            print(
                                f"[DEBUG] Relation '{rel_name}' has empty/unsupported fieldPairs:"
                                f" type={type(field_pairs_obj)}"
                                f" repr={field_pairs_obj!r}"
                            )
                        except Exception:
                            print(f"[DEBUG] Relation '{rel_name}' has empty/unsupported fieldPairs")

                    for referencing_field, referenced_field in field_pairs_list:
                        new_rel.addFieldPair(str(referencing_field), str(referenced_field))

                    try:
                        if field_pairs_list:
                            print(f"[DEBUG] Relation '{rel_name}' field pairs copied: {[(str(a), str(b)) for a, b in field_pairs_list]}")
                    except Exception:
                        pass

                    # Do not call addRelation here: in some QGIS versions this validates
                    # against QgsProject.instance() instead of target_project and rejects
                    # otherwise-correct relations. We stage relations and set them in batch.
                    prepared_relations[new_rel.id()] = new_rel
                except Exception as e:
                    print(f"[DEBUG] Failed to copy a relation: {str(e)}")

            if prepared_relations:
                try:
                    # In some QGIS builds, relation validation uses QgsProject.instance()
                    # internally. If so, relations can be incorrectly rejected when we build
                    # them against an in-memory project object. We temporarily switch the
                    # global instance to target_project while adding relations, then restore.
                    from qgis.core import QgsProject as _QgsProjectClass
                    original_project_instance = _QgsProjectClass.instance()
                    switched_instance = False
                    if hasattr(_QgsProjectClass, "setInstance"):
                        try:
                            _QgsProjectClass.setInstance(target_project)
                            switched_instance = True
                        except Exception as e:
                            print(f"[DEBUG] Could not switch QgsProject.instance(): {str(e)}")

                    try:
                        # Prefer explicit addRelation so we know whether each relation is accepted.
                        for relation in prepared_relations.values():
                            ok = target_relation_manager.addRelation(relation)
                            if ok:
                                copied += 1
                            else:
                                rel_label = relation.name() if hasattr(relation, "name") else relation.id()
                                extra_reason = None
                                for attr in ("validationError", "validationErrorString", "errorString"):
                                    if hasattr(relation, attr):
                                        try:
                                            extra_reason = getattr(relation, attr)()
                                            break
                                        except Exception:
                                            pass
                                print(f"[DEBUG] addRelation rejected '{rel_label}': {extra_reason if extra_reason else 'unknown reason'}")
                    finally:
                        if switched_instance:
                            try:
                                _QgsProjectClass.setInstance(original_project_instance)
                            except Exception as e:
                                print(f"[DEBUG] Failed to restore QgsProject.instance(): {str(e)}")
                except Exception as e:
                    print(f"[DEBUG] Failed while adding staged relations: {str(e)}")

            if copied:
                print(f"[DEBUG] Copied {copied} relation(s) into field project")
            try:
                current_relations = target_relation_manager.relations()
                current_count = len(current_relations) if hasattr(current_relations, "__len__") else "unknown"
                print(f"[DEBUG] Field-project relation manager currently has: {current_count} relation(s)")
            except Exception:
                pass
        except Exception as e:
            print(f"[DEBUG] Failed to copy project relations: {str(e)}")

    def _extract_relation_field_pairs(self, relation: Any) -> List[tuple]:
        """
        Extract (referencing_field, referenced_field) pairs from a QgsRelation-like object.
        """
        field_pairs_obj = relation.fieldPairs() if hasattr(relation, "fieldPairs") else None
        field_pairs_list: List[tuple] = []
        if not field_pairs_obj:
            return field_pairs_list

        try:
            if hasattr(field_pairs_obj, "items"):
                field_pairs_list = [(k, v) for k, v in field_pairs_obj.items()]
            elif hasattr(field_pairs_obj, "keys") and hasattr(field_pairs_obj, "values"):
                keys = list(field_pairs_obj.keys())
                values = list(field_pairs_obj.values())
                field_pairs_list = list(zip(keys, values))
            elif hasattr(field_pairs_obj, "__iter__"):
                keys = list(field_pairs_obj)
                values = list(field_pairs_obj.values()) if hasattr(field_pairs_obj, "values") else []
                if keys and values and len(keys) == len(values):
                    field_pairs_list = list(zip(keys, values))
        except Exception:
            return []
        return field_pairs_list

    def _inject_relations_into_qgs_xml(
        self,
        qgs_path: str,
        source_project: QgsProject,
        target_project: QgsProject,
        source_to_target_layer_ids: Dict[str, str],
    ) -> None:
        """
        Inject mapped relations directly into the generated .qgs file.
        """
        try:
            if not qgs_path or not os.path.exists(qgs_path):
                return

            relation_manager = source_project.relationManager() if source_project else None
            if not relation_manager:
                return

            def _resolve_target_layer_id(src_layer_id: str) -> Optional[str]:
                mapped = source_to_target_layer_ids.get(src_layer_id)
                if mapped and target_project.mapLayer(mapped) is not None:
                    return mapped
                src_layer = source_project.mapLayer(src_layer_id)
                if not src_layer:
                    return None
                matches = target_project.mapLayersByName(src_layer.name()) if hasattr(target_project, "mapLayersByName") else []
                if matches:
                    resolved = matches[0].id()
                    source_to_target_layer_ids[src_layer_id] = resolved
                    return resolved
                return None

            relations_payload: List[Dict[str, Any]] = []
            for rel in relation_manager.relations().values():
                src_ref_ing = rel.referencingLayerId()
                src_ref_ed = rel.referencedLayerId()
                tgt_ref_ing = _resolve_target_layer_id(src_ref_ing)
                tgt_ref_ed = _resolve_target_layer_id(src_ref_ed)
                if not tgt_ref_ing or not tgt_ref_ed:
                    continue
                if target_project.mapLayer(tgt_ref_ing) is None or target_project.mapLayer(tgt_ref_ed) is None:
                    continue

                field_pairs = self._extract_relation_field_pairs(rel)
                if not field_pairs:
                    continue

                rel_id = rel.id() if hasattr(rel, "id") and rel.id() else f"archeosync_{uuid.uuid4().hex[:12]}"
                rel_name = rel.name() if hasattr(rel, "name") else ""
                if not rel_name:
                    rel_name = rel_id

                relations_payload.append(
                    {
                        "id": str(rel_id),
                        "name": str(rel_name),
                        "referencingLayer": str(tgt_ref_ing),
                        "referencedLayer": str(tgt_ref_ed),
                        "field_pairs": [(str(a), str(b)) for a, b in field_pairs],
                    }
                )

            if not relations_payload:
                print("[DEBUG] No relations available for XML injection")
                return

            tree = ET.parse(qgs_path)
            root = tree.getroot()
            relations_node = root.find("relations")
            if relations_node is None:
                relations_node = ET.Element("relations")
                root.append(relations_node)
            else:
                for child in list(relations_node):
                    relations_node.remove(child)

            for rel_data in relations_payload:
                rel_el = ET.SubElement(
                    relations_node,
                    "relation",
                    {
                        "id": rel_data["id"],
                        "name": rel_data["name"],
                        "referencingLayer": rel_data["referencingLayer"],
                        "referencedLayer": rel_data["referencedLayer"],
                        "strength": "Association",
                    },
                )
                for referencing_field, referenced_field in rel_data["field_pairs"]:
                    ET.SubElement(
                        rel_el,
                        "fieldRef",
                        {
                            "referencingField": referencing_field,
                            "referencedField": referenced_field,
                        },
                    )

            tree.write(qgs_path, encoding="utf-8", xml_declaration=False)
            print(f"[DEBUG] Injected {len(relations_payload)} relation(s) directly into .qgs XML")
        except Exception as e:
            print(f"[DEBUG] Failed to inject relations into .qgs XML: {str(e)}")

    def _inject_map_view_into_qgs_xml(
        self,
        qgs_path: str,
        view_payload: Dict[str, Any],
    ) -> None:
        """
        Inject map canvas extent and rotation directly into the generated .qgs file.

        QGIS restores the main map view from the ``mapcanvas`` element when present.
        Programmatic ``viewSettings()`` updates alone are not always serialized or
        applied reliably across QGIS versions, so we mirror the desktop save format.
        """
        try:
            if not qgs_path or not os.path.exists(qgs_path) or not view_payload:
                return

            xmin = view_payload.get('xmin')
            ymin = view_payload.get('ymin')
            xmax = view_payload.get('xmax')
            ymax = view_payload.get('ymax')
            if None in (xmin, ymin, xmax, ymax):
                return

            rotation = float(view_payload.get('rotation', 0.0) or 0.0)
            map_units = view_payload.get('map_units') or 'meters'

            tree = ET.parse(qgs_path)
            root = tree.getroot()
            spatial_ref_node = root.find('projectCrs/spatialrefsys')

            view_settings_node = root.find('ProjectViewSettings')
            if view_settings_node is None:
                view_settings_node = ET.Element('ProjectViewSettings')
                root.append(view_settings_node)
            else:
                for child in list(view_settings_node):
                    if child.tag in ('DefaultViewExtent', 'PresetFullExtent'):
                        view_settings_node.remove(child)

            view_settings_node.set('UseProjectScales', '0')
            view_settings_node.set('rotation', repr(rotation))

            default_extent = ET.SubElement(
                view_settings_node,
                'DefaultViewExtent',
                {
                    'xmin': repr(xmin),
                    'ymin': repr(ymin),
                    'xmax': repr(xmax),
                    'ymax': repr(ymax),
                },
            )
            if spatial_ref_node is not None:
                default_extent.append(copy.deepcopy(spatial_ref_node))

            mapcanvas_node = None
            for candidate in root.findall('mapcanvas'):
                if candidate.get('name') in (None, 'theMapCanvas'):
                    mapcanvas_node = candidate
                    break

            if mapcanvas_node is None:
                mapcanvas_node = ET.Element('mapcanvas')
                relations_node = root.find('relations')
                if relations_node is not None:
                    root.insert(list(root).index(relations_node) + 1, mapcanvas_node)
                else:
                    root.append(mapcanvas_node)
            else:
                for child in list(mapcanvas_node):
                    if child.tag in ('extent', 'rotation', 'units', 'destinationsrs', 'rendermaptile'):
                        mapcanvas_node.remove(child)

            mapcanvas_node.set('annotationsVisible', '1')
            mapcanvas_node.set('name', 'theMapCanvas')

            units_el = ET.SubElement(mapcanvas_node, 'units')
            units_el.text = map_units

            extent_el = ET.SubElement(mapcanvas_node, 'extent')
            for tag, value in (
                ('xmin', xmin),
                ('ymin', ymin),
                ('xmax', xmax),
                ('ymax', ymax),
            ):
                coord_el = ET.SubElement(extent_el, tag)
                coord_el.text = repr(value)

            rotation_el = ET.SubElement(mapcanvas_node, 'rotation')
            rotation_el.text = repr(rotation)

            destinationsrs_el = ET.SubElement(mapcanvas_node, 'destinationsrs')
            if spatial_ref_node is not None:
                destinationsrs_el.append(copy.deepcopy(spatial_ref_node))

            render_tile_el = ET.SubElement(mapcanvas_node, 'rendermaptile')
            render_tile_el.text = '0'

            tree.write(qgs_path, encoding='utf-8', xml_declaration=False)
            print(
                f"[DEBUG] Injected map view into .qgs XML "
                f"(extent={xmin},{ymin},{xmax},{ymax}, rotation={rotation})"
            )
        except Exception as e:
            print(f"[DEBUG] Failed to inject map view into .qgs XML: {str(e)}")

    def _map_units_label_for_crs(self, crs: Any) -> str:
        """Return the QGIS map-units label stored in .qgs mapcanvas nodes."""
        try:
            from qgis.core import QgsUnitTypes
            if crs and crs.isValid():
                return QgsUnitTypes.toString(crs.mapUnits())
        except Exception:
            pass
        return 'meters'

    def _filter_expression_uses_qgis_syntax(self, filter_expression: str) -> bool:
        """Return True when the expression uses QGIS tokens (e.g. $geometry, $id)."""
        return "$" in filter_expression

    def _get_source_layer_active_filter(self, source_layer: QgsVectorLayer) -> Optional[str]:
        """
        Return the active filter configured on a layer in the main project.

        Prefers the provider subset string; falls back to the QGIS filter expression.
        """
        if not source_layer:
            return None
        subset = (source_layer.subsetString() or "").strip()
        if subset:
            return subset
        if hasattr(source_layer, "filterExpression"):
            expression = (source_layer.filterExpression() or "").strip()
            if expression:
                return expression
        return None

    def _combine_export_filter_expressions(
        self,
        *filter_expressions: Optional[str],
    ) -> Optional[str]:
        """Combine export filters with AND, preserving each non-empty expression."""
        parts = [
            expression.strip()
            for expression in filter_expressions
            if expression and expression.strip()
        ]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return " AND ".join(f"({part})" for part in parts)

    def _export_memory_layer_to_project(
        self,
        memory_layer: QgsVectorLayer,
        source_layer: QgsVectorLayer,
        output_path: str,
        layer_name: str,
        project: QgsProject,
    ) -> bool:
        """Write a memory layer to Geopackage and register it in the target project."""
        success = self._copy_layer_to_geopackage(
            memory_layer,
            output_path,
            layer_name,
            properties_source_layer=source_layer,
        )
        if not success:
            return False
        layer = QgsVectorLayer(output_path, layer_name, "ogr")
        if layer.isValid():
            layer.triggerRepaint()
            project.addMapLayer(layer)
            return True
        return False

    def _build_memory_layer_from_feature_iterator(
        self,
        source_layer: QgsVectorLayer,
        features,
    ) -> Optional[QgsVectorLayer]:
        """Copy features from an iterator into a new memory layer."""
        try:
            memory_layer = QgsVectorLayer(
                self._memory_layer_uri_for_vector_layer(source_layer),
                "filtered",
                "memory",
            )
            if not memory_layer.isValid():
                print(f"[DEBUG] Could not create memory layer for {source_layer.name()}")
                return None

            fields_to_drop = self._collect_non_exportable_field_names(source_layer)
            source_fields = source_layer.fields()
            kept_field_names: List[str] = []

            memory_layer.startEditing()
            for i in range(source_fields.count()):
                field = source_fields[i]
                if field.name() in fields_to_drop:
                    continue
                memory_layer.addAttribute(field)
                kept_field_names.append(field.name())
            memory_layer.updateFields()

            kept_indexes = [source_fields.indexOf(name) for name in kept_field_names]
            features_to_add: List[QgsFeature] = []
            for feature in features:
                new_feature = QgsFeature(memory_layer.fields())
                geom = feature.geometry()
                if geom and not geom.isNull() and not geom.isEmpty():
                    new_feature.setGeometry(geom)
                new_feature.setAttributes([feature.attribute(idx) for idx in kept_indexes])
                features_to_add.append(new_feature)

            if features_to_add:
                memory_layer.addFeatures(features_to_add)
            memory_layer.commitChanges()
            memory_layer.updateExtents()
            return memory_layer
        except Exception as e:
            print(f"Error building memory layer from features: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _export_layer_with_feature_request(
        self,
        source_layer_id: str,
        output_path: str,
        layer_name: str,
        project: QgsProject,
        filter_expression: Optional[str] = None,
        feature_ids: Optional[List[Any]] = None,
    ) -> bool:
        """
        Export layer features using QgsFeatureRequest without setSubsetString.

        Required for QGIS expressions and for providers (e.g. PostgreSQL) whose
        subset filters are SQL, not expression syntax.
        """
        try:
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer or not isinstance(source_layer, QgsVectorLayer):
                return False

            request = QgsFeatureRequest()
            if feature_ids is not None:
                request.setFilterFids(feature_ids)
            else:
                combined_filter = self._combine_export_filter_expressions(
                    self._get_source_layer_active_filter(source_layer),
                    filter_expression,
                )
                if not combined_filter:
                    return False
                request.setFilterExpression(combined_filter)

            memory_layer = self._build_memory_layer_from_feature_iterator(
                source_layer,
                source_layer.getFeatures(request),
            )
            if memory_layer is None:
                return False

            filtered_count = memory_layer.featureCount()
            print(
                f"[DEBUG] Exporting layer '{layer_name}' via feature request "
                f"({filtered_count} feature(s))"
            )
            if filtered_count == 0:
                return False
            return self._export_memory_layer_to_project(
                memory_layer,
                source_layer,
                output_path,
                layer_name,
                project,
            )
        except Exception as e:
            print(f"Error exporting layer with feature request: {str(e)}")
            return False

    def _create_filtered_layer(self, source_layer_id: str, output_path: str, layer_name: str, 
                             filter_expression: str, project: QgsProject) -> bool:
        """Create a filtered copy of a layer."""
        try:
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer:
                return False

            layer_filter = self._get_source_layer_active_filter(source_layer)
            combined_filter = self._combine_export_filter_expressions(
                layer_filter,
                filter_expression,
            )
            if not combined_filter:
                return False

            layer_uses_expression_filter = (
                not (source_layer.subsetString() or "").strip()
                and bool(layer_filter)
            )
            if (
                self._filter_expression_uses_qgis_syntax(combined_filter)
                or layer_uses_expression_filter
            ):
                return self._export_layer_with_feature_request(
                    source_layer_id,
                    output_path,
                    layer_name,
                    project,
                    filter_expression=filter_expression,
                )

            original_subset = source_layer.subsetString()
            original_filter_expression = ""
            if hasattr(source_layer, "filterExpression"):
                original_filter_expression = source_layer.filterExpression() or ""

            try:
                # Apply SQL-compatible provider subset filter
                source_layer.setSubsetString(combined_filter)
                if hasattr(source_layer, "setFilterExpression"):
                    source_layer.setFilterExpression("")

                # Count features for debug output
                filtered_count = 0
                for feature in source_layer.getFeatures():
                    filtered_count += 1
                print(
                    f"[DEBUG] Filtering layer '{layer_name}' with expression: {combined_filter}"
                )
                print(f"[DEBUG] Number of features after filtering: {filtered_count}")

                # Copy layer
                success = self._copy_layer_to_geopackage(source_layer, output_path, layer_name)
            finally:
                source_layer.setSubsetString(original_subset)
                if hasattr(source_layer, "setFilterExpression"):
                    source_layer.setFilterExpression(original_filter_expression)

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
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer:
                print(f"[DEBUG] Could not get source layer for ID: {source_layer_id}")
                return False
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

    def _parse_unsupported_geopackage_field_error(self, err: Any) -> Optional[str]:
        """
        Extract the field name from a Geopackage writer unsupported-type error.

        Supports English and French QGIS messages.
        """
        try:
            if isinstance(err, (tuple, list)) and len(err) >= 2 and isinstance(err[1], str):
                message = err[1]
            else:
                message = str(err)

            patterns = [
                r"Unsupported type for field\s+([A-Za-z0-9_]+)",
                r"Type non supporté pour le champ\s+([A-Za-z0-9_]+)",
                r"Type non supporte pour le champ\s+([A-Za-z0-9_]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, message, flags=re.IGNORECASE)
                if match:
                    return match.group(1)
            return None
        except Exception:
            return None

    def _collect_non_exportable_field_names(self, source_layer: QgsVectorLayer) -> set:
        """
        Return attribute field names that cannot be written to Geopackage.

        PostgreSQL layers may expose extra geometry-valued columns (e.g. section_geometry)
        that OGR refuses to serialize.
        """
        drop_names = set()
        if not source_layer or not source_layer.isValid():
            return drop_names

        non_exportable_type_names = {
            "geometry",
            "geography",
            "json",
            "jsonb",
            "bytea",
        }
        for field in source_layer.fields():
            field_name = field.name()
            type_name = (field.typeName() or "").lower()
            if type_name in non_exportable_type_names or "geometry" in type_name:
                drop_names.add(field_name)
                continue
            try:
                if hasattr(field, "isGeometryType") and field.isGeometryType():
                    drop_names.add(field_name)
            except Exception:
                pass
        return drop_names

    def _copy_layer_to_geopackage(
        self,
        source_layer,
        output_path,
        layer_name,
        properties_source_layer=None,
    ):
        """Copy a layer to a Geopackage file with preserved forms, styles, and field configurations."""
        try:
            print(f"[DEBUG] _copy_layer_to_geopackage called for layer: {layer_name}")
            from qgis.core import QgsVectorFileWriter
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name

            def _write_layer(layer_to_write: QgsVectorLayer) -> Any:
                """Write with V2 when possible, otherwise classic API."""
                if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV2"):
                    try:
                        return QgsVectorFileWriter.writeAsVectorFormatV2(layer_to_write, output_path, options)
                    except TypeError:
                        # Some QGIS versions expose the method but with a different signature.
                        pass

                return QgsVectorFileWriter.writeAsVectorFormat(
                    layer_to_write, output_path, "UTF-8", layer_to_write.crs(), "GPKG", False, ["layerName=" + layer_name]
                )

            fields_to_drop = self._collect_non_exportable_field_names(source_layer)
            layer_to_write = source_layer
            if fields_to_drop:
                print(
                    f"[DEBUG] Omitting non-exportable field(s) for {layer_name}: "
                    f"{', '.join(sorted(fields_to_drop))}"
                )
                safe_layer = self._create_export_layer_without_fields(source_layer, fields_to_drop)
                if safe_layer is not None:
                    layer_to_write = safe_layer

            error = _write_layer(layer_to_write)
            while True:
                unsupported_field = self._parse_unsupported_geopackage_field_error(error)
                if not unsupported_field:
                    break
                if unsupported_field in fields_to_drop:
                    break
                fields_to_drop.add(unsupported_field)
                print(
                    f"[DEBUG] Detected unsupported attribute type for field "
                    f"'{unsupported_field}', retrying without it"
                )
                safe_layer = self._create_export_layer_without_fields(source_layer, fields_to_drop)
                if safe_layer is None:
                    print(f"[DEBUG] Could not create safe export layer for {layer_name}")
                    return False
                layer_to_write = safe_layer
                error = _write_layer(layer_to_write)

            # Accept both int and tuple return types
            if (isinstance(error, int) and error != QgsVectorFileWriter.NoError) or \
               (isinstance(error, (tuple, list)) and len(error) > 0 and error[0] != QgsVectorFileWriter.NoError):
                # Preserve previous log wording for easier debugging.
                print(f"Error writing layer to Geopackage (classic): {error}")
                return False
            
            # After successful data copy, copy forms, styles, and field configurations
            props_layer = properties_source_layer if properties_source_layer is not None else source_layer
            self._copy_layer_properties_to_geopackage(props_layer, output_path, layer_name)
            return True
        except Exception as e:
            print(f"Error copying layer to Geopackage: {str(e)}")
            return False

    def _create_export_layer_without_fields(self, source_layer: QgsVectorLayer, fields_to_drop: set) -> Optional[QgsVectorLayer]:
        """
        Build a memory layer suitable for vector export.

        Some providers/styles can expose fields with types that OGR/GPKG cannot write
        (e.g. a geometry-valued attribute like 'section_geometry'). For exports, we
        recreate a layer without these fields and copy features over.
        """
        try:
            if not source_layer or not source_layer.isValid():
                return None

            drop_names = {str(name) for name in fields_to_drop if name}
            if not drop_names:
                return source_layer

            wkb_type = source_layer.wkbType()
            geom_string = QgsWkbTypes.displayString(wkb_type)
            crs_string = self._get_crs_string(source_layer.crs())
            export_layer = QgsVectorLayer(f"{geom_string}?crs={crs_string}", "export", "memory")
            if not export_layer.isValid():
                return None

            source_fields = source_layer.fields()
            kept_field_names: List[str] = []
            export_layer.startEditing()
            for i in range(source_fields.count()):
                field = source_fields[i]
                if field.name() in drop_names:
                    continue
                export_layer.addAttribute(field)
                kept_field_names.append(field.name())
            export_layer.updateFields()

            kept_indexes = [source_fields.indexOf(name) for name in kept_field_names]
            new_features: List[QgsFeature] = []
            for feature in source_layer.getFeatures():
                new_feat = QgsFeature(export_layer.fields())
                new_feat.setGeometry(feature.geometry())
                new_feat.setAttributes([feature.attribute(idx) for idx in kept_indexes])
                new_features.append(new_feat)

            export_layer.addFeatures(new_features)
            export_layer.commitChanges()
            return export_layer
        except Exception as e:
            print(f"[DEBUG] Failed to create export-safe layer: {str(e)}")
            return None

    def _copy_layer_structure_to_geopackage(self, source_layer, output_path, layer_name):
        """Copy only the structure of a layer to a Geopackage file (no features) with preserved forms and styles."""
        try:
            print(f"[DEBUG] Creating structure for layer: {layer_name}")
            
            from qgis.core import QgsVectorFileWriter
            
            uri = self._memory_layer_uri_for_vector_layer(source_layer)
            print(f"[DEBUG] Memory layer URI for structure export: {uri}")
            
            temp_layer = QgsVectorLayer(uri, "temp", "memory")
            
            if not temp_layer.isValid():
                print(f"Error: Could not create temporary layer for {layer_name}")
                return False
            
            print(f"[DEBUG] Successfully created temporary memory layer")
            
            # Copy all fields (including virtual fields) with proper field configurations
            temp_layer.startEditing()
            source_fields = source_layer.fields()
            
            # Create a mapping of field names to their configurations
            field_configs = {}
            for i in range(source_fields.count()):
                field_name = source_fields[i].name()
                field_configs[field_name] = {
                    'field': source_fields[i],
                    'editor_widget': source_layer.editorWidgetSetup(i),
                    'default_value': source_layer.defaultValueDefinition(i),
                    'constraints': source_layer.constraints(i) if hasattr(source_layer, 'constraints') else None
                }
            
            # Add fields to temp layer
            for field_name, config in field_configs.items():
                temp_layer.addAttribute(config['field'])
            
            temp_layer.commitChanges()
            
            # Now apply field configurations after the layer is committed
            temp_layer.startEditing()
            for field_name, config in field_configs.items():
                field_idx = temp_layer.fields().indexOf(field_name)
                if field_idx >= 0:
                    # Set editor widget configuration
                    if config['editor_widget'] and hasattr(config['editor_widget'], 'type'):
                        temp_layer.setEditorWidgetSetup(field_idx, config['editor_widget'])
                    
                    # Set default value definition
                    if config['default_value'] and config['default_value'].isValid():
                        temp_layer.setDefaultValueDefinition(field_idx, config['default_value'])
                    
                    # Set field constraints if available
                    if config['constraints'] and hasattr(temp_layer, 'setConstraints'):
                        temp_layer.setConstraints(field_idx, config['constraints'])
            
            temp_layer.commitChanges()

            # Ensure the output directory exists
            import os
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

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
                    
                    print(f"[DEBUG] Successfully created Geopackage structure for {layer_name}")
                    
                    # Verify the Geopackage was created and the layer exists
                    if not os.path.exists(output_path):
                        print(f"Error: Geopackage file was not created: {output_path}")
                        return False
                    
                    # Try to load the layer from the Geopackage to verify it was created correctly
                    test_layer = QgsVectorLayer(f"{output_path}|layername={layer_name}", "test", "ogr")
                    if not test_layer.isValid():
                        # Try alternative loading method
                        test_layer = QgsVectorLayer(output_path, "test", "ogr")
                        if not test_layer.isValid():
                            print(f"Error: Could not load layer from created Geopackage: {output_path}")
                            return False
                    
                    # After successful structure copy, copy forms, styles, and field configurations
                    properties_success = self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
                    if not properties_success:
                        print(f"Warning: Failed to copy properties to Geopackage for {layer_name}, but structure was created")
                        return True  # Return True because the structure was created successfully
                    
                    return True
                except TypeError as e:
                    # Fallback to classic API
                    print(f"[DEBUG] V2 API failed, falling back to classic API for {layer_name}: {str(e)}")
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
            
            print(f"[DEBUG] Successfully created Geopackage structure for {layer_name} (classic API)")
            
            # Verify the Geopackage was created and the layer exists
            if not os.path.exists(output_path):
                print(f"Error: Geopackage file was not created: {output_path}")
                return False
            
            # Try to load the layer from the Geopackage to verify it was created correctly
            test_layer = QgsVectorLayer(f"{output_path}|layername={layer_name}", "test", "ogr")
            if not test_layer.isValid():
                # Try alternative loading method
                test_layer = QgsVectorLayer(output_path, "test", "ogr")
                if not test_layer.isValid():
                    print(f"Error: Could not load layer from created Geopackage: {output_path}")
                    return False
            
            # After successful structure copy, copy forms, styles, and field configurations
            print(f"[DEBUG] About to copy properties to Geopackage for {layer_name}")
            properties_success = self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
            if not properties_success:
                print(f"Warning: Failed to copy properties to Geopackage for {layer_name}, but structure was created")
                return True  # Return True because the structure was created successfully
            
            # Verification step removed for cleaner output
            
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
                # Try alternative loading method
                try:
                    # Try loading with the full path including layer name
                    target_layer = QgsVectorLayer(f"{output_path}|layername={layer_name}", layer_name, "ogr")
                    if not target_layer.isValid():
                        print(f"[DEBUG] Warning: Could not load target layer for property copying: {output_path}")
                        return False
                except Exception as e:
                    print(f"[DEBUG] Warning: Could not load target layer for property copying: {str(e)}")
                    return False
            
            # Copy layer properties using the layer service methods
            self._layer_service._copy_layer_properties(source_layer, target_layer)
            
            # Try to copy QML style with improved method
            qml_success = self._layer_service._copy_qml_style(source_layer, target_layer)
            
            # If QML style copying failed, use renderer fallback
            if not qml_success:
                print(f"[DEBUG] QML style copying failed for {layer_name}, using renderer clone as fallback")
                self._layer_service._copy_renderer_fallback(source_layer, target_layer)
            
            # Force the layer to save its style to the Geopackage
            # Use QML save/load method (most reliable)
            style_saved = False
            
            # Method 1: Save as QML and load back (most reliable)
            try:
                # Save as QML and then load it back
                temp_qml = target_layer.saveNamedStyle("")
                if isinstance(temp_qml, tuple) and len(temp_qml) == 2 and temp_qml[0] and isinstance(temp_qml[1], str):
                    load_result = target_layer.loadNamedStyle(temp_qml[1])
                    if isinstance(load_result, tuple) and load_result[0]:
                        print(f"[DEBUG] Used QML save/load method for {layer_name}")
                        style_saved = True
                    else:
                        print(f"[DEBUG] QML load failed: {load_result[1] if isinstance(load_result, tuple) and len(load_result) > 1 else load_result}")
                else:
                    print(f"[DEBUG] QML save failed: {temp_qml[1] if isinstance(temp_qml, tuple) and len(temp_qml) > 1 else temp_qml}")
            except Exception as e:
                print(f"[DEBUG] QML save/load method failed: {str(e)}")
            
            # Method 2: Save QML file in the same directory as the Geopackage
            # This is the most reliable method and ensures the style is preserved
            if not style_saved:
                try:
                    import os
                    qml_path = os.path.splitext(output_path)[0] + ".qml"
                    save_result = target_layer.saveNamedStyle(qml_path)
                    if isinstance(save_result, tuple) and save_result[0]:
                        print(f"[DEBUG] Saved QML style file: {qml_path}")
                        # Try to load the QML style back to ensure it's properly associated
                        load_result = target_layer.loadNamedStyle(qml_path)
                        if isinstance(load_result, tuple) and load_result[0]:
                            print(f"[DEBUG] Successfully loaded QML style from {qml_path}")
                            style_saved = True
                        else:
                            print(f"[DEBUG] Failed to load QML style from {qml_path}: {load_result[1] if isinstance(load_result, tuple) and len(load_result) > 1 else load_result}")
                    else:
                        print(f"[DEBUG] Failed to save QML style file: {qml_path}: {save_result[1] if isinstance(save_result, tuple) and len(save_result) > 1 else save_result}")
                except Exception as e:
                    print(f"[DEBUG] Error saving QML style file: {str(e)}")
            
            if not style_saved:
                print(f"[DEBUG] Warning: Could not save style to Geopackage for {layer_name}, but layer structure and properties were copied successfully")
            
            # Force the layer to update and save changes
            target_layer.triggerRepaint()
            target_layer.updateExtents()
            
            print(f"Successfully copied forms, styles, and field configurations to {layer_name}")
            return True
            
        except Exception as e:
            print(f"Error copying layer properties to Geopackage: {str(e)}")
            import traceback
            traceback.print_exc()
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

    def _get_relationship_filter_expression_for_ids(
        self,
        layer_id: str,
        recording_areas_layer_id: str,
        recording_area_ids: List[Any],
    ) -> Optional[str]:
        """Build a subset expression for features related to multiple recording areas."""
        if not recording_area_ids:
            return None
        try:
            from qgis.core import QgsProject

            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if not recording_layer:
                return None

            relation_manager = QgsProject.instance().relationManager()
            for relation in relation_manager.relations().values():
                if (
                    relation.referencingLayerId() == layer_id
                    and relation.referencedLayerId() == recording_areas_layer_id
                ):
                    field_pairs = relation.fieldPairs()
                    if not field_pairs:
                        continue
                    referencing_field = list(field_pairs.keys())[0]
                    referenced_field = list(field_pairs.values())[0]
                    referenced_values = self._collect_recording_area_referenced_values(
                        recording_layer,
                        referenced_field,
                        recording_area_ids,
                    )
                    if not referenced_values:
                        return None
                    in_clause = self._format_sql_in_list(referenced_values)
                    return f'"{referencing_field}" IN ({in_clause})'
            return None
        except Exception as e:
            print(f"Error building multi-area relationship filter: {str(e)}")
            return None

    def _collect_recording_area_referenced_values(
        self,
        recording_layer: QgsVectorLayer,
        referenced_field: str,
        recording_area_ids: List[Any],
    ) -> List[Any]:
        """Collect referenced-field values for the given recording-area feature IDs."""
        field_idx = recording_layer.fields().indexOf(referenced_field)
        if field_idx < 0:
            return []
        id_set = set(recording_area_ids)
        values = []
        seen = set()
        for feature in recording_layer.getFeatures():
            if feature.id() not in id_set:
                continue
            value = feature.attribute(field_idx)
            if value is None or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values

    def _format_sql_in_list(self, values: List[Any]) -> str:
        """Format Python values for use in a QgsVectorLayer subset IN clause."""
        formatted = []
        for value in values:
            if isinstance(value, str):
                escaped = str(value).replace("'", "''")
                formatted.append(f"'{escaped}'")
            else:
                formatted.append(str(value))
        return ", ".join(formatted)

    def _build_feature_id_subset_expression(self, feature_ids: List[Any]) -> Optional[str]:
        """Build a QgsVectorLayer subset expression filtering by internal feature IDs."""
        if not feature_ids:
            return None
        return f'$id IN ({self._format_sql_in_list(feature_ids)})'

    def _build_sql_primary_key_in_filter(
        self,
        source_layer: QgsVectorLayer,
        feature_ids: List[Any],
    ) -> Optional[str]:
        """
        Build a provider SQL subset filter on the layer primary key.

        Matches per-zone recording-area export (``id = <feature id>``) but for
        multiple features. Uses the layer's declared primary-key field when available.
        """
        if not feature_ids:
            return None
        pk_fields = source_layer.primaryKeyFields() if hasattr(source_layer, "primaryKeyFields") else []
        if pk_fields:
            field_name = pk_fields[0]
        elif source_layer.fields().indexOf("id") >= 0:
            field_name = "id"
        else:
            return None
        in_clause = self._format_sql_in_list(feature_ids)
        if field_name == "id":
            return f"id IN ({in_clause})"
        return f'"{field_name}" IN ({in_clause})'

    def _build_extent_intersects_subset_expression(
        self,
        extent_geometry: QgsGeometry,
        source_layer: QgsVectorLayer,
        extent_crs_authid: Optional[str] = None,
    ) -> Optional[str]:
        """
        Build a subset expression selecting features intersecting an extent geometry.

        The extent is transformed into the source layer CRS before building the WKT.
        """
        extent_in_layer_crs = self._layer_service.transform_geometry_to_layer_crs(
            extent_geometry,
            source_layer,
            extent_crs_authid,
        )
        if not extent_in_layer_crs or extent_in_layer_crs.isNull() or extent_in_layer_crs.isEmpty():
            return None
        wkt = extent_in_layer_crs.asWkt().replace("'", "''")
        return f"intersects($geometry, geom_from_wkt('{wkt}'))"

    def _export_extra_layer_for_global_project(
        self,
        extra_layer_id: str,
        output_path: str,
        layer_name: str,
        extent_geometry: QgsGeometry,
        project: QgsProject,
        extent_crs_authid: Optional[str] = None,
    ) -> bool:
        """
        Export an extra context layer for a global field project.

        Attribute-only layers (e.g. lookup tables) are copied in full; spatial layers
        are clipped to the project extent.
        """
        if self._layer_service.is_valid_no_geometry_layer(extra_layer_id):
            return self._create_layer_copy(
                extra_layer_id,
                output_path,
                layer_name,
                project,
            )
        return self._create_extent_intersect_layer_copy(
            source_layer_id=extra_layer_id,
            output_path=output_path,
            layer_name=layer_name,
            extent_geometry=extent_geometry,
            project=project,
            extent_crs_authid=extent_crs_authid,
        )

    def _create_global_recording_areas_layer_copy(
        self,
        recording_areas_layer_id: str,
        recording_area_ids: List[Any],
        output_path: str,
        layer_name: str,
        extent_geometry: QgsGeometry,
        project: QgsProject,
        extent_crs_authid: Optional[str] = None,
    ) -> bool:
        """
        Export recording areas intersecting the global extent into the field project.

        Prefer the same SQL subset + direct Geopackage export used for per-zone projects
        (``"id" IN (...)`` on the primary key), then fall back to spatial clipping.
        """
        source_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
        if source_layer and isinstance(source_layer, QgsVectorLayer) and recording_area_ids:
            sql_filter = self._build_sql_primary_key_in_filter(source_layer, recording_area_ids)
            if sql_filter:
                print(
                    f"[DEBUG] Exporting recording areas for {layer_name} "
                    f"with SQL filter: {sql_filter}"
                )
                if self._create_filtered_layer(
                    recording_areas_layer_id,
                    output_path,
                    layer_name,
                    sql_filter,
                    project,
                ):
                    return True
                print(
                    f"[DEBUG] SQL primary-key export failed for {layer_name}, "
                    "trying spatial clip"
                )

        if self._create_extent_intersect_layer_copy(
            source_layer_id=recording_areas_layer_id,
            output_path=output_path,
            layer_name=layer_name,
            extent_geometry=extent_geometry,
            project=project,
            extent_crs_authid=extent_crs_authid,
        ):
            return True

        print(
            f"Warning: Could not export intersecting recording areas for {layer_name}; "
            "creating empty context layer"
        )
        return self._create_empty_layer_copy(
            recording_areas_layer_id,
            output_path,
            layer_name,
            project,
        )

    def _create_extent_intersect_layer_copy(
        self,
        source_layer_id: str,
        output_path: str,
        layer_name: str,
        extent_geometry: QgsGeometry,
        project: QgsProject,
        extent_crs_authid: Optional[str] = None,
    ) -> bool:
        """Export vector features intersecting an extent geometry to Geopackage."""
        try:
            source_layer = self._layer_service.get_layer_by_id(source_layer_id)
            if not source_layer or not isinstance(source_layer, QgsVectorLayer):
                return False

            spatial_filter = self._build_extent_intersects_subset_expression(
                extent_geometry,
                source_layer,
                extent_crs_authid,
            )
            if spatial_filter and self._export_layer_with_feature_request(
                source_layer_id,
                output_path,
                layer_name,
                project,
                filter_expression=spatial_filter,
            ):
                return True
            if spatial_filter:
                print(
                    f"[DEBUG] Spatial feature-request export failed for {layer_name}, "
                    "trying memory-layer path"
                )

            filtered_layer = self._build_memory_layer_with_intersecting_features(
                source_layer,
                extent_geometry,
                extent_crs_authid,
            )
            if filtered_layer is None:
                print(f"[DEBUG] Memory export failed for {layer_name}, trying structure + features fallback")
                return self._create_extent_intersect_layer_copy_fallback(
                    source_layer=source_layer,
                    output_path=output_path,
                    layer_name=layer_name,
                    extent_geometry=extent_geometry,
                    project=project,
                    extent_crs_authid=extent_crs_authid,
                )

            return self._export_memory_layer_to_project(
                filtered_layer,
                source_layer,
                output_path,
                layer_name,
                project,
            )
        except Exception as e:
            print(f"Error creating extent-intersect layer copy: {str(e)}")
            return False

    def _memory_layer_uri_for_vector_layer(self, source_layer: QgsVectorLayer) -> str:
        """Build a memory provider URI compatible with the source layer geometry."""
        crs_string = self._get_crs_string(source_layer.crs())
        wkb_type = source_layer.wkbType()
        geom_string = QgsWkbTypes.displayString(wkb_type)
        memory_layer = QgsVectorLayer(f"{geom_string}?crs={crs_string}", "probe", "memory")
        if memory_layer.isValid():
            return f"{geom_string}?crs={crs_string}"

        geometry_type = source_layer.geometryType()
        if geometry_type == QgsWkbTypes.PointGeometry:
            geom_string = "Point"
        elif geometry_type == QgsWkbTypes.LineGeometry:
            geom_string = "LineString"
        elif geometry_type == QgsWkbTypes.PolygonGeometry:
            geom_string = "MultiPolygon" if QgsWkbTypes.isMultiType(wkb_type) else "Polygon"
        elif geometry_type == QgsWkbTypes.NullGeometry:
            geom_string = "NoGeometry"
        else:
            geom_string = "Polygon"
        return f"{geom_string}?crs={crs_string}"

    def _build_memory_layer_with_intersecting_features(
        self,
        source_layer: QgsVectorLayer,
        extent_geometry: QgsGeometry,
        extent_crs_authid: Optional[str] = None,
    ) -> Optional[QgsVectorLayer]:
        """Create an in-memory layer containing features intersecting the extent."""
        try:
            extent_in_layer_crs = self._layer_service.transform_geometry_to_layer_crs(
                extent_geometry,
                source_layer,
                extent_crs_authid,
            )
            if not extent_in_layer_crs:
                return None

            def _intersecting_features():
                for feature in source_layer.getFeatures():
                    geom = feature.geometry()
                    if not geom or geom.isNull() or geom.isEmpty():
                        continue
                    if geom.intersects(extent_in_layer_crs):
                        yield feature

            return self._build_memory_layer_from_feature_iterator(
                source_layer,
                _intersecting_features(),
            )
        except Exception as e:
            print(f"Error building filtered memory layer: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _create_extent_intersect_layer_copy_fallback(
        self,
        source_layer: QgsVectorLayer,
        output_path: str,
        layer_name: str,
        extent_geometry: QgsGeometry,
        project: QgsProject,
        extent_crs_authid: Optional[str] = None,
    ) -> bool:
        """
        Fallback export when the memory-layer path fails.

        Writes layer structure to GPKG then appends intersecting features directly.
        """
        try:
            if not self._copy_layer_structure_to_geopackage(source_layer, output_path, layer_name):
                return False

            extent_in_layer_crs = self._layer_service.transform_geometry_to_layer_crs(
                extent_geometry,
                source_layer,
                extent_crs_authid,
            )
            if not extent_in_layer_crs:
                layer = QgsVectorLayer(output_path, layer_name, "ogr")
                if layer.isValid():
                    project.addMapLayer(layer)
                    return True
                return False

            target_layer = QgsVectorLayer(output_path, layer_name, "ogr")
            if not target_layer.isValid():
                return False

            target_layer.startEditing()
            added = 0
            for feature in source_layer.getFeatures():
                geom = feature.geometry()
                if not geom or geom.isNull() or geom.isEmpty():
                    continue
                if not geom.intersects(extent_in_layer_crs):
                    continue
                new_feature = QgsFeature(target_layer.fields())
                new_feature.setGeometry(geom)
                for field_name in feature.fields().names():
                    if field_name in target_layer.fields().names():
                        new_feature[field_name] = feature[field_name]
                if target_layer.addFeature(new_feature):
                    added += 1
            target_layer.commitChanges()
            self._copy_layer_properties_to_geopackage(source_layer, output_path, layer_name)
            project.addMapLayer(target_layer)
            print(f"[DEBUG] Fallback export added {added} feature(s) to {layer_name}")
            return True
        except Exception as e:
            print(f"Error in extent intersect fallback export: {str(e)}")
            return False

    def _create_alternative_objects_layer_copy(
        self,
        source_layer_id: str,
        recording_areas_layer_id: str,
        recording_area_ids: List[Any],
        output_path: str,
        layer_name: str,
        project: QgsProject,
    ) -> bool:
        """Export alternative objects rows linked to recording areas within the extent."""
        try:
            filter_expression = self._get_relationship_filter_expression_for_ids(
                source_layer_id,
                recording_areas_layer_id,
                recording_area_ids,
            )
            if not filter_expression:
                recording_field = self._settings_manager.get_value(
                    'alternative_objects_recording_area_field',
                    '',
                )
                if recording_field and recording_area_ids:
                    in_clause = self._format_sql_in_list(recording_area_ids)
                    filter_expression = f'"{recording_field}" IN ({in_clause})'

            if filter_expression:
                return self._create_filtered_layer(
                    source_layer_id=source_layer_id,
                    output_path=output_path,
                    layer_name=layer_name,
                    filter_expression=filter_expression,
                    project=project,
                )

            return self._create_layer_copy(
                source_layer_id=source_layer_id,
                output_path=output_path,
                layer_name=layer_name,
                project=project,
            )
        except Exception as e:
            print(f"Error creating alternative objects layer copy: {str(e)}")
            return False

    def _apply_readonly_layers_in_project(
        self,
        project: QgsProject,
        readonly_source_layer_ids: List[str],
        source_to_target_layer_ids: Dict[str, str],
    ) -> None:
        """Mark exported context layers as read-only in the generated project."""
        for source_layer_id in readonly_source_layer_ids:
            target_layer_id = source_to_target_layer_ids.get(source_layer_id)
            if not target_layer_id:
                continue
            target_layer = project.mapLayer(target_layer_id)
            if isinstance(target_layer, QgsVectorLayer):
                target_layer.setReadOnly(True)
                target_layer.setCustomProperty("archeosync/readonly", True)

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

    def _create_recording_area_bookmark(
        self,
        project: QgsProject,
        feature_data: Dict[str, Any],
        recording_area_name: str,
        map_rotation: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a bookmark for the recording area and configure the initial map view.

        The bookmark extent is also written as the project's default view extent so
        the field project opens zoomed on the recording area. The map rotation is
        taken from the main project canvas when provided.

        Returns:
            Payload used to inject ``mapcanvas`` view state into the saved .qgs file.
        """
        try:
            # Get the geometry as a QgsGeometry object
            geometry_wkt = feature_data['geometry_wkt']
            geom = QgsGeometry.fromWkt(geometry_wkt)

            # Get the project CRS
            project_crs = project.crs()
            
            # Import bookmark classes lazily for forward compatibility.
            # Some QGIS versions may expose bookmark APIs differently.
            try:
                from qgis.core import QgsBookmark, QgsReferencedRectangle
            except ImportError:
                print("Bookmark API not available in this QGIS version, skipping bookmark creation.")
                return None

            # Create a referenced rectangle with the project CRS
            bounding_box = geom.boundingBox()
            referenced_rect = QgsReferencedRectangle(bounding_box, project_crs)

            # Create a new bookmark
            bookmark = QgsBookmark()
            bookmark.setName(recording_area_name)
            bookmark.setExtent(referenced_rect)
            if hasattr(bookmark, 'setRotation'):
                bookmark.setRotation(map_rotation)
            # Add the bookmark to the project's bookmark manager
            project.bookmarkManager().addBookmark(bookmark)
            self._set_recording_area_initial_map_view(project, referenced_rect, map_rotation)
            print(f"Created bookmark for {recording_area_name} with extent: {bounding_box}")
            return {
                'xmin': bounding_box.xMinimum(),
                'ymin': bounding_box.yMinimum(),
                'xmax': bounding_box.xMaximum(),
                'ymax': bounding_box.yMaximum(),
                'rotation': map_rotation,
                'map_units': self._map_units_label_for_crs(project_crs),
            }
        except Exception as e:
            print(f"Error creating recording area bookmark: {str(e)}")
            return None

    def _set_recording_area_initial_map_view(
        self,
        project: QgsProject,
        referenced_rect: Any,
        map_rotation: float = 0.0,
    ) -> None:
        """Set default view extent and rotation for first project open."""
        view_settings_factory = getattr(project, 'viewSettings', None)
        if not callable(view_settings_factory):
            return
        try:
            view_settings = view_settings_factory()
            view_settings.setDefaultViewExtent(referenced_rect)
            view_settings.setDefaultRotation(map_rotation)
            if hasattr(view_settings, 'setRestoreProjectExtentOnProjectLoad'):
                view_settings.setRestoreProjectExtentOnProjectLoad(False)
        except Exception as e:
            print(f"Error setting initial map view for recording area project: {str(e)}")

 