"""
Core interfaces for the ArcheoSync plugin.

This module defines the core interfaces that follow the Interface Segregation Principle
and enable dependency inversion throughout the application. These interfaces provide
the contract that all implementations must follow, ensuring consistency and testability.

The interfaces are designed to be:
- Focused: Each interface has a single, well-defined responsibility
- Minimal: Only essential methods are included
- Stable: Interfaces should rarely change once established
- Testable: Easy to mock for unit testing

Example usage:
    # Inject dependencies through interfaces
    settings_manager = QGISSettingsManager()
    file_system_service = QGISFileSystemService()
    validator = ArcheoSyncConfigurationValidator(file_system_service)
    
    dialog = SettingsDialog(
        settings_manager=settings_manager,
        file_system_service=file_system_service,
        configuration_validator=validator
    )
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    message: str


class ISettingsManager(ABC):
    """Interface for settings management operations."""
    
    @abstractmethod
    def set_value(self, key: str, value: Any) -> None:
        """Save a value to settings."""
        pass
    
    @abstractmethod
    def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from settings."""
        pass
    
    @abstractmethod
    def remove_value(self, key: str) -> None:
        """Remove a setting value."""
        pass
    
    @abstractmethod
    def clear_all(self) -> None:
        """Clear all settings."""
        pass


class IFileSystemService(ABC):
    """Interface for file system operations."""
    
    @abstractmethod
    def select_directory(self, title: str, initial_path: Optional[str] = None) -> Optional[str]:
        """Open directory selection dialog."""
        pass
    
    @abstractmethod
    def path_exists(self, path: str) -> bool:
        """Check if a path exists."""
        pass
    
    @abstractmethod
    def create_directory(self, path: str) -> bool:
        """Create a directory if it doesn't exist."""
        pass
    
    @abstractmethod
    def is_directory(self, path: str) -> bool:
        """Check if a path is a directory."""
        pass
    
    @abstractmethod
    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""
        pass
    
    @abstractmethod
    def is_writable(self, path: str) -> bool:
        """Check if a path is writable."""
        pass
    
    @abstractmethod
    def is_readable(self, path: str) -> bool:
        """Check if a path is readable."""
        pass
    
    @abstractmethod
    def list_files(self, directory: str, extension: Optional[str] = None) -> list:
        """List files in a directory."""
        pass
    
    @abstractmethod
    def list_directories(self, directory: str) -> list:
        """List directories in a directory."""
        pass
    
    @abstractmethod
    def contains_qgs_file(self, directory: str) -> bool:
        """Check if a directory contains a .qgs file."""
        pass
    
    @abstractmethod
    def move_file(self, source_path: str, destination_path: str) -> bool:
        """Move a file from source to destination."""
        pass
    
    @abstractmethod
    def move_directory(self, source_path: str, destination_path: str) -> bool:
        """Move a directory from source to destination."""
        pass


class ITranslationService(ABC):
    """Interface for translation operations."""
    
    @abstractmethod
    def translate(self, message: str) -> str:
        """Translate a message."""
        pass
    
    @abstractmethod
    def get_current_locale(self) -> str:
        """Get the current locale."""
        pass


class IPluginActionManager(ABC):
    """Interface for managing plugin actions."""
    
    @abstractmethod
    def add_action(self, icon_path: str, text: str, callback: callable, 
                   enabled: bool = True, add_to_menu: bool = True, 
                   add_to_toolbar: bool = True, status_tip: Optional[str] = None,
                   whats_this: Optional[str] = None) -> Any:
        """Add a toolbar icon to the toolbar."""
        pass
    
    @abstractmethod
    def remove_action(self, action: Any) -> None:
        """Remove an action from the interface."""
        pass


class IUserInterface(ABC):
    """Interface for user interface operations."""
    
    @abstractmethod
    def show_dialog(self, dialog: Any) -> int:
        """Show a dialog and return the result."""
        pass
    
    @abstractmethod
    def show_message(self, title: str, message: str, message_type: str = "info") -> None:
        """Show a message to the user."""
        pass


class IProjectManager(ABC):
    """Interface for project management operations."""
    
    @abstractmethod
    def create_field_project(self, template_path: str, destination_path: str) -> bool:
        """Create a new field project from template."""
        pass
    
    @abstractmethod
    def import_total_station_data(self, csv_folder: str, project_path: str) -> bool:
        """Import total station data from CSV files."""
        pass
    
    @abstractmethod
    def import_completed_project(self, project_path: str) -> bool:
        """Import a completed field project."""
        pass


class IConfigurationValidator(ABC):
    """Interface for configuration validation."""
    
    @abstractmethod
    def validate_field_projects_folder(self, path: str) -> List[str]:
        """Validate field projects folder configuration."""
        pass
    
    @abstractmethod
    def validate_total_station_folder(self, path: str) -> List[str]:
        """Validate total station folder configuration."""
        pass
    
    @abstractmethod
    def validate_completed_projects_folder(self, path: str) -> List[str]:
        """Validate completed projects folder configuration."""
        pass
    
    @abstractmethod
    def validate_csv_archive_folder(self, path: str) -> List[str]:
        """Validate CSV archive folder configuration."""
        pass
    
    def validate_field_project_archive_folder(self, path: str) -> List[str]:
        """Validate field project archive folder configuration."""
        pass
    

    
    @abstractmethod
    def validate_recording_areas_layer(self, layer_id: str) -> List[str]:
        """Validate recording areas layer configuration."""
        pass
    
    @abstractmethod
    def validate_objects_layer(self, layer_id: str) -> List[str]:
        """Validate objects layer configuration."""
        pass
    
    @abstractmethod
    def validate_features_layer(self, layer_id: str) -> List[str]:
        """Validate features layer configuration."""
        pass

    @abstractmethod
    def validate_objects_layer_fields(self, layer_id: str, number_field: Optional[str], level_field: Optional[str]) -> ValidationResult:
        """
        Validate the field selections for the objects layer.
        
        Args:
            layer_id: The layer ID to validate fields for
            number_field: The selected number field (should be integer)
            level_field: The selected level field (can be any type)
            
        Returns:
            ValidationResult indicating success or failure with details
        """
        pass

    @abstractmethod
    def validate_layer_relationships(self, recording_areas_layer_id: str, objects_layer_id: str, features_layer_id: str) -> List[str]:
        """
        Validate that child layers have proper relationships with the recording areas layer.
        
        Args:
            recording_areas_layer_id: The recording areas layer ID (parent)
            objects_layer_id: The objects layer ID (child)
            features_layer_id: The features layer ID (child, optional)
            
        Returns:
            List of validation error messages (empty if valid)
        """
        pass


class ILayerService(ABC):
    """Interface for QGIS layer operations."""
    
    @abstractmethod
    def get_polygon_layers(self) -> List[Dict[str, Any]]:
        """Get all polygon layers from the current QGIS project."""
        pass
    
    @abstractmethod
    def get_polygon_and_multipolygon_layers(self) -> List[Dict[str, Any]]:
        """Get all polygon and multipolygon layers from the current QGIS project."""
        pass
    
    @abstractmethod
    def get_vector_layers(self) -> List[Dict[str, Any]]:
        """Get all vector layers from the current QGIS project."""
        pass
    
    @abstractmethod
    def get_raster_layers(self) -> List[Dict[str, Any]]:
        """Get all raster layers from the current QGIS project."""
        pass
    
    @abstractmethod
    def get_raster_layers_overlapping_feature(self, feature, recording_areas_layer_id: str) -> List[Dict[str, Any]]:
        """
        Get raster layers that overlap with a specific polygon feature.
        
        Args:
            feature: The polygon feature to check overlap with
            recording_areas_layer_id: The recording areas layer ID (for CRS transformation if needed)
            
        Returns:
            List of dictionaries containing overlapping raster layer information
        """
        pass
    
    @abstractmethod
    def get_layer_by_id(self, layer_id: str) -> Optional[Any]:
        """Get a layer by its ID."""
        pass
    
    @abstractmethod
    def is_valid_polygon_layer(self, layer_id: str) -> bool:
        """Check if a layer is a valid polygon layer."""
        pass
    
    @abstractmethod
    def is_valid_polygon_or_multipolygon_layer(self, layer_id: str) -> bool:
        """Check if a layer is a valid polygon or multipolygon layer."""
        pass
    
    @abstractmethod
    def get_layer_info(self, layer_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a layer."""
        pass

    @abstractmethod
    def get_layer_fields(self, layer_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get field information from a layer.
        
        Args:
            layer_id: The layer ID to get fields for
            
        Returns:
            List of field information dictionaries or None if layer not found
        """
        pass

    @abstractmethod
    def get_selected_features_count(self, layer_id: str) -> int:
        """
        Get the number of selected features in a layer.
        
        Args:
            layer_id: The layer ID to get selected features count for
            
        Returns:
            Number of selected features, 0 if layer not found or no features selected
        """
        pass

    @abstractmethod
    def get_selected_features_info(self, layer_id: str) -> List[Dict[str, Any]]:
        """
        Get information about selected features in a layer.
        
        Args:
            layer_id: The layer ID to get selected features for
            
        Returns:
            List of dictionaries containing feature information with 'name' field,
            sorted alphabetically by name
        """
        pass

    @abstractmethod
    def get_layer_relationships(self, layer_id: str) -> List[Any]:
        """
        Get all relationships for a layer.
        
        Args:
            layer_id: The layer ID to get relationships for
            
        Returns:
            List of relationship objects or empty list if no relationships found
        """
        pass

    @abstractmethod
    def get_related_objects_info(self, recording_area_feature, objects_layer_id: str, 
                                number_field: Optional[str], level_field: Optional[str]) -> Dict[str, Any]:
        """
        Get information about objects related to a recording area feature.
        
        Args:
            recording_area_feature: The recording area feature to get related objects for
            objects_layer_id: The objects layer ID
            number_field: The number field name (optional)
            level_field: The level field name (optional)
            
        Returns:
            Dictionary with 'last_number' and 'last_level' values, or empty strings if not found
        """
        pass

    @abstractmethod
    def calculate_next_level(self, last_level: str, level_field: str, objects_layer_id: str) -> str:
        """
        Calculate the next level value based on the last level and field type.
        
        Args:
            last_level: The last level value (can be empty string)
            level_field: The level field name
            objects_layer_id: The objects layer ID
            
        Returns:
            The next level value as a string
        """
        pass
    
    @abstractmethod
    def create_empty_layer_copy(self, source_layer_id: str, new_layer_name: str) -> Optional[str]:
        """
        Create an empty layer with the same structure (fields, geometry type, CRS) as the source layer.
        
        Args:
            source_layer_id: The ID of the source layer to copy structure from
            new_layer_name: The name for the new empty layer
            
        Returns:
            The ID of the newly created layer, or None if creation failed
        """
        pass
    
    @abstractmethod
    def remove_layer_from_project(self, layer_id: str) -> bool:
        """
        Remove a layer from the current QGIS project.
        
        Args:
            layer_id: The ID of the layer to remove
            
        Returns:
            True if the layer was successfully removed, False otherwise
        """
        pass





class IProjectCreationService(ABC):
    """Interface for QGIS project creation operations."""
    
    @abstractmethod
    def create_field_project(self,
                           feature_data: Dict[str, Any],
                           recording_areas_layer_id: str,
                           objects_layer_id: str,
                           features_layer_id: Optional[str],
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
        pass


class ICSVImportService(ABC):
    """Interface for CSV import operations."""
    
    @abstractmethod
    def validate_csv_files(self, csv_files: List[str]) -> ValidationResult:
        """
        Validate that all CSV files have required X, Y, Z columns.
        
        Args:
            csv_files: List of CSV file paths to validate
            
        Returns:
            ValidationResult indicating if files are valid and any error messages
        """
        pass
    
    @abstractmethod
    def get_column_mapping(self, csv_files: List[str]) -> Dict[str, List[Optional[str]]]:
        """
        Get column mapping across multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths to analyze
            
        Returns:
            Dictionary mapping unified column names to lists of column names from each file
        """
        pass
    
    @abstractmethod
    def import_csv_files(self, csv_files: List[str], column_mapping: Optional[Dict[str, List[Optional[str]]]] = None) -> ValidationResult:
        """
        Import CSV files into a PointZ vector layer and add to QGIS project.
        
        Args:
            csv_files: List of CSV file paths to import
            column_mapping: Optional column mapping (if None, will be generated automatically)
            
        Returns:
            ValidationResult indicating if import was successful and any error messages
        """
        pass


class IRasterProcessingService(ABC):
    """
    Interface for raster processing operations.
    
    This interface defines the contract for raster processing services that can
    clip raster layers to polygon geometries with configurable offsets. It is
    designed for archaeological recording scenarios where background imagery
    needs to be limited to specific recording areas.
    
    The interface requires implementations to:
    - Clip raster layers to polygon geometries
    - Support configurable buffer offsets
    - Handle coordinate system transformations
    - Provide GDAL availability checking
    - Return file paths for clipped outputs
    """
    
    @abstractmethod
    def clip_raster_to_feature(self, 
                              raster_layer_id: str,
                              feature_geometry: Any,
                              offset_meters: float = 0.2,
                              output_path: Optional[str] = None) -> Optional[str]:
        """
        Clip a raster layer to a feature geometry with an offset.
        
        This method should clip a raster layer to the boundary of a polygon feature,
        optionally adding a buffer zone around the feature. The clipped raster
        should be saved as a GeoTIFF file.
        
        Args:
            raster_layer_id: ID of the raster layer to clip (must exist in QGIS project)
            feature_geometry: QgsGeometry of the polygon feature to clip to
            offset_meters: Offset in meters to expand the clipping area (default: 0.2)
            output_path: Optional output path for the clipped raster (auto-generated if None)
            
        Returns:
            Path to the clipped raster file (GeoTIFF), or None if operation failed
            
        Note:
            Implementations should handle coordinate system transformations
            and temporary file cleanup automatically.
        """
        pass
    
    @abstractmethod
    def clip_raster_to_geometry(self, 
                               raster_layer_id: str,
                               geometry_wkt: str,
                               output_path: Optional[str] = None,
                               offset_meters: float = 0.2) -> bool:
        """
        Clip a raster layer to a geometry defined by WKT string with an offset.
        
        This method should clip a raster layer to the boundary of a polygon defined by
        a WKT (Well-Known Text) string, optionally adding a buffer zone around
        the geometry. The clipped raster should be saved as a GeoTIFF file.
        
        Args:
            raster_layer_id: ID of the raster layer to clip (must exist in QGIS project)
            geometry_wkt: WKT string defining the polygon geometry to clip to
            output_path: Optional output path for the clipped raster (auto-generated if None)
            offset_meters: Offset in meters to expand the clipping area (default: 0.2)
            
        Returns:
            True if clipping was successful, False otherwise
            
        Note:
            Implementations should handle coordinate system transformations
            and temporary file cleanup automatically.
        """
        pass
    
    @abstractmethod
    def is_gdal_available(self) -> bool:
        """
        Check if GDAL command line tools are available.
        
        Verifies that the required GDAL command-line tools (gdalwarp, ogr2ogr)
        are available in the system PATH for raster processing operations.
        
        Returns:
            True if both gdalwarp and ogr2ogr are available, False otherwise
            
        Note:
            This method should attempt to run version commands for both tools
            to verify their availability and proper installation.
        """
        pass
    
    @abstractmethod
    def get_gdal_debug_info(self) -> str:
        """
        Get detailed debugging information about GDAL tool availability.
        
        Returns:
            String containing detailed information about GDAL tool locations and availability
            
        Note:
            This method should provide comprehensive information about where
            GDAL tools were searched and their availability status.
        """
        pass 


class IFieldProjectImportService(ABC):
    """Interface for field project import operations."""
    
    @abstractmethod
    def import_field_projects(self, project_paths: List[str]) -> ValidationResult:
        """
        Import completed field projects and merge their Objects and Features layers.
        
        Args:
            project_paths: List of paths to completed field project directories
            
        Returns:
            ValidationResult indicating if import was successful and any error messages
        """
        pass
    
    @abstractmethod
    def _scan_project_layers(self, project_path: str) -> Dict[str, List[str]]:
        """
        Scan a field project directory for layer files.
        
        Args:
            project_path: Path to the field project directory
            
        Returns:
            Dictionary mapping layer types to lists of file paths
        """
        pass
    
    @abstractmethod
    def _process_data_gpkg(self, data_gpkg_path: str) -> Dict[str, List[Any]]:
        """
        Process a data.gpkg file to extract Objects and Features layers.
        
        Args:
            data_gpkg_path: Path to the data.gpkg file
            
        Returns:
            Dictionary mapping layer types to lists of features
        """
        pass
    
    @abstractmethod
    def _process_individual_layers(self, layer_files: Dict[str, List[str]]) -> Dict[str, List[Any]]:
        """
        Process individual layer files (not in data.gpkg).
        
        Args:
            layer_files: Dictionary mapping layer types to lists of file paths
            
        Returns:
            Dictionary mapping layer types to lists of features
        """
        pass
    
    @abstractmethod
    def _create_merged_layer(self, layer_name: str, features: List[Any]) -> Optional[Any]:
        """
        Create a merged layer from a list of features.
        
        Args:
            layer_name: Name for the merged layer
            features: List of features to merge
            
        Returns:
            QGIS layer object, or None if failed
        """
        pass 