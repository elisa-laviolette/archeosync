# Changelog

All notable changes to the ArcheoSync QGIS plugin will be documented in this file.

## [0.2.0] - 2025-01-03

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

## [0.1.0] - 2025-01-01

### Initial Development Release

- Basic field recording preparation functionality
- Total station CSV import capabilities
- QField integration support
- Template project management
- Basic settings dialog
- Multi-language support

---

*This changelog follows the [Keep a Changelog](https://keepachangelog.com/) format.* 