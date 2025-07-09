# ArcheoSync Architecture

This document describes the architecture of the ArcheoSync QGIS plugin, focusing on the SOLID principles implementation and clean architecture patterns.

## Overview

The plugin follows SOLID principles and clean architecture to ensure maintainability, testability, and extensibility.

## SOLID Principles Implementation

### Single Responsibility Principle (SRP)
Each class has one reason to change:
- `QGISSettingsManager`: Only manages settings
- `QGISFileSystemService`: Only handles file operations
- `ArcheoSyncConfigurationValidator`: Only validates configuration

### Open/Closed Principle (OCP)
Open for extension, closed for modification:
```python
# Extend functionality by implementing interfaces
class CustomSettingsManager(ISettingsManager):
    def set_value(self, key: str, value: Any) -> None:
        # Custom implementation
        pass
```

### Liskov Substitution Principle (LSP)
Any implementation can be substituted:
```python
# This works with any ISettingsManager implementation
def save_settings(settings_manager: ISettingsManager):
    settings_manager.set_value('key', 'value')
```

### Interface Segregation Principle (ISP)
Focused, specific interfaces:
- `ISettingsManager`: Settings operations only
- `IFileSystemService`: File operations only
- `ITranslationService`: Translation operations only

### Dependency Inversion Principle (DIP)
Depend on abstractions, not concretions:
```python
class SettingsDialog:
    def __init__(self, settings_manager: ISettingsManager):  # Interface, not concrete class
        self._settings_manager = settings_manager
```

## Package Structure

```
archeosync/
├── core/                    # Core abstractions
│   ├── __init__.py
│   └── interfaces.py        # All interface definitions
├── services/               # Concrete implementations
│   ├── __init__.py
│   ├── settings_service.py
│   ├── file_system_service.py
│   ├── translation_service.py
│   └── configuration_validator.py
├── ui/                     # User interface components
│   ├── __init__.py
│   ├── settings_dialog.py
│   └── prepare_recording_dialog.py
├── test/                   # Test suite
│   ├── test_core_interfaces.py
│   ├── test_services.py
│   └── test_ui_components.py
└── archeo_sync.py          # Main plugin class
```

## Core Interfaces

### ISettingsManager
Interface for settings management operations:
- `set_value(key: str, value: Any) -> None`
- `get_value(key: str, default: Any = None) -> Any`
- `remove_value(key: str) -> None`
- `clear_all() -> None`

### IFileSystemService
Interface for file system operations:
- `select_directory(title: str, initial_path: Optional[str] = None) -> Optional[str]`
- `path_exists(path: str) -> bool`
- `create_directory(path: str) -> bool`

### ITranslationService
Interface for translation operations:
- `translate(message: str) -> str`
- `get_current_locale() -> str`

### IConfigurationValidator
Interface for configuration validation:
- `validate_field_projects_folder(path: str) -> List[str]`
- `validate_total_station_folder(path: str) -> List[str]`
- `validate_all_settings(settings: dict) -> dict`

### ILayerService
Interface for QGIS layer operations:
- `get_polygon_layers() -> List[Dict[str, Any]]`
- `get_layer_by_id(layer_id: str) -> Optional[Any]`
- `get_selected_features_count(layer_id: str) -> int`
- `get_selected_features_info(layer_id: str) -> List[Dict[str, Any]]`
- `get_layer_info(layer_id: str) -> Optional[Dict[str, Any]]`
- `get_related_objects_info(
    recording_area_feature,
    objects_layer_id: str,
    number_field: Optional[str],
    level_field: Optional[str],
    recording_areas_layer_id: Optional[str] = None
) -> Dict[str, Any]`
- `calculate_next_level(
    last_level: str,
    level_field: str,
    objects_layer_id: str
) -> str`

## Service Implementations

### QGISSettingsManager
QGIS-specific implementation using QSettings for persistent storage.

### QGISFileSystemService
QGIS-specific implementation with Qt dialog integration.

### QGISTranslationService
QGIS-specific implementation using QGIS translation system.

### ArcheoSyncConfigurationValidator
Comprehensive validation with detailed error reporting.

### QGISLayerService
QGIS-specific implementation for layer operations including selected features counting and intelligent level calculation with case preservation.

## UI Components

### SettingsDialog
Clean, testable settings dialog with dependency injection and real-time validation.

### PrepareRecordingDialog
Dialog for recording preparation showing selected entities in a table with names from layer display expressions, sorted alphabetically. Features editable "Next object number" and "Next level" columns that automatically calculate appropriate values based on existing data and field types.

## Testing Strategy

### Interface Tests
Test interface compliance and SOLID principles.

### Service Tests
Test concrete implementations with mocked dependencies.

### UI Tests
Test UI components with mocked services.

## Benefits

1. **Testability**: All components can be unit tested with mocks
2. **Maintainability**: Clear separation of concerns
3. **Extensibility**: Easy to add new features through interfaces
4. **Reliability**: Comprehensive validation and error handling
5. **Performance**: Optimized operations and caching
6. **User Experience**: Intelligent default values and case preservation for better usability

## Design Patterns

- **Dependency Injection**: All dependencies injected through constructors
- **Interface Segregation**: Focused, specific interfaces
- **Strategy Pattern**: Different implementations can be swapped
- **Factory Pattern**: Service creation and management
- **Observer Pattern**: UI updates based on state changes 

## QGISLayerService.get_related_objects_info Update

### New Signature

```
def get_related_objects_info(
    recording_area_feature,
    objects_layer_id: str,
    number_field: Optional[str],
    level_field: Optional[str],
    recording_areas_layer_id: Optional[str] = None
) -> Dict[str, Any]
```

- **recording_area_feature**: The feature in the recording areas layer.
- **objects_layer_id**: The ID of the objects layer.
- **number_field**: The name of the number field (optional).
- **level_field**: The name of the level field (optional).
- **recording_areas_layer_id**: The ID of the recording areas (parent) layer. **Required** for correct relationship lookup.

### Rationale
Previously, the method attempted to access `feature.layer()`, which is not available on QgsFeature. The new signature requires the parent layer ID to be passed explicitly, ensuring compatibility and correctness.

### Usage Example
```python
related_info = layer_service.get_related_objects_info(
    feature, objects_layer_id, number_field, level_field, recording_areas_layer_id
)
```

### Impact
- All usages in dialogs and tests must now provide the parent layer ID.
- This change improves reliability and avoids runtime errors.

## QGISLayerService.calculate_next_level Method

### New Method

```
def calculate_next_level(
    last_level: str,
    level_field: str,
    objects_layer_id: str
) -> str
```

- **last_level**: The last level value (can be empty string).
- **level_field**: The level field name.
- **objects_layer_id**: The objects layer ID.

### Features
- **Intelligent Increment**: Automatically determines increment logic based on field type
- **Case Preservation**: Maintains original case (uppercase/lowercase) when incrementing
- **Type-Aware**: Handles integer and string fields differently
- **Fallback Logic**: Provides sensible defaults for edge cases

### Increment Logic
- **Integer Fields**: Numeric increment (1 → 2, 10 → 11)
- **String Fields**: 
  - Single character: alphabetical increment (a → b, A → B, z → aa, Z → AA)
  - Multi-character: append "1" as fallback
- **Empty Values**: Start with "1" for integers, "a" for strings

### Usage Example
```python
next_level = layer_service.calculate_next_level(
    last_level, level_field, objects_layer_id
)
``` 