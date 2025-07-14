"""
QField service implementation for ArcheoSync plugin.

This module provides a concrete implementation of the IQFieldService interface
for handling QField operations and integration with the QFieldSync plugin.

Key Features:
- QFieldSync plugin integration
- QField project packaging
- Layer configuration for QField projects
- Background image clipping to recording areas
- Error handling and validation

Usage:
    qfield_service = QGISQFieldService(settings_manager, layer_service)
    
    if qfield_service.is_qfield_enabled():
        success = qfield_service.package_for_qfield(
            recording_area_feature=feature,
            recording_areas_layer_id='layer_id',
            objects_layer_id='objects_layer_id',
            features_layer_id='features_layer_id',
            background_layer_id='background_layer_id',
            destination_folder='/path/to/destination',
            project_name='Recording_Area_1'
        )

The service provides:
- Automatic QFieldSync plugin detection
- Layer configuration for QField projects
- Background image processing
- Project packaging and export
- Comprehensive error handling
"""

import os
from typing import Optional, Any, Dict, List
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry, QgsWkbTypes
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QColor

try:
    from ..core.interfaces import IQFieldService, ISettingsManager, ILayerService, ValidationResult
except ImportError:
    from core.interfaces import IQFieldService, ISettingsManager, ILayerService, ValidationResult

# QFieldSync packaging imports
try:
    from libqfieldsync.offline_converter import OfflineConverter, ExportType, PackagingCanceledException
    from libqfieldsync.offliners import QgisCoreOffliner
except ImportError:
    OfflineConverter = None
    ExportType = None
    QgisCoreOffliner = None

class QGISQFieldService(IQFieldService):
    """
    QGIS-specific implementation of QField operations using QFieldSync's libqfieldsync.
    """
    def __init__(self, settings_manager: ISettingsManager, layer_service: ILayerService, file_system_service: Optional[Any] = None, raster_processing_service: Optional[Any] = None):
        """
        Initialize the QField service.
        
        Args:
            settings_manager: Service for managing settings
            layer_service: Service for layer operations
            file_system_service: Service for file system operations (optional)
            raster_processing_service: Service for raster processing operations (optional)
        """
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._file_system_service = file_system_service
        self._raster_processing_service = raster_processing_service
        
        # Check if QFieldSync is available
        self._qfieldsync_available = self._check_qfieldsync_availability()

    def _check_qfieldsync_availability(self) -> bool:
        """
        Check if QFieldSync (libqfieldsync) is available in the QGIS environment.
        """
        return OfflineConverter is not None and QgisCoreOffliner is not None

    def is_qfield_enabled(self) -> bool:
        return self._settings_manager.get_value('use_qfield', False)

    def get_qfieldsync_plugin(self) -> Optional[Any]:
        """Get the QFieldSync plugin instance if available."""
        try:
            from qgis.core import QgsApplication
            iface = QgsApplication.instance().interface()
            if iface:
                # Try to get QFieldSync plugin from QGIS plugin manager
                from qgis.utils import plugins
                if 'qfieldsync' in plugins:
                    return plugins['qfieldsync']
        except Exception as e:
            print(f"Error getting QFieldSync plugin: {str(e)}")
        return None
    
    def import_qfield_projects(self, project_paths: List[str]) -> ValidationResult:
        """
        Import QField projects and collect Objects and Features layers from data.gpkg files.
        
        Args:
            project_paths: List of paths to QField project directories
            
        Returns:
            ValidationResult with success status and message
        """
        try:
            if not project_paths:
                return ValidationResult(False, "No project paths provided")
            
            # Collect all Objects and Features layers from all projects
            all_objects_features = []
            all_features_features = []
            
            for project_path in project_paths:
                # Check if project path exists and contains data.gpkg
                data_gpkg_path = os.path.join(project_path, "data.gpkg")
                if not os.path.exists(data_gpkg_path):
                    print(f"Warning: data.gpkg not found in {project_path}")
                    continue
                
                # Load the data.gpkg file
                data_layer = QgsVectorLayer(data_gpkg_path, "temp_data", "ogr")
                if not data_layer.isValid():
                    print(f"Warning: Could not load data.gpkg from {project_path}")
                    continue
                
                # Get all sublayers from the data.gpkg
                sublayers = data_layer.dataProvider().subLayers()
                
                for sublayer in sublayers:
                    # Parse sublayer info to get layer name and path
                    layer_info = sublayer.split('!!::!!')
                    if len(layer_info) >= 2:
                        layer_name = layer_info[1]  # Layer name is the second part
                        layer_path = f"{data_gpkg_path}|layername={layer_name}"
                        
                        # Load the sublayer
                        sublayer_obj = QgsVectorLayer(layer_path, layer_name, "ogr")
                        if not sublayer_obj.isValid():
                            continue
                        
                        # Check if this is an Objects or Features layer (prefix match, case-insensitive)
                        lname = layer_name.lower()
                        if lname.startswith("objects"):
                            # Collect all features from Objects layer
                            for feature in sublayer_obj.getFeatures():
                                all_objects_features.append(feature)
                        elif lname.startswith("features"):
                            # Collect all features from Features layer
                            for feature in sublayer_obj.getFeatures():
                                all_features_features.append(feature)
            
            # Create merged layers if we have data
            success_count = 0
            error_count = 0
            
            if all_objects_features:
                success = self._create_merged_layer("New Objects", all_objects_features)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            
            if all_features_features:
                success = self._create_merged_layer("New Features", all_features_features)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            
            if success_count == 0 and error_count == 0:
                return ValidationResult(False, "No Objects or Features layers found in the selected QField projects")
            
            # Archive QField projects if archive folder is configured
            if self._file_system_service:
                self._archive_qfield_projects(project_paths)
            
            message = f"Successfully imported {success_count} layer(s)"
            if error_count > 0:
                message += f" with {error_count} error(s)"
            
            return ValidationResult(True, message)
            
        except Exception as e:
            return ValidationResult(False, f"Error importing QField projects: {str(e)}")
    
    def _archive_qfield_projects(self, project_paths: List[str]) -> None:
        """
        Move imported QField projects to the archive folder.
        
        Args:
            project_paths: List of QField project paths to archive
        """
        try:
            # Get archive folder from settings
            archive_folder = self._settings_manager.get_value('qfield_archive_folder', '')
            if not archive_folder:
                return  # No archive folder configured
            
            # Create archive folder if it doesn't exist
            if not self._file_system_service.path_exists(archive_folder):
                if not self._file_system_service.create_directory(archive_folder):
                    print(f"Warning: Could not create QField archive folder: {archive_folder}")
                    return
            
            # Move each QField project to archive
            for project_path in project_paths:
                if self._file_system_service.path_exists(project_path):
                    project_name = os.path.basename(project_path)
                    archive_path = os.path.join(archive_folder, project_name)
                    
                    if self._file_system_service.move_directory(project_path, archive_path):
                        print(f"Archived QField project: {project_name}")
                    else:
                        print(f"Warning: Could not archive QField project: {project_name}")
                        
        except Exception as e:
            print(f"Error archiving QField projects: {str(e)}")
    
    def _create_merged_layer(self, layer_name: str, features: List[QgsFeature]) -> bool:
        """
        Create a merged layer from a list of features.
        
        Args:
            layer_name: Name for the new layer
            features: List of features to merge
            
        Returns:
            True if layer was created successfully, False otherwise
        """
        try:
            if not features:
                return False
            
            # Get the first feature to determine geometry type and fields
            first_feature = features[0]
            geometry_type = first_feature.geometry().type()
            
            # Use the current project CRS
            project_crs = QgsProject.instance().crs().authid()
            
            # Create memory layer with same structure
            if geometry_type == QgsWkbTypes.PointGeometry:
                layer_uri = f"Point?crs={project_crs}"
            elif geometry_type == QgsWkbTypes.LineGeometry:
                layer_uri = f"LineString?crs={project_crs}"
            elif geometry_type == QgsWkbTypes.PolygonGeometry:
                layer_uri = f"Polygon?crs={project_crs}"
            else:
                layer_uri = f"Point?crs={project_crs}"  # Default to point
            
            # Add fields from the first feature
            fields = first_feature.fields()
            for field in fields:
                layer_uri += f"&field={field.name()}:{field.typeName()}"
            
            # Create the layer
            merged_layer = QgsVectorLayer(layer_uri, layer_name, "memory")
            if not merged_layer.isValid():
                return False
            
            # Add features to the layer
            merged_layer.startEditing()
            for feature in features:
                merged_layer.addFeature(feature)
            merged_layer.commitChanges()
            
            # Add layer to project
            QgsProject.instance().addMapLayer(merged_layer)
            
            return True
            
        except Exception as e:
            print(f"Error creating merged layer {layer_name}: {str(e)}")
            return False

    def package_for_qfield(self, 
                          recording_area_feature: Any,
                          recording_areas_layer_id: str,
                          objects_layer_id: str,
                          features_layer_id: Optional[str],
                          background_layer_id: Optional[str],
                          extra_layers: Optional[List[str]] = None,
                          destination_folder: str = "",
                          project_name: str = "") -> bool:
        """
        Package a QField project for a specific recording area using QFieldSync's OfflineConverter.
        Creates empty objects and features layers for offline editing in QField.
        """
        try:
            if not self._qfieldsync_available:
                raise RuntimeError("QFieldSync (libqfieldsync) is not available")
            if not recording_area_feature or not recording_areas_layer_id or not objects_layer_id:
                raise ValueError("Required parameters are missing")
            if not destination_folder or not project_name:
                raise ValueError("Destination folder and project name are required")

            # Extract geometry data early to avoid issues with deleted QGIS objects
            area_of_interest = None
            area_of_interest_crs = None
            if hasattr(recording_area_feature, 'geometry') and recording_area_feature.geometry():
                geom = recording_area_feature.geometry()
                if geom and not geom.isNull():
                    # Extract geometry as WKT immediately to avoid reference issues
                    area_of_interest = geom.asWkt()
                    # Get CRS from current project
                    area_of_interest_crs = QgsProject.instance().crs().authid()

            # Prepare output directory and project file
            project_dir = os.path.join(destination_folder, project_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)
            project_file = os.path.join(project_dir, f"{project_name}_qfield.qgs")

            # Work with the original project and configure QFieldSync layer settings
            original_project = QgsProject.instance()
            
            # Store original layer configurations to restore later
            original_layer_configs = {}
            
            # Store created empty layers to remove later
            created_empty_layers = []
            
            try:
                # Use original layers directly for offline editing (no need to create copies)
                empty_objects_layer_id = objects_layer_id
                print(f"Using original objects layer directly: {empty_objects_layer_id}")
                
                # Use original features layer directly if features layer is configured
                empty_features_layer_id = None
                if features_layer_id:
                    empty_features_layer_id = features_layer_id
                    print(f"Using original features layer directly: {empty_features_layer_id}")
                
                # Configure QFieldSync layer settings for all layers
                for layer in original_project.mapLayers().values():
                    try:
                        from libqfieldsync.layer import LayerSource, SyncAction
                        layer_source = LayerSource(layer, original_project)
                        # Store original configuration
                        original_layer_configs[layer.id()] = {
                            'action': layer_source.action,
                            'cloud_action': layer_source.cloud_action
                        }
                        # Default: REMOVE
                        layer_source.action = SyncAction.REMOVE
                        layer_source.cloud_action = SyncAction.REMOVE
                        # 1. Empty objects layer: OFFLINE (editable)
                        if empty_objects_layer_id and layer.id() == empty_objects_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        # 2. Empty features layer: OFFLINE (editable)
                        elif empty_features_layer_id and layer.id() == empty_features_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        # 3. Original objects/features layers: REMOVE
                        elif layer.id() == objects_layer_id or (features_layer_id and layer.id() == features_layer_id):
                            layer_source.action = SyncAction.REMOVE
                            layer_source.cloud_action = SyncAction.REMOVE
                        # 4. Recording areas layer: COPY (read-only)
                        elif layer.id() == recording_areas_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 5. Background raster: COPY (read-only) if selected
                        elif background_layer_id and layer.id() == background_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 6. Extra layers: COPY (read-only)
                        elif extra_layers and layer.id() in extra_layers:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 7. All others: REMOVE (already set by default)
                        layer_source.apply()
                    except ImportError:
                        print("Warning: Could not import LayerSource from libqfieldsync")
                    except Exception as e:
                        print(f"Warning: Could not configure layer {layer.name()}: {str(e)}")
                
                if not area_of_interest:
                    # fallback: use original project extent or create default
                    try:
                        # Try to get extent from original project's map canvas
                        from qgis.core import QgsApplication
                        iface = QgsApplication.instance().interface()
                        if iface and iface.mapCanvas():
                            area_of_interest = iface.mapCanvas().extent().asWktPolygon()
                        else:
                            # Create a default extent
                            from qgis.core import QgsRectangle
                            area_of_interest = QgsRectangle(-180, -90, 180, 90).asWktPolygon()
                    except:
                        # Last resort: create a default extent
                        from qgis.core import QgsRectangle
                        area_of_interest = QgsRectangle(-180, -90, 180, 90).asWktPolygon()
                    area_of_interest_crs = original_project.crs().authid()

                # Attachments and dirs to copy (not used in this minimal example)
                attachment_dirs = []  # Empty list instead of None
                dirs_to_copy = {}     # Empty dict instead of list - should be Dict[str, bool]
                export_title = project_name

                # Use QgisCoreOffliner for offline editing
                offliner = QgisCoreOffliner(offline_editing=False)

                # Validate that we have all required data before proceeding
                if not area_of_interest:
                    print(f"Warning: No area of interest found for {project_name}, using fallback extent")

                # Call the packaging logic with the original project
                success = self._package_with_offline_converter(
                    original_project,
                    project_file,
                    area_of_interest,
                    area_of_interest_crs,
                    attachment_dirs,
                    offliner,
                    ExportType.Cable,
                    dirs_to_copy,
                    export_title,
                    recording_area_feature.id() if hasattr(recording_area_feature, 'id') else None,
                    recording_areas_layer_id,
                    extra_layers,
                    objects_layer_id,
                    features_layer_id
                )
                
                return success
                
            finally:
                # Restore original layer configurations
                for layer_id, config in original_layer_configs.items():
                    try:
                        layer = original_project.mapLayer(layer_id)
                        if layer:
                            from libqfieldsync.layer import LayerSource
                            layer_source = LayerSource(layer, original_project)
                            layer_source.action = config['action']
                            layer_source.cloud_action = config['cloud_action']
                            layer_source.apply()
                    except Exception as e:
                        print(f"Warning: Could not restore layer configuration for {layer_id}: {str(e)}")
                
                # Remove the created empty layers from the main QGIS project
                # Note: These layers must remain in the project during QFieldSync packaging
                # They will be removed after the packaging is complete
                for layer_id in created_empty_layers:
                    try:
                        if self._layer_service.remove_layer_from_project(layer_id):
                            print(f"Removed empty layer: {layer_id}")
                        else:
                            print(f"Warning: Could not remove empty layer: {layer_id}")
                    except Exception as e:
                        print(f"Error removing empty layer {layer_id}: {str(e)}")
                        
        except Exception as e:
            print(f"Error packaging QField project for {project_name}: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _package_with_offline_converter(self, project, project_file, area_of_interest, area_of_interest_crs, attachment_dirs, offliner, export_type, dirs_to_copy, export_title, selected_feature_id=None, recording_areas_layer_id=None, extra_layers=None, objects_layer_id=None, features_layer_id=None) -> bool:
        """
        Use QFieldSync's OfflineConverter to package the project.
        """
        try:
            print(f"DEBUG: Starting _package_with_offline_converter")
            print(f"DEBUG: project type: {type(project)}")
            print(f"DEBUG: project_file type: {type(project_file)}")
            print(f"DEBUG: area_of_interest type: {type(area_of_interest)}")
            print(f"DEBUG: area_of_interest_crs type: {type(area_of_interest_crs)}")
            print(f"DEBUG: attachment_dirs type: {type(attachment_dirs)}")
            print(f"DEBUG: offliner type: {type(offliner)}")
            print(f"DEBUG: export_type type: {type(export_type)}")
            print(f"DEBUG: dirs_to_copy type: {type(dirs_to_copy)}")
            print(f"DEBUG: export_title type: {type(export_title)}")
            print(f"DEBUG: selected_feature_id: {selected_feature_id}")
            print(f"DEBUG: recording_areas_layer_id: {recording_areas_layer_id}")
            print(f"DEBUG: extra_layers: {extra_layers}")
            
            # Store references to original layers that will be used directly in QField project
            original_layers_to_clear = {}
            print(f"DEBUG: Creating original_layers_to_clear dictionary")
            
            # Find the objects and features layers by their IDs
            objects_layer = project.mapLayer(objects_layer_id) if objects_layer_id else None
            features_layer = project.mapLayer(features_layer_id) if features_layer_id else None
            
            if objects_layer:
                original_layers_to_clear[objects_layer.name()] = objects_layer
                print(f"DEBUG: Added objects layer '{objects_layer.name()}' (ID: {objects_layer_id}) to original_layers_to_clear")
            
            if features_layer:
                original_layers_to_clear[features_layer.name()] = features_layer
                print(f"DEBUG: Added features layer '{features_layer.name()}' (ID: {features_layer_id}) to original_layers_to_clear")
            
            print(f"DEBUG: original_layers_to_clear keys: {list(original_layers_to_clear.keys())}")
            print(f"DEBUG: original_layers_to_clear type: {type(original_layers_to_clear)}")
            
            # Verify original layers are found
            for layer_name, layer in original_layers_to_clear.items():
                print(f"DEBUG: Found original layer for {layer_name}")
                if layer.renderer():
                    print(f"DEBUG: {layer_name} has renderer: {type(layer.renderer())}")
                else:
                    print(f"DEBUG: {layer_name} has no renderer")
            
            # Create the converter with proper parameters
            # Following the QFieldSync pattern from package_dialog.py
            print(f"DEBUG: Creating OfflineConverter")
            converter = OfflineConverter(
                project,
                project_file,
                area_of_interest,
                area_of_interest_crs,
                attachment_dirs,
                offliner,
                export_type,
                create_basemap=True,
                dirs_to_copy=dirs_to_copy,
                export_title=export_title
            )
            
            # Run the conversion
            print(f"DEBUG: Running converter.convert()")
            success = converter.convert()
            print(f"DEBUG: converter.convert() returned: {success}")
            print(f"DEBUG: converter.convert() type: {type(success)}")
            if success is None:
                print(f"DEBUG: converter.convert() returned None, treating as success")
                success = True
            
            if success:
                # Clear data from original layers in the QField project
                print(f"DEBUG: Calling _clear_data_from_original_layers")
                self._clear_data_from_original_layers(project_file, original_layers_to_clear)
                
                # Filter recording area layer to only include the selected feature
                if selected_feature_id is not None and recording_areas_layer_id is not None:
                    print(f"DEBUG: Calling _filter_recording_area_layer")
                    self._filter_recording_area_layer(project_file, selected_feature_id, recording_areas_layer_id)
                # Filter extra layers if needed
                if selected_feature_id is not None and recording_areas_layer_id is not None and extra_layers:
                    print(f"DEBUG: Calling _filter_related_extra_layers")
                    self._filter_related_extra_layers(project_file, selected_feature_id, recording_areas_layer_id, extra_layers)
            else:
                print(f"DEBUG: Converter.convert() returned False, skipping data clearing")
            
            return success
            
        except Exception as e:
            print(f"Error in _package_with_offline_converter: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _clear_data_from_original_layers(self, project_file: str, original_layers_to_clear: Dict[str, QgsVectorLayer]) -> None:
        """
        Clear data from original layers in the QField project while preserving symbology.
        This method removes all features from the original layers that were used directly
        in the QField project, keeping their symbology, form configuration, and field properties.
        """
        try:
            print(f"DEBUG: Starting data clearing from original layers")
            print(f"DEBUG: Project file: {project_file}")
            print(f"DEBUG: Original layers to clear: {list(original_layers_to_clear.keys())}")
            
            # Load the QField project
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                print(f"DEBUG: Could not read QField project file: {project_file}")
                return
            
            print(f"DEBUG: Successfully loaded QField project with {len(qfield_project.mapLayers())} layers")
            
            # Find and clear data from the original layers in the project
            for layer in qfield_project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    layer_name = layer.name()
                    layer_id = layer.id()
                    print(f"DEBUG: Checking layer: {layer_name} (ID: {layer_id})")
                    
                    # Check if this is one of our original layers by name or by checking if it's an offline layer
                    should_clear = False
                    clear_reason = ""
                    
                    # First, check by exact name match
                    if layer_name in original_layers_to_clear:
                        should_clear = True
                        clear_reason = "exact name match"
                    # Second, check if this is an offline layer (which would be our objects/features layers)
                    elif layer.customProperty("qfieldsync/is_offline_editable"):
                        should_clear = True
                        clear_reason = "offline editable layer"
                    # Third, check by layer name patterns (case-insensitive)
                    elif any(name.lower() in layer_name.lower() for name in ["objects", "objets", "features", "fugaces"]):
                        should_clear = True
                        clear_reason = "name pattern match"
                    
                    if should_clear:
                        print(f"DEBUG: Found layer to clear: {layer_name} (reason: {clear_reason})")
                        
                        # Start editing
                        layer.startEditing()
                        
                        # Get all feature IDs
                        feature_ids = [f.id() for f in layer.getFeatures()]
                        print(f"DEBUG: Found {len(feature_ids)} features to delete in {layer_name}")
                        
                        # Delete all features
                        if feature_ids:
                            success = layer.deleteFeatures(feature_ids)
                            if success:
                                print(f"DEBUG: Successfully deleted {len(feature_ids)} features from {layer_name}")
                            else:
                                print(f"DEBUG: Failed to delete features from {layer_name}")
                        
                        # Commit changes
                        if layer.commitChanges():
                            print(f"DEBUG: Successfully committed changes to {layer_name}")
                        else:
                            print(f"DEBUG: Failed to commit changes to {layer_name}")
                            layer.rollBack()
                    else:
                        print(f"DEBUG: Skipping layer {layer_name} (not identified for clearing)")
            
            # Save the updated project
            print(f"DEBUG: Saving updated QField project...")
            if qfield_project.write(project_file):
                print(f"DEBUG: Successfully saved updated QField project")
            else:
                print(f"DEBUG: Failed to save updated QField project")
            
        except Exception as e:
            print(f"DEBUG: Error clearing data from original layers: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _apply_symbology_to_project_file(self, project_file: str, symbology_data: Dict[str, Dict[str, Any]]) -> None:
        """
        Apply symbology directly to the project file by loading it and updating the layers.
        This is an alternative approach to ensure symbology is preserved.
        """
        try:
            print(f"DEBUG: Starting project file symbology application")
            print(f"DEBUG: Project file: {project_file}")
            
            # Load the QField project
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                print(f"DEBUG: Could not read QField project file: {project_file}")
                return
            
            print(f"DEBUG: Successfully loaded QField project with {len(qfield_project.mapLayers())} layers")
            
            # Find and update the offline layers in the project
            for layer in qfield_project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    layer_name = layer.name().lower()
                    print(f"DEBUG: Checking layer: {layer.name()} (lowercase: {layer_name})")
                    
                    # Check if this is an Objects or Features layer
                    if layer_name.startswith("objects") and "Objects" in symbology_data:
                        print(f"DEBUG: Applying symbology to project Objects layer: {layer.name()}")
                        self._apply_symbology_from_data(layer, symbology_data["Objects"])
                    elif layer_name.startswith("features") and "Features" in symbology_data:
                        print(f"DEBUG: Applying symbology to project Features layer: {layer.name()}")
                        self._apply_symbology_from_data(layer, symbology_data["Features"])
            
            # Save the updated project
            print(f"DEBUG: Saving updated project file...")
            if qfield_project.write(project_file):
                print(f"DEBUG: Successfully saved updated project file")
            else:
                print(f"DEBUG: Failed to save updated project file")
                
        except Exception as e:
            print(f"DEBUG: Error applying symbology to project file: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _extract_layer_symbology(self, layer: QgsVectorLayer) -> Dict[str, Any]:
        """
        Extract symbology information from a layer and store it in a format that can be preserved.
        This avoids issues with C++ object deletion.
        """
        try:
            symbology_data = {}
            
            # Extract renderer information
            if layer.renderer():
                renderer = layer.renderer()
                symbology_data['renderer_type'] = renderer.type()
                
                # For single symbol renderer, extract symbol information
                if renderer.type() == 'singleSymbol':
                    symbol = renderer.symbol()
                    if symbol:
                        symbology_data['symbol'] = {
                            'type': symbol.symbolLayer(0).layerType() if symbol.symbolLayerCount() > 0 else 'SimpleMarker',
                            'color': symbol.color().name(),
                            'outline_color': symbol.symbolLayer(0).strokeColor().name() if symbol.symbolLayerCount() > 0 else '',
                            'outline_width': symbol.symbolLayer(0).strokeWidth() if symbol.symbolLayerCount() > 0 else 0,
                            'size': symbol.symbolLayer(0).size() if symbol.symbolLayerCount() > 0 else 1
                        }
            
            # Extract form configuration
            form_config = layer.editFormConfig()
            symbology_data['form_config'] = {
                'layout': form_config.layout(),
                'suppress_form': form_config.suppress()
            }
            
            # Extract field configurations
            fields_data = {}
            for i in range(layer.fields().count()):
                field = layer.fields().field(i)
                field_data = {
                    'name': field.name(),
                    'type': field.type(),
                    'type_name': field.typeName(),
                    'length': field.length(),
                    'precision': field.precision(),
                    'comment': field.comment(),
                    'alias': field.alias()
                }
                
                # Extract editor widget setup
                editor_widget = layer.editorWidgetSetup(i)
                if editor_widget.type() != 'Hidden':
                    field_data['editor_widget'] = {
                        'type': editor_widget.type(),
                        'config': editor_widget.config()
                    }
                
                # Extract default value definition
                default_value = layer.defaultValueDefinition(i)
                if default_value:
                    field_data['default_value'] = {
                        'expression': default_value.expression(),
                        'apply_on_update': default_value.applyOnUpdate()
                    }
                
                fields_data[field.name()] = field_data
            
            symbology_data['fields'] = fields_data
            
            print(f"DEBUG: Extracted symbology data for {layer.name()}")
            return symbology_data
            
        except Exception as e:
            print(f"DEBUG: Error extracting symbology from {layer.name()}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}

    def _apply_symbology_from_data(self, target_layer: QgsVectorLayer, symbology_data: Dict[str, Any]) -> None:
        """
        Apply symbology from extracted data to a target layer.
        This avoids issues with C++ object deletion.
        """
        try:
            print(f"DEBUG: Applying symbology data to {target_layer.name()}")
            
            # Apply renderer
            if 'renderer_type' in symbology_data and symbology_data['renderer_type'] == 'singleSymbol':
                if 'symbol' in symbology_data:
                    symbol_data = symbology_data['symbol']
                    
                    # Create symbol based on type
                    if symbol_data['type'] == 'SimpleFill':
                        from qgis.core import QgsSimpleFillSymbolLayer, QgsFillSymbol
                        symbol_layer = QgsSimpleFillSymbolLayer()
                        symbol_layer.setColor(QColor(symbol_data['color']))
                        symbol_layer.setStrokeColor(QColor(symbol_data['outline_color']))
                        symbol_layer.setStrokeWidth(symbol_data['outline_width'])
                        symbol = QgsFillSymbol([symbol_layer])
                    elif symbol_data['type'] == 'SimpleMarker':
                        from qgis.core import QgsSimpleMarkerSymbolLayer, QgsMarkerSymbol
                        symbol_layer = QgsSimpleMarkerSymbolLayer()
                        symbol_layer.setColor(QColor(symbol_data['color']))
                        symbol_layer.setStrokeColor(QColor(symbol_data['outline_color']))
                        symbol_layer.setStrokeWidth(symbol_data['outline_width'])
                        symbol_layer.setSize(symbol_data['size'])
                        symbol = QgsMarkerSymbol([symbol_layer])
                    else:
                        # Default to simple fill for polygons
                        from qgis.core import QgsSimpleFillSymbolLayer, QgsFillSymbol
                        symbol_layer = QgsSimpleFillSymbolLayer()
                        symbol_layer.setColor(QColor(symbol_data['color']))
                        symbol = QgsFillSymbol([symbol_layer])
                    
                    # Create renderer and apply
                    from qgis.core import QgsSingleSymbolRenderer
                    renderer = QgsSingleSymbolRenderer(symbol)
                    target_layer.setRenderer(renderer)
                    print(f"DEBUG: Applied renderer to {target_layer.name()}")
            
            # Apply form configuration
            if 'form_config' in symbology_data:
                form_config = target_layer.editFormConfig()
                form_config.setLayout(symbology_data['form_config']['layout'])
                form_config.setSuppress(symbology_data['form_config']['suppress_form'])
                target_layer.setEditFormConfig(form_config)
                print(f"DEBUG: Applied form configuration to {target_layer.name()}")
            
            # Apply field configurations
            if 'fields' in symbology_data:
                target_fields = target_layer.fields()
                for field_name, field_data in symbology_data['fields'].items():
                    field_idx = target_fields.indexFromName(field_name)
                    if field_idx >= 0:
                        # Apply editor widget setup
                        if 'editor_widget' in field_data:
                            from qgis.core import QgsEditorWidgetSetup
                            widget_setup = QgsEditorWidgetSetup(
                                field_data['editor_widget']['type'],
                                field_data['editor_widget']['config']
                            )
                            target_layer.setEditorWidgetSetup(field_idx, widget_setup)
                        
                        # Apply default value definition
                        if 'default_value' in field_data:
                            from qgis.core import QgsDefaultValue
                            default_value = QgsDefaultValue(
                                field_data['default_value']['expression'],
                                field_data['default_value']['apply_on_update']
                            )
                            target_layer.setDefaultValueDefinition(field_idx, default_value)
                
                print(f"DEBUG: Applied field configurations to {target_layer.name()}")
            
            print(f"DEBUG: Successfully applied symbology data to {target_layer.name()}")
            
        except Exception as e:
            print(f"DEBUG: Error applying symbology data to {target_layer.name()}: {str(e)}")
            import traceback
            traceback.print_exc()

    def _apply_symbology_to_layer(self, target_layer: QgsVectorLayer, source_layer: QgsVectorLayer) -> None:
        """
        Apply symbology from a source layer to a target layer.
        This includes renderer, form configuration, and field properties.
        """
        try:
            print(f"DEBUG: Applying symbology from {source_layer.name()} to {target_layer.name()}")
            
            # Copy renderer
            if hasattr(source_layer, 'renderer') and source_layer.renderer():
                target_layer.setRenderer(source_layer.renderer().clone())
                print(f"DEBUG: Copied renderer from {source_layer.name()}")
            else:
                print(f"DEBUG: Source layer {source_layer.name()} has no renderer, skipping.")
            
            # Copy form configuration
            if hasattr(source_layer, 'editFormConfig') and source_layer.editFormConfig():
                target_layer.setEditFormConfig(source_layer.editFormConfig().clone())
                print(f"DEBUG: Copied form config from {source_layer.name()}")
            else:
                print(f"DEBUG: Source layer {source_layer.name()} has no form config, skipping.")
            
            # Copy fields
            target_layer.startEditing()
            for field in source_layer.fields():
                if not target_layer.fields().indexFromName(field.name()) >= 0:
                    target_layer.addField(field)
                    print(f"DEBUG: Added field {field.name()} to {target_layer.name()}")
                else:
                    print(f"DEBUG: Field {field.name()} already exists in {target_layer.name()}, skipping.")
            
            target_layer.commitChanges()
            print(f"DEBUG: Copied fields from {source_layer.name()} to {target_layer.name()}")
            
        except Exception as e:
            print(f"DEBUG: Error applying symbology to {target_layer.name()}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def package_for_qfield_with_data(self, 
                                   feature_data: Dict[str, Any],
                                   recording_areas_layer_id: str,
                                   objects_layer_id: str,
                                   features_layer_id: Optional[str],
                                   background_layer_id: Optional[str],
                                   extra_layers: Optional[List[str]] = None,
                                   destination_folder: str = "",
                                   project_name: str = "",
                                   add_variables: bool = True,
                                   next_values: Dict[str, str] = None) -> bool:
        """
        Package a QField project for a specific recording area using extracted feature data.
        
        Args:
            feature_data: Dictionary containing feature data (id, geometry_wkt, attributes)
            recording_areas_layer_id: ID of the recording areas layer
            objects_layer_id: ID of the objects layer
            features_layer_id: ID of the features layer (optional)
            background_layer_id: ID of the background image layer (optional)
            extra_layers: List of additional layer IDs to include as read-only (optional)
            destination_folder: Folder where to save the QField project
            project_name: Name for the QField project
            add_variables: Whether to add project variables (next_number, next_level, recording_area_name)
            next_values: Dictionary containing next_number, next_level, and background_image values (required if add_variables=True)
            
        Returns:
            True if packaging was successful, False otherwise
        """
        # Debug: Log the type and value of feature_data
        print(f"DEBUG: feature_data type: {type(feature_data)}")
        print(f"DEBUG: feature_data value: {feature_data}")
        if isinstance(feature_data, list):
            print(f"DEBUG: feature_data is a list with {len(feature_data)} elements")
            if feature_data:
                print(f"DEBUG: First element type: {type(feature_data[0])}")
                print(f"DEBUG: First element value: {feature_data[0]}")
        
        try:
            if not self._qfieldsync_available:
                raise RuntimeError("QFieldSync (libqfieldsync) is not available")
            if not feature_data or not recording_areas_layer_id or not objects_layer_id:
                raise ValueError("Required parameters are missing")
            if not destination_folder or not project_name:
                raise ValueError("Destination folder and project name are required")
            if add_variables and not next_values:
                raise ValueError("next_values is required when add_variables=True")

            # Prepare output directory and project file
            project_dir = os.path.join(destination_folder, project_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)
            project_file = os.path.join(project_dir, f"{project_name}_qfield.qgs")

            # Work with the original project and configure QFieldSync layer settings
            original_project = QgsProject.instance()
            
            # Store original layer configurations to restore later
            original_layer_configs = {}
            
            # Store created empty layers to remove later
            created_empty_layers = []
            
            # Store clipped raster layer to remove later
            clipped_raster_layer_id = None
            
            try:
                # Use original layers directly for offline editing (no need to create copies)
                empty_objects_layer_id = objects_layer_id
                print(f"Using original objects layer directly: {empty_objects_layer_id}")
                
                # Use original features layer directly if features layer is configured
                empty_features_layer_id = None
                if features_layer_id:
                    empty_features_layer_id = features_layer_id
                    print(f"Using original features layer directly: {empty_features_layer_id}")
                
                # Process background raster if specified
                if background_layer_id:
                    # Create geometry from WKT for raster processing
                    from qgis.core import QgsGeometry
                    # Create geometry from WKT and convert 3D to 2D if needed
                    wkt = feature_data.get('geometry_wkt', '')
                    if ' Z ' in wkt:
                        # Convert 3D geometry to 2D by removing Z coordinates
                        wkt_2d = wkt.replace(' Z ', ' ').replace(' Z(', ' (').replace(' Z)', ' )')
                        # Remove Z coordinates from coordinate tuples
                        import re
                        wkt_2d = re.sub(r'(\d+\.\d+)\s+(\d+\.\d+)\s+\d+\.\d+', r'\1 \2', wkt_2d)
                        print(f"[DEBUG] Converted 3D WKT to 2D: {wkt_2d}")
                        feature_geometry = QgsGeometry.fromWkt(wkt_2d)
                    else:
                        feature_geometry = QgsGeometry.fromWkt(wkt)
                    
                    # Note: QgsGeometry doesn't have CRS, but we'll handle this in the raster processing service
                    if feature_geometry is not None and not feature_geometry.isNull():
                        print(f"[DEBUG] Geometry created successfully, will use project CRS for processing")
                    
                    if feature_geometry is not None and not feature_geometry.isNull():
                        clipped_raster_layer_id = self._process_background_raster(
                            background_layer_id=background_layer_id,
                            feature_geometry=feature_geometry,
                            project_name=project_name
                        )
                        if clipped_raster_layer_id:
                            print(f"Successfully processed background raster: {clipped_raster_layer_id}")
                        else:
                            print("Warning: Failed to process background raster")
                    else:
                        print("Warning: Could not create geometry from WKT for raster processing")
                
                # Configure QFieldSync layer settings for all layers
                for layer in original_project.mapLayers().values():
                    try:
                        from libqfieldsync.layer import LayerSource, SyncAction
                        layer_source = LayerSource(layer, original_project)
                        
                        # Store original configuration
                        original_layer_configs[layer.id()] = {
                            'action': layer_source.action,
                            'cloud_action': layer_source.cloud_action
                        }
                        
                        # Default: REMOVE
                        layer_source.action = SyncAction.REMOVE
                        layer_source.cloud_action = SyncAction.REMOVE
                        
                        # Debug logging
                        print(f"DEBUG: Configuring layer '{layer.name()}' (ID: {layer.id()})")
                        print(f"DEBUG: - empty_objects_layer_id: {empty_objects_layer_id}")
                        print(f"DEBUG: - empty_features_layer_id: {empty_features_layer_id}")
                        print(f"DEBUG: - objects_layer_id: {objects_layer_id}")
                        print(f"DEBUG: - features_layer_id: {features_layer_id}")
                        print(f"DEBUG: - recording_areas_layer_id: {recording_areas_layer_id}")
                        print(f"DEBUG: - background_layer_id: {background_layer_id}")
                        print(f"DEBUG: - extra_layers: {extra_layers}")
                        
                        # 1. Empty objects layer: OFFLINE (editable)
                        if empty_objects_layer_id and layer.id() == empty_objects_layer_id:
                            print(f"DEBUG: Setting layer '{layer.name()}' to OFFLINE (empty objects)")
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        # 2. Empty features layer: OFFLINE (editable)
                        elif empty_features_layer_id and layer.id() == empty_features_layer_id:
                            print(f"DEBUG: Setting layer '{layer.name()}' to OFFLINE (empty features)")
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        # 3. Original objects/features layers: REMOVE
                        elif layer.id() == objects_layer_id or (features_layer_id and layer.id() == features_layer_id):
                            print(f"DEBUG: Setting layer '{layer.name()}' to REMOVE (original objects/features)")
                            layer_source.action = SyncAction.REMOVE
                            layer_source.cloud_action = SyncAction.REMOVE
                        # 4. Recording areas layer: COPY (read-only)
                        elif layer.id() == recording_areas_layer_id:
                            print(f"DEBUG: Setting layer '{layer.name()}' to COPY (recording areas)")
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 5. Background raster: COPY (read-only) if selected
                        elif background_layer_id and layer.id() == background_layer_id:
                            print(f"DEBUG: Setting layer '{layer.name()}' to REMOVE (original background)")
                            layer_source.action = SyncAction.REMOVE
                            layer_source.cloud_action = SyncAction.REMOVE
                        # 5b. Clipped background raster: COPY (read-only) if available
                        elif clipped_raster_layer_id and layer.id() == clipped_raster_layer_id:
                            print(f"DEBUG: Setting layer '{layer.name()}' to COPY (clipped background)")
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 6. Extra layers: COPY (read-only)
                        elif extra_layers and layer.id() in extra_layers:
                            print(f"DEBUG: Setting layer '{layer.name()}' to COPY (extra layer)")
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        # 7. All others: REMOVE (already set by default)
                        else:
                            print(f"DEBUG: Setting layer '{layer.name()}' to REMOVE (default)")
                        
                        layer_source.apply()
                        
                    except ImportError:
                        print("Warning: Could not import LayerSource from libqfieldsync")
                    except Exception as e:
                        print(f"Warning: Could not configure layer {layer.name()}: {str(e)}")
                
                # Use the pre-extracted geometry data
                area_of_interest = feature_data.get('geometry_wkt')
                area_of_interest_crs = original_project.crs().authid()
                
                if not area_of_interest:
                    # fallback: use original project extent or create default
                    try:
                        # Try to get extent from original project's map canvas
                        from qgis.core import QgsApplication
                        iface = QgsApplication.instance().interface()
                        if iface and iface.mapCanvas():
                            area_of_interest = iface.mapCanvas().extent().asWktPolygon()
                        else:
                            # Create a default extent
                            from qgis.core import QgsRectangle
                            area_of_interest = QgsRectangle(-180, -90, 180, 90).asWktPolygon()
                    except:
                        # Last resort: create a default extent
                        from qgis.core import QgsRectangle
                        area_of_interest = QgsRectangle(-180, -90, 180, 90).asWktPolygon()
                    area_of_interest_crs = original_project.crs().authid()

                # Attachments and dirs to copy (not used in this minimal example)
                attachment_dirs = []  # Empty list instead of None
                dirs_to_copy = {}     # Empty dict instead of list - should be Dict[str, bool]
                export_title = project_name

                # Use QgisCoreOffliner for offline editing
                offliner = QgisCoreOffliner(offline_editing=False)

                # Validate that we have all required data before proceeding
                if not area_of_interest:
                    print(f"Warning: No area of interest found for {project_name}, using fallback extent")

                # Call the packaging logic with the original project
                success = self._package_with_offline_converter(
                    original_project,
                    project_file,
                    area_of_interest,
                    area_of_interest_crs,
                    attachment_dirs,
                    offliner,
                    ExportType.Cable,
                    dirs_to_copy,
                    export_title,
                    feature_data.get('id', None),
                    recording_areas_layer_id,
                    extra_layers,
                    objects_layer_id,
                    features_layer_id
                )
                
                if success and add_variables:
                    # Add project variables to the created QField project
                    self._add_project_variables_to_qfield_project(
                        project_file, feature_data, next_values
                    )
                
                # Ensure raster layer is visible in the QField project
                if success and clipped_raster_layer_id:
                    self._ensure_raster_visibility_in_qfield_project(
                        project_file, clipped_raster_layer_id
                    )
                
                return success
                
            finally:
                # Restore original layer configurations
                for layer_id, config in original_layer_configs.items():
                    try:
                        layer = original_project.mapLayer(layer_id)
                        if layer:
                            from libqfieldsync.layer import LayerSource
                            layer_source = LayerSource(layer, original_project)
                            layer_source.action = config['action']
                            layer_source.cloud_action = config['cloud_action']
                            layer_source.apply()
                    except Exception as e:
                        print(f"Warning: Could not restore layer configuration for {layer_id}: {str(e)}")
                
                # Remove the created empty layers from the main QGIS project
                # Note: These layers must remain in the project during QFieldSync packaging
                # They will be removed after the packaging is complete
                for layer_id in created_empty_layers:
                    try:
                        if self._layer_service.remove_layer_from_project(layer_id):
                            print(f"Removed empty layer: {layer_id}")
                        else:
                            print(f"Warning: Could not remove empty layer: {layer_id}")
                    except Exception as e:
                        print(f"Error removing empty layer {layer_id}: {str(e)}")
                
                # Remove the clipped raster layer from the main QGIS project
                if clipped_raster_layer_id:
                    self._cleanup_clipped_raster(clipped_raster_layer_id)
                        
        except Exception as e:
            print(f"Error packaging QField project for {project_name}: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return False



    def _add_project_variables_to_qfield_project(self, project_file: str, 
                                                feature_data: Dict[str, Any], 
                                                next_values: Dict[str, str]) -> None:
        """
        Add project variables to the QField project file.
        
        Args:
            project_file: Path to the QField project file
            feature_data: Dictionary containing feature data
            next_values: Dictionary containing next_number, next_level, and background_image values
        """
        # Comprehensive defensive check at the very beginning
        print(f"DEBUG: _add_project_variables_to_qfield_project - feature_data type: {type(feature_data)}")
        print(f"DEBUG: _add_project_variables_to_qfield_project - feature_data value: {feature_data}")
        
        # Defensive: if feature_data is a list, use the first element
        if isinstance(feature_data, list):
            print(f"DEBUG: feature_data is a list with {len(feature_data)} elements, using first element")
            if feature_data:
                feature_data = feature_data[0]
                print(f"DEBUG: Using first element: {feature_data}")
            else:
                feature_data = {}
                print(f"DEBUG: Empty list, using empty dict")
        
        # Additional safety check: ensure feature_data is a dict
        if not isinstance(feature_data, dict):
            print(f"DEBUG: feature_data is not a dict, converting to empty dict. Type: {type(feature_data)}")
            feature_data = {}
        
        try:
            # Load the QField project
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                print(f"Warning: Could not read QField project file: {project_file}")
                return
            
            # Add recording_area variable (display name of the recording area)
            # Use safe access with additional checks
            # In your data, display_name is directly in feature_data
            recording_area_name = feature_data.get('display_name', '')
            
            # Set recording_area_name from top-level or attributes dict
            recording_area_name = feature_data.get('display_name', '')
            if not recording_area_name:
                attributes = feature_data.get('attributes', {})
                if isinstance(attributes, dict):
                    recording_area_name = attributes.get('display_name', '')

            # Add level variable (next level value)
            next_level = next_values.get('next_level', '')
            
            # Add first_number variable (next number value)
            next_number = next_values.get('next_number', '')
            
            # Set project variables using the correct QGIS API
            # Read existing variables
            names, _ = qfield_project.readListEntry('Variables', 'variableNames')
            values, _ = qfield_project.readListEntry('Variables', 'variableValues')
            if names is None:
                names = []
            if values is None:
                values = []

            def set_var(name, value):
                if not value:
                    return
                if name in names:
                    idx = names.index(name)
                    values[idx] = value
                else:
                    names.append(name)
                    values.append(value)

            set_var('recording_area', recording_area_name)
            set_var('level', next_level)
            set_var('first_number', next_number)

            qfield_project.writeEntry('Variables', 'variableNames', names)
            qfield_project.writeEntry('Variables', 'variableValues', values)
            print(f"Set project variables: {list(zip(names, values))}")
                
            # Save the project with the new variables
            if not qfield_project.write(project_file):
                print(f"Warning: Could not save QField project with variables: {project_file}")
            else:
                print(f"Successfully added project variables to: {project_file}")
                
        except Exception as e:
            print(f"Error adding project variables to QField project: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _process_background_raster(self, 
                                  background_layer_id: str,
                                  feature_geometry: Any,
                                  project_name: str) -> Optional[str]:
        """
        Process background raster by clipping it to the recording area with offset.
        
        Args:
            background_layer_id: ID of the background raster layer
            feature_geometry: QgsGeometry of the recording area feature
            project_name: Name of the project for naming the clipped raster
            
        Returns:
            ID of the clipped raster layer, or None if processing failed
        """
        try:
            if not self._raster_processing_service:
                print("Warning: Raster processing service not available")
                return None
            
            # Check if GDAL is available
            if not self._raster_processing_service.is_gdal_available():
                print("Warning: GDAL command line tools not available")
                print("This will prevent background image clipping for QField projects.")
                print("To enable raster clipping, ensure gdalwarp and ogr2ogr are available.")
                
                # Provide debugging information if available
                if hasattr(self._raster_processing_service, 'get_gdal_debug_info'):
                    debug_info = self._raster_processing_service.get_gdal_debug_info()
                    print("\nGDAL Debug Information:")
                    print(debug_info)
                
                return None
            
            # Get raster clipping offset from settings
            # Get offset_meters from settings and ensure it's a float
            offset_meters_raw = self._settings_manager.get_value('raster_clipping_offset', 0.2)
            try:
                offset_meters = float(offset_meters_raw)
                print(f"[DEBUG] Converted offset_meters from {type(offset_meters_raw)} to float: {offset_meters}")
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error converting offset_meters to float: {e}, using default 0.2")
                offset_meters = 0.2
            
            print(f"[DEBUG] Clipping raster: background_layer_id={background_layer_id}, offset_meters={offset_meters}")
            
            # Create clipped raster
            clipped_raster_path = self._raster_processing_service.clip_raster_to_feature(
                raster_layer_id=background_layer_id,
                feature_geometry=feature_geometry,
                offset_meters=offset_meters
            )
            print(f"[DEBUG] Clipped raster path returned: {clipped_raster_path}")
            if clipped_raster_path and os.path.exists(clipped_raster_path):
                print(f"[DEBUG] Clipped raster file exists: {clipped_raster_path}")
            else:
                print(f"[DEBUG] Clipped raster file does NOT exist: {clipped_raster_path}")
            
            if not clipped_raster_path:
                print("Error: Failed to clip raster")
                return None
            
            # Load the clipped raster into QGIS
            clipped_layer_name = f"{project_name}_Background"
            clipped_layer = QgsRasterLayer(clipped_raster_path, clipped_layer_name, "gdal")
            print(f"[DEBUG] Created QgsRasterLayer: valid={clipped_layer.isValid()}, name={clipped_layer.name()}, source={clipped_layer.source()}")
            
            if not clipped_layer.isValid():
                print(f"Error: Failed to load clipped raster: {clipped_raster_path}")
                return None
            
            # Add the clipped layer to the project
            QgsProject.instance().addMapLayer(clipped_layer)
            print(f"[DEBUG] Added clipped raster layer to project: id={clipped_layer.id()}, name={clipped_layer.name()}")
            
            # Ensure the layer is visible in the layer tree
            try:
                from qgis.core import QgsLayerTreeLayer
                layer_tree_root = QgsProject.instance().layerTreeRoot()
                
                # Find the layer node in the tree
                layer_node = layer_tree_root.findLayer(clipped_layer.id())
                if layer_node:
                    # Set the layer as visible
                    layer_node.setItemVisibilityChecked(True)
                    print(f"[DEBUG] Set raster layer visibility to True: {clipped_layer.name()}")
                    
                    # Move the layer to the bottom of the tree
                    try:
                        # Clone the node and insert at the bottom
                        layer_node_clone = layer_node.clone()
                        layer_tree_root.addChildNode(layer_node_clone)
                        # Remove the original node
                        layer_node.parent().removeChildNode(layer_node)
                        print(f"[DEBUG] Moved raster layer to bottom of tree: {clipped_layer.name()}")
                    except Exception as e:
                        print(f"[DEBUG] Could not move layer to bottom: {str(e)}")
                else:
                    print(f"[DEBUG] Could not find layer node in tree for: {clipped_layer.name()}")
            except Exception as e:
                print(f"[DEBUG] Could not set layer visibility: {str(e)}")
            
            # Set QFieldSync-specific property to ensure visibility in QField project
            try:
                # Set a custom property that QFieldSync might use to determine visibility
                clipped_layer.setCustomProperty("QFieldSync/visible", True)
                print(f"[DEBUG] Set QFieldSync visible property for: {clipped_layer.name()}")
            except Exception as e:
                print(f"[DEBUG] Could not set QFieldSync visible property: {str(e)}")
            
            return clipped_layer.id()
            
        except Exception as e:
            print(f"Error processing background raster: {str(e)}")
            return None
    
    def _ensure_raster_visibility_in_qfield_project(self, project_file: str, raster_layer_id: str) -> None:
        """
        Ensure the raster layer is visible in the QField project file.
        
        Args:
            project_file: Path to the QField project file
            raster_layer_id: ID of the raster layer to make visible
        """
        try:
            # Load the QField project
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                print(f"Warning: Could not read QField project: {project_file}")
                return
            
            # Find the raster layer in the project
            raster_layer = qfield_project.mapLayer(raster_layer_id)
            if not raster_layer:
                print(f"Warning: Could not find raster layer {raster_layer_id} in QField project")
                return
            
            # Ensure the layer is visible in the layer tree
            layer_tree_root = qfield_project.layerTreeRoot()
            layer_node = layer_tree_root.findLayer(raster_layer_id)
            if layer_node:
                layer_node.setItemVisibilityChecked(True)
                print(f"[DEBUG] Set raster layer visibility in QField project: {raster_layer.name()}")
            else:
                print(f"[DEBUG] Could not find layer node in QField project for: {raster_layer.name()}")
            
            # Save the updated project
            if not qfield_project.write(project_file):
                print(f"Warning: Could not save updated QField project: {project_file}")
            else:
                print(f"[DEBUG] Successfully updated QField project with visible raster layer")
                
        except Exception as e:
            print(f"Error ensuring raster visibility in QField project: {str(e)}")
    
    def _cleanup_clipped_raster(self, clipped_layer_id: str) -> None:
        """
        Remove the clipped raster layer from the QGIS project.
        
        Args:
            clipped_layer_id: ID of the clipped raster layer to remove
        """
        try:
            if clipped_layer_id and self._layer_service:
                if self._layer_service.remove_layer_from_project(clipped_layer_id):
                    print(f"Successfully removed clipped raster layer: {clipped_layer_id}")
                else:
                    print(f"Warning: Could not remove clipped raster layer: {clipped_layer_id}")
        except Exception as e:
            print(f"Error removing clipped raster layer: {str(e)}")

    def _filter_recording_area_layer(self, project_file: str, selected_feature_id: Any, recording_areas_layer_id: str) -> None:
        """
        Filter the recording area layer in the QField project to only include the selected feature.
        
        Args:
            project_file: Path to the QField project file
            selected_feature_id: ID of the selected recording area feature
            recording_areas_layer_id: ID of the recording areas layer
        """
        try:
            # Load the QField project
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                return
            
            # Find the recording areas layer in the project
            recording_layer = None
            for layer in qfield_project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer):
                    # The layer ID in the QField project might be different from the original
                    # So we'll look for a layer that contains recording area features
                    if layer.featureCount() > 0:
                        # Check if this layer has features that match our recording area pattern
                        # We'll assume it's the recording area layer if it has the right number of features
                        # and we can find our selected feature in it
                        for feature in layer.getFeatures():
                            if feature.id() == selected_feature_id:
                                recording_layer = layer
                                break
                        if recording_layer:
                            break
            
            if not recording_layer:
                return
            
            # Start editing
            recording_layer.startEditing()
            
            # Get all feature IDs except the selected one
            features_to_delete = []
            for feature in recording_layer.getFeatures():
                if feature.id() != selected_feature_id:
                    features_to_delete.append(feature.id())
            
            # Delete all features except the selected one
            if features_to_delete:
                recording_layer.deleteFeatures(features_to_delete)
            
            # Commit changes
            if not recording_layer.commitChanges():
                recording_layer.rollBack()
            
            # Save the updated project
            qfield_project.write(project_file)
            
        except Exception as e:
            # Silently handle errors to avoid disrupting the packaging process
            pass

    def _filter_related_extra_layers(self, project_file: str, selected_feature_id: Any, recording_areas_layer_id: str, extra_layer_ids: Optional[List[str]]) -> None:
        """
        For each extra layer that has a relation to the recording area layer, filter it to only keep features related to the selected recording area.
        Args:
            project_file: Path to the QField project file
            selected_feature_id: ID of the selected recording area feature
            recording_areas_layer_id: ID of the recording areas layer
            extra_layer_ids: List of extra layer IDs to check and filter
        """
        if not extra_layer_ids:
            return
        try:
            from qgis.core import QgsProject, QgsVectorLayer
            qfield_project = QgsProject()
            if not qfield_project.read(project_file):
                return
            # Find the recording area feature in the QField project
            recording_layer = qfield_project.mapLayer(recording_areas_layer_id)
            if not recording_layer or not isinstance(recording_layer, QgsVectorLayer):
                return
            selected_feature = None
            for feature in recording_layer.getFeatures():
                if feature.id() == selected_feature_id:
                    selected_feature = feature
                    break
            if not selected_feature:
                return
            # For each extra layer, check for relation and filter
            project_relations = qfield_project.relationManager().relations().values()
            for extra_layer_id in extra_layer_ids:
                extra_layer = qfield_project.mapLayer(extra_layer_id)
                if not extra_layer or not isinstance(extra_layer, QgsVectorLayer):
                    continue
                # Find relation where extra layer is referencing and recording area is referenced
                for relation in project_relations:
                    if (relation.referencingLayerId() == extra_layer_id and
                        relation.referencedLayerId() == recording_areas_layer_id):
                        # Get related features
                        related_features = relation.getRelatedFeatures(selected_feature)
                        related_ids = set(f.id() for f in related_features)
                        # Start editing
                        extra_layer.startEditing()
                        # Delete features not related
                        to_delete = [f.id() for f in extra_layer.getFeatures() if f.id() not in related_ids]
                        if to_delete:
                            extra_layer.deleteFeatures(to_delete)
                        # Commit changes
                        if not extra_layer.commitChanges():
                            extra_layer.rollBack()
                        break  # Only one relation per extra layer
            # Save the updated project
            qfield_project.write(project_file)
        except Exception as e:
            # Silently handle errors to avoid disrupting the packaging process
            pass