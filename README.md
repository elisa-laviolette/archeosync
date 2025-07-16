# ArcheoSync

A QGIS plugin for archaeologists to prepare data for field work and import it back into the project.

## Features

- **Configuration Management**: Set up folders for field projects, total station data, and completed projects
- **Archive Management**: Configure archive folders for imported CSV files and field projects
- **Prepare Recording**: Create field projects for selected recording areas with proper layer configuration
- **Import Data**: Import CSV files from total station data and completed field projects
- **Automatic Archiving**: Imported files and projects are automatically moved to archive folders after successful import
- **Mobile Integration**: Seamless integration with mobile data collection tools
- **Layer Management**: Automatic layer creation and configuration for field work
- **Background Image Selection**: Intelligent selection of overlapping raster layers for each recording area
- **Raster Processing**: Automatic clipping of background images to recording areas with configurable offsets
- **Smart Field Validation**: Automatic detection and validation of object numbering and level fields
- **Empty Layer Creation**: Automatic creation of empty "Objects" and "Features" layers for offline editing
- **CSV Import Service**: Comprehensive CSV import with column mapping and validation
- **Field Project Import**: Import completed field projects and merge Objects/Features layers
- **Column Mapping Dialog**: Interactive column mapping for CSV files with different structures
- **Intelligent Data Filtering**: Automatic filtering of field projects to include only relevant data:
  - **Recording Area Filtering**: Keeps only the selected recording area feature
  - **Related Extra Layers Filtering**: Filters extra layers based on QGIS relations
  - **Relation-Based Filtering**: Uses QGIS relations to identify and preserve related features

## Installation

1. Download the plugin files
2. Place them in your QGIS plugins directory
3. Enable the plugin in QGIS Plugin Manager

## Usage

### Configuration

1. Go to **Plugins > ArcheoSync > Configuration**
2. The configuration dialog is organized into three tabs for better organization:

   **Folders Tab:**
   - **Field Projects Destination**: Where new field projects will be created
   - **Total Station CSV Files**: Folder containing CSV files from total station data
   - **Completed Field Projects**: Folder containing completed field projects (with .qgs files)
   - **CSV Archive Folder**: Folder where imported CSV files will be moved after successful import
   - **Field Project Archive Folder**: Folder where imported field projects will be moved after successful import

   **Layers Tab:**
   - **Recording Areas Layer**: Select the layer containing recording area polygons
   - **Objects Layer**: Select the layer for archaeological objects
   - **Features Layer**: Select the layer for archaeological features
   - **Objects Field Configuration**: Configure number and level fields for the objects layer
   - **Extra Layers for Field Projects**: Select additional vector layers to include in field projects

   **Raster Tab:**
   - **Raster Clipping Offset**: Configure the offset (in meters) for clipping background images to recording areas
   - **Raster Enhancement Settings**: Adjust visual properties of clipped raster layers:
     - **Brightness**: Adjust brightness from -255 to +255 (default: 0)
     - **Contrast**: Adjust contrast from -100 to +100 (default: 0)
     - **Saturation**: Adjust saturation from -100 to +100 (default: 0)

### Prepare Recording

1. Select recording areas in your QGIS project
2. Go to **Plugins > ArcheoSync > Prepare Recording**
3. The dialog will show:
   - **Recording Areas**: Names from layer display expressions, sorted alphabetically
   - **Next Object Number**: Editable column with automatic calculation based on existing data
   - **Next Level**: Editable column with intelligent increment logic:
  - Letter + number patterns (e.g., 'A1' → 'A2', 'B3' → 'B4')
  - Pure numeric strings increment numerically (e.g., '5' → '6')
  - Mixed content appends '1' (e.g., 'Level A' → 'Level A1')
  - Case preservation maintained throughout
   - **Background Image**: Dropdown selection of overlapping raster layers for each area
4. Configure the next values for objects and features
5. Click OK to create QGIS field projects for each selected recording area

**Project Naming**: When a level is defined, field project names will be the display name of the recording area followed by '_' and the content of the Next level column. For example: "Test Area_A" or "Excavation Site_Level 1". If no level is defined, only the recording area name is used.

**Background Image Processing**: When a background image is selected, the system will automatically clip the raster to the recording area boundary with a configurable offset (default: 20 cm). This ensures the background image extends slightly beyond the recording area for better context in the field. The original raster remains unchanged, and the clipped version is used only for the field project. Background images are positioned at the bottom of the layer tree for optimal visualization.

**Raster Enhancement**: Clipped raster layers can be enhanced with brightness, contrast, and saturation adjustments. These settings are applied during field project creation and saved in QML style files to ensure consistent appearance across different QGIS installations. Enhancement settings are particularly useful for improving visibility of archaeological features in challenging lighting conditions or for highlighting specific elements in the background imagery.

**Intelligent Data Filtering**: When creating field projects, the system automatically filters the data to include only relevant information:
- **Recording Area Filtering**: Only the selected recording area feature is kept in the recording areas layer
- **Related Extra Layers Filtering**: For extra layers with QGIS relations to the recording areas layer, only features related to the selected recording area are kept
- **Relation-Based Filtering**: Uses QGIS relation manager to identify related features across layers
- **Clean Datasets**: Creates focused, efficient field projects with only the necessary data for field work

The raster processing service uses GDAL for high-quality clipping operations and handles:
- Coordinate system transformations
- Temporary file management
- Buffer zone creation around recording areas
- GeoTIFF output format for maximum compatibility
- Automatic cleanup of temporary files

### Import Data

1. Go to **Plugins > ArcheoSync > Import Data**
2. The dialog will display:
   - **Total Station CSV Files**: All CSV files found in the configured total station folder
   - **Completed Field Projects**: All folders containing .qgs files in the completed projects folder
3. Select the files and projects you want to import
4. Click OK to proceed with import

#### CSV Import Features
- **Automatic Validation**: Validates that CSV files contain required X, Y, Z columns (case-insensitive)
- **Column Mapping**: Automatically maps columns across multiple CSV files with different structures
- **Interactive Mapping**: If columns differ, shows a dialog to manually map columns
- **PointZ Layer Creation**: Creates PointZ vector layers with all CSV attributes
- **Project Integration**: Automatically adds imported layers to the QGIS project
- **Automatic Archiving**: Moves imported CSV files to the configured archive folder after successful import
- **Error Handling**: Comprehensive error handling with user-friendly messages

#### Field Project Import Features
- **Data.gpkg Processing**: Automatically processes data.gpkg files from field projects
- **Layer Merging**: Merges Objects and Features layers from multiple projects
- **Layer Creation**: Creates new "New Objects" and "New Features" layers in the project
- **Feature Collection**: Collects all features from completed field recordings
- **Automatic Archiving**: Moves imported field projects to the configured archive folder after successful import
- **Validation**: Validates project structure and data integrity

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

The project includes comprehensive test coverage with robust validation and quality assurance.

### Project Structure

- `archeosync/`: Main plugin package
  - `core/`: Core interfaces and abstractions
  - `services/`: Service implementations
  - `ui/`: User interface components
  - `test/`: Test files with comprehensive coverage

### Key Services

- **QGISSettingsManager**: QGIS-specific settings management
- **QGISFileSystemService**: File system operations with Qt integration and archive functionality
- **QGISLayerService**: Layer operations including spatial analysis
- **QGISProjectCreationService**: Field project creation and packaging with automatic archiving and intelligent filtering
- **QGISRasterProcessingService**: GDAL-based raster clipping with coordinate system handling
- **CSVImportService**: CSV import with column mapping, validation, and automatic archiving
- **ArcheoSyncConfigurationValidator**: Comprehensive validation system including archive folder validation

## Recent Updates

### Version 0.13.0 (Latest)
- **Raster Enhancement Settings**: Added comprehensive raster enhancement capabilities for field projects
  - **Brightness Control**: Adjust brightness from -255 to +255 with slider controls
  - **Contrast Control**: Adjust contrast from -100 to +100 for better feature distinction
  - **Saturation Control**: Adjust saturation from -100 to +100 for color enhancement
  - **Style Persistence**: Enhancement settings saved in QML files for consistent appearance
  - **User Interface**: Enhanced settings dialog with dedicated raster enhancement section
  - **Validation**: Comprehensive validation for all enhancement parameters
  - **Integration**: Seamless integration with existing raster clipping workflow
- **Technical Improvements**: Enhanced raster processing with QGIS renderer integration
  - Direct integration with QGIS raster renderer methods
  - Automatic QML style file generation with enhancement parameters
  - Real-time preview and validation of enhancement settings
  - Comprehensive test coverage for all enhancement functionality

### Version 0.10.1
- **Raster Clipping Coordinate Comparison Fix**: Fixed critical error in temporary shapefile creation during raster clipping
  - **Root Cause**: QgsPointXY objects were being compared directly with `!=` operator, causing type comparison errors
  - **Solution**: Implemented proper coordinate comparison using `.x()` and `.y()` methods for QgsPointXY objects
  - **Impact**: Resolves "'>' not supported between instances of 'str' and 'int'" error when preparing recordings with background images
  - **Compatibility**: Works with both single and multipart polygons, handles both closed and unclosed coordinate sequences
  - **Testing**: Added comprehensive tests for coordinate comparison scenarios to prevent regression
- **Enhanced Error Handling**: Improved robustness of polygon coordinate processing in raster clipping operations
- **Test Coverage**: Expanded to 357 tests with comprehensive coverage

### Version 0.10.0
- **Intelligent Field Project Data Filtering**: Added automatic filtering of field projects to include only relevant data
  - **Recording Area Filtering**: Automatically keeps only the selected recording area feature
  - **Related Extra Layers Filtering**: Filters extra layers based on QGIS relations to recording areas
  - **Relation-Based Filtering**: Uses QGIS relation manager to identify and preserve related features
  - **Clean Datasets**: Creates focused, efficient field projects for field work
- **Enhanced Test Coverage**: Expanded to 357 tests with comprehensive filtering test coverage
- **Code Quality**: Removed debug outputs and improved error handling for production readiness

### Version 0.9.0
- **Raster Processing Service**: Added GDAL-based raster clipping with configurable offsets
- **Background Image Clipping**: Automatic clipping of background images to recording area boundaries
- **Coordinate System Handling**: Automatic CRS transformations and validation
- **Temporary File Management**: Intelligent cleanup of temporary files during processing
- **Test Coverage**: Expanded to 351 tests with comprehensive coverage

### Version 0.8.0
- **Archive Folder Management**: Added configuration for CSV and field project archive folders
- **Automatic Archiving**: Imported files and projects are automatically moved to archive folders after successful import
- **Enhanced File System Service**: Added move operations for files and directories
- **Configuration Validation**: Real-time validation of archive folder paths
- **Test Coverage**: Expanded to 347 tests with comprehensive coverage

### Version 0.7.0
- **Project Creation Service Consolidation**: Eliminated redundant methods and improved API design
- **Extra Layers Support**: Added support for additional read-only layers in field projects
- **Enhanced Configuration**: Multi-select widget for extra vector layers

### Version 0.6.0
- **Complete Import System**: Comprehensive CSV import and field project import functionality
- **Column Mapping Dialog**: Interactive UI for CSV column mapping
- **Project Creation Enhancements**: Complete project packaging with empty layer creation

### Version 0.5.0
- **Project Creation Integration**: Complete field project packaging with empty layer creation
- **Background Image Support**: Intelligent raster layer selection for recording areas
- **Enhanced UI**: Improved user experience with better validation and error handling
- **Test Coverage**: Expanded to 324 tests with comprehensive coverage

### Version 0.4.0
- **Background Image Selection**: Added spatial analysis for overlapping raster layers
- **Raster Layer Support**: Extended layer service with spatial intersection detection
- **Project Creation Service**: Implemented comprehensive project packaging

### Version 0.3.0
- **Objects/Features Layer Support**: Added polygon/multipolygon geometry support
- **Field Validation**: Intelligent field type detection and validation
- **Next Values Columns**: Editable columns for object numbering and level information

## License

This project is licensed under the GNU General Public License v2.0. 