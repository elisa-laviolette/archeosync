#!/usr/bin/env python3
"""
Debug script for out-of-bounds detection service.

This script helps debug the out-of-bounds detection by running it directly
and showing detailed output about what's happening.
"""

import sys
import os

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
    from core.data_structures import WarningData
    print("Successfully imported OutOfBoundsDetectorService")
except ImportError as e:
    print(f"Error importing OutOfBoundsDetectorService: {e}")
    sys.exit(1)

def create_mock_services():
    """Create mock services for testing."""
    from unittest.mock import Mock
    
    # Mock settings manager
    settings_manager = Mock()
    settings_manager.get_value.side_effect = lambda key: {
        'recording_areas_layer': 'recording_areas_layer_id',
        'objects_layer': 'objects_layer_id',
        'features_layer': 'features_layer_id',
        'small_finds_layer': 'small_finds_layer_id',
        'objects_number_field': 'number'
    }.get(key, '')
    
    # Mock layer service
    layer_service = Mock()
    
    # Mock translation service
    translation_service = Mock()
    translation_service.translate.return_value = "Translated message"
    
    return settings_manager, layer_service, translation_service

def test_service_creation():
    """Test that the service can be created."""
    print("\n=== Testing Service Creation ===")
    
    settings_manager, layer_service, translation_service = create_mock_services()
    
    try:
        service = OutOfBoundsDetectorService(
            settings_manager=settings_manager,
            layer_service=layer_service,
            translation_service=translation_service
        )
        print("✓ Service created successfully")
        print(f"  Max distance: {service._max_distance_meters} meters")
        return service
    except Exception as e:
        print(f"✗ Error creating service: {e}")
        return None

def test_detection_with_no_layers():
    """Test detection when no layers are configured."""
    print("\n=== Testing Detection with No Layers ===")
    
    settings_manager, layer_service, translation_service = create_mock_services()
    
    # Mock no layers configured
    settings_manager.get_value.return_value = ''
    
    service = OutOfBoundsDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = service.detect_out_of_bounds_features()
    print(f"Warnings returned: {len(warnings)}")
    for warning in warnings:
        print(f"  - {warning}")

def test_detection_with_missing_layers():
    """Test detection when layers are configured but not found."""
    print("\n=== Testing Detection with Missing Layers ===")
    
    settings_manager, layer_service, translation_service = create_mock_services()
    
    # Mock layers configured but not found
    layer_service.get_layer_by_id.return_value = None
    
    service = OutOfBoundsDetectorService(
        settings_manager=settings_manager,
        layer_service=layer_service,
        translation_service=translation_service
    )
    
    warnings = service.detect_out_of_bounds_features()
    print(f"Warnings returned: {len(warnings)}")
    for warning in warnings:
        print(f"  - {warning}")

def main():
    """Main debug function."""
    print("=== Out-of-Bounds Detection Service Debug ===")
    
    # Test service creation
    service = test_service_creation()
    if not service:
        return
    
    # Test with no layers
    test_detection_with_no_layers()
    
    # Test with missing layers
    test_detection_with_missing_layers()
    
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    main() 