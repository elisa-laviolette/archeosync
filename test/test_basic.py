# coding=utf-8
"""Basic tests that don't require QGIS environment."""

import pytest


@pytest.mark.unit
class TestBasic:
    """Basic tests that don't require QGIS."""

    def test_basic_import(self):
        """Test that basic imports work."""
        import sys
        assert sys.version_info >= (3, 6)

    def test_pytest_working(self):
        """Test that pytest is working correctly."""
        assert True

    def test_plugin_metadata(self):
        """Test that plugin metadata can be read."""
        import os
        metadata_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metadata.txt')
        assert os.path.exists(metadata_file)
        
        with open(metadata_file, 'r') as f:
            content = f.read()
            assert 'name=' in content
            assert 'version=' in content


if __name__ == '__main__':
    pytest.main([__file__]) 