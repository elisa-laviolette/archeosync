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
- **Background Image Selection**: Automatic detection of raster layers overlapping recording areas for background image selection
- **Empty Layer Creation**: Automatic creation of empty objects and features layers for QField offline editing

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

### Setup

1. **Open the configuration**: Go to Plugins → ArcheoSync → Configuration
2. **Configure folders**: Set up your folder paths
3. **Select recording areas layer**: Choose a polygon layer from your project for recording areas
4. **Configure objects layer**: Select a mandatory polygon/multipolygon layer for objects with optional field selections
The objects layer must have a relationship with the recording areas layer:
   - The relationship defines which objects belong to which recording area
   - The objects layer should be the child layer (referencing layer)
   - The recording areas layer should be the parent layer (referenced layer)
   - The relationship can be configured in QGIS Layer Properties → Relations

5. **Configure objects layer fields**: 
- **Number Field**: Choose an integer field to track sequential object numbers
  - Must be an integer type field
  - Used to determine the next available number for new objects
  - The plugin will show the last used number for each recording area
- **Level Field**: Choose a field to record object levels
  - Can be any field type (text, numeric, etc.)
  - Used to track subsequent recordings in the same area
  - The plugin will show the last recorded level for each recording area

6. **Configure features layer**: Optionally select a polygon/multipolygon layer for features
7. **Validate configuration**: The plugin will validate all settings
8. **Save settings**: Click OK to save your configuration

### Recording Preparation

1. **Select entities**: In your QGIS project, select entities in the configured Recording areas layer
2. **Open Prepare Recording**: Go to Plugins → ArcheoSync → Prepare Recording
3. **Review selection**: The dialog will show the number of selected entities and display them in a table with:
   - Entity name (from display expression or common fields)
   - Last object number (if configured)
   - Next object number (editable, defaults to last number + 1)
   - Last level (if configured)
   - Next level (editable, defaults to incremented last level)
   - Background image (dropdown with overlapping raster layers)
4. **Prepare recording**: Click "Prepare Recording" to continue (only enabled when entities are selected)

The table displays entity names sorted alphabetically. Names are extracted from:
- Layer display expressions (from the Display tab in layer properties)
- Common name fields (name, title, label, etc.)
- Feature IDs (as fallback)

**Background Image Selection:**
- Each recording area shows a dropdown with available raster layers
- Only raster layers that spatially overlap with the recording area are shown
- Users can select "No image" or any overlapping raster layer
- Raster layer names include dimensions (width x height) for easy identification
- The selection is preserved when getting next values for field preparation

**Next Values Calculation:**
- **Next object number**: Automatically calculated as the last object number + 1 (or 1 if no previous objects exist)
- **Next level**: Automatically calculated based on the level field type:
  - For integer fields: increments numerically (1 → 2, 10 → 11)
  - For string fields: increments alphabetically (a → b, A → B, z → aa, Z → AA)
  - Case is preserved (uppercase stays uppercase, lowercase stays lowercase)
  - For complex strings: appends "1" as fallback
- **Background image**: Selected raster layer ID or empty string for "No image"

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
- **Empty Layers for Offline Editing**: The plugin automatically creates empty objects and features layers in QField projects:
  - **Objects Layer**: Creates an empty layer named "Objects" with the same structure as the configured objects layer
  - **Features Layer**: Creates an empty layer named "Features" with the same structure as the configured features layer (if configured)
  - **Offline Editing**: Both empty layers are configured for offline editing in QField
  - **Same Structure**: Empty layers maintain the same fields, forms, and styling as the original layers
  - **No Data**: Empty layers contain no features, allowing field workers to add new data
  - **Automatic Cleanup**: Empty layers are automatically removed from the main QGIS project after QField project creation

When QField is disabled:
- Template project folder is required
- Traditional QGIS project workflow is used

## Development

### Running Tests

```bash
# Run all tests (unit tests + QGIS-dependent tests)
make test-all

# Run unit tests only (no QGIS dependencies)
make test

# Run specific test categories
python -m pytest test/test_core_interfaces.py
python -m pytest test/test_services.py
python -m pytest test/test_ui_components.py
python -m pytest test/test_layer_service.py

# Run tests with coverage
python -m pytest --cov=services --cov=ui --cov=core test/
```

### Test Results

- **264 tests total**
- **263 tests passing**
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
  - `qfield_service.py`: QField integration with empty layer creation
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

- **Background Image Selection**: Added spatial analysis for raster layer selection
- **Empty Layer Creation**: Simplified naming convention ("Objects", "Features") for better usability
- **Enhanced Layer Service**: Added raster layer support and spatial intersection detection
- **Improved Validation**: Comprehensive configuration validation with relationship checking
- **Better Error Handling**: More robust error handling throughout the application
- **Performance Optimization**: Optimized operations and caching for better performance

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 