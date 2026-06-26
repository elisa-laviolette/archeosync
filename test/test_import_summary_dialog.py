"""
Tests for ImportSummaryDialog.

This module tests the import summary dialog functionality.
"""

import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

try:
    from qgis.PyQt import QtWidgets
    from ui.import_summary_dialog import (
        ImportSummaryDialog,
        ImportSummaryDockWidget,
        DOCK_WIDGET_AREAS,
        _qmessagebox_yes_no_dialog_args,
    )
    from core.data_structures import ImportSummaryData, WarningData
except ImportError:
    from qgis.PyQt import QtWidgets
    from ..ui.import_summary_dialog import (
        ImportSummaryDialog,
        ImportSummaryDockWidget,
        DOCK_WIDGET_AREAS,
        _qmessagebox_yes_no_dialog_args,
    )
    from ..core.data_structures import ImportSummaryData, WarningData


class TestImportSummaryDialog(unittest.TestCase):
    """Test cases for ImportSummaryDialog."""

    @staticmethod
    def _mock_feature_for_layer_copy():
        """Minimal feature mock for ``build_layer_copy_jobs`` field mapping."""
        mock_fields = Mock()
        mock_fields.count.return_value = 0
        mock_feature = Mock()
        mock_feature.fields.return_value = mock_fields
        return mock_feature
    
    def setUp(self):
        """Set up test fixtures."""
        if QtWidgets.QApplication.instance() is None:
            self._qt_app = QtWidgets.QApplication(sys.argv if sys.argv else ["test"])
        else:
            self._qt_app = QtWidgets.QApplication.instance()

        self.mock_iface = Mock()
        self.mock_settings_manager = Mock()
        self.mock_csv_import_service = Mock()
        self.mock_field_project_import_service = Mock()
        self.mock_layer_service = Mock()
        self.mock_translation_service = Mock()
        # Configure the translation service to return the input string
        self.mock_translation_service.translate.side_effect = lambda x: x
        
        # Create parent widget for testing
        self.parent = QtWidgets.QWidget()
        
        # Create sample summary data
        self.summary_data = ImportSummaryData(
            csv_points_count=10,
            features_count=5,
            objects_count=3,
            small_finds_count=2,
            csv_duplicates=1,
            features_duplicates=0,
            objects_duplicates=1,
            small_finds_duplicates=0,
            duplicate_objects_warnings=[
                WarningData(
                    message="Test duplicate warning",
                    recording_area_name="Test Area",
                    layer_name="Test Layer",
                    filter_expression="test_filter"
                )
            ],
            skipped_numbers_warnings=[
                WarningData(
                    message="Test skipped numbers warning",
                    recording_area_name="Test Area",
                    layer_name="Test Layer",
                    filter_expression="test_filter",
                    skipped_numbers=[2, 4]
                )
            ]
        )
        
        self.dialog = ImportSummaryDialog(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
    
    def test_init_with_services(self):
        """Test that the dialog initializes correctly with all services."""
        self.assertEqual(self.dialog._summary_data, self.summary_data)
        self.assertEqual(self.dialog._iface, self.mock_iface)
        self.assertEqual(self.dialog._settings_manager, self.mock_settings_manager)
        self.assertEqual(self.dialog._csv_import_service, self.mock_csv_import_service)
        self.assertEqual(self.dialog._field_project_import_service, self.mock_field_project_import_service)
        self.assertEqual(self.dialog._layer_service, self.mock_layer_service)
        self.assertEqual(self.dialog._translation_service, self.mock_translation_service)
    
    def test_both_object_warning_types_visible_in_summary_panel(self):
        """Duplicate and skipped-number warnings must both appear in the objects section."""
        data = ImportSummaryData(
            objects_count=2,
            duplicate_objects_warnings=[
                WarningData(
                    message="Duplicate object warning",
                    recording_area_name="Zone A",
                    layer_name="New Objects",
                    filter_expression='"fid" = 1',
                )
            ],
            skipped_numbers_warnings=[
                WarningData(
                    message="Skipped numbers warning",
                    recording_area_name="Zone B",
                    layer_name="New Objects",
                    filter_expression='"fid" = 2',
                    skipped_numbers=[4],
                )
            ],
        )
        dock = ImportSummaryDockWidget(
            summary_data=data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            parent=self.parent,
        )
        texts = {lbl.text() for lbl in dock.findChildren(QtWidgets.QLabel)}
        self.assertIn("Duplicate Objects Warnings:", texts)
        self.assertIn("Skipped Numbers Warnings:", texts)
        self.assertTrue(any("Duplicate object warning" in t for t in texts))
        self.assertTrue(any("Skipped numbers warning" in t for t in texts))

    def test_both_object_warning_types_visible_after_refresh(self):
        """Refresh must keep duplicate and skipped warnings visible together in the panel."""
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.detect_duplicate_objects.return_value = [
            WarningData(
                message="Refreshed duplicate warning",
                recording_area_name="Zone A",
                layer_name="New Objects",
                filter_expression='"fid" = 1',
            )
        ]
        mock_skipped_detector = Mock()
        mock_skipped_detector.detect_skipped_numbers.return_value = [
            WarningData(
                message="Refreshed skipped warning",
                recording_area_name="Zone B",
                layer_name="New Objects",
                filter_expression='"fid" = 2',
                skipped_numbers=[4],
            )
        ]
        mock_oob = Mock()
        mock_oob.detect_out_of_bounds_features.return_value = []
        mock_distance = Mock()
        mock_distance.detect_distance_warnings.return_value = []
        mock_missing_ts = Mock()
        mock_missing_ts.detect_missing_total_station_warnings.return_value = []
        mock_dup_ts = Mock()
        mock_dup_ts.detect_duplicate_identifiers_warnings.return_value = []
        mock_height = Mock()
        mock_height.detect_height_difference_warnings.return_value = []

        with patch(
            "ui.import_summary_dialog.DuplicateObjectsDetectorService",
            return_value=mock_duplicate_detector,
        ), patch(
            "ui.import_summary_dialog.SkippedNumbersDetectorService",
            return_value=mock_skipped_detector,
        ), patch(
            "services.out_of_bounds_detector_service.OutOfBoundsDetectorService",
            return_value=mock_oob,
        ), patch(
            "services.distance_detector_service.DistanceDetectorService",
            return_value=mock_distance,
        ), patch(
            "services.missing_total_station_detector_service.MissingTotalStationDetectorService",
            return_value=mock_missing_ts,
        ), patch(
            "services.duplicate_total_station_identifiers_detector_service.DuplicateTotalStationIdentifiersDetectorService",
            return_value=mock_dup_ts,
        ), patch(
            "services.height_difference_detector_service.HeightDifferenceDetectorService",
            return_value=mock_height,
        ), patch("qgis.PyQt.QtWidgets.QMessageBox"):
            self.dialog._summary_data.objects_count = 5
            self._run_warning_refresh_pipeline_immediately(self.dialog)

        texts = {lbl.text() for lbl in self.dialog.findChildren(QtWidgets.QLabel)}
        self.assertIn("Duplicate Objects Warnings:", texts)
        self.assertIn("Skipped Numbers Warnings:", texts)
        self.assertTrue(any("Refreshed duplicate warning" in t for t in texts))
        self.assertTrue(any("Refreshed skipped warning" in t for t in texts))

    def test_out_of_bounds_warnings_visible_in_summary_panel(self):
        """Out-of-bounds warnings on ImportSummaryData must appear in the dock scroll content."""
        data = ImportSummaryData(
            features_count=1,
            out_of_bounds_warnings=[
                WarningData(
                    message="Features 2 outside boundary",
                    recording_area_name="21_J49",
                    layer_name="New Features",
                    filter_expression='"fid" IN (2)',
                )
            ],
        )
        dock = ImportSummaryDockWidget(
            summary_data=data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            parent=self.parent,
        )
        texts = {lbl.text() for lbl in dock.findChildren(QtWidgets.QLabel)}
        self.assertIn("Out-of-Bounds Warnings:", texts)
        self.assertTrue(any("Features 2 outside boundary" in t for t in texts))

    def test_effective_warnings_keep_import_lists_when_detector_returns_empty_mid_refresh(self):
        """Empty detector output must not hide import warnings until refresh completes."""
        self.dialog._warnings_analysis_running = True
        self.dialog._warning_refresh_results = {"duplicate_objects_warnings": []}
        self.assertEqual(len(self.dialog._effective_warnings("duplicate_objects_warnings")), 1)
        self.assertEqual(len(self.dialog._effective_warnings("skipped_numbers_warnings")), 1)

        self.dialog._warnings_analysis_running = False
        self.assertEqual(len(self.dialog._effective_warnings("duplicate_objects_warnings")), 1)

        self.dialog._apply_accumulated_warning_refresh_results()
        self.assertEqual(self.dialog._summary_data.duplicate_objects_warnings, [])

    def test_effective_warnings_shows_detector_output_when_non_empty(self):
        """New detector warnings replace import-time lists immediately during refresh."""
        refreshed = WarningData(
            message="Refreshed duplicate warning",
            recording_area_name="Zone A",
            layer_name="New Objects",
            filter_expression='"fid" = 1',
        )
        self.dialog._warnings_analysis_running = True
        self.dialog._warning_refresh_results = {"duplicate_objects_warnings": [refreshed]}
        effective = self.dialog._effective_warnings("duplicate_objects_warnings")
        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0].message, "Refreshed duplicate warning")

    def test_pending_warning_categories_remain_visible_after_partial_refresh_steps(self):
        """Warnings for not-yet-run detectors must stay visible while earlier steps finish."""
        oob_warning = WarningData(
            message="import oob warning",
            recording_area_name="Zone",
            layer_name="New Features",
            filter_expression='"fid" = 1',
        )
        data = ImportSummaryData(
            csv_points_count=10,
            objects_count=3,
            features_count=1,
            duplicate_objects_warnings=[
                WarningData(
                    message="import dup warning",
                    recording_area_name="Zone",
                    layer_name="New Objects",
                    filter_expression='"fid" = 2',
                )
            ],
            skipped_numbers_warnings=[
                WarningData(
                    message="import skipped warning",
                    recording_area_name="Zone",
                    layer_name="New Objects",
                    filter_expression='"fid" = 3',
                    skipped_numbers=[4],
                )
            ],
            out_of_bounds_warnings=[oob_warning],
        )
        dock = ImportSummaryDockWidget(
            summary_data=data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            parent=self.parent,
        )
        dock._warnings_analysis_running = True
        dock._warning_refresh_results = {
            "duplicate_objects_warnings": [],
            "skipped_numbers_warnings": [],
        }
        dock._recreate_summary_content()

        texts = {lbl.text() for lbl in dock.findChildren(QtWidgets.QLabel)}
        self.assertTrue(any("import dup warning" in t for t in texts))
        self.assertTrue(any("import skipped warning" in t for t in texts))
        self.assertTrue(any("import oob warning" in t for t in texts))

    def test_finalize_preserves_warnings_outside_refresh_plan(self):
        """Categories not scanned by the current plan must keep import-time warnings."""
        missing_warning = WarningData(
            message="missing total station warning",
            recording_area_name="Zone",
            layer_name="New Objects",
            filter_expression='"fid" = 1',
        )
        self.dialog._summary_data.csv_points_count = 5
        self.dialog._summary_data.objects_count = 0
        self.dialog._summary_data.missing_total_station_warnings = [missing_warning]
        self.dialog._warning_refresh_plan = self.dialog._build_warning_refresh_plan()
        self.dialog._warning_refresh_results = {"out_of_bounds_warnings": []}

        self.dialog._apply_accumulated_warning_refresh_results()
        planned_keys = self.dialog._planned_warning_result_keys()
        for result_key in self.dialog._WARNING_RESULT_KEYS:
            if result_key in planned_keys and result_key not in self.dialog._warning_refresh_results:
                setattr(self.dialog._summary_data, result_key, [])

        self.assertEqual(len(self.dialog._summary_data.missing_total_station_warnings), 1)

    def test_refresh_warnings_button_exists(self):
        """Test that the refresh warnings button is created."""
        self.assertIsNotNone(self.dialog._refresh_button)
        self.assertEqual(self.dialog._refresh_button.text(), "Refresh Warnings")
    
    def _run_warning_refresh_pipeline_immediately(self, dialog, trigger=None):
        """Execute the incremental warning refresh synchronously in tests."""

        def sync_dispatch(_description, runner, on_success, on_error):
            try:
                on_success(runner())
            except Exception as exc:
                on_error(exc)

        if trigger is None:
            trigger = dialog._handle_refresh_warnings

        with patch(
            "ui.import_summary_dialog.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ), patch.object(
            dialog,
            "_dispatch_warning_detection_step",
            side_effect=sync_dispatch,
        ):
            trigger()

    def test_refresh_warnings_calls_virtual_field_sync_before_detectors(self):
        """Refresh must sync virtual fields like the initial summary so detectors stay consistent."""
        with patch.object(
            self.dialog, "_sync_virtual_fields_to_temporary_import_layers"
        ) as mock_sync, patch(
            "ui.import_summary_dialog.DuplicateObjectsDetectorService",
            return_value=Mock(detect_duplicate_objects=Mock(return_value=[])),
        ), patch(
            "ui.import_summary_dialog.SkippedNumbersDetectorService",
            return_value=Mock(detect_skipped_numbers=Mock(return_value=[])),
        ), patch("qgis.PyQt.QtWidgets.QMessageBox"), patch.object(
            self.dialog, "_recreate_summary_content"
        ):
            self.dialog._summary_data.objects_count = 2
            self._run_warning_refresh_pipeline_immediately(self.dialog)
        mock_sync.assert_called_once()

    def test_refresh_warnings_success(self):
        """Test that refresh warnings works correctly."""
        # Mock the detection services
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.detect_duplicate_objects.return_value = [
            WarningData(
                message="Updated duplicate warning",
                recording_area_name="Updated Area",
                layer_name="Updated Layer",
                filter_expression="updated_filter"
            )
        ]
        
        mock_skipped_detector = Mock()
        mock_skipped_detector.detect_skipped_numbers.return_value = [
            WarningData(
                message="Updated skipped numbers warning",
                recording_area_name="Updated Area",
                layer_name="Updated Layer",
                filter_expression="updated_filter"
            )
        ]

        mock_oob = Mock()
        mock_oob.detect_out_of_bounds_features.return_value = []
        mock_distance = Mock()
        mock_distance.detect_distance_warnings.return_value = []
        mock_missing_ts = Mock()
        mock_missing_ts.detect_missing_total_station_warnings.return_value = []
        mock_dup_ts = Mock()
        mock_dup_ts.detect_duplicate_identifiers_warnings.return_value = []
        mock_height = Mock()
        mock_height.detect_height_difference_warnings.return_value = []
        
        # Mock the service classes
        with patch('ui.import_summary_dialog.DuplicateObjectsDetectorService', return_value=mock_duplicate_detector), \
             patch('ui.import_summary_dialog.SkippedNumbersDetectorService', return_value=mock_skipped_detector), \
             patch('services.out_of_bounds_detector_service.OutOfBoundsDetectorService', return_value=mock_oob), \
             patch('services.distance_detector_service.DistanceDetectorService', return_value=mock_distance), \
             patch('services.missing_total_station_detector_service.MissingTotalStationDetectorService', return_value=mock_missing_ts), \
             patch('services.duplicate_total_station_identifiers_detector_service.DuplicateTotalStationIdentifiersDetectorService', return_value=mock_dup_ts), \
             patch('services.height_difference_detector_service.HeightDifferenceDetectorService', return_value=mock_height), \
             patch('qgis.PyQt.QtWidgets.QMessageBox'), \
             patch.object(self.dialog, '_recreate_summary_content') as mock_recreate:
            
            # Set up summary data with objects
            self.dialog._summary_data.objects_count = 5
            
            self._run_warning_refresh_pipeline_immediately(self.dialog)
            
            # Verify the services were called
            mock_duplicate_detector.detect_duplicate_objects.assert_called_once()
            mock_skipped_detector.detect_skipped_numbers.assert_called_once()
            
            # Verify the summary data was updated (detector output replaces import-time warnings)
            self.assertEqual(len(self.dialog._summary_data.duplicate_objects_warnings), 1)
            self.assertEqual(
                self.dialog._summary_data.duplicate_objects_warnings[0].recording_area_name,
                "Updated Area",
            )
            self.assertEqual(len(self.dialog._summary_data.skipped_numbers_warnings), 1)
            
            # Verify the UI was recreated after each completed detector step
            self.assertGreaterEqual(mock_recreate.call_count, 1)

    def test_refresh_warnings_clears_resolved_duplicate_object_warnings(self):
        """Resolved duplicate warnings must disappear after refresh, not linger from import."""
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.detect_duplicate_objects.return_value = []

        mock_skipped_detector = Mock()
        mock_skipped_detector.detect_skipped_numbers.return_value = []
        mock_oob = Mock()
        mock_oob.detect_out_of_bounds_features.return_value = []
        mock_distance = Mock()
        mock_distance.detect_distance_warnings.return_value = []
        mock_missing_ts = Mock()
        mock_missing_ts.detect_missing_total_station_warnings.return_value = []
        mock_dup_ts = Mock()
        mock_dup_ts.detect_duplicate_identifiers_warnings.return_value = []
        mock_height = Mock()
        mock_height.detect_height_difference_warnings.return_value = []

        with patch(
            "ui.import_summary_dialog.DuplicateObjectsDetectorService",
            return_value=mock_duplicate_detector,
        ), patch(
            "ui.import_summary_dialog.SkippedNumbersDetectorService",
            return_value=mock_skipped_detector,
        ), patch(
            "services.out_of_bounds_detector_service.OutOfBoundsDetectorService",
            return_value=mock_oob,
        ), patch(
            "services.distance_detector_service.DistanceDetectorService",
            return_value=mock_distance,
        ), patch(
            "services.missing_total_station_detector_service.MissingTotalStationDetectorService",
            return_value=mock_missing_ts,
        ), patch(
            "services.duplicate_total_station_identifiers_detector_service.DuplicateTotalStationIdentifiersDetectorService",
            return_value=mock_dup_ts,
        ), patch(
            "services.height_difference_detector_service.HeightDifferenceDetectorService",
            return_value=mock_height,
        ), patch("qgis.PyQt.QtWidgets.QMessageBox"), patch.object(
            self.dialog, "_recreate_summary_content"
        ):
            self.assertEqual(len(self.dialog._summary_data.duplicate_objects_warnings), 1)
            self._run_warning_refresh_pipeline_immediately(self.dialog)

        self.assertEqual(self.dialog._summary_data.duplicate_objects_warnings, [])
    
    def test_refresh_warnings_error_handling(self):
        """Test that refresh warnings handles errors gracefully."""
        # Mock the detection services to raise an exception
        self.dialog._summary_data.objects_count = 1
        with patch('ui.import_summary_dialog.DuplicateObjectsDetectorService', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox') as mock_message_box:
            self._run_warning_refresh_pipeline_immediately(self.dialog)
            mock_message_box.critical.assert_called_once()
    
    def test_refresh_warnings_no_objects(self):
        """Test that refresh warnings works when no objects are imported."""
        # Create summary data with no objects
        no_objects_data = ImportSummaryData(
            csv_points_count=10,
            features_count=5,
            objects_count=0,  # No objects
            small_finds_count=2
        )
        
        dialog = ImportSummaryDialog(
            summary_data=no_objects_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            translation_service=self.mock_translation_service,
            parent=self.parent
        )
        
        with patch(
            "ui.import_summary_dialog.DuplicateObjectsDetectorService",
            return_value=Mock(detect_duplicate_objects=Mock(return_value=[])),
        ), patch(
            "ui.import_summary_dialog.SkippedNumbersDetectorService",
            return_value=Mock(detect_skipped_numbers=Mock(return_value=[])),
        ), patch(
            "services.out_of_bounds_detector_service.OutOfBoundsDetectorService",
            return_value=Mock(detect_out_of_bounds_features=Mock(return_value=[])),
        ), patch(
            "services.distance_detector_service.DistanceDetectorService",
            return_value=Mock(detect_distance_warnings=Mock(return_value=[])),
        ), patch(
            "services.duplicate_total_station_identifiers_detector_service.DuplicateTotalStationIdentifiersDetectorService",
            return_value=Mock(detect_duplicate_identifiers_warnings=Mock(return_value=[])),
        ), patch(
            "services.height_difference_detector_service.HeightDifferenceDetectorService",
            return_value=Mock(detect_height_difference_warnings=Mock(return_value=[])),
        ), patch('qgis.PyQt.QtWidgets.QMessageBox') as mock_qmessagebox, \
             patch.object(dialog, '_recreate_summary_content') as mock_recreate:
            
            # Configure the mock QMessageBox
            mock_qmessagebox.information = Mock()
            
            self._run_warning_refresh_pipeline_immediately(dialog)
            
            # Verify that UI was recreated as detector steps complete
            self.assertGreaterEqual(mock_recreate.call_count, 1)

    def test_warnings_analysis_indicator_hidden_by_default(self):
        """Busy indicator is hidden until warning analysis starts."""
        self.assertFalse(self.dialog._warnings_analysis_container.isVisible())

    def test_set_warnings_analysis_busy_toggles_indicator_and_buttons(self):
        """Busy state shows progress bar and disables import actions."""
        self.dialog._set_warnings_analysis_busy(True)
        self.assertTrue(self.dialog._warnings_analysis_container.isVisible())
        self.assertEqual(self.dialog._warnings_analysis_progress.minimum(), 0)
        self.assertEqual(self.dialog._warnings_analysis_progress.maximum(), 0)
        self.assertFalse(self.dialog._refresh_button.isEnabled())
        self.assertFalse(self.dialog._validate_button.isEnabled())
        self.assertFalse(self.dialog._cancel_button.isEnabled())

        self.dialog._set_warnings_analysis_busy(False)
        self.assertFalse(self.dialog._warnings_analysis_container.isVisible())
        self.assertTrue(self.dialog._refresh_button.isEnabled())
        self.assertTrue(self.dialog._validate_button.isEnabled())
        self.assertTrue(self.dialog._cancel_button.isEnabled())

    def test_set_warnings_analysis_busy_supports_determinate_progress(self):
        """When steps are known, the progress bar uses a determinate range."""
        self.dialog._set_warnings_analysis_busy(True, total_steps=5)
        self.assertEqual(self.dialog._warnings_analysis_progress.maximum(), 5)
        self.assertEqual(self.dialog._warnings_analysis_progress.value(), 0)
        self.assertFalse(self.dialog._refresh_button.isEnabled())
        self.assertFalse(self.dialog._validate_button.isEnabled())
        self.assertFalse(self.dialog._cancel_button.isEnabled())

        self.dialog._set_warnings_analysis_busy(False)
        self.assertFalse(self.dialog._warnings_analysis_container.isVisible())
        self.assertTrue(self.dialog._refresh_button.isEnabled())
        self.assertTrue(self.dialog._validate_button.isEnabled())
        self.assertTrue(self.dialog._cancel_button.isEnabled())

    def test_build_warning_refresh_plan_includes_object_checks(self):
        """Warning refresh plan should include object-related detectors when objects were imported."""
        self.dialog._summary_data.objects_count = 3
        self.dialog._summary_data.features_count = 0
        self.dialog._summary_data.csv_points_count = 0

        plan = self.dialog._build_warning_refresh_plan()
        result_keys = [step[0] for step in plan]

        self.assertIsNone(result_keys[0])
        self.assertIn("duplicate_objects_warnings", result_keys)
        self.assertIn("skipped_numbers_warnings", result_keys)

    def test_build_warning_refresh_plan_includes_out_of_bounds_for_csv_only_import(self):
        """Topo CSV import alone must still run out-of-bounds detection."""
        self.dialog._summary_data.objects_count = 0
        self.dialog._summary_data.features_count = 0
        self.dialog._summary_data.small_finds_count = 0
        self.dialog._summary_data.csv_points_count = 5

        plan = self.dialog._build_warning_refresh_plan()
        result_keys = [step[0] for step in plan]

        self.assertIn("out_of_bounds_warnings", result_keys)

    def test_refresh_warnings_silently_does_not_show_success_dialog(self):
        """Automatic background refresh must not show modal success popups."""
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.detect_duplicate_objects.return_value = []
        mock_skipped_detector = Mock()
        mock_skipped_detector.detect_skipped_numbers.return_value = []
        mock_oob = Mock()
        mock_oob.detect_out_of_bounds_features.return_value = []
        mock_distance = Mock()
        mock_distance.detect_distance_warnings.return_value = []
        mock_missing_ts = Mock()
        mock_missing_ts.detect_missing_total_station_warnings.return_value = []
        mock_dup_ts = Mock()
        mock_dup_ts.detect_duplicate_identifiers_warnings.return_value = []
        mock_height = Mock()
        mock_height.detect_height_difference_warnings.return_value = []

        self.dialog._summary_data.objects_count = 1

        with patch('ui.import_summary_dialog.DuplicateObjectsDetectorService', return_value=mock_duplicate_detector), \
             patch('ui.import_summary_dialog.SkippedNumbersDetectorService', return_value=mock_skipped_detector), \
             patch('services.out_of_bounds_detector_service.OutOfBoundsDetectorService', return_value=mock_oob), \
             patch('services.distance_detector_service.DistanceDetectorService', return_value=mock_distance), \
             patch('services.missing_total_station_detector_service.MissingTotalStationDetectorService', return_value=mock_missing_ts), \
             patch('services.duplicate_total_station_identifiers_detector_service.DuplicateTotalStationIdentifiersDetectorService', return_value=mock_dup_ts), \
             patch('services.height_difference_detector_service.HeightDifferenceDetectorService', return_value=mock_height), \
             patch('qgis.PyQt.QtWidgets.QMessageBox') as mock_qmessagebox, \
             patch.object(self.dialog, '_recreate_summary_content'):
            self._run_warning_refresh_pipeline_immediately(
                self.dialog,
                trigger=self.dialog.refresh_warnings_silently,
            )

        mock_qmessagebox.information.assert_not_called()
        self.assertFalse(self.dialog._warnings_analysis_container.isVisible())
    
    def test_recreate_summary_content(self):
        """Test that the summary content recreation works correctly."""
        # Mock the widget and layout structure
        mock_widget = Mock()
        mock_layout = Mock()
        mock_scroll_area = Mock()
        
        # Set up the mock structure
        mock_widget.layout.return_value = mock_layout
        mock_layout.count.return_value = 1
        mock_layout.itemAt.return_value.widget.return_value = mock_scroll_area
        mock_scroll_area.__class__ = type(QtWidgets.QScrollArea())
        
        with patch.object(self.dialog, 'widget', return_value=mock_widget), \
             patch.object(self.dialog, '_create_summary_content') as mock_create:
            
            # Call the recreate method
            self.dialog._recreate_summary_content()
            
            # Verify that the scroll area was removed and recreated
            mock_layout.removeItem.assert_called_once()
            mock_scroll_area.deleteLater.assert_called_once()
            mock_create.assert_called_once()
    
    def test_recreate_summary_content_error_handling(self):
        """Test that recreate summary content handles errors gracefully."""
        # Mock the layout to raise an exception
        with patch.object(self.dialog, 'layout', side_effect=Exception("Test error")):
            
            # Call the recreate method - should not raise an exception
            try:
                self.dialog._recreate_summary_content()
            except Exception:
                self.fail("_recreate_summary_content should handle exceptions gracefully")
    
    def test_dock_widget_creation(self):
        """Test that dock widget can be created successfully."""
        # Create a dock widget
        dock_widget = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            parent=self.parent
        )
        
        # Check that it's a dock widget
        from qgis.PyQt.QtWidgets import QDockWidget
        self.assertIsInstance(dock_widget, QDockWidget)
        
        # Check that it has the correct title
        self.assertEqual(dock_widget.windowTitle(), "Import Summary")
    
    def test_dock_widget_allowed_areas(self):
        """Test that dock widget has correct allowed areas."""
        # Create a dock widget
        dock_widget = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            parent=self.parent
        )
        
        # Check that it allows all dock areas (Qt5/Qt6 via DOCK_WIDGET_AREAS)
        expected_areas = DOCK_WIDGET_AREAS.all_sides
        self.assertEqual(dock_widget.allowedAreas(), expected_areas)
    
    def test_cancel_button_exists(self):
        """Test that the cancel button is created."""
        self.assertIsNotNone(self.dialog._cancel_button)
        self.assertEqual(self.dialog._cancel_button.text(), "Cancel Import")
    
    def test_cancel_button_confirmation_yes(self):
        """Test that cancel button shows confirmation dialog and proceeds when user clicks Yes."""
        std_btns, default_no, yes_val, _no_val = _qmessagebox_yes_no_dialog_args()
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Configure the mock to return Yes
            mock_question.return_value = yes_val
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify confirmation dialog was shown
            mock_question.assert_called_once_with(
                self.dialog,
                "Cancel Import",
                "Are you sure you want to cancel the import? This will delete all temporary import layers and cannot be undone.",
                std_btns,
                default_no,
            )
            
            # Verify temporary layers were deleted
            mock_delete.assert_called_once()
            self.mock_csv_import_service.clear_last_imported_files.assert_called_once()
            self.mock_field_project_import_service.clear_last_imported_projects.assert_called_once()
            self.mock_layer_service.clear_caches.assert_called_once()
            
            # Verify widget was deleted
            mock_delete_later.assert_called_once()
    
    def test_cancel_button_confirmation_no(self):
        """Test that cancel button shows confirmation dialog and does nothing when user clicks No."""
        _std_btns, _default_no, _yes_val, no_val = _qmessagebox_yes_no_dialog_args()
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question, \
             patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later:
            
            # Configure the mock to return No
            mock_question.return_value = no_val
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify confirmation dialog was shown
            mock_question.assert_called_once()
            
            # Verify temporary layers were NOT deleted
            mock_delete.assert_not_called()
            
            # Verify widget was NOT deleted
            mock_delete_later.assert_not_called()
    
    def test_cancel_button_error_handling(self):
        """Test that cancel button handles errors gracefully."""
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox.critical') as mock_critical:
            
            # Call the cancel method
            self.dialog._handle_cancel()
            
            # Verify error message was shown
            mock_critical.assert_called_once_with(
                self.dialog,
                "Cancel Error",
                "An error occurred while canceling the import: Test error"
            )
    
    def test_delete_temporary_layers_includes_csv_layer(self):
        """Test that the delete temporary layers method includes the CSV temporary layer."""
        with patch('qgis.core.QgsProject') as mock_project_class:
            
            # Create mock project and layers
            mock_project = Mock()
            mock_project_class.instance.return_value = mock_project
            self.mock_layer_service.repair_definitive_project_relations.return_value = 0
            self.mock_layer_service.remove_import_clone_relations.return_value = 0
            
            # Create mock layers
            mock_objects_layer = Mock()
            mock_objects_layer.name.return_value = "New Objects"
            mock_objects_layer.id.return_value = "objects_layer_id"
            
            mock_features_layer = Mock()
            mock_features_layer.name.return_value = "New Features"
            mock_features_layer.id.return_value = "features_layer_id"
            
            mock_csv_layer = Mock()
            mock_csv_layer.name.return_value = "Imported_CSV_Points"
            mock_csv_layer.id.return_value = "csv_layer_id"
            
            # Set up the project to return our mock layers
            mock_project.mapLayers.return_value = {
                "objects_layer_id": mock_objects_layer,
                "features_layer_id": mock_features_layer,
                "csv_layer_id": mock_csv_layer
            }
            
            # Call the delete method
            self.dialog._delete_temporary_layers()
            
            self.mock_layer_service.repair_definitive_project_relations.assert_called_once()
            self.mock_layer_service.remove_import_clone_relations.assert_called_once()
            
            # Check that removeMapLayer was called for each temporary layer
            self.assertEqual(mock_project.removeMapLayer.call_count, 3)
            
            # Verify the specific layer IDs were called
            mock_project.removeMapLayer.assert_any_call("objects_layer_id")
            mock_project.removeMapLayer.assert_any_call("features_layer_id")
            mock_project.removeMapLayer.assert_any_call("csv_layer_id")
    
    def test_copy_temporary_to_definitive_layers_includes_csv_points(self):
        """Test that the copy temporary to definitive layers method includes the CSV points layer."""
        try:
            from services.import_validation_service import CopyBatchResult
        except ImportError:
            from ..services.import_validation_service import CopyBatchResult

        with patch('qgis.core.QgsProject') as mock_project_class, \
             patch.object(
                 self.dialog._feature_copier,
                 'copy_features_batch',
                 return_value=CopyBatchResult(2, 2, 0, [1, 2]),
             ) as mock_batch, \
             patch.object(self.dialog._feature_copier, 'select_copied_features') as mock_select, \
             patch('qgis.PyQt.QtWidgets.QMessageBox.information'):
            mock_project = Mock()
            mock_project_class.instance.return_value = mock_project

            mock_csv_layer = Mock()
            mock_csv_layer.name.return_value = "Imported_CSV_Points"
            mock_csv_layer.featureCount.return_value = 2
            mock_csv_layer.fields.return_value = Mock(count=Mock(return_value=0))
            mock_csv_layer.getFeatures.return_value = [
                self._mock_feature_for_layer_copy(),
                self._mock_feature_for_layer_copy(),
            ]

            mock_definitive_layer = Mock()
            mock_definitive_layer.name.return_value = "Total Station Points"
            mock_definitive_layer.id.return_value = "definitive_layer_id"
            mock_definitive_layer.fields.return_value = Mock(count=Mock(return_value=0))

            mock_project.mapLayers.return_value = {
                "csv_layer_id": mock_csv_layer,
                "definitive_layer_id": mock_definitive_layer,
            }

            def mock_get_value(key, default=None):
                if key == 'total_station_points_layer':
                    return "definitive_layer_id"
                return default

            self.dialog._settings_manager.get_value = mock_get_value

            self.dialog._copy_temporary_to_definitive_layers()

            mock_csv_layer.getFeatures.assert_called_once()
            mock_batch.assert_called_once()
            self.assertIs(mock_batch.call_args.kwargs['target_layer'], mock_definitive_layer)
            mock_select.assert_called_once_with(mock_definitive_layer, [1, 2])

    def test_copy_temporary_to_definitive_layers_processes_all_import_layers(self):
        """Validation copy must process objects, features, small finds, and topo points."""
        try:
            from services.import_validation_service import CopyBatchResult
        except ImportError:
            from ..services.import_validation_service import CopyBatchResult

        with patch('qgis.core.QgsProject') as mock_project_class, \
             patch.object(
                 self.dialog._feature_copier,
                 'copy_features_batch',
                 return_value=CopyBatchResult(1, 1, 0, [1]),
             ) as mock_copy, \
             patch.object(self.dialog._feature_copier, 'select_copied_features'), \
             patch('qgis.PyQt.QtWidgets.QMessageBox.information'):
            mock_project = Mock()
            mock_project_class.instance.return_value = mock_project

            temp_layers = {}
            definitive_layers = {}
            mapping = {
                "New Objects": ("objects_layer", "objects_def_id"),
                "New Features": ("features_layer", "features_def_id"),
                "New Small Finds": ("small_finds_layer", "small_finds_def_id"),
                "Imported_CSV_Points": ("total_station_points_layer", "points_def_id"),
            }

            for layer_name, (_setting_key, definitive_id) in mapping.items():
                temp_layer = Mock()
                temp_layer.name.return_value = layer_name
                temp_layer.featureCount.return_value = 1
                temp_layer.fields.return_value = Mock(count=Mock(return_value=0))
                temp_layer.getFeatures.return_value = [self._mock_feature_for_layer_copy()]
                temp_layers[layer_name] = temp_layer

                definitive_layer = Mock()
                definitive_layer.id.return_value = definitive_id
                definitive_layer.name.return_value = f"def_{layer_name}"
                definitive_layer.fields.return_value = Mock(count=Mock(return_value=0))
                definitive_layers[definitive_id] = definitive_layer

            all_layers = {}
            i = 0
            for temp_layer in temp_layers.values():
                all_layers[f"tmp_{i}"] = temp_layer
                i += 1
            for definitive_layer in definitive_layers.values():
                all_layers[f"def_{i}"] = definitive_layer
                i += 1
            mock_project.mapLayers.return_value = all_layers

            def mock_get_value(key, default=None):
                for _layer_name, (setting_key, definitive_id) in mapping.items():
                    if key == setting_key:
                        return definitive_id
                return default

            self.dialog._settings_manager.get_value = mock_get_value

            self.dialog._copy_temporary_to_definitive_layers()

            self.assertEqual(mock_copy.call_count, 4)
    
    def test_validate_button_exists(self):
        """Test that the validate button is created."""
        self.assertIsNotNone(self.dialog._validate_button)
        self.assertEqual(self.dialog._validate_button.text(), "Validate")
    
    def test_validate_button_success(self):
        """Test that validate button properly deletes the dock widget on success."""
        with patch.object(self.dialog, '_has_warnings', return_value=False), \
             patch.object(self.dialog, '_finalize_validation_success') as mock_finalize, \
             patch.object(self.dialog, '_start_async_validation', side_effect=mock_finalize):
            self.dialog._handle_validate()

            mock_finalize.assert_called_once()

    def test_finalize_validation_success_cleans_up(self):
        """Successful validation archives data and removes the dock widget."""
        self.dialog._validation_copied_counts = {"New Objects": 2}
        with patch.object(self.dialog, '_delete_temporary_layers') as mock_delete, \
             patch.object(self.dialog, '_archive_imported_data') as mock_archive, \
             patch.object(self.dialog, 'deleteLater') as mock_delete_later, \
             patch('qgis.PyQt.QtWidgets.QMessageBox.information'):
            self.dialog._finalize_validation_success()

            mock_delete.assert_called_once()
            mock_archive.assert_called_once()
            self.mock_iface.removeDockWidget.assert_called_once_with(self.dialog)
            mock_delete_later.assert_called_once()

    def test_archive_imported_data_only_archives_csv_when_configured(self):
        """Only the data types imported in the current session should be archived."""
        dock = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            archive_csv=True,
            archive_projects=False,
            parent=self.parent,
        )
        dock._archive_imported_data()
        self.mock_csv_import_service.archive_last_imported_files.assert_called_once()
        self.mock_field_project_import_service.archive_last_imported_projects.assert_not_called()

    def test_archive_imported_data_only_archives_projects_when_configured(self):
        """Project archiving is skipped when the current session did not import projects."""
        dock = ImportSummaryDockWidget(
            summary_data=self.summary_data,
            iface=self.mock_iface,
            settings_manager=self.mock_settings_manager,
            csv_import_service=self.mock_csv_import_service,
            field_project_import_service=self.mock_field_project_import_service,
            layer_service=self.mock_layer_service,
            archive_csv=False,
            archive_projects=True,
            parent=self.parent,
        )
        dock._archive_imported_data()
        self.mock_csv_import_service.archive_last_imported_files.assert_not_called()
        self.mock_field_project_import_service.archive_last_imported_projects.assert_called_once()
    
    def test_validate_button_error_handling(self):
        """Test that validate button handles errors gracefully."""
        with patch.object(self.dialog, '_start_async_validation', side_effect=Exception("Test error")), \
             patch('qgis.PyQt.QtWidgets.QMessageBox.critical') as mock_critical:
            
            # Call the validate method
            self.dialog._handle_validate()
            
            # Verify error message was shown
            mock_critical.assert_called_once_with(
                self.dialog,
                "Validation Error",
                "An error occurred during validation: Test error"
            )
            
            # Verify the dock widget was NOT removed from the interface on error
            self.mock_iface.removeDockWidget.assert_not_called()
    
    def test_has_warnings_with_duplicates(self):
        """Test that _has_warnings returns True when duplicate warnings exist."""
        # Set up summary data with duplicate warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_with_skipped_numbers(self):
        """Test that _has_warnings returns True when skipped numbers warnings exist."""
        # Set up summary data with skipped numbers warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = [WarningData("test", "area", "layer", "filter")]
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_with_both_types(self):
        """Test that _has_warnings returns True when both types of warnings exist."""
        # Set up summary data with both types of warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test1", "area1", "layer1", "filter1")]
        self.dialog._summary_data.skipped_numbers_warnings = [WarningData("test2", "area2", "layer2", "filter2")]
        
        self.assertTrue(self.dialog._has_warnings())
    
    def test_has_warnings_without_warnings(self):
        """Test that _has_warnings returns False when no warnings exist."""
        # Set up summary data with no warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        self.assertFalse(self.dialog._has_warnings())
    
    def test_qmessagebox_yes_no_helper_matches_runtime(self):
        """Helper must use the same Yes/No flags as the active PyQt (Qt5 vs QGIS 4 / Qt6)."""
        std_btns, default_no, yes_val, no_val = _qmessagebox_yes_no_dialog_args()
        qmb = QtWidgets.QMessageBox
        if hasattr(qmb, "Yes"):
            self.assertEqual(std_btns, qmb.Yes | qmb.No)
            self.assertEqual(default_no, qmb.No)
            self.assertEqual(yes_val, qmb.Yes)
            self.assertEqual(no_val, qmb.No)
        else:
            std = qmb.StandardButton
            self.assertEqual(std_btns, std.Yes | std.No)
            self.assertEqual(default_no, std.No)
            self.assertEqual(yes_val, std.Yes)
            self.assertEqual(no_val, std.No)
    
    def test_confirm_validation_with_warnings_duplicates_only(self):
        """Test confirmation dialog when only duplicate warnings exist."""
        # Set up summary data with only duplicate warnings
        self.dialog._summary_data.duplicate_objects_warnings = [
            WarningData("test1", "area1", "layer1", "filter1"),
            WarningData("test2", "area2", "layer2", "filter2")
        ]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        _std_btns, _default_no, yes_val, _no_val = _qmessagebox_yes_no_dialog_args()
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = yes_val
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertTrue(result)
    
    def test_confirm_validation_with_warnings_skipped_only(self):
        """Test confirmation dialog when only skipped numbers warnings exist."""
        # Set up summary data with only skipped numbers warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = [
            WarningData("test1", "area1", "layer1", "filter1"),
            WarningData("test2", "area2", "layer2", "filter2"),
            WarningData("test3", "area3", "layer3", "filter3")
        ]
        
        _std_btns, _default_no, _yes_val, no_val = _qmessagebox_yes_no_dialog_args()
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = no_val
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertFalse(result)
    
    def test_confirm_validation_with_warnings_both_types(self):
        """Test confirmation dialog when both types of warnings exist."""
        # Set up summary data with both types of warnings
        self.dialog._summary_data.duplicate_objects_warnings = [
            WarningData("test1", "area1", "layer1", "filter1")
        ]
        self.dialog._summary_data.skipped_numbers_warnings = [
            WarningData("test2", "area2", "layer2", "filter2"),
            WarningData("test3", "area3", "layer3", "filter3")
        ]
        
        _std_btns, _default_no, yes_val, _no_val = _qmessagebox_yes_no_dialog_args()
        with patch('qgis.PyQt.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = yes_val
            
            result = self.dialog._confirm_validation_with_warnings()
            
            # Verify the confirmation dialog was shown
            mock_question.assert_called_once()
            self.assertTrue(result)
    
    def test_validate_with_warnings_user_confirms(self):
        """Test validation when warnings exist and user confirms."""
        # Set up summary data with warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=True), \
             patch.object(self.dialog, '_confirm_validation_with_warnings', return_value=True), \
             patch.object(self.dialog, '_start_async_validation') as mock_start:
            self.dialog._handle_validate()
            mock_start.assert_called_once()
    
    def test_validate_with_warnings_user_cancels(self):
        """Test validation when warnings exist and user cancels."""
        # Set up summary data with warnings
        self.dialog._summary_data.duplicate_objects_warnings = [WarningData("test", "area", "layer", "filter")]
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=True), \
             patch.object(self.dialog, '_confirm_validation_with_warnings', return_value=False), \
             patch.object(self.dialog, '_start_async_validation') as mock_start:
            self.dialog._handle_validate()
            mock_start.assert_not_called()
    
    def test_validate_without_warnings(self):
        """Test validation when no warnings exist."""
        # Set up summary data with no warnings
        self.dialog._summary_data.duplicate_objects_warnings = []
        self.dialog._summary_data.skipped_numbers_warnings = []
        
        with patch.object(self.dialog, '_has_warnings', return_value=False), \
             patch.object(self.dialog, '_confirm_validation_with_warnings') as mock_confirm, \
             patch.object(self.dialog, '_start_async_validation') as mock_start:
            self.dialog._handle_validate()
            mock_confirm.assert_not_called()
            mock_start.assert_called_once()


class TestImportSummaryFeatureCopy(unittest.TestCase):
    """QGIS-backed tests for feature copy/default replay without full dialog UI."""

    def setUp(self):
        if QtWidgets.QApplication.instance() is None:
            self._qt_app = QtWidgets.QApplication(sys.argv if sys.argv else ["test"])

    @staticmethod
    def _feature_copy_helper():
        return ImportSummaryDockWidget.__new__(ImportSummaryDockWidget)

    def test_case_insensitive_field_matching_csv_points(self):
        """Total station points copy when field names differ only by case."""
        from qgis.core import QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant

        temp_fields = QgsFields()
        temp_fields.append(QgsField('pointid', QVariant.String))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setAttribute('pointid', 'TS001')
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=PointID:string",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())

        new_feature = self._feature_copy_helper()._create_feature_with_target_structure(temp_feature, def_layer)

        self.assertEqual(new_feature['PointID'], 'TS001')

    def test_apply_layer_default_value_when_source_field_missing(self):
        """Missing source attributes should be populated from target layer default values."""
        from qgis.core import QgsDefaultValue, QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer
        from qgis.PyQt.QtCore import QVariant

        temp_fields = QgsFields()
        temp_fields.append(QgsField('pointid', QVariant.String))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setAttribute('pointid', 'TS001')
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=PointID:string&field=operation_id:integer",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        operation_idx = def_layer.fields().indexOf('operation_id')
        def_layer.setDefaultValueDefinition(operation_idx, QgsDefaultValue('6'))

        new_feature = self._feature_copy_helper()._create_feature_with_target_structure(temp_feature, def_layer)

        self.assertEqual(new_feature['PointID'], 'TS001')
        self.assertEqual(new_feature['operation_id'], 6)

    def test_topo_import_applies_default_values_with_real_layers(self):
        """Topo CSV validation should fill definitive defaults using QgsVectorLayerUtils."""
        from qgis.core import (
            QgsDefaultValue,
            QgsFeature,
            QgsFields,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=pointid:string&field=site_code:string&field=sequence:integer",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        site_idx = def_layer.fields().indexOf('site_code')
        sequence_idx = def_layer.fields().indexOf('sequence')
        def_layer.setDefaultValueDefinition(site_idx, QgsDefaultValue("'SITE-A'"))
        def_layer.setDefaultValueDefinition(sequence_idx, QgsDefaultValue('maximum("sequence") + 1'))

        def_layer.startEditing()
        existing = QgsFeature(def_layer.fields())
        existing.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.0, 2.0)))
        existing.setAttribute('pointid', 'P1')
        existing.setAttribute('site_code', 'SITE-A')
        existing.setAttribute('sequence', 3)
        def_layer.addFeature(existing)
        def_layer.commitChanges()

        temp_fields = QgsFields()
        temp_fields.append(QgsField('pointid', QVariant.String))
        temp_fields.append(QgsField('x', QVariant.Double))
        temp_fields.append(QgsField('y', QVariant.Double))
        temp_fields.append(QgsField('z', QVariant.Double))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))
        temp_feature.setAttribute('pointid', 'TS002')

        new_feature = self._feature_copy_helper()._create_feature_with_target_structure(temp_feature, def_layer)

        self.assertEqual(new_feature['pointid'], 'TS002')
        self.assertEqual(new_feature['site_code'], 'SITE-A')
        self.assertEqual(new_feature['sequence'], 4)

    def test_self_referencing_default_preserves_imported_integer(self):
        """Imported integer values must not be replaced by self-referencing CASE defaults."""
        from qgis.core import (
            QgsDefaultValue,
            QgsFeature,
            QgsFields,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=object_id:string&field=square_meter_id:integer",
            "Objects",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        square_idx = def_layer.fields().indexOf('square_meter_id')
        def_layer.setDefaultValueDefinition(
            square_idx,
            QgsDefaultValue(
                'CASE WHEN "square_meter_id" IS NULL THEN 3 ELSE "square_meter_id" END'
            ),
        )

        temp_fields = QgsFields()
        temp_fields.append(QgsField('object_id', QVariant.String))
        temp_fields.append(QgsField('square_meter_id', QVariant.Int))
        temp_feature = QgsFeature(temp_fields)
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.0, 2.0)))
        temp_feature.setAttribute('object_id', 'OBJ-1')
        temp_feature.setAttribute('square_meter_id', 7)

        new_feature = self._feature_copy_helper()._create_feature_with_target_structure(
            temp_feature, def_layer
        )

        self.assertEqual(new_feature['object_id'], 'OBJ-1')
        self.assertEqual(new_feature['square_meter_id'], 7)

    def test_topo_csv_date_copied_to_definitive_layer(self):
        """Survey date from the temp topo layer should override definitive defaults."""
        from qgis.core import (
            QgsDefaultValue,
            QgsFeature,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QDate

        def_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=pointid:string&field=DateLeve:date",
            "Total Station Points",
            "memory",
        )
        self.assertTrue(def_layer.isValid())
        date_idx = def_layer.fields().indexOf('DateLeve')
        def_layer.setDefaultValueDefinition(date_idx, QgsDefaultValue("to_date('2000-01-01')"))

        temp_layer = QgsVectorLayer(
            "Point?crs=EPSG:4326&field=pointid:string&field=DateLeve:date",
            "Imported_CSV_Points",
            "memory",
        )
        self.assertTrue(temp_layer.isValid())
        temp_feature = QgsFeature(temp_layer.fields())
        temp_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(100.0, 200.0)))
        temp_feature.setAttribute('pointid', 'PINC150725')
        temp_feature.setAttribute('DateLeve', QDate(2025, 7, 15))

        new_feature = self._feature_copy_helper()._create_feature_with_target_structure(
            temp_feature, def_layer
        )

        self.assertEqual(new_feature['pointid'], 'PINC150725')
        self.assertEqual(new_feature['DateLeve'], QDate(2025, 7, 15))


if __name__ == '__main__':
    unittest.main() 