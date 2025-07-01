# coding=utf-8
"""Dialog test.

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
    from qgis.PyQt.QtGui import QDialogButtonBox, QDialog # type: ignore
    from archeo_sync_dialog import ArcheoSyncDialog
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app
QGIS_APP = get_qgis_app()


@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class ArcheoSyncDialogTest:
    """Test dialog works."""

    def setup_method(self):
        """Runs before each test."""
        self.dialog = ArcheoSyncDialog(None)

    def teardown_method(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_ok(self):
        """Test we can click OK."""

        button = self.dialog.button_box.button(QDialogButtonBox.Ok)
        button.click()
        result = self.dialog.result()
        assert result == QDialog.Accepted

    def test_dialog_cancel(self):
        """Test we can click cancel."""
        button = self.dialog.button_box.button(QDialogButtonBox.Cancel)
        button.click()
        result = self.dialog.result()
        assert result == QDialog.Rejected

if __name__ == "__main__":
    pytest.main([__file__])

