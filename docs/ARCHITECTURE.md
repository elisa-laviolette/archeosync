# ArcheoSync Architecture

This document describes the architecture of the ArcheoSync QGIS plugin, focusing on the SOLID principles implementation and clean architecture patterns.

## Overview

The plugin follows SOLID principles and clean architecture to ensure maintainability, testability, and extensibility. The current version includes 325 tests with 325 passing and 1 skipped, demonstrating robust code quality and comprehensive coverage.

## SOLID Principles Implementation

### Single Responsibility Principle (SRP)
Each class has one reason to change:
- `QGISSettingsManager`: Only manages settings
- `QGISFileSystemService`: Only handles file operations
- `ArcheoSyncConfigurationValidator`: Only validates configuration
- `QGISQFieldService`: Only handles QField integration and packaging

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
- `IQFieldService`: QField operations only

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
│   ├── configuration_validator.py
│   ├── layer_service.py
│   └── qfield_service.py
├── ui/                     # User interface components
│   ├── __init__.py
│   ├── settings_dialog.py
│   ├── import_data_dialog.py
│   └── prepare_recording_dialog.py
├── test/                   # Test suite (325 tests)
│   ├── test_core_interfaces.py
│   ├── test_services.py
│   ├── test_ui_components.py
│   ├── test_import_data_dialog.py
│   ├── test_layer_service.py
│   ├── test_qfield_service.py
│   ├── test_csv_import_service.py
│   ├── test_prepare_recording_dialog.py
│   └── test_settings_dialog.py
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
- `get_polygon_and_multipolygon_layers() -> List[Dict[str, Any]]`
- `get_raster_layers() -> List[Dict[str, Any]]`
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
- `get_raster_layers_overlapping_feature(
    feature,
    recording_areas_layer_id: str
) -> List[Dict[str, Any]]`
- `create_empty_layer_copy(source_layer_id: str, new_layer_name: str) -> Optional[str]`
- `remove_layer_from_project(layer_id: str) -> bool`

### IQFieldService
Interface for QField integration:
- `package_for_qfield(
    recording_area_feature: Any,
    recording_areas_layer_id: str,
    objects_layer_id: str,
    features_layer_id: Optional[str],
    background_layer_id: Optional[str],
    extra_layers: Optional[List[str]] = None,
    destination_folder: str,
    project_name: str
) -> bool`
- `package_for_qfield_with_data(
    feature_data: Dict[str, Any],
    recording_areas_layer_id: str,
    objects_layer_id: str,
    features_layer_id: Optional[str],
    background_layer_id: Optional[str],
    extra_layers: Optional[List[str]] = None,
    destination_folder: str,
    project_name: str,
    add_variables: bool = True,
    next_values: Dict[str, str] = None
) -> bool`

## Service Implementations

### QGISSettingsManager
QGIS-specific implementation using QSettings for persistent storage.

### QGISFileSystemService
QGIS-specific implementation with Qt dialog integration.

### QGISTranslationService
QGIS-specific implementation using QGIS translation system.

### ArcheoSyncConfigurationValidator
Comprehensive validation with detailed error reporting and relationship checking.

### QGISLayerService
QGIS-specific implementation for layer operations including:
- Selected features counting
- Intelligent level calculation with case preservation
- Raster layer spatial analysis for background image selection
- Empty layer creation for QField offline editing
- Layer structure copying with styling preservation

### QGISQFieldService
QGIS-specific implementation for QField integration including:
- Automatic empty layer creation ("Objects", "Features")
- Layer configuration for offline editing with extra layers support
- Project packaging with area of interest
- Automatic cleanup of temporary layers
- Project variable injection for field preparation (optional)
- QField project import with data.gpkg processing
- Layer merging from multiple completed projects
- Consolidated method design eliminating code duplication

### CSVImportService
QGIS-specific implementation for CSV import operations including:
- CSV file validation for required X, Y, Z columns (case-insensitive)
- Column mapping across multiple CSV files with different structures
- PointZ vector layer creation with attribute preservation
- Automatic project integration
- Comprehensive error handling and validation
- Interactive column mapping dialog integration

## UI Components

### SettingsDialog
Clean, testable settings dialog with dependency injection and real-time validation.

### PrepareRecordingDialog
Dialog for recording preparation showing selected entities in a table with:
- Names from layer display expressions, sorted alphabetically
- Editable "Next object number" and "Next level" columns
- Automatic calculation of appropriate values based on existing data and field types
- "Background image" column with dropdown selection of overlapping raster layers
- Real-time validation and error handling

### ImportDataDialog
Dialog for importing data from CSV files and completed field projects with:
- **Dual List Interface**: Separate lists for CSV files and completed projects
- **Default Selection**: All items are selected by default for convenience
- **Quick Selection Controls**: "Select All" and "Deselect All" buttons for both lists
- **Alphabetical Sorting**: Both lists are sorted alphabetically by name for easy navigation
- **Real-time Scanning**: Automatic folder scanning with refresh capabilities
- **Error Handling**: Graceful handling of missing folders and file system errors
- **Dependency Injection**: Clean architecture with injected services for testability
- **Multi-selection Support**: Users can select multiple files and projects simultaneously
- **Tooltip Information**: Full file paths displayed on hover for clarity

### ColumnMappingDialog
Dialog for mapping columns across multiple CSV files with:
- **Visual Table Interface**: Clear table showing column mapping across files
- **Dropdown Selection**: Interactive dropdowns for column matching
- **Include/Exclude Options**: Checkboxes to include or exclude columns
- **Real-time Validation**: Validation of required columns (X, Y, Z)
- **User-friendly Error Messages**: Clear guidance for column mapping
- **Flexible Mapping**: Support for different column structures across files

## Testing Strategy

### Interface Tests
Test interface compliance and SOLID principles.

### Service Tests
Test concrete implementations with mocked dependencies.

### UI Tests
Test UI components with mocked services.

### Integration Tests
Test real QGIS environment integration.

## Benefits

1. **Testability**: All components can be unit tested with mocks (325 tests, 325 passing, 1 skipped)
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
- **Template Method Pattern**: QField packaging with customizable steps

## QField Integration Architecture

### Empty Layer Creation
The QField service creates empty layers for offline editing:
1. **Layer Copying**: Creates empty copies of configured objects and features layers
2. **Naming Convention**: Uses simple names "Objects" and "Features" for better usability
3. **Structure Preservation**: Maintains fields, forms, and styling from original layers
4. **Configuration**: Sets layers for offline editing in QField
5. **Cleanup**: Automatically removes temporary layers after project creation

### Project Packaging
The packaging process includes:
1. **Area of Interest**: Extracts geometry from recording area features
2. **Layer Configuration**: Configures all layers for appropriate sync actions
3. **Background Images**: Includes selected raster layers as background imagery
4. **Project Variables**: Injects next values for field preparation
5. **Export**: Creates QField-compatible project files

## Performance Considerations

- **Spatial Analysis**: Efficient spatial intersection checking using QGIS geometry operations
- **Layer Caching**: Intelligent caching of layer information to reduce repeated lookups
- **Memory Management**: Proper cleanup of QGIS objects to prevent memory leaks
- **Error Recovery**: Graceful handling of QGIS object deletion issues

## Latest Features (v0.7.0)

### QField Service Consolidation
- **Method Consolidation**: Eliminated redundant `package_for_qfield_with_data_and_variables` method
- **Enhanced API**: Updated `package_for_qfield_with_data` with optional parameters:
  - `add_variables`: Controls whether to add project variables (default: True)
  - `next_values`: Required when `add_variables=True` for field preparation
  - `extra_layers`: Support for additional read-only layers in QField projects
- **Code Quality**: Reduced duplication and improved maintainability
- **Backward Compatibility**: All existing functionality preserved

### Extra Layers Support
- **Configuration Dialog**: Added multi-select widget for extra vector layers
- **Read-Only Layers**: Selected extra layers are included as read-only in QField projects
- **Recording Areas Integration**: Recording areas layer is always included and locked
- **User-Friendly Interface**: Checkbox selection with clear labeling

## Previous Features (v0.6.0)

### Complete Import System
- **CSV Import Service**: Comprehensive CSV import with validation and column mapping
  - Automatic validation of required X, Y, Z columns (case-insensitive)
  - Intelligent column mapping across multiple CSV files
  - Interactive column mapping dialog for manual matching
  - PointZ vector layer creation with attribute preservation
  - Automatic project integration and error handling

- **QField Project Import**: Import completed QField projects
  - Automatic processing of data.gpkg files from project directories
  - Merging of Objects and Features layers from multiple projects
  - Creation of new layers for imported data
  - Feature collection and validation from field recordings

- **Column Mapping Dialog**: Interactive UI for CSV column mapping
  - Visual table interface for mapping columns across files
  - Dropdown selection with validation
  - Include/exclude options for each column
  - Real-time validation of required columns

### QField Integration Enhancements
- **Complete Project Packaging**: Full QField project creation with proper layer configuration
- **Empty Layer Creation**: Automatic creation of "Objects" and "Features" layers for offline editing
- **Background Image Integration**: Intelligent selection and inclusion of overlapping raster layers
- **Project Variables**: Automatic injection of next values for field preparation
- **Cleanup Management**: Proper removal of temporary layers after project creation

### Background Image Selection
- **Spatial Analysis**: Automatic detection of raster layers overlapping with recording areas
- **Smart Filtering**: Only shows relevant raster layers for each specific recording area
- **User-Friendly Interface**: Dropdown selection with layer dimensions and "No image" option
- **Performance Optimized**: Efficient spatial intersection checking using QGIS geometry operations

### Enhanced Field Validation
- **Intelligent Level Calculation**: Smart increment logic with case preservation
- **Field Type Detection**: Automatic detection of integer vs string fields
- **Next Value Prediction**: Automatic calculation of appropriate next values based on existing data
- **Real-time Validation**: Immediate feedback on field configuration and data integrity

## Future Enhancements

- **Cloud Integration**: Support for QFieldCloud synchronization
- **Advanced Validation**: More sophisticated relationship validation
- **Performance Monitoring**: Metrics collection for optimization
- **Plugin Ecosystem**: Extension points for third-party integrations 