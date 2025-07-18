# Changelog

All notable changes to the ArcheoSync QGIS plugin will be documented in this file.

## [0.17.0] - 2025-01-XX

### New Features

- **Import Summary Validation**: Enhanced import summary dialog with validation functionality
  - **Validate Button**: Replaced "OK" button with "Validate" button for feature validation workflow
  - **Feature Copying**: Automatically copies features from temporary layers to definitive layers
    - Copies from "New Objects" to configured Objects layer
    - Copies from "New Features" to configured Features layer  
    - Copies from "New Small Finds" to configured Small Finds layer
  - **Edit Mode Preservation**: Keeps definitive layers in edit mode after copying for continued editing
  - **Success Feedback**: Shows summary message with count of copied features for each layer type
  - **Error Handling**: Comprehensive error handling with user-friendly error messages
  - **Translation Support**: Full internationalization for validation messages with French translations
  - **Settings Integration**: Uses configured layer settings to identify definitive layers

- **Duplicate Objects Warnings**: Added comprehensive warnings for duplicate objects with the same recording area and number
  - **Import Summary Integration**: Warnings are displayed in the import summary dialog after successful data import
  - **Multi-Layer Detection**: Detects duplicates within the "New Objects" layer (imported objects), within the original "Objects" layer (existing objects), and between both layers
  - **Detailed Information**: Shows specific recording area names and object numbers for each duplicate found
  - **User-Friendly Display**: Color-coded warnings in orange for easy identification in the summary dialog
  - **Translation Support**: Full internationalization support for warning messages with French translations
  - **Automatic Detection**: Runs automatically when objects are imported, providing immediate feedback to users
  - **Error Handling**: Graceful handling of missing configuration or layers without failing the import process

## [0.16.0] - 2025-07-17

### Bug Fixes

- **Small Finds Duplicate Detection Fix**: Fixed issue where Small Finds features with virtual "Metre" fields were not being detected as duplicates during import
  - **Virtual Field Detection**: Enhanced `_is_virtual_field` method to better detect virtual expression fields, including common field names like "Metre", "Meter", "Area", etc.
  - **Signature Comparison**: Improved feature signature creation to exclude known virtual fields that are added during import process but don't represent actual data differences
  - **Duplicate Filtering**: Small Finds features with virtual "Metre" fields are now properly filtered out when they already exist in the current project
  - **Test Coverage**: Added comprehensive test to verify virtual field detection and signature comparison works correctly

## [0.15.0] - 2025-07-16

### New Features

- **Import Summary Dialog**: Added comprehensive summary dialog that displays after successful data import operations
  - **Import Statistics Display**: Shows detailed counts of imported CSV points, features, objects, and small finds
    - Displays total number of CSV points imported from total station data
    - Shows count of archaeological features imported from field projects
    - Reports number of archaeological objects imported from field projects
    - Displays count of small finds imported from field projects
  - **Duplicate Detection Reporting**: Displays number of duplicates detected and filtered out during import
    - Shows duplicate counts for each data type (CSV points, features, objects, small finds)
    - Color-coded display with green for successful imports and orange for duplicates
    - Only displays duplicate sections when duplicates are actually detected
  - **User-Friendly Interface**: Clean, organized dialog with intuitive design
    - Organized sections for each data type with clear headings
    - Scrollable content area for handling large amounts of data
    - Color-coded statistics with green for successful imports and orange for duplicates
    - Modal dialog with OK button for easy dismissal
  - **Translation Support**: Full internationalization support for all dialog elements
    - Complete French translations for all dialog strings
    - Complete Afrikaans translations for all dialog strings
    - Graceful fallback to English when translation service is not available
    - Translation service integration with dependency injection
  - **Automatic Display**: Dialog appears automatically after successful import operations
    - Triggers after successful CSV import operations
    - Triggers after successful field project import operations
    - Triggers after mixed import operations (both CSV and field projects)
    - Only displays when data is actually imported (counts > 0)
  - **Comprehensive Coverage**: Covers all import scenarios and data types
    - Handles CSV-only imports with point statistics
    - Handles field project-only imports with feature/object/small finds statistics
    - Handles mixed imports with combined statistics
    - Graceful handling of empty imports with no data sections displayed

### Technical Improvements

- **Enhanced Import Workflow**: Improved import process with better user feedback and statistics collection
  - **Statistics Collection**: Enhanced import services to collect and provide detailed import statistics
    - CSV import service provides count of imported features via `get_last_import_count()` method
    - Field project import service provides comprehensive statistics via `get_last_import_stats()` method
    - Statistics include counts and duplicate information for all data types
    - Integration with existing import workflow without breaking changes
  - **Seamless Integration**: Summary dialog integrates with existing CSV and field project import workflows
    - Modified `_handle_import_data_accepted()` method in main plugin to collect statistics
    - Added `_show_import_summary()` method to display the summary dialog
    - Integration with both CSV and field project import services
    - Maintains existing error handling and validation workflows
  - **Error Handling**: Graceful handling of missing data or translation services
    - Dialog works correctly when no translation service is provided
    - Handles cases where no data is imported gracefully
    - Proper error handling for dialog creation and display
    - Fallback behavior for missing dependencies
  - **SOLID Design**: Follows dependency injection and single responsibility principles
    - `ImportSummaryDialog` class with single responsibility for summary display
    - `ImportSummaryData` dataclass for clean data structure
    - Dependency injection for translation service
    - Interface-based design for extensibility
    - Clean separation of concerns between UI and business logic

### Test Coverage

- **Comprehensive Testing**: Added extensive test coverage for import summary dialog functionality
  - **Dialog Initialization Tests**: Tests for proper dialog creation and setup
    - Tests dialog initialization with various data scenarios
    - Tests dialog properties (modal, window title, etc.)
    - Tests handling of empty summary data
  - **Data Display Tests**: Tests for correct display of import statistics
    - Tests CSV section display when CSV data is present
    - Tests features section display when features data is present
    - Tests objects section display when objects data is present
    - Tests small finds section display when small finds data is present
  - **Translation Service Tests**: Tests for translation service integration
    - Tests translation service usage when provided
    - Tests graceful handling when no translation service is available
    - Tests translation of dialog strings and content
  - **Data Structure Tests**: Tests for `ImportSummaryData` dataclass
    - Tests data structure initialization and field access
    - Tests default values for all fields
    - Tests data integrity and type safety
  - **Integration Tests**: Tests for integration with main plugin workflow
    - Tests statistics collection from import services
    - Tests dialog display after successful imports
    - Tests error handling and edge cases

## [0.14.0] - 2025-07-16

### New Features

- **Duplicate Detection for Field Project Import**: Added intelligent duplicate detection to prevent importing features that already exist in the current project
  - **Automatic Duplicate Filtering**: Filters out features that already exist in Objects, Features, and Small Finds layers before creating merged layers
  - **Smart Feature Comparison**: Creates unique signatures based on feature attributes and geometry to identify duplicates
  - **Existing Layer Integration**: Retrieves existing layers from current project using settings configuration
  - **Seamless User Experience**: Works automatically without user intervention during import process
  - **Comprehensive Coverage**: Handles duplicates across all layer types (Objects, Features, Small Finds)
  - **Performance Optimized**: Efficient duplicate detection that scales with project size

- **Small Finds Layer Support**: Added support for small finds layers in field project creation and import
  - **Small Finds Layer Configuration**: New layer selector in settings dialog for small finds layers
    - Supports point, multipoint, and no geometry layer types
    - Optional configuration with proper validation
    - User-friendly dropdown with layer information display
  - **Field Project Creation**: Small finds layers are automatically included in field projects
    - Creates empty small finds layer copies for offline editing
    - Preserves layer structure, styling, and field configurations
    - Integrates with existing field project creation workflow
  - **Field Project Import**: Enhanced import functionality to process small finds layers
    - Automatic detection and processing of small finds layer files
    - Merging of small finds layers from multiple projects
    - Creation of "New Small Finds" layer in the current project
    - Support for both data.gpkg and individual layer file formats

### Technical Improvements

- **Enhanced Field Project Import Service**: Extended import service with duplicate detection capabilities
  - `_get_existing_layer()` method to retrieve existing layers from current project
  - `_filter_duplicates()` method with intelligent feature comparison using unique signatures
  - Integration with existing settings service for layer retrieval
  - Automatic duplicate filtering during import workflow
  - Bug fix for small finds layer processing in `_process_individual_layers()`
- **Enhanced Layer Service**: Extended layer service with small finds support
  - `get_point_and_multipoint_layers()` method for small finds layer detection
  - `get_no_geometry_layers()` method for small finds without geometry
  - `is_valid_point_or_multipoint_layer()` validation method
  - `is_valid_no_geometry_layer()` validation method
- **Configuration Validation**: Added comprehensive validation for small finds layers
  - Validates layer geometry types (point, multipoint, or no geometry)
  - Checks layer relationships with recording areas layer
  - Integration with existing validation framework
- **Service Architecture**: Enhanced services with translation support
  - Project creation service now supports translated layer names
  - Field project import service supports translated merged layer names
  - Optional translation service integration for internationalization
- **Internationalization**: Added French translations for small finds feature
  - "Small Finds Layer:" → "Couche des petits objets :"
  - "Small Finds" → "Petits objets"
  - "New Small Finds" → "Nouveaux petits objets"
  - Placeholder text and error messages translated

### Test Coverage

- **Comprehensive Testing**: Added extensive test coverage for duplicate detection and small finds functionality
  - Tests for duplicate detection with various feature types and geometries
  - Tests for existing layer retrieval and integration
  - Tests for feature signature creation and comparison
  - Tests for duplicate filtering during import workflow
  - Tests for small finds layer validation (point, multipoint, no geometry)
  - Tests for layer relationship validation
  - Tests for field project creation with small finds layers
  - Tests for field project import with small finds layers
  - Tests for layer detection and processing in various scenarios

## [0.13.0] - 2025-07-16

### New Features

- **Raster Enhancement Settings**: Added three new slider settings in the Raster tab of the configuration dialog for adjusting clipped raster layers:
  - **Brightness**: Adjust brightness from -255 to +255 (default: 0)
  - **Contrast**: Adjust contrast from -100 to +100 (default: 0)  
  - **Saturation**: Adjust saturation from -100 to +100 (default: 0)
  - Settings are applied to clipped raster layers when creating field projects
  - Real-time value display with slider controls
  - Proper validation and persistence of enhancement values
  - Comprehensive test coverage for all new settings

### Technical Improvements

- **Enhanced Settings Dialog**: Extended raster configuration tab with new enhancement section
  - User-friendly slider widgets with value labels
  - Proper integration with existing settings management
  - Validation for enhancement value ranges
  - Revert functionality for cancelled changes
- **Configuration Validation**: Added validation methods for raster enhancement settings
  - Type checking for integer values
  - Range validation for brightness (-255 to 255), contrast (-100 to 100), saturation (-100 to 100)
  - Integration with existing validation framework

## [0.12.0] - 2025-07-15

### New Features

- **Enhanced Field Project Import**: Extended field project import functionality to process individual layer files
  - **Dual Import Support**: Now processes both data.gpkg files and individual layer files (Objects.gpkg, Features.gpkg, etc.)
  - **Individual Layer Processing**: Can import Objects and Features layers that are not contained within data.gpkg files
  - **Hybrid Support**: Handles projects with both data.gpkg and individual layer files simultaneously
  - **Flexible File Detection**: Automatically detects and processes various layer file naming conventions
  - **Comprehensive Layer Merging**: Merges all discovered Objects and Features layers into new project layers

### Technical Improvements

- **FieldProjectImportService**: New dedicated service for field project import operations
  - Clean separation of concerns with focused import functionality
  - Comprehensive validation and error handling
  - Automatic archiving of imported projects
  - Project integration with current QGIS project
- **Enhanced Test Coverage**: Added comprehensive test suite for field project import service
  - Tests for data.gpkg processing
  - Tests for individual layer file processing
  - Tests for hybrid scenarios with both file types
  - Tests for layer detection and validation
- **Architecture Enhancement**: Improved service architecture with dedicated import service
  - Follows clean architecture principles
  - Dependency injection for testability
  - Interface-based design for extensibility

## [0.11.0] - 2025-07-15

### Breaking Changes

- **QField Dependency Removal**: Removed all QField-specific dependencies and references
  - **Service Renaming**: Renamed `QGISQFieldService` to `QGISProjectCreationService`
  - **Interface Updates**: Updated `IQFieldService` to `IProjectCreationService`
  - **Method Renaming**: Renamed QField-specific methods to generic field project methods
  - **Documentation Updates**: Updated all documentation to remove QField references
  - **Architecture Changes**: Updated architecture documentation to reflect field project creation focus
  - **User Interface**: Updated UI text and labels to use generic field project terminology
  - **Configuration**: Updated settings dialog to use field project archive folder terminology

### Technical Improvements

- **Clean Architecture**: Simplified architecture by removing QField-specific abstractions
- **Generic Implementation**: Made project creation service more generic for various mobile field tools
- **Documentation Cleanup**: Comprehensive removal of QField references from all documentation files
- **Future Flexibility**: Architecture now supports integration with various mobile field data collection tools

## [0.10.1] - 2025-07-14

### Bug Fixes

- **Raster Clipping Coordinate Comparison**: Fixed critical error in temporary shapefile creation during raster clipping
  - **Root Cause**: QgsPointXY objects were being compared directly with `!=` operator, causing type comparison errors
  - **Solution**: Implemented proper coordinate comparison using `.x()` and `.y()` methods for QgsPointXY objects
  - **Impact**: Resolves "'>' not supported between instances of 'str' and 'int'" error when preparing recordings with background images
  - **Compatibility**: Works with both single and multipart polygons, handles both closed and unclosed coordinate sequences
  - **Testing**: Added comprehensive tests for coordinate comparison scenarios to prevent regression

### Technical Improvements

- **Enhanced Error Handling**: Improved robustness of polygon coordinate processing in raster clipping operations
- **Test Coverage**: Added specific tests for coordinate comparison fix with both single and multipart polygons
- **Code Quality**: More explicit and type-safe coordinate comparison logic

## [0.10.0] - 2025-07-12

### New Features

- **Intelligent Field Project Data Filtering**: Added automatic filtering of field projects to include only relevant data
  - **Recording Area Filtering**: Automatically filters recording areas layer to keep only the selected feature
    - Identifies the correct recording area layer in field projects
    - Removes all features except the selected recording area
    - Preserves project structure and layer configuration
  - **Related Extra Layers Filtering**: Filters extra layers based on QGIS relations
    - Analyzes QGIS relations between extra layers and recording areas layer
    - Keeps only features related to the selected recording area
    - Uses relation field mappings to identify related features
    - Supports multiple relation types and field configurations

### Technical Improvements

- **Enhanced Test Coverage**: Expanded test suite to 357 tests with comprehensive coverage
  - **Filtering Tests**: Comprehensive test suite for new filtering functionality
    - Tests for recording area layer filtering
    - Tests for related extra layers filtering with relations
    - Tests for filtering when no relations exist
    - Tests for error handling and edge cases
    - Integration tests with packaging workflow
  - **Mock Improvements**: Enhanced mocking for QGIS components
    - Proper QgsVectorLayer mocking with spec
    - QgsProject mocking with correct return values
    - Relation manager mocking with dictionary structure
    - Comprehensive test coverage for all filtering scenarios
- **Code Quality**: Removed debug outputs and improved error handling
  - Clean production code without debug statements
  - Silent error handling for filtering operations
  - Improved code maintainability and readability

## [0.9.0] - 2025-07-11

### New Features

- **Raster Clipping for Field Projects**: Added automatic background image clipping to recording areas when creating field projects
  - Configurable offset (default: 20 cm) to expand clipping area beyond recording area boundary
  - Uses GDAL tools (gdalwarp) for precise raster clipping with -cutline and -crop_to_cutline options
  - Original raster remains unchanged; clipped version is used only for field projects
  - Automatic cleanup of temporary clipped rasters after project creation
  - Settings dialog includes new "Raster Clipping Offset" configuration option
  - Comprehensive error handling and GDAL availability checking

### Technical Improvements

- **Raster Processing Service**: New service for handling GDAL-based raster operations
  - GDAL command line tool integration (gdalwarp, ogr2ogr)
  - Temporary file management and cleanup
  - Coordinate system handling and WKT to GeoJSON conversion
  - Comprehensive test coverage for all raster processing operations
- **Enhanced Project Creation Service**: Integrated raster processing into field project creation workflow
  - Automatic raster clipping before project packaging
  - Layer configuration to use clipped raster instead of original
  - Proper cleanup of temporary layers and files
- **Settings Management**: Added raster clipping offset configuration
  - New setting: `raster_clipping_offset` (default: 0.2 meters)
  - Settings dialog includes user-friendly configuration widget
  - Proper validation and persistence of offset values

## [0.8.0] - 2025-07-11

### New Features
- **Archive Folder Management**: Added configuration for automatic archiving of imported files
  - CSV Archive Folder: Configure dedicated folder for archiving imported CSV files
  - Field Project Archive Folder: Configure dedicated folder for archiving imported field projects
  - Archive folder selectors in settings dialog with browse functionality
  - Real-time validation of archive folder paths (existence, writability, directory type)

- **Automatic Archiving**: Imported files and projects are automatically moved to archive folders
  - CSV files are moved to CSV archive folder after successful import
  - Field projects are moved to field project archive folder after successful import
  - Archive operations only occur after successful import to prevent data loss
  - Graceful error handling with user feedback for archive operations

### Technical Improvements
- **Enhanced File System Service**: Added move operations for files and directories
  - `move_file()` method for moving individual files
  - `move_directory()` method for moving entire directories
  - Integration with existing file system operations
  - Proper error handling and validation

## [0.7.0] - 2025-07-10

### New Features
- **Extra Layers Support**: Added configuration option for additional vector layers in field projects
  - Multi-select widget in settings dialog for choosing extra layers
  - Selected layers are included as read-only in field projects
  - Recording areas layer is always included and cannot be deselected
  - User-friendly checkbox interface with clear labeling

### Technical Improvements
- **Project Creation Service Consolidation**: Eliminated redundant method implementation
  - Removed `package_for_qfield_with_data_and_variables` method
  - Enhanced `package_for_qfield_with_data` with optional parameters:
    - `add_variables`: Controls project variable injection (default: True)
    - `next_values`: Required when `add_variables=True` for field preparation
    - `extra_layers`: Support for additional read-only layers
  - Improved code maintainability and reduced duplication
  - Preserved all existing functionality with backward compatibility

## [0.6.0] - 2025-07-10

### New Features
- **CSV Import System**: Implemented comprehensive CSV import functionality
  - Automatic validation of CSV files for required X, Y, Z columns (case-insensitive)
  - Intelligent column mapping across multiple CSV files with different structures
  - Interactive column mapping dialog for manual column matching
  - PointZ vector layer creation with all CSV attributes preserved

- **Field Project Import**: Added import functionality for completed field projects
  - Automatic processing of data.gpkg files from field project directories
  - Merging of Objects and Features layers from multiple projects
  - Creation of new "New Objects" and "New Features" layers in the project
  - Feature collection and validation from completed field recordings
  - Support for multiple project import in a single operation

- **Enhanced Project Naming**: Field project names now include level information when available
  - When a level is defined, project names follow the pattern: "Recording Area Name_Level"
  - Examples: "Test Area_A", "Excavation Site_Level 1", "Trench 1_B"
  - If no level is defined, only the recording area name is used
  - Project names are automatically cleaned for file system compatibility

### Technical Improvements
- **Enhanced Test Coverage**: Expanded test suite to 324 tests with comprehensive coverage
- **Service Architecture**: Added CSVImportService with clean interface implementation
- **UI Components**: New ColumnMappingDialog with dependency injection
- **Error Handling**: Comprehensive validation and error reporting throughout import process
- **Documentation**: Updated README and architecture documentation for import features

## [0.5.0] - 2025-07-10

### New Features
- **Prepare Recording with QField Support**: Implemented prepare recording functionality with QField integration
  - Automatically creates QField project folder structure
  - Packages selected layers and background images for offline use
  - Configures QField project settings for optimal mobile usage
  - Handles empty layer creation and cleanup seamlessly
  - Preserves layer styling, forms, and field configurations

### Technical Improvements

- **Documentation Updates**: Comprehensive updates to README.md reflecting current project state
- **Enhanced Test Coverage**: Expanded test suite to 324 tests with 324 passing
- **Code Quality**: Continued improvements to code quality and maintainability
- **User Experience**: Enhanced usability with better error messages and validation feedback

## [0.4.0] - 2025-07-09

### New Features

- **Background Image Selection**: Added "Background image" column to the recording areas table
  - Dropdown menu allows users to select raster layers that overlap with each recording area
  - Only shows raster layers that spatially intersect with the recording area geometry
  - Includes "No image" option for areas without background imagery
  - Raster layer names display with dimensions (width x height) for easy identification
  - Selection is preserved when getting next values for field preparation
- **Raster Layer Support**: Extended layer service to support raster layer operations
  - Added `get_raster_layers()` method to retrieve all raster layers from QGIS project
  - Added `get_raster_layers_overlapping_feature()` method for spatial relationship checking
  - Updated `get_layer_by_id()` to support both vector and raster layers
  - Enhanced spatial intersection detection using QGIS geometry operations

### Technical Improvements

- **Extended Interfaces**: Added raster layer methods to ILayerService interface
- **Spatial Analysis**: Implemented efficient spatial intersection checking between polygon features and raster extents
- **UI Enhancement**: Added custom dropdown widgets for background image selection in table cells
- **Test Coverage**: Added comprehensive tests for raster layer functionality and background image selection
- **Documentation**: Updated README and user documentation for background image feature
- **Layer Service Enhancement**: Added `create_empty_layer_copy()` and `remove_layer_from_project()` methods
- **QField Service**: Implemented comprehensive QField packaging with empty layer creation and cleanup

## [0.3.0] - 2025-07-08

### New Features

- **Objects Layer Support**: Added mandatory objects layer selection with polygon/multipolygon geometry support
- **Features Layer Support**: Added optional features layer selection with polygon/multipolygon geometry support
- **Field Validation**: Intelligent field type detection and validation for objects layer
- **Number Field Selection**: Optional integer field selection for object numbering with smart filtering
- **Level Field Selection**: Optional field selection for object level information
- **Enhanced UI**: Added field selection widgets that appear when objects layer is selected
- **Next Values Columns**: Added "Next object number" and "Next level" columns to the recording preparation table
  - Next object number is editable and defaults to last object number + 1
  - Next level is editable and automatically increments based on field type and case preservation
  - Columns only appear when corresponding fields are configured in settings

### Bug Fixes

- **Field Type Filtering**: Fixed issue where Real/float fields were incorrectly shown in integer field dropdown
- **Layer Service**: Corrected `is_integer` logic to exclude Real field types (type ID 6)

### Technical Improvements

- **Extended Interfaces**: Added validation methods for objects and features layers in core interfaces
- **Layer Service Enhancement**: Added `get_polygon_and_multipolygon_layers()` method for objects/features layers
- **Configuration Validation**: Extended validation to include objects layer requirements and field validation
- **UI Components**: Added comprehensive field selection widgets with proper visibility management
- **Test Coverage**: Added 36 new tests covering objects/features layer functionality and field validation
- **Level Calculation Logic**: Added intelligent level increment logic with case preservation
- **Table Editing**: Enhanced table with editable next value columns and read-only last value columns

### Test Results

- **225 tests passing** (increased from 169)
- **1 test skipped** (QGIS-specific translation test)
- **0 failures**

## [0.2.0] - 2025-07-03

### Major Refactoring

- **SOLID Principles Implementation**: Complete refactoring to follow SOLID principles
- **Clean Architecture**: Separation of concerns with clear interfaces and implementations
- **Dependency Injection**: All services are now injected through constructors
- **Comprehensive Testing**: 127 unit tests with full coverage of core functionality
- **Type Hints**: Complete type annotations throughout the codebase

### New Architecture

- **Core Interfaces** (`core/interfaces.py`): Define contracts for all services
- **Service Implementations** (`services/`): Concrete implementations with dependency injection
- **UI Components** (`ui/`): Clean, testable UI components
- **Testing Framework** (`test/`): Comprehensive test suite with mocking

### Technical Improvements

- **Code Quality**: PEP 8 compliance with enhanced standards
- **Error Handling**: Comprehensive error handling throughout
- **Performance**: Optimized file operations and settings management
- **Maintainability**: Clear separation of concerns and modular design
- **Extensibility**: Easy to add new features through interfaces
- **Testability**: All components can be unit tested with mocks

### Breaking Changes

- **Plugin Class**: Renamed to `ArcheoSyncPlugin`
- **Import Structure**: New package structure with core, services, and ui modules
- **Dependencies**: All dependencies now injected through constructors

## [0.1.0] - 2025-07-01

### Initial Development Release

- Basic field recording preparation functionality
- Total station CSV import capabilities
- QField integration support
- Template project management
- Basic settings dialog
- Multi-language support

---

*This changelog follows the [Keep a Changelog](https://keepachangelog.com/) format.* 