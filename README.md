# ArcheoSync QGIS Plugin

A QGIS plugin for archaeologists to prepare data for field recording and import it back into the project. This plugin follows SOLID principles and clean architecture patterns for maintainability, testability, and extensibility.

## Features

- **Field Project Management**: Prepare and manage field recording projects
- **Recording Preparation**: View selected entities in Recording areas layer for field preparation
- **Total Station Integration**: Import CSV data from total station devices
- **QField Integration**: Support for QField mobile data collection
- **Template Projects**: Use template QGIS projects for consistency
- **Polygon Layer Selection**: Choose polygon layers from your QGIS project for recording areas
- **Objects and Features Layers**: Select additional polygon/multipolygon layers for objects and features with field validation
- **Configuration Validation**: Comprehensive validation of all settings with conditional requirements
- **Internationalization**: Multi-language support
- **Layer Service**: Intelligent detection of polygon layers (supports both simple polygons and multipolygons)

## Installation

### Prerequisites

- QGIS 3.0 or later
- Python 3.7 or later

### Installation Steps

1. **Copy the plugin folder** to your QGIS plugins directory:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. **Enable the plugin**:
   - Open QGIS
   - Go to Plugins → Manage and Install Plugins
   - Search for "ArcheoSync" and enable it

## Usage

### Basic Setup

1. **Launch the plugin**: Go to Plugins → ArcheoSync → Configuration
2. **Configure settings**: Set up your folder paths and preferences
3. **Select recording areas layer**: Choose a polygon layer from your project for recording areas
4. **Configure objects layer**: Select a mandatory polygon/multipolygon layer for objects with optional field selections
5. **Configure features layer**: Optionally select a polygon/multipolygon layer for features
6. **Validate configuration**: The plugin will validate all settings
7. **Save settings**: Click OK to save your configuration

### Recording Preparation

1. **Select entities**: In your QGIS project, select entities in the configured Recording areas layer
2. **Open Prepare Recording**: Go to Plugins → ArcheoSync → Prepare Recording
3. **Review selection**: The dialog will show the number of selected entities and display them in a table
4. **Prepare recording**: Click "Prepare Recording" to continue (only enabled when entities are selected)

The table displays entity names sorted alphabetically. Names are extracted from:
- Layer display expressions (from the Display tab in layer properties)
- Common name fields (name, title, label, etc.)
- Feature IDs (as fallback)

### Configuration Options

- **Field Projects Destination**: Folder where new field projects will be created
- **Total Station CSV Files**: Folder containing CSV files from total station devices
- **Completed Field Projects**: Folder containing completed field projects to import
- **Recording Areas Layer**: Polygon layer from your QGIS project to define recording areas
- **Objects Layer**: Mandatory polygon/multipolygon layer for archaeological objects
  - **Number Field**: Optional integer field for object numbering
  - **Level Field**: Optional field for object level information
- **Features Layer**: Optional polygon/multipolygon layer for archaeological features
- **QField Integration**: Enable/disable QField for mobile data collection
- **Template QGIS Project**: Template project folder (only required when QField is disabled)

### Layer Selection

The plugin automatically detects all polygon layers in your current QGIS project:

- **Supported formats**: Shapefiles, GeoPackages, GeoJSON, and other vector formats
- **Geometry types**: Both simple polygons and multipolygons are supported
- **Layer information**: Shows layer name and feature count for easy identification
- **Refresh functionality**: Click the refresh button to update the layer list

#### Objects Layer Configuration

- **Mandatory selection**: Objects layer must be selected
- **Field validation**: Number field must be integer type if selected
- **Optional fields**: Both number and level fields are optional
- **Smart filtering**: Only integer fields appear in the number field dropdown

#### Features Layer Configuration

- **Optional selection**: Features layer is not required
- **Same geometry support**: Supports polygon and multipolygon layers

### QField Integration

When QField is enabled:
- Template project folder becomes optional
- Plugin optimizes settings for mobile data collection
- Validation rules are adjusted accordingly

When QField is disabled:
- Template project folder is required
- Traditional QGIS project workflow is used

## Development

### Running Tests

```bash
# Run all tests
python -m pytest test/

# Run specific test categories
python -m pytest test/test_core_interfaces.py
python -m pytest test/test_services.py
python -m pytest test/test_ui_components.py
python -m pytest test/test_layer_service.py

# Run tests with coverage
python -m pytest --cov=services --cov=ui --cov=core test/
```

### Test Results

- **169 tests passing**
- **1 test skipped** (QGIS-specific translation test)
- **0 failures**

### Architecture

The plugin follows SOLID principles and clean architecture:

- **Core Interfaces** (`core/interfaces.py`): Define contracts for all services
- **Service Implementations** (`services/`): Concrete implementations of interfaces
  - `settings_service.py`: QGIS settings management
  - `file_system_service.py`: File system operations
  - `layer_service.py`: QGIS layer operations and polygon detection
  - `configuration_validator.py`: Settings validation with conditional logic
  - `translation_service.py`: Internationalization support
- **UI Components** (`ui/`): User interface components with dependency injection
- **Comprehensive Testing** (`test/`): Full test suite with mocking

### Key Design Principles

- **Dependency Injection**: All services are injected through constructors
- **Interface Segregation**: Focused, specific interfaces for each concern
- **Single Responsibility**: Each class has a single, well-defined responsibility
- **Testability**: All components can be unit tested with mocks
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Validation**: Smart validation that adapts to user choices (e.g., QField settings)

### Recent Improvements

- **Objects and Features Layers**: Added support for additional polygon/multipolygon layers
- **Field Validation**: Intelligent field type detection and validation
- **Enhanced Layer Detection**: Improved polygon layer detection supporting multiple geometry types
- **Conditional Validation**: Template project folder validation based on QField setting
- **Better Error Messages**: More descriptive error messages for configuration issues
- **Robust Testing**: Comprehensive test coverage for all new features
- **Code Quality**: Clean, maintainable code following best practices

## Requirements

- QGIS 3.0 or later
- Python 3.7 or later

## Troubleshooting

### Common Issues

**No polygon layers found in dropdown:**
- Ensure you have polygon layers loaded in your QGIS project
- Check that layers are valid and not broken
- Try refreshing the layer list using the refresh button

**Objects layer validation error:**
- Objects layer is mandatory and must be selected
- Ensure the selected layer has polygon or multipolygon geometry
- If selecting a number field, ensure it is an integer type

**Number field shows Real/float fields:**
- Only integer fields should appear in the number field dropdown
- If you see Real/float fields, this indicates a bug that has been fixed in the latest version

**Template project folder validation error:**
- When using QField, the template project folder is not required
- Uncheck the QField option if you want to use a template project

**Layer service errors:**
- Verify that your polygon layers are valid
- Check the QGIS layer panel for any layer loading errors
- Ensure layers have proper coordinate reference systems

## Author

Elisa Caron-Laviolette  
Email: elisa.laviolette@gmail.com

## License

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version. 