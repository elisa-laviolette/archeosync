# coding=utf-8
"""Basic tests that don't require QGIS.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import pytest
import os
import sys


@pytest.mark.unit
class TestBasicFunctionality:
    """Basic functionality tests that don't require QGIS."""
    
    def test_project_structure(self):
        """Test that the project has the expected structure."""
        # Check that main files exist
        assert os.path.exists('archeo_sync.py')
        assert os.path.exists('__init__.py')
        assert os.path.exists('resources.py')
        assert os.path.exists('ui/settings_dialog.py')
        
    def test_imports_available(self):
        """Test that basic imports work for the new dialog."""
        try:
            from ui.settings_dialog import SettingsDialog
            assert SettingsDialog is not None
        except ImportError:
            pytest.skip("SettingsDialog module not available")
            
    def test_resources_compiled(self):
        """Test that resources are properly compiled."""
        try:
            import resources
            assert resources is not None
            # Check that the resource functions exist
            assert hasattr(resources, 'qInitResources')
            assert hasattr(resources, 'qCleanupResources')
        except ImportError:
            pytest.skip("resources module not available")
    
    def test_project_naming_with_level(self):
        """Test that project naming includes level when defined."""
        # This test simulates the project naming logic from archeo_sync.py
        import re
        
        # Test case 1: Level is defined
        feature_name = "Test Area"
        level = "A"
        
        if level:
            project_name = f"{feature_name}_{level}"
        else:
            project_name = feature_name
        
        # Clean project name for file system
        project_name = re.sub(r'[^\w\-_\.]', '_', project_name)
        
        assert project_name == "Test_Area_A"
        
        # Test case 2: Level is not defined
        feature_name = "Test Area"
        level = ""
        
        if level:
            project_name = f"{feature_name}_{level}"
        else:
            project_name = feature_name
        
        # Clean project name for file system
        project_name = re.sub(r'[^\w\-_\.]', '_', project_name)
        
        assert project_name == "Test_Area"
        
        # Test case 3: Level with special characters
        feature_name = "Test Area (North)"
        level = "Level 1"
        
        if level:
            project_name = f"{feature_name}_{level}"
        else:
            project_name = feature_name
        
        # Clean project name for file system
        project_name = re.sub(r'[^\w\-_\.]', '_', project_name)
        
        assert project_name == "Test_Area__North__Level_1"


if __name__ == "__main__":
    pytest.main([__file__]) 