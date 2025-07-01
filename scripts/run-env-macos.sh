#!/bin/bash

# Default QGIS installation path for macOS
QGIS_PREFIX_PATH="/Applications/QGIS-LTR.app/Contents/MacOS"
if [ -n "$1" ]; then
    QGIS_PREFIX_PATH=$1
fi

PROJ_LIB="/Applications/QGIS-LTR.app/Contents/Resources/proj"

echo "Setting up QGIS environment for macOS..."
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

# Fix Python compatibility issues for Python 3.10+
export PYTHONPATH=${QGIS_PREFIX_PATH}/../Resources/python:${QGIS_PREFIX_PATH}/../Resources/python/plugins:${PYTHONPATH}

echo "QGIS environment variables set:"
echo "  QGIS_PREFIX_PATH: $QGIS_PREFIX_PATH"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  PROJ_LIB: $PROJ_LIB"
echo ""
echo "To use this script, source it:"
echo "  source $BASH_SOURCE [optional_qgis_path]"
echo ""
echo "Then run your tests:"
echo "  make test" 