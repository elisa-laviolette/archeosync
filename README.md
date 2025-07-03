# ArcheoSync QGIS Plugin

A QGIS plugin for archaeologists to prepare data for field recording and import it back into the project. This plugin follows SOLID principles and clean architecture patterns for maintainability, testability, and extensibility.

## Features

- **Field Project Management**: Prepare and manage field recording projects
- **Total Station Integration**: Import CSV data from total station devices
- **QField Integration**: Support for QField mobile data collection
- **Template Projects**: Use template QGIS projects for consistency
- **Configuration Validation**: Comprehensive validation of all settings
- **Internationalization**: Multi-language support

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

1. **Launch the plugin**: Go to Plugins → ArcheoSync → Prepare field recording
2. **Configure settings**: Set up your folder paths and preferences
3. **Validate configuration**: The plugin will validate all settings
4. **Save settings**: Click OK to save your configuration

### Configuration Options

- **Field Projects Destination**: Folder where new field projects will be created
- **Total Station CSV Files**: Folder containing CSV files from total station devices
- **Completed Field Projects**: Folder containing completed field projects to import
- **QField Integration**: Enable/disable QField for mobile data collection
- **Template QGIS Project**: Template project folder (when QField is disabled)

## Development

### Running Tests

```bash
# Run all tests
python -m pytest test/

# Run specific test categories
python -m pytest test/test_core_interfaces.py
python -m pytest test/test_services.py
python -m pytest test/test_ui_components.py
```

### Test Results

- **129 tests passing**
- **1 test skipped** (QGIS-specific translation test)
- **0 failures**

### Architecture

The plugin follows SOLID principles and clean architecture:

- **Core Interfaces** (`core/interfaces.py`): Define contracts for all services
- **Service Implementations** (`services/`): Concrete implementations of interfaces
- **UI Components** (`ui/`): User interface components with dependency injection
- **Comprehensive Testing** (`test/`): Full test suite with mocking

### Key Design Principles

- **Dependency Injection**: All services are injected through constructors
- **Interface Segregation**: Focused, specific interfaces for each concern
- **Single Responsibility**: Each class has a single, well-defined responsibility
- **Testability**: All components can be unit tested with mocks

## Requirements

- QGIS 3.0 or later
- Python 3.7 or later

## Author

Elisa Caron-Laviolette  
Email: elisa.laviolette@gmail.com

## License

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version. 