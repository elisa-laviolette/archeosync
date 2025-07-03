"""
Configuration validator service for ArcheoSync plugin.

This module provides validation logic for plugin configuration settings,
ensuring data integrity and user experience. The validator performs comprehensive
checks on all plugin settings to prevent configuration errors and provide
meaningful feedback to users.

Key Features:
- Comprehensive path validation
- Permission checking for directories
- File type validation
- Detailed error reporting
- Batch validation for multiple settings

Validation Rules:
- Field Projects Folder: Must exist, be writable, and be a directory
- Total Station Folder: Must exist, be readable, and contain CSV files
- Completed Projects Folder: Must exist, be readable, and be a directory
- Template Project Folder: Must exist, be readable, and contain QGIS project files

Usage:
    file_service = QGISFileSystemService()
    validator = ArcheoSyncConfigurationValidator(file_service)
    
    # Validate individual settings
    errors = validator.validate_field_projects_folder('/path/to/folder')
    
    # Validate all settings at once
    settings = {
        'field_projects_folder': '/path/to/field',
        'total_station_folder': '/path/to/total'
    }
    results = validator.validate_all_settings(settings)
    
    if validator.has_validation_errors(results):
        all_errors = validator.get_all_errors(results)
        print("Validation errors:", all_errors)

The validator provides:
- Clear, actionable error messages
- Comprehensive validation coverage
- Performance-optimized checks
- Extensible validation rules
"""

from typing import List
from pathlib import Path

try:
    from ..core.interfaces import IConfigurationValidator, IFileSystemService
except ImportError:
    from core.interfaces import IConfigurationValidator, IFileSystemService


class ArcheoSyncConfigurationValidator(IConfigurationValidator):
    """
    Configuration validator for ArcheoSync plugin settings.
    
    This class provides validation logic for all plugin configuration settings,
    ensuring that paths are valid and accessible.
    """
    
    def __init__(self, file_system_service: IFileSystemService):
        """
        Initialize the configuration validator.
        
        Args:
            file_system_service: Service for file system operations
        """
        self._file_system_service = file_system_service
    
    def validate_field_projects_folder(self, path: str) -> List[str]:
        """
        Validate field projects folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not path:
            errors.append("Field projects folder path is required")
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"Field projects folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"Field projects path is not a directory: {path}")
        else:
            # Check if directory is writable
            try:
                test_file = Path(path) / ".test_write"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError):
                errors.append(f"Field projects folder is not writable: {path}")
        
        return errors
    
    def validate_total_station_folder(self, path: str) -> List[str]:
        """
        Validate total station folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not path:
            errors.append("Total station folder path is required")
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"Total station folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"Total station path is not a directory: {path}")
        else:
            # Check if directory contains CSV files
            csv_files = self._file_system_service.list_files(path, '.csv')
            if not csv_files:
                errors.append(f"No CSV files found in total station folder: {path}")
        
        return errors
    
    def validate_completed_projects_folder(self, path: str) -> List[str]:
        """
        Validate completed projects folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not path:
            errors.append("Completed projects folder path is required")
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"Completed projects folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"Completed projects path is not a directory: {path}")
        else:
            # Check if directory is readable
            try:
                list(Path(path).iterdir())
            except (OSError, PermissionError):
                errors.append(f"Completed projects folder is not readable: {path}")
        
        return errors
    
    def validate_template_project_folder(self, path: str) -> List[str]:
        """
        Validate template project folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not path:
            errors.append("Template project folder path is required")
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"Template project folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"Template project path is not a directory: {path}")
        else:
            # Check if directory contains QGIS project files
            qgz_files = self._file_system_service.list_files(path, '.qgz')
            qgs_files = self._file_system_service.list_files(path, '.qgs')
            
            if not qgz_files and not qgs_files:
                errors.append(f"No QGIS project files (.qgz or .qgs) found in template folder: {path}")
        
        return errors
    
    def validate_all_settings(self, settings: dict) -> dict:
        """
        Validate all plugin settings at once.
        
        Args:
            settings: Dictionary containing all settings to validate
            
        Returns:
            Dictionary mapping setting names to lists of error messages
        """
        validation_results = {}
        
        # Validate each setting
        if 'field_projects_folder' in settings:
            validation_results['field_projects_folder'] = self.validate_field_projects_folder(
                settings['field_projects_folder']
            )
        
        if 'total_station_folder' in settings:
            validation_results['total_station_folder'] = self.validate_total_station_folder(
                settings['total_station_folder']
            )
        
        if 'completed_projects_folder' in settings:
            validation_results['completed_projects_folder'] = self.validate_completed_projects_folder(
                settings['completed_projects_folder']
            )
        
        if 'template_project_folder' in settings:
            validation_results['template_project_folder'] = self.validate_template_project_folder(
                settings['template_project_folder']
            )
        
        return validation_results
    
    def has_validation_errors(self, validation_results: dict) -> bool:
        """
        Check if any validation errors exist.
        
        Args:
            validation_results: Dictionary of validation results
            
        Returns:
            True if any errors exist, False otherwise
        """
        return any(errors for errors in validation_results.values())
    
    def get_all_errors(self, validation_results: dict) -> List[str]:
        """
        Get all validation error messages as a flat list.
        
        Args:
            validation_results: Dictionary of validation results
            
        Returns:
            List of all error messages
        """
        all_errors = []
        for setting_name, errors in validation_results.items():
            for error in errors:
                all_errors.append(f"{setting_name}: {error}")
        return all_errors 