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