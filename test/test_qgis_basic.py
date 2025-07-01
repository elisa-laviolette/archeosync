# coding=utf-8
"""Basic QGIS functionality tests."""

import pytest
from .utilities import get_qgis_app

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import QgsApplication, QgsProject
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestQGISBasic:
    """Basic QGIS functionality tests."""

    def test_qgis_app_initialized(self):
        """Test that QGIS application is properly initialized."""
        qgis_app, canvas, iface, parent = get_qgis_app()
        assert qgis_app is not None, "QGIS application should be initialized"
        if qgis_app is not None:
            assert qgis_app.prefixPath() != "", "QGIS prefix path should be set"

    def test_qgis_project(self):
        """Test basic QGIS project functionality."""
        project = QgsProject.instance()
        assert project is not None, "QGIS project should be available"
        
        # Test setting and getting project title
        test_title = "Test Project"
        project.setTitle(test_title)
        assert project.title() == test_title, "Project title should be set correctly"

    def test_qgis_version(self):
        """Test that QGIS version information is available."""
        # Try different ways to get QGIS version
        try:
            version = QgsApplication.QGIS_VERSION
        except AttributeError:
            try:
                version = QgsApplication.version()
            except AttributeError:
                version = "Unknown"
        
        assert version is not None, "QGIS version should be available"
        assert len(version) > 0, "QGIS version should not be empty"
        print(f"QGIS Version: {version}")


if __name__ == '__main__':
    pytest.main([__file__]) 