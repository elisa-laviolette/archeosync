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
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry
from qgis.PyQt.QtWidgets import QMessageBox

try:
    from ..core.interfaces import IQFieldService, ISettingsManager, ILayerService
except ImportError:
    from core.interfaces import IQFieldService, ISettingsManager, ILayerService

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
    def __init__(self, settings_manager: ISettingsManager, layer_service: ILayerService):
        self._settings_manager = settings_manager
        self._layer_service = layer_service
        self._qfieldsync_available = OfflineConverter is not None and QgisCoreOffliner is not None

    def is_qfield_enabled(self) -> bool:
        return self._settings_manager.get_value('use_qfield', False)

    def get_qfieldsync_plugin(self) -> Optional[Any]:
        # No longer relevant: return True if QFieldSync is available
        return self._qfieldsync_available

    def package_for_qfield(self, 
                          recording_area_feature: Any,
                          recording_areas_layer_id: str,
                          objects_layer_id: str,
                          features_layer_id: Optional[str],
                          background_layer_id: Optional[str],
                          destination_folder: str,
                          project_name: str) -> bool:
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
                        
                        # Set layers to REMOVE by default
                        layer_source.action = SyncAction.REMOVE
                        layer_source.cloud_action = SyncAction.REMOVE
                        
                        # Set recording areas layer as COPY (read-only)
                        if layer.id() == recording_areas_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set background layer as COPY (read-only) if specified
                        elif background_layer_id and layer.id() == background_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set empty objects layer for OFFLINE editing
                        elif empty_objects_layer_id and layer.id() == empty_objects_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Set empty features layer for OFFLINE editing
                        elif empty_features_layer_id and layer.id() == empty_features_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Apply the configuration
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
                                   destination_folder: str,
                                   project_name: str) -> bool:
        """
        Package a QField project for a specific recording area using extracted feature data.
        This method avoids issues with QGIS object deletion by using pre-extracted data.
        Creates empty objects and features layers for offline editing in QField.
        """
        try:
            if not self._qfieldsync_available:
                raise RuntimeError("QFieldSync (libqfieldsync) is not available")
            if not feature_data or not recording_areas_layer_id or not objects_layer_id:
                raise ValueError("Required parameters are missing")
            if not destination_folder or not project_name:
                raise ValueError("Destination folder and project name are required")

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
                        
                        # Set layers to REMOVE by default
                        layer_source.action = SyncAction.REMOVE
                        layer_source.cloud_action = SyncAction.REMOVE
                        
                        # Set recording areas layer as COPY (read-only)
                        if layer.id() == recording_areas_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set background layer as COPY (read-only) if specified
                        elif background_layer_id and layer.id() == background_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set empty objects layer for OFFLINE editing
                        elif empty_objects_layer_id and layer.id() == empty_objects_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Set empty features layer for OFFLINE editing
                        elif empty_features_layer_id and layer.id() == empty_features_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Apply the configuration
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

    def package_for_qfield_with_data_and_variables(self, 
                                                 feature_data: Dict[str, Any],
                                                 recording_areas_layer_id: str,
                                                 objects_layer_id: str,
                                                 features_layer_id: Optional[str],
                                                 background_layer_id: Optional[str],
                                                 destination_folder: str,
                                                 project_name: str,
                                                 next_values: Dict[str, str]) -> bool:
        """
        Package a QField project for a specific recording area using extracted feature data
        and add project variables for recording area, level, and first number.
        
        Args:
            feature_data: Dictionary containing feature data (id, geometry_wkt, attributes)
            recording_areas_layer_id: ID of the recording areas layer
            objects_layer_id: ID of the objects layer
            features_layer_id: ID of the features layer (optional)
            background_layer_id: ID of the background image layer (optional)
            destination_folder: Folder where to save the QField project
            project_name: Name for the QField project
            next_values: Dictionary containing next_number, next_level, and background_image values
            
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
                        
                        # Set layers to REMOVE by default
                        layer_source.action = SyncAction.REMOVE
                        layer_source.cloud_action = SyncAction.REMOVE
                        
                        # Set recording areas layer as COPY (read-only)
                        if layer.id() == recording_areas_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set background layer as COPY (read-only) if specified
                        elif background_layer_id and layer.id() == background_layer_id:
                            layer_source.action = SyncAction.COPY
                            layer_source.cloud_action = SyncAction.COPY
                            # Make it read-only by locking all editing operations
                            layer_source.is_feature_addition_locked = True
                            layer_source.is_attribute_editing_locked = True
                            layer_source.is_geometry_editing_locked = True
                            layer_source.is_feature_deletion_locked = True
                        
                        # Set empty objects layer for OFFLINE editing
                        elif empty_objects_layer_id and layer.id() == empty_objects_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Set empty features layer for OFFLINE editing
                        elif empty_features_layer_id and layer.id() == empty_features_layer_id:
                            layer_source.action = SyncAction.OFFLINE
                            layer_source.cloud_action = SyncAction.OFFLINE
                            # Enable all editing operations for offline editing
                            layer_source.is_feature_addition_locked = False
                            layer_source.is_attribute_editing_locked = False
                            layer_source.is_geometry_editing_locked = False
                            layer_source.is_feature_deletion_locked = False
                        
                        # Apply the configuration
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
                
                if success:
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