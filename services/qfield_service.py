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
                # Create empty objects layer for offline editing
                empty_objects_layer_id = self._layer_service.create_empty_layer_copy(
                    objects_layer_id, 
                    "Objects"
                )
                if empty_objects_layer_id:
                    created_empty_layers.append(empty_objects_layer_id)
                    print(f"Created empty objects layer: {empty_objects_layer_id}")
                else:
                    print("Warning: Failed to create empty objects layer")
                
                # Create empty features layer for offline editing if features layer is configured
                empty_features_layer_id = None
                if features_layer_id:
                    empty_features_layer_id = self._layer_service.create_empty_layer_copy(
                        features_layer_id, 
                        "Features"
                    )
                    if empty_features_layer_id:
                        created_empty_layers.append(empty_features_layer_id)
                        print(f"Created empty features layer: {empty_features_layer_id}")
                    else:
                        print("Warning: Failed to create empty features layer")
                
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
                    export_title
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

    def _package_with_offline_converter(self, project, project_file, area_of_interest, area_of_interest_crs, attachment_dirs, offliner, export_type, dirs_to_copy, export_title) -> bool:
        """
        Use QFieldSync's OfflineConverter to package the project.
        """
        try:
            # Create the converter with proper parameters
            # Following the QFieldSync pattern from package_dialog.py
            converter = OfflineConverter(
                project,
                project_file,
                area_of_interest,
                area_of_interest_crs,
                attachment_dirs,
                offliner,
                export_type,
                dirs_to_copy=dirs_to_copy,
                export_title=export_title,
            )
            
            # Convert the project
            converter.convert()
            return True
            
        except PackagingCanceledException:
            print("Packaging was canceled.")
            return False
        except Exception as e:
            print(f"Error in OfflineConverter: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return False
    
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
                # Create empty objects layer for offline editing
                empty_objects_layer_id = self._layer_service.create_empty_layer_copy(
                    objects_layer_id, 
                    "Objects"
                )
                if empty_objects_layer_id:
                    created_empty_layers.append(empty_objects_layer_id)
                    print(f"Created empty objects layer: {empty_objects_layer_id}")
                else:
                    print("Warning: Failed to create empty objects layer")
                
                # Create empty features layer for offline editing if features layer is configured
                empty_features_layer_id = None
                if features_layer_id:
                    empty_features_layer_id = self._layer_service.create_empty_layer_copy(
                        features_layer_id, 
                        "Features"
                    )
                    if empty_features_layer_id:
                        created_empty_layers.append(empty_features_layer_id)
                        print(f"Created empty features layer: {empty_features_layer_id}")
                    else:
                        print("Warning: Failed to create empty features layer")
                
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
                    export_title
                )
                
                if success and add_variables:
                    # Add project variables to the created QField project
                    self._add_project_variables_to_qfield_project(
                        project_file, feature_data, next_values
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
                return None
            
            # Get raster clipping offset from settings
            offset_meters = self._settings_manager.get_value('raster_clipping_offset', 0.2)
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
            
            return clipped_layer.id()
            
        except Exception as e:
            print(f"Error processing background raster: {str(e)}")
            return None
    
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