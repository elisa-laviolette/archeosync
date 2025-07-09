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
    def validate_template_project_folder(self, path: str) -> List[str]:
        """Validate template project folder configuration."""
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