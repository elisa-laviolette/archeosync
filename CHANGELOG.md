# Changelog

All notable changes to the ArcheoSync QGIS plugin will be documented in this file.

## [0.10.0] - 2025-07-12

### New Features

- **Intelligent QField Data Filtering**: Added automatic filtering of QField projects to include only relevant data
  - **Recording Area Filtering**: Automatically filters recording areas layer to keep only the selected feature
    - Identifies the correct recording area layer in QField projects
    - Removes all features except the selected recording area
    - Preserves project structure and layer configuration
  - **Related Extra Layers Filtering**: Filters extra layers based on QGIS relations
    - Analyzes QGIS relations between extra layers and recording areas layer
    - Keeps only features related to the selected recording area
    - Uses relation field mappings to identify related features
    - Supports multiple relation types and field configurations

### Technical Improvements

- **Enhanced Test Coverage**: Expanded test suite to 351 tests with comprehensive coverage
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

- **Raster Clipping for QField Projects**: Added automatic background image clipping to recording areas when creating QField projects
  - Configurable offset (default: 20 cm) to expand clipping area beyond recording area boundary
  - Uses GDAL tools (gdalwarp) for precise raster clipping with -cutline and -crop_to_cutline options
  - Original raster remains unchanged; clipped version is used only for QField projects
  - Automatic cleanup of temporary clipped rasters after project creation
  - Settings dialog includes new "Raster Clipping Offset" configuration option
  - Comprehensive error handling and GDAL availability checking

### Technical Improvements

- **Raster Processing Service**: New service for handling GDAL-based raster operations
  - GDAL command line tool integration (gdalwarp, ogr2ogr)
  - Temporary file management and cleanup
  - Coordinate system handling and WKT to GeoJSON conversion
  - Comprehensive test coverage for all raster processing operations
- **Enhanced QField Service**: Integrated raster processing into QField project creation workflow
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
  - QField Archive Folder: Configure dedicated folder for archiving imported QField projects
  - Archive folder selectors in settings dialog with browse functionality
  - Real-time validation of archive folder paths (existence, writability, directory type)

- **Automatic Archiving**: Imported files and projects are automatically moved to archive folders
  - CSV files are moved to CSV archive folder after successful import
  - QField projects are moved to QField archive folder after successful import
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
- **Extra Layers Support**: Added configuration option for additional vector layers in QField projects
  - Multi-select widget in settings dialog for choosing extra layers
  - Selected layers are included as read-only in QField projects
  - Recording areas layer is always included and cannot be deselected
  - User-friendly checkbox interface with clear labeling

### Technical Improvements
- **QField Service Consolidation**: Eliminated redundant method implementation
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

- **QField Project Import**: Added import functionality for completed QField projects
  - Automatic processing of data.gpkg files from QField project directories
  - Merging of Objects and Features layers from multiple projects
  - Creation of new "New Objects" and "New Features" layers in the project
  - Feature collection and validation from completed field recordings
  - Support for multiple project import in a single operation

- **Enhanced Project Naming**: QField project names now include level information when available
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