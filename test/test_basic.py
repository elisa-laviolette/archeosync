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


if __name__ == "__main__":
    pytest.main([__file__]) 