# coding=utf-8
"""Common functionality used by regression tests."""

import sys
import os
import logging

# Fix Python 3.10+ compatibility issues
try:
    from collections.abc import Callable
except ImportError:
    try:
        from collections import Callable
    except ImportError:
        Callable = None

try:
    from types import UnionType
except ImportError:
    UnionType = None

LOGGER = logging.getLogger('QGIS')
QGIS_APP = None  # Static variable used to hold hand to running QGIS app
CANVAS = None
PARENT = None
IFACE = None


def get_qgis_app():
    """ Start one QGIS application to test against.

    :returns: Handle to QGIS app, canvas, iface and parent. If there are any
        errors the tuple members will be returned as None.
    :rtype: (QgsApplication, CANVAS, IFACE, PARENT)

    If QGIS is already running the handle to that app will be returned.
    """

    try:
        from qgis.PyQt import QtGui, QtCore # type: ignore
        from qgis.PyQt.QtWidgets import QApplication # type: ignore
        from qgis.core import QgsApplication # type: ignore
        from qgis.gui import QgsMapCanvas # type: ignore
        from .qgis_interface import QgisInterface
    except ImportError:
        return None, None, None, None

    global QGIS_APP  # pylint: disable=W0603

    if QGIS_APP is None:
        try:
            gui_flag = True  # All test will run qgis in gui mode
            # Set QGIS_PREFIX_PATH explicitly
            prefix_path = os.environ.get('QGIS_PREFIX_PATH', '/Applications/QGIS-LTR.app/Contents/MacOS')
            
            # Ensure we have a QApplication instance first
            if QApplication.instance() is None:
                QApplication(sys.argv)
            
            QGIS_APP = QgsApplication.instance()
            if QGIS_APP is None:
                QGIS_APP = QgsApplication(sys.argv, gui_flag)
                QGIS_APP.setPrefixPath(prefix_path, True)
                QGIS_APP.initQgis()
            
            s = QGIS_APP.showSettings()
            LOGGER.debug(s)
        except Exception as e:
            LOGGER.error(f"Failed to initialize QGIS: {e}")
            return None, None, None, None

    global PARENT  # pylint: disable=W0603
    if PARENT is None:
        try:
            PARENT = QtGui.QWidget()
        except Exception as e:
            LOGGER.error(f"Failed to create parent widget: {e}")
            return QGIS_APP, None, None, None

    global CANVAS  # pylint: disable=W0603
    if CANVAS is None:
        try:
            CANVAS = QgsMapCanvas(PARENT)
            CANVAS.resize(QtCore.QSize(400, 400))
        except Exception as e:
            LOGGER.error(f"Failed to create map canvas: {e}")
            return QGIS_APP, None, None, PARENT

    global IFACE  # pylint: disable=W0603
    if IFACE is None:
        try:
            IFACE = QgisInterface(CANVAS)
        except Exception as e:
            LOGGER.error(f"Failed to create QGIS interface: {e}")
            return QGIS_APP, CANVAS, None, PARENT

    return QGIS_APP, CANVAS, IFACE, PARENT
