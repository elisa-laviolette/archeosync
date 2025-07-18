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
- Layer validation for QGIS layers
- Detailed error reporting
- Batch validation for multiple settings

Validation Rules:
- Field Projects Folder: Must exist, be writable, and be a directory
- Total Station Folder: Must exist and be a directory (CSV files are optional)
- Completed Projects Folder: Must exist, be readable, and be a directory
- Template Project Folder: Must exist, be readable, and contain QGIS project files
- Recording Areas Layer: Must be a valid polygon layer in the current project

Usage:
    file_service = QGISFileSystemService()
    layer_service = QGISLayerService()
    validator = ArcheoSyncConfigurationValidator(file_service, layer_service)
    
    # Validate individual settings
    errors = validator.validate_field_projects_folder('/path/to/folder')
    
    # Validate all settings at once
    settings = {
        'field_projects_folder': '/path/to/field',
        'total_station_folder': '/path/to/total',
        'recording_areas_layer': 'layer_id_123'
    }
    results = validator.validate_all_settings(settings)
    
    if validator.has_validation_errors(results):
        all_errors = validator.get_all_errors(results)
        # Validation errors would be handled by the calling code

The validator provides:
- Clear, actionable error messages
- Comprehensive validation coverage
- Performance-optimized checks
- Extensible validation rules
"""

from typing import List, Optional
from pathlib import Path

try:
    from ..core.interfaces import IConfigurationValidator, IFileSystemService, ILayerService, ValidationResult
except ImportError:
    from core.interfaces import IConfigurationValidator, IFileSystemService, ILayerService, ValidationResult




class ArcheoSyncConfigurationValidator(IConfigurationValidator):
    """
    Configuration validator for ArcheoSync plugin settings.
    
    This class provides validation logic for all plugin configuration settings,
    ensuring that paths are valid and accessible, and layers are valid.
    """
    
    def __init__(self, file_system_service: IFileSystemService, layer_service: ILayerService = None):
        """
        Initialize the configuration validator.
        
        Args:
            file_system_service: Service for file system operations
            layer_service: Service for layer operations (optional)
        """
        self._file_system_service = file_system_service
        self._layer_service = layer_service
    
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
        elif not self._file_system_service.is_writable(path):
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
        # Note: CSV files are not required - the folder just needs to exist
        
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
        elif not self._file_system_service.is_readable(path):
            errors.append(f"Completed projects folder is not readable: {path}")
        
        return errors
    
    def validate_csv_archive_folder(self, path: str) -> List[str]:
        """
        Validate CSV archive folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # CSV archive folder is optional, so no error if empty
        if not path:
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"CSV archive folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"CSV archive path is not a directory: {path}")
        elif not self._file_system_service.is_writable(path):
            errors.append(f"CSV archive folder is not writable: {path}")
        
        return errors
    
    def validate_field_project_archive_folder(self, path: str) -> List[str]:
        """
        Validate field project archive folder configuration.
        
        Args:
            path: Path to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Field project archive folder is optional, so no error if empty
        if not path:
            return errors
        
        if not self._file_system_service.path_exists(path):
            errors.append(f"Field project archive folder does not exist: {path}")
        elif not self._file_system_service.is_directory(path):
            errors.append(f"Field project archive path is not a directory: {path}")
        elif not self._file_system_service.is_writable(path):
            errors.append(f"Field project archive folder is not writable: {path}")
        
        return errors
    

    

    
    def validate_recording_areas_layer(self, layer_id: str) -> List[str]:
        """
        Validate recording areas layer configuration.
        
        Args:
            layer_id: Layer ID to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not layer_id:
            # Recording areas layer is optional, so no error if not set
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for validation")
            return errors
        
        if not self._layer_service.is_valid_polygon_layer(layer_id):
            errors.append(f"Selected layer is not a valid polygon layer: {layer_id}")
        
        layer_info = self._layer_service.get_layer_info(layer_id)
        if not layer_info:
            errors.append(f"Layer not found in current project: {layer_id}")
        elif not layer_info.get('is_valid', False):
            errors.append(f"Selected layer is not valid: {layer_info.get('name', layer_id)}")
        
        return errors
    
    def validate_objects_layer(self, layer_id: str) -> List[str]:
        """
        Validate objects layer configuration.
        
        Args:
            layer_id: Layer ID to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not layer_id:
            # Objects layer is mandatory, so error if not set
            errors.append("Objects layer is required")
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for validation")
            return errors
        
        if not self._layer_service.is_valid_polygon_or_multipolygon_layer(layer_id):
            errors.append(f"Selected layer is not a valid polygon or multipolygon layer: {layer_id}")
        
        layer_info = self._layer_service.get_layer_info(layer_id)
        if not layer_info:
            errors.append(f"Layer not found in current project: {layer_id}")
        elif not layer_info.get('is_valid', False):
            errors.append(f"Selected layer is not valid: {layer_info.get('name', layer_id)}")
        
        return errors
    
    def validate_features_layer(self, layer_id: str) -> List[str]:
        """
        Validate features layer configuration.
        
        Args:
            layer_id: Layer ID to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not layer_id:
            # Features layer is optional, so no error if not set
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for validation")
            return errors
        
        if not self._layer_service.is_valid_polygon_or_multipolygon_layer(layer_id):
            errors.append(f"Selected layer is not a valid polygon or multipolygon layer: {layer_id}")
        
        layer_info = self._layer_service.get_layer_info(layer_id)
        if not layer_info:
            errors.append(f"Layer not found in current project: {layer_id}")
        elif not layer_info.get('is_valid', False):
            errors.append(f"Selected layer is not valid: {layer_info.get('name', layer_id)}")
        
        return errors

    def validate_small_finds_layer(self, layer_id: str) -> List[str]:
        """
        Validate small finds layer configuration.
        
        Args:
            layer_id: Layer ID to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not layer_id:
            # Small finds layer is optional, so no error if not set
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for validation")
            return errors
        
        # Check if it's a valid point/multipoint layer or no geometry layer
        is_valid_point = self._layer_service.is_valid_point_or_multipoint_layer(layer_id)
        is_valid_no_geom = self._layer_service.is_valid_no_geometry_layer(layer_id)
        
        if not is_valid_point and not is_valid_no_geom:
            errors.append(f"Selected layer is not a valid point/multipoint layer or no geometry layer: {layer_id}")
        
        layer_info = self._layer_service.get_layer_info(layer_id)
        if not layer_info:
            errors.append(f"Layer not found in current project: {layer_id}")
        elif not layer_info.get('is_valid', False):
            errors.append(f"Selected layer is not valid: {layer_info.get('name', layer_id)}")
        
        return errors

    def validate_total_station_points_layer(self, layer_id: str) -> List[str]:
        """
        Validate total station points layer configuration.
        
        Args:
            layer_id: Layer ID to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not layer_id:
            # Total station points layer is optional, so no error if not set
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for validation")
            return errors
        
        # Check if it's a valid point/multipoint layer
        is_valid_point = self._layer_service.is_valid_point_or_multipoint_layer(layer_id)
        
        if not is_valid_point:
            errors.append(f"Selected layer is not a valid point/multipoint layer: {layer_id}")
        
        layer_info = self._layer_service.get_layer_info(layer_id)
        if not layer_info:
            errors.append(f"Layer not found in current project: {layer_id}")
        elif not layer_info.get('is_valid', False):
            errors.append(f"Selected layer is not valid: {layer_info.get('name', layer_id)}")
        
        return errors
    
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
        # If no layer is selected, fields are not applicable
        if not layer_id:
            return ValidationResult(True, "No layer selected, field validation skipped")
        
        # Get layer fields
        fields = self._layer_service.get_layer_fields(layer_id)
        if fields is None:
            return ValidationResult(False, f"Could not retrieve fields for layer {layer_id}")
        
        # Create a map of field names to field info for easy lookup
        field_map = {field['name']: field for field in fields}
        
        # Validate number field if provided
        if number_field:
            if number_field not in field_map:
                return ValidationResult(False, f"Number field '{number_field}' not found in layer")
            
            if not field_map[number_field]['is_integer']:
                return ValidationResult(False, f"Number field '{number_field}' must be an integer field")
        
        # Validate level field if provided
        if level_field:
            if level_field not in field_map:
                return ValidationResult(False, f"Level field '{level_field}' not found in layer")
        
        return ValidationResult(True, "Field validation successful")
    
    def validate_layer_relationships(self, recording_areas_layer_id: str, objects_layer_id: str, features_layer_id: str, small_finds_layer_id: str) -> List[str]:
        """
        Validate that child layers have proper relationships with the recording areas layer.
        
        Args:
            recording_areas_layer_id: The recording areas layer ID (parent)
            objects_layer_id: The objects layer ID (child)
            features_layer_id: The features layer ID (child, optional)
            small_finds_layer_id: The small finds layer ID (child, optional)
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # If no recording areas layer is set, relationships are not required
        if not recording_areas_layer_id:
            return errors
        
        # If no child layers are set, relationships are not required
        if not objects_layer_id and not features_layer_id and not small_finds_layer_id:
            return errors
        
        if not self._layer_service:
            errors.append("Layer service not available for relationship validation")
            return errors
        
        # Validate objects layer relationship if set
        if objects_layer_id:
            if not self._has_valid_relationship(recording_areas_layer_id, objects_layer_id):
                errors.append("Objects layer must have a relationship with Recording areas layer")
        
        # Validate features layer relationship if set
        if features_layer_id:
            if not self._has_valid_relationship(recording_areas_layer_id, features_layer_id):
                errors.append("Features layer must have a relationship with Recording areas layer")
        
        # Validate small finds layer relationship if set
        if small_finds_layer_id:
            if not self._has_valid_relationship(recording_areas_layer_id, small_finds_layer_id):
                errors.append("Small finds layer must have a relationship with Recording areas layer")
        
        return errors

    def _has_valid_relationship(self, parent_layer_id: str, child_layer_id: str) -> bool:
        """
        Check if there is a valid relationship between parent and child layers.
        
        Args:
            parent_layer_id: The parent layer ID (recording areas)
            child_layer_id: The child layer ID (objects or features)
            
        Returns:
            True if a valid relationship exists, False otherwise
        """
        # Get all relationships for the child layer
        child_relations = self._layer_service.get_layer_relationships(child_layer_id)
        
        # Check if any relationship connects the child to the parent
        for relation in child_relations:
            # For a valid relationship, the child should be the referencing layer
            # and the parent should be the referenced layer
            if (relation.referencingLayerId() == child_layer_id and 
                relation.referencedLayerId() == parent_layer_id):
                return True
        
        return False
    
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
        
        if 'csv_archive_folder' in settings:
            validation_results['csv_archive_folder'] = self.validate_csv_archive_folder(
                settings['csv_archive_folder']
            )
        
        if 'field_project_archive_folder' in settings:
            validation_results['field_project_archive_folder'] = self.validate_field_project_archive_folder(
                settings['field_project_archive_folder']
            )
        
        if 'raster_brightness' in settings:
            validation_results['raster_brightness'] = self.validate_raster_brightness(
                settings['raster_brightness']
            )
        
        if 'raster_contrast' in settings:
            validation_results['raster_contrast'] = self.validate_raster_contrast(
                settings['raster_contrast']
            )
        
        if 'raster_saturation' in settings:
            validation_results['raster_saturation'] = self.validate_raster_saturation(
                settings['raster_saturation']
            )
        
        if 'recording_areas_layer' in settings:
            validation_results['recording_areas_layer'] = self.validate_recording_areas_layer(
                settings['recording_areas_layer']
            )
        
        if 'objects_layer' in settings:
            validation_results['objects_layer'] = self.validate_objects_layer(
                settings['objects_layer']
            )
            
            # Validate objects layer fields if layer is selected
            if settings['objects_layer']:
                number_field = settings.get('objects_number_field', '')
                level_field = settings.get('objects_level_field', '')
                field_validation = self.validate_objects_layer_fields(
                    settings['objects_layer'], 
                    number_field if number_field else None, 
                    level_field if level_field else None
                )
                if not field_validation.is_valid:
                    validation_results['objects_layer_fields'] = [field_validation.message]
        
        if 'features_layer' in settings:
            validation_results['features_layer'] = self.validate_features_layer(
                settings['features_layer']
            )
        
        if 'small_finds_layer' in settings:
            validation_results['small_finds_layer'] = self.validate_small_finds_layer(
                settings['small_finds_layer']
            )
        
        if 'total_station_points_layer' in settings:
            validation_results['total_station_points_layer'] = self.validate_total_station_points_layer(
                settings['total_station_points_layer']
            )
        
        # Validate layer relationships if layers are configured
        recording_areas_layer = settings.get('recording_areas_layer', '')
        objects_layer = settings.get('objects_layer', '')
        features_layer = settings.get('features_layer', '')
        small_finds_layer = settings.get('small_finds_layer', '')
        
        if recording_areas_layer or objects_layer or features_layer or small_finds_layer:
            relationship_errors = self.validate_layer_relationships(
                recording_areas_layer,
                objects_layer,
                features_layer,
                small_finds_layer
            )
            if relationship_errors:
                validation_results['layer_relationships'] = relationship_errors
        
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

    def validate_raster_brightness(self, value: int) -> List[str]:
        """
        Validate raster brightness setting.
        
        Args:
            value: Brightness value to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not isinstance(value, int):
            errors.append("Brightness value must be an integer")
        elif value < -255 or value > 255:
            errors.append("Brightness value must be between -255 and 255")
        
        return errors
    
    def validate_raster_contrast(self, value: int) -> List[str]:
        """
        Validate raster contrast setting.
        
        Args:
            value: Contrast value to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not isinstance(value, int):
            errors.append("Contrast value must be an integer")
        elif value < -100 or value > 100:
            errors.append("Contrast value must be between -100 and 100")
        
        return errors
    
    def validate_raster_saturation(self, value: int) -> List[str]:
        """
        Validate raster saturation setting.
        
        Args:
            value: Saturation value to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not isinstance(value, int):
            errors.append("Saturation value must be an integer")
        elif value < -100 or value > 100:
            errors.append("Saturation value must be between -100 and 100")
        
        return errors 