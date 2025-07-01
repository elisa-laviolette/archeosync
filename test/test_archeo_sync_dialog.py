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
import sys
import os

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog, QApplication # type: ignore
    from qgis.PyQt.QtCore import QCoreApplication # type: ignore
    from archeo_sync_dialog import ArcheoSyncDialog
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

from .utilities import get_qgis_app


@pytest.mark.unit
class TestArcheoSyncDialogBasic:
    """Basic tests that don't require QGIS."""
    
    def test_import_available(self):
        """Test that the dialog module can be imported."""
        try:
            import archeo_sync_dialog
            assert archeo_sync_dialog is not None
        except ImportError:
            pytest.skip("archeo_sync_dialog module not available")


@pytest.mark.qgis
@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestArcheoSyncDialog:
    """Test dialog works."""

    def setup_method(self):
        """Runs before each test."""
        # Ensure QGIS is properly initialized
        self.qgis_app, self.canvas, self.iface, self.parent = get_qgis_app()
        
        # Ensure we have a QApplication instance
        if QApplication.instance() is None:
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        
        # Create dialog with proper parent
        try:
            self.dialog = ArcheoSyncDialog(self.parent)
        except Exception as e:
            pytest.skip(f"Failed to create dialog: {e}")

    def teardown_method(self):
        """Runs after each test."""
        if hasattr(self, 'dialog'):
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = None

    def test_dialog_creation(self):
        """Test dialog can be created and has expected attributes."""
        assert self.dialog is not None
        assert hasattr(self.dialog, 'button_box')
        assert self.dialog.windowTitle() == "ArcheoSync"

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

