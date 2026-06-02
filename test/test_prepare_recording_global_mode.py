"""Tests for global mode in PrepareRecordingDialog."""

import unittest
from unittest.mock import Mock, patch

try:
    from qgis.PyQt import QtWidgets
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

if QGIS_AVAILABLE:
    from ui.prepare_recording_dialog import (
        PrepareRecordingDialog,
        PREPARATION_MODE_GLOBAL,
        PREPARATION_MODE_RECORDING_AREA,
        EXTENT_SOURCE_MANUAL,
        EXTENT_SOURCE_LAYER,
    )


@unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
class TestPrepareRecordingGlobalMode(unittest.TestCase):
    """UI tests for preparation mode switching."""

    def setUp(self):
        self.layer_service = Mock()
        self.layer_service.get_vector_layers.return_value = [
            {'id': 'layer1', 'name': 'Boundary'},
        ]
        self.layer_service.get_layer_info.return_value = {'name': 'Alt'}
        self.settings_manager = Mock()
        self.settings_manager.get_value.side_effect = lambda key, default=None: {
            'recording_areas_layer': 'ra',
            'extra_field_layers': [],
            'alternative_objects_layer': '',
        }.get(key, default)
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.dialog = PrepareRecordingDialog(
            layer_service=self.layer_service,
            settings_manager=self.settings_manager,
        )

    def test_default_mode_is_recording_area(self):
        self.assertEqual(self.dialog.get_preparation_mode(), PREPARATION_MODE_RECORDING_AREA)

    def test_global_mode_options(self):
        self.dialog._mode_global_radio.setChecked(True)
        self.dialog._on_preparation_mode_changed()
        self.dialog._global_project_name_edit.setText('Site_Global')
        self.dialog._extent_xmin.setValue(0)
        self.dialog._extent_ymin.setValue(0)
        self.dialog._extent_xmax.setValue(10)
        self.dialog._extent_ymax.setValue(10)
        options = self.dialog.get_global_project_options()
        self.assertEqual(self.dialog.get_preparation_mode(), PREPARATION_MODE_GLOBAL)
        self.assertEqual(options['project_name'], 'Site_Global')
        self.assertEqual(options['extent_source'], EXTENT_SOURCE_MANUAL)
        self.assertIsNotNone(options['manual_bounds'])

    def test_global_extent_layer_source(self):
        self.dialog._mode_global_radio.setChecked(True)
        self.dialog._on_preparation_mode_changed()
        self.dialog._extent_layer_radio.setChecked(True)
        self.dialog._on_extent_source_changed()
        self.dialog._extent_layer_combo.setCurrentIndex(1)
        options = self.dialog.get_global_project_options()
        self.assertEqual(options['extent_source'], EXTENT_SOURCE_LAYER)
        self.assertEqual(options['extent_layer_id'], 'layer1')
