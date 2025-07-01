# coding=utf-8
"""Resources test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'elisa.laviolette@gmail.com'
__date__ = '2025-07-01'
__copyright__ = 'Copyright 2025, Elisa Caron-Laviolette'

import pytest

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtGui import QIcon
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False



@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestArcheoSyncResources:
    """Test rerources work."""

    def setup_method(self):
        """Runs before each test."""
        pass

    def teardown_method(self):
        """Runs after each test."""
        pass

    def test_icon_png(self):
        """Test we can click OK."""
        path = ':/plugins/ArcheoSync/icon.png'
        icon = QIcon(path)
        assert not icon.isNull()

if __name__ == "__main__":
    pytest.main([__file__])



