# Changelog

All notable changes to the ArcheoSync QGIS plugin will be documented in this file.

## [0.3.0] - 2025-07-08

### New Features

- **Objects Layer Support**: Added mandatory objects layer selection with polygon/multipolygon geometry support
- **Features Layer Support**: Added optional features layer selection with polygon/multipolygon geometry support
- **Field Validation**: Intelligent field type detection and validation for objects layer
- **Number Field Selection**: Optional integer field selection for object numbering with smart filtering
- **Level Field Selection**: Optional field selection for object level information
- **Enhanced UI**: Added field selection widgets that appear when objects layer is selected

### Bug Fixes

- **Field Type Filtering**: Fixed issue where Real/float fields were incorrectly shown in integer field dropdown
- **Layer Service**: Corrected `is_integer` logic to exclude Real field types (type ID 6)

### Technical Improvements

- **Extended Interfaces**: Added validation methods for objects and features layers in core interfaces
- **Layer Service Enhancement**: Added `get_polygon_and_multipolygon_layers()` method for objects/features layers
- **Configuration Validation**: Extended validation to include objects layer requirements and field validation
- **UI Components**: Added comprehensive field selection widgets with proper visibility management
- **Test Coverage**: Added 36 new tests covering objects/features layer functionality and field validation

### Test Results

- **169 tests passing** (increased from 133)
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