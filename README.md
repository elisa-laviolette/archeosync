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
- **Empty Layer Creation**: Automatic creation of empty "Objects", "Features", and "Small Finds" layers for offline editing
- **Small Finds Support**: Comprehensive support for small finds layers with point, multipoint, and no geometry types
- **CSV Import Service**: Comprehensive CSV import with column mapping and validation
- **Field Project Import**: Import completed field projects and merge Objects/Features/Small Finds layers
- **Duplicate Detection**: Intelligent duplicate detection prevents importing features that already exist in the current project
  - **Automatic Duplicate Filtering**: Filters out features that already exist in Objects, Features, and Small Finds layers before creating merged layers
  - **Smart Feature Comparison**: Creates unique signatures based on feature attributes and geometry to identify duplicates (excluding layer-specific feature IDs and virtual fields)
  - **Virtual Field Handling**: Properly detects and excludes virtual expression fields (like "Metre" fields) that are added during import but don't represent data differences
  - **Existing Layer Integration**: Retrieves existing layers from current project using settings configuration
  - **Seamless User Experience**: Works automatically without user intervention during import process
  - **Comprehensive Coverage**: Handles duplicates across all layer types (Objects, Features, Small Finds)
  - **Performance Optimized**: Efficient duplicate detection that scales with project size
- **Column Mapping Dialog**: Interactive column mapping for CSV files with different structures
- **Import Summary Dialog**: Comprehensive summary dialog showing import statistics after data import
  - **Import Statistics**: Displays counts of imported CSV points, features, objects, and small finds
  - **Duplicate Detection**: Shows number of duplicates detected and filtered out during import
  - **User-Friendly Interface**: Clean, organized display with sections for each data type
  - **Translation Support**: Full internationalization support for summary dialog
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
   - **Small Finds Layer**: Select the layer for small finds (supports point, multipoint, and no geometry types)
   - **Total Station Points Layer**: Select the layer for total station points (supports point and multipoint types)
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
- **Layer Merging**: Merges Objects, Features, and Small Finds layers from multiple projects
- **Duplicate Detection**: Automatically filters out features that already exist in the current project's Objects, Features, and Small Finds layers
- **Smart Feature Comparison**: Uses unique signatures based on attributes and geometry to identify duplicates (excluding layer-specific feature IDs)
- **Layer Creation**: Creates new "New Objects", "New Features", and "New Small Finds" layers in the project
- **Feature Collection**: Collects all features from completed field recordings
- **Automatic Archiving**: Moves imported field projects to the configured archive folder after successful import
- **Validation**: Validates project structure and data integrity

#### Import Summary Dialog
After successful import, the plugin displays a comprehensive summary dialog showing:
- **CSV Points**: Number of total station points imported from CSV files
- **Features**: Number of archaeological features imported from field projects
- **Objects**: Number of archaeological objects imported from field projects
- **Small Finds**: Number of small finds imported from field projects
- **Duplicate Detection**: Number of duplicates detected and filtered out during import for each data type
- **Duplicate Objects Warnings**: Detailed warnings about objects with the same recording area and number
  - Detects duplicates within the "New Objects" layer (imported objects)
  - Detects duplicates within the original "Objects" layer (existing objects)
  - Detects duplicates between both layers
  - Shows specific recording area names and object numbers for each duplicate
  - Color-coded warnings in orange for easy identification

#### Validation and Layer Copying
When you click the "Validate" button in the import summary dialog:
- **Feature Copying**: Features are automatically copied from temporary layers to your configured definitive layers:
  - "New Objects" → configured Objects layer
  - "New Features" → configured Features layer
  - "New Small Finds" → configured Small Finds layer
  - "Imported_CSV_Points" → configured Total Station Points layer
- **Edit Mode**: The definitive layers are kept in edit mode for review
- **Feature Selection**: Newly copied features are automatically selected for easy identification
- **User Control**: You can save or cancel the changes as needed
- **Validation Button**: "Validate" button to copy features from temporary to definitive layers
  - Copies features from "New Objects" to the configured Objects layer
  - Copies features from "New Features" to the configured Features layer
  - Copies features from "New Small Finds" to the configured Small Finds layer
  - Keeps definitive layers in edit mode for further editing
  - Shows summary of copied features with success message
- **Clean Interface**: Organized sections with clear statistics and color-coded information
- **Translation Support**: Full internationalization with French and Afrikaans translations

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

### Version 0.15.0 (Latest)
- **Import Summary Dialog**: Added comprehensive summary dialog that displays after successful data import
  - **Import Statistics Display**: Shows detailed counts of imported CSV points, features, objects, and small finds
  - **Duplicate Detection Reporting**: Displays number of duplicates detected and filtered out during import for each data type
  - **User-Friendly Interface**: Clean, organized dialog with sections for each data type and color-coded information
  - **Translation Support**: Full internationalization with French and Afrikaans translations for all dialog elements
  - **Automatic Display**: Dialog appears automatically after successful import operations
  - **Comprehensive Coverage**: Covers all import scenarios including CSV files, field projects, and mixed imports
- **Enhanced Import Workflow**: Improved import process with better user feedback
  - **Statistics Collection**: Enhanced import services to collect and provide detailed import statistics
  - **Seamless Integration**: Summary dialog integrates with existing CSV and field project import workflows
  - **Error Handling**: Graceful handling of missing data or translation services
  - **SOLID Design**: Follows dependency injection and single responsibility principles

### Version 0.14.0
- **Duplicate Detection for Field Project Import**: Added intelligent duplicate detection to prevent importing features that already exist in the current project
  - **Automatic Duplicate Filtering**: Filters out features that already exist in Objects, Features, and Small Finds layers before creating merged layers
  - **Smart Feature Comparison**: Creates unique signatures based on feature attributes and geometry to identify duplicates
  - **Existing Layer Integration**: Retrieves existing layers from current project using settings configuration
  - **Seamless User Experience**: Works automatically without user intervention during import process
  - **Comprehensive Coverage**: Handles duplicates across all layer types (Objects, Features, Small Finds)
  - **Performance Optimized**: Efficient duplicate detection that scales with project size
- **Small Finds Layer Support**: Added comprehensive support for small finds layers in field project creation and import
  - **Small Finds Configuration**: New layer selector in settings dialog supporting point, multipoint, and no geometry types
  - **Field Project Creation**: Small finds layers automatically included in field projects with empty layer creation
  - **Field Project Import**: Enhanced import functionality to process and merge small finds layers from multiple projects
  - **Layer Validation**: Comprehensive validation for small finds layer geometry types and relationships
  - **Internationalization**: Complete French translations for small finds feature ("Petits objets")
  - **Service Architecture**: Enhanced services with optional translation support for internationalization
- **Technical Improvements**: Extended layer service with small finds support and enhanced import service
  - New methods for point/multipoint and no geometry layer detection
  - Enhanced configuration validation for small finds layers
  - Duplicate detection methods in field project import service
  - Comprehensive test coverage for all small finds and duplicate detection functionality
  - Integration with existing field project workflow

### Version 0.13.0
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