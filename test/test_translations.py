# coding=utf-8
"""Safe Translations Test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
from .utilities import get_qgis_app

__author__ = 'ismailsunni@yahoo.co.id'
__date__ = '12/10/2011'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')
import pytest
import os

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.PyQt.QtCore import QCoreApplication, QTranslator
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

QGIS_APP = get_qgis_app()


@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestSafeTranslations:
    """Test translations work."""

    def setup_method(self):
        """Runs before each test."""
        if 'LANG' in iter(os.environ.keys()):
            os.environ.__delitem__('LANG')

    def teardown_method(self):
        """Runs after each test."""
        if 'LANG' in iter(os.environ.keys()):
            os.environ.__delitem__('LANG')

    # Remove or adapt test_qgis_translations and any direct QCoreApplication.translate tests for plugin translation


if __name__ == "__main__":
    pytest.main([__file__])
