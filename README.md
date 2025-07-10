# ArcheoSync

A QGIS plugin for archaeologists to prepare data for field work and import it back into the project.

## Features

- **Configuration Management**: Set up folders for field projects, total station data, and completed projects
- **Prepare Recording**: Create QField projects for selected recording areas with proper layer configuration
- **Import Data**: Import CSV files from total station data and completed field projects
- **QField Integration**: Seamless integration with QField for mobile data collection
- **Layer Management**: Automatic layer creation and configuration for field work
- **Background Image Selection**: Intelligent selection of overlapping raster layers for each recording area
- **Smart Field Validation**: Automatic detection and validation of object numbering and level fields
- **Empty Layer Creation**: Automatic creation of empty "Objects" and "Features" layers for offline editing

## Installation

1. Download the plugin files
2. Place them in your QGIS plugins directory
3. Enable the plugin in QGIS Plugin Manager

## Usage

### Configuration

1. Go to **Plugins > ArcheoSync > Configuration**
2. Set up the following folders:
   - **Field Projects Destination**: Where new field projects will be created
   - **Total Station CSV Files**: Folder containing CSV files from total station data
   - **Completed Field Projects**: Folder containing completed field projects (with .qgs files)
   - **Template QGIS Project**: Template project for field work (optional if using QField)
3. Select the appropriate layers for recording areas, objects, and features
4. Configure field mappings for objects layer (number and level fields)
5. Choose whether to use QField integration

### Prepare Recording

1. Select recording areas in your QGIS project
2. Go to **Plugins > ArcheoSync > Prepare Recording**
3. The dialog will show:
   - **Recording Areas**: Names from layer display expressions, sorted alphabetically
   - **Next Object Number**: Editable column with automatic calculation based on existing data
   - **Next Level**: Editable column with intelligent increment logic and case preservation
   - **Background Image**: Dropdown selection of overlapping raster layers for each area
4. Configure the next values for objects and features
5. Click OK to create QField projects for each selected recording area

### Import Data

1. Go to **Plugins > ArcheoSync > Import Data**
2. The dialog will display:
   - **Total Station CSV Files**: All CSV files found in the configured total station folder
   - **Completed Field Projects**: All folders containing .qgs files in the completed projects folder
3. Select the files and projects you want to import
4. Click OK to proceed with import (import functionality to be implemented)

## Architecture

The plugin follows clean architecture principles with:

- **Dependency Injection**: All services are injected for testability
- **Interface Segregation**: Services depend on interfaces, not concretions
- **Single Responsibility**: Each class has a single, well-defined purpose
- **Clean Separation**: UI, business logic, and data access are separated

### SOLID Principles Implementation

- **Single Responsibility Principle**: Each class has one reason to change
- **Open/Closed Principle**: Open for extension, closed for modification
- **Liskov Substitution Principle**: Any implementation can be substituted
- **Interface Segregation Principle**: Focused, specific interfaces
- **Dependency Inversion Principle**: Depend on abstractions, not concretions

## Development

### Running Tests

```bash
make test
```

The project includes 317 tests with 317 passing and 1 skipped (QGIS-specific translation test).

### Project Structure

- `archeosync/`: Main plugin package
  - `core/`: Core interfaces and abstractions
  - `services/`: Service implementations
  - `ui/`: User interface components
  - `test/`: Test files (317 tests)

### Key Services

- **QGISSettingsManager**: QGIS-specific settings management
- **QGISFileSystemService**: File system operations with Qt integration
- **QGISLayerService**: Layer operations including spatial analysis
- **QGISQFieldService**: QField integration and project packaging
- **ArcheoSyncConfigurationValidator**: Comprehensive validation system

## Recent Updates

### Version 0.5.0 (Latest)
- **QField Integration**: Complete QField project packaging with empty layer creation
- **Background Image Support**: Intelligent raster layer selection for recording areas
- **Enhanced UI**: Improved user experience with better validation and error handling
- **Test Coverage**: Expanded to 317 tests with comprehensive coverage

### Version 0.4.0
- **Background Image Selection**: Added spatial analysis for overlapping raster layers
- **Raster Layer Support**: Extended layer service with spatial intersection detection
- **QField Service**: Implemented comprehensive project packaging

### Version 0.3.0
- **Objects/Features Layer Support**: Added polygon/multipolygon geometry support
- **Field Validation**: Intelligent field type detection and validation
- **Next Values Columns**: Editable columns for object numbering and level information

## License

This project is licensed under the GNU General Public License v2.0. 