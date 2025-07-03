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
│   └── settings_dialog.py
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

## Service Implementations

### QGISSettingsManager
QGIS-specific implementation using QSettings for persistent storage.

### QGISFileSystemService
QGIS-specific implementation with Qt dialog integration.

### QGISTranslationService
QGIS-specific implementation using QGIS translation system.

### ArcheoSyncConfigurationValidator
Comprehensive validation with detailed error reporting.

## UI Components

### SettingsDialog
Clean, testable settings dialog with dependency injection and real-time validation.

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

## Design Patterns

- **Dependency Injection**: All dependencies injected through constructors
- **Interface Segregation**: Focused, specific interfaces
- **Strategy Pattern**: Different implementations can be swapped
- **Factory Pattern**: Service creation and management
- **Observer Pattern**: UI updates based on state changes 