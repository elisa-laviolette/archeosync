#!/bin/bash

# Test setup script for ArcheoSync plugin
# This script helps set up the environment for running tests

set -e

echo "Setting up test environment for ArcheoSync plugin..."

# Check if we're in the right directory
if [ ! -f "archeo_sync_dialog.py" ]; then
    echo "Error: Please run this script from the plugin root directory"
    exit 1
fi

# Default QGIS installation path for macOS
QGIS_PREFIX_PATH="/Applications/QGIS-LTR.app/Contents/MacOS"
if [ -n "$1" ]; then
    QGIS_PREFIX_PATH=$1
fi

# Check if QGIS is installed
if [ ! -d "$QGIS_PREFIX_PATH" ]; then
    echo "Warning: QGIS not found at $QGIS_PREFIX_PATH"
    echo "You may need to install QGIS or specify the correct path"
    echo "Usage: $0 [qgis_path]"
fi

PROJ_LIB="/Applications/QGIS-LTR.app/Contents/Resources/proj"

echo "Setting up QGIS environment..."
echo "QGIS PATH: $QGIS_PREFIX_PATH"

# Set QGIS environment variables
export QGIS_PREFIX_PATH=${QGIS_PREFIX_PATH}
export QGIS_PATH=${QGIS_PREFIX_PATH}
export PYTHONPATH=${QGIS_PREFIX_PATH}/../Resources/python:${QGIS_PREFIX_PATH}/../Resources/python/plugins:${PYTHONPATH}
export PROJ_LIB=${PROJ_LIB}

# Set QGIS debug settings
export QGIS_DEBUG=0
export QGIS_LOG_FILE=/tmp/archeosync/qgis.log

# Create log directory if it doesn't exist
mkdir -p /tmp/archeosync

echo "QGIS environment variables set:"
echo "  QGIS_PREFIX_PATH: $QGIS_PREFIX_PATH"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  PROJ_LIB: $PROJ_LIB"
echo ""

echo "Test options:"
echo "  1. Run unit tests only (no QGIS required):"
echo "     make unittest"
echo ""
echo "  2. Run basic tests (no QGIS required):"
echo "     make test"
echo ""
echo "  3. Run full test suite (requires QGIS):"
echo "     make test-qgis"
echo ""
echo "  4. Run tests with current environment:"
echo "     python -m pytest test/ -v -m 'not qgis'"
echo ""

echo "To use this script, source it:"
echo "  source $BASH_SOURCE [optional_qgis_path]" 