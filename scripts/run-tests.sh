#!/bin/bash

# Test runner script for ArcheoSync plugin
# This script handles Python compatibility issues and QGIS environment setup

set -e

echo "========================================="
echo "ArcheoSync Plugin Test Runner"
echo "========================================="

# Check if QGIS environment is set up
if [ -z "$QGIS_PREFIX_PATH" ]; then
    echo "QGIS environment not set up. Please source the environment script first:"
    echo "  source scripts/run-env-macos.sh [qgis_path]"
    exit 1
fi

echo "QGIS Prefix Path: $QGIS_PREFIX_PATH"
echo "Python Path: $PYTHONPATH"
echo ""

# Set Python warnings to ignore deprecation warnings
export PYTHONWARNINGS="ignore::DeprecationWarning,ignore::PendingDeprecationWarning"

# Run tests with proper error handling
echo "Running tests..."
python -m pytest test/ -v --tb=short --disable-warnings

echo ""
echo "Tests completed!" 