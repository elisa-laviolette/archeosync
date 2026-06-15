"""
Import Summary Dialog for ArcheoSync plugin.

This module provides a dock widget that displays a summary of imported data after
the import process is complete. It shows statistics about imported points,
features, objects, small finds, and detected duplicates.

Key Features:
- Displays import statistics in a clear, organized format
- Shows counts for different data types (CSV points, features, objects, small finds)
- Reports duplicate detection results
- Clean, user-friendly interface
- Supports translation
- Provides buttons to open attribute tables filtered to show concerned entities
- Uses QDockWidget to prevent floating above other windows

Architecture Benefits:
- Single Responsibility: Only handles summary display
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new summary information

Usage:
    Import ``DOCK_WIDGET_AREAS`` from this module with ``ImportSummaryDockWidget`` so dock
    placement works on both QGIS 3 (Qt5) and QGIS 4 (Qt6).

    summary_data = ImportSummaryData(
        csv_points_count=150,
        features_count=25,
        objects_count=10,
        small_finds_count=5,
        csv_duplicates=3,
        features_duplicates=1,
        objects_duplicates=0,
        small_finds_duplicates=2
    )
    
    # Create dock widget
    dock_widget = ImportSummaryDockWidget(summary_data, iface=iface, parent=parent_widget)
    iface.addDockWidget(DOCK_WIDGET_AREAS.right, dock_widget)
"""

from typing import Optional, List, Dict, Any, Union, Callable, Tuple
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox, QDockWidget
from qgis.PyQt.QtCore import Qt, QTimer

try:
    from ..core.interfaces import ISettingsManager, ILayerService
    from ..core.data_structures import WarningData, ImportSummaryData
    from ..core.ui_responsiveness import flush_ui_updates, maybe_yield_to_ui, reset_yield_counter
    from ..core.warning_detection_runner import dispatch_warning_detection_step
    from ..services.import_validation_service import (
        IMPORT_LAYER_MAPPINGS,
        ImportFeatureCopier,
        LayerCopyJob,
        block_job_target_signals,
        build_layer_copy_jobs,
        ensure_job_expression_context,
        load_job_source_features,
        load_job_source_features_chunk,
        unblock_job_target_signals,
    )
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService
    from core.data_structures import WarningData, ImportSummaryData
    from core.ui_responsiveness import flush_ui_updates, maybe_yield_to_ui, reset_yield_counter
    from core.warning_detection_runner import dispatch_warning_detection_step
    from services.import_validation_service import (
        IMPORT_LAYER_MAPPINGS,
        ImportFeatureCopier,
        LayerCopyJob,
        block_job_target_signals,
        build_layer_copy_jobs,
        ensure_job_expression_context,
        load_job_source_features,
        load_job_source_features_chunk,
        unblock_job_target_signals,
    )


def _align_center_flag():
    """Return a center-alignment flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "AlignCenter"):
        return Qt.AlignCenter
    alignment_flag = getattr(Qt, "AlignmentFlag", None)
    if alignment_flag is not None and hasattr(alignment_flag, "AlignCenter"):
        return alignment_flag.AlignCenter
    raise AttributeError("Qt center alignment flag is not available.")


def _qmessagebox_yes_no_dialog_args():
    """
    Return ``QMessageBox.question`` button flags and reply values for Qt5 and Qt6.

    PyQt6 (QGIS 4) exposes affirmative/negative actions under
    ``QMessageBox.StandardButton``; PyQt5 keeps ``QMessageBox.Yes`` / ``No`` on the
    class itself. Using the wrong API raises ``AttributeError`` at dialog build time.

    Returns:
        tuple: ``(standard_buttons, default_button, yes_reply, no_reply)`` — third and
        fourth arguments to ``QMessageBox.question``, then values to compare the return
        value against for Yes vs No.
    """
    if hasattr(QMessageBox, "Yes"):
        yes = QMessageBox.Yes
        no = QMessageBox.No
    else:
        std = QMessageBox.StandardButton
        yes = std.Yes
        no = std.No
    return yes | no, no, yes, no


class DockWidgetAreas:
    """
    Qt5 vs Qt6 dock area flags for QDockWidget and QMainWindow.

    Qt5 exposes ``Qt.LeftDockWidgetArea`` on ``Qt``; Qt6 nests them under
    ``Qt.DockWidgetArea`` (PyQt6 / QGIS 4).
    """

    __slots__ = ("left", "right", "top", "bottom")

    def __init__(self) -> None:
        if hasattr(Qt, "LeftDockWidgetArea"):
            self.left = Qt.LeftDockWidgetArea
            self.right = Qt.RightDockWidgetArea
            self.top = Qt.TopDockWidgetArea
            self.bottom = Qt.BottomDockWidgetArea
        else:
            dwa = Qt.DockWidgetArea
            self.left = dwa.LeftDockWidgetArea
            self.right = dwa.RightDockWidgetArea
            self.top = dwa.TopDockWidgetArea
            self.bottom = dwa.BottomDockWidgetArea

    @property
    def all_sides(self) -> int:
        """Bit mask allowing docking on all four sides."""
        return self.left | self.right | self.top | self.bottom


DOCK_WIDGET_AREAS = DockWidgetAreas()


def _scroll_bar_as_needed_policy():
    """Return ScrollBarAsNeeded policy compatible with Qt5 and Qt6."""
    if hasattr(Qt, "ScrollBarAsNeeded"):
        return Qt.ScrollBarAsNeeded
    scroll_policy = getattr(Qt, "ScrollBarPolicy", None)
    if scroll_policy is not None and hasattr(scroll_policy, "ScrollBarAsNeeded"):
        return scroll_policy.ScrollBarAsNeeded
    raise AttributeError("Qt ScrollBarAsNeeded policy is not available.")


def _default_qdockwidget_features():
    """
    Default QDockWidget feature flags (closable, movable, floatable) for Qt5 and Qt6.

    Qt6 may nest these under ``QDockWidget.DockWidgetFeature``.
    """
    if hasattr(QDockWidget, "DockWidgetClosable"):
        return (
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
    feat = QDockWidget.DockWidgetFeature
    return feat.DockWidgetClosable | feat.DockWidgetMovable | feat.DockWidgetFloatable

# Import detection services at module level for testability
DuplicateObjectsDetectorService = None
SkippedNumbersDetectorService = None
OutOfBoundsDetectorService = None

try:
    from services.duplicate_objects_detector_service import DuplicateObjectsDetectorService
    from services.skipped_numbers_detector_service import SkippedNumbersDetectorService
    from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
except ImportError:
    # Fallback for when running as a plugin
    try:
        import sys
        import os
        # Add the project root to the path to enable absolute imports
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from services.duplicate_objects_detector_service import DuplicateObjectsDetectorService
        from services.skipped_numbers_detector_service import SkippedNumbersDetectorService
        from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
    except ImportError:
        # For testing purposes, these will be mocked
        pass





class ImportSummaryDockWidget(QDockWidget):
    """
    Import Summary dock widget for ArcheoSync plugin.
    
    Displays a summary of imported data after the import process is complete.
    Uses QDockWidget to prevent floating above other windows and allow docking
    into the main QGIS interface.
    All user-facing strings are wrapped in self.tr() for translation.
    """
    
    def __init__(self, 
                 summary_data: ImportSummaryData,
                 iface=None,
                 settings_manager=None,
                 csv_import_service=None,
                 field_project_import_service=None,
                 layer_service=None,
                 parent=None):
        """
        Initialize the import summary dock widget.
        
        Args:
            summary_data: Data containing import statistics
            iface: QGIS interface for opening attribute tables
            settings_manager: Settings manager for accessing layer configurations
            csv_import_service: CSV import service for archiving files after validation
            field_project_import_service: Field project import service for archiving projects after validation
            layer_service: Layer service for layer operations
            parent: Parent widget for the dock widget
        """
        print(f"[DEBUG][UI] ImportSummaryDockWidget created with {len(getattr(summary_data, 'distance_warnings', []))} distance warnings")
        super().__init__(parent)
        
        # Store injected dependencies
        self._summary_data = summary_data
        self._iface = iface
        self._settings_manager = settings_manager
        self._csv_import_service = csv_import_service
        self._field_project_import_service = field_project_import_service
        self._layer_service = layer_service
        self._parent = parent
        
        self._validation_running = False
        self._validation_jobs: List[LayerCopyJob] = []
        self._validation_job_index = 0
        self._validation_copied_counts: Dict[str, int] = {}
        self._validation_missing_configurations: List[str] = []
        self._validation_canvas_rendering_was_enabled: Optional[bool] = None
        self._feature_copier = ImportFeatureCopier()

        # Initialize UI
        self._setup_ui()
        self._setup_connections()

    def _append_out_of_bounds_warnings_section(
        self, content_layout: QtWidgets.QVBoxLayout
    ) -> None:
        """
        Append out-of-bounds (recording area boundary) warnings to the scrollable summary.

        Reads ``ImportSummaryData.out_of_bounds_warnings`` (filled at import and on refresh).
        Each structured warning can open the temporary layer attribute table with a filter
        applied so the user can inspect offending features.
        """
        warnings_list = getattr(self._summary_data, "out_of_bounds_warnings", None) or []
        if not warnings_list:
            return
        print(f"[DEBUG][UI] Displaying {len(warnings_list)} out-of-bounds warnings")
        warnings_layout = QtWidgets.QVBoxLayout()
        warnings_label = QtWidgets.QLabel(self.tr("Out-of-Bounds Warnings:"))
        warnings_label.setStyleSheet("font-weight: bold; color: #A0522D;")
        warnings_layout.addWidget(warnings_label)
        for warning in warnings_list:
            maybe_yield_to_ui()
            warning_item_layout = QtWidgets.QHBoxLayout()
            if hasattr(warning, "message"):
                warning_text = warning.message
            else:
                warning_text = str(warning)
            warning_item = QtWidgets.QLabel(f"• {warning_text}")
            warning_item.setStyleSheet("color: #A0522D; margin-left: 10px;")
            warning_item.setWordWrap(True)
            warning_item_layout.addWidget(warning_item)
            if hasattr(warning, "message") and self._iface:
                if getattr(warning, "second_layer_name", None):
                    button = QtWidgets.QPushButton(self.tr("Select and Show Both Entities"))
                    button.setStyleSheet(
                        "background-color: #FF6B35; color: white; border: none; "
                        "padding: 5px; border-radius: 3px;"
                    )
                    button.clicked.connect(
                        lambda checked, w=warning: self._open_both_filtered_attribute_tables(w)
                    )
                else:
                    button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                    button.setStyleSheet(
                        "background-color: #4CAF50; color: white; border: none; "
                        "padding: 5px; border-radius: 3px;"
                    )
                    button.clicked.connect(
                        lambda checked, w=warning: self._open_filtered_attribute_table(w)
                    )
                warning_item_layout.addWidget(button)
            warning_item_layout.addStretch()
            warnings_layout.addLayout(warning_item_layout)
        content_layout.addLayout(warnings_layout)
        print("[DEBUG][UI] Added out-of-bounds warnings layout to content_layout")
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        title_text = self.tr("Import Summary")
        if getattr(self._summary_data, 'is_global_project', False):
            title_text = self.tr("Global Project Import Summary")
        self.setWindowTitle(title_text)
        self.setAllowedAreas(DOCK_WIDGET_AREAS.all_sides)
        self.setFeatures(_default_qdockwidget_features())
        
        # Create the main widget
        main_widget = QtWidgets.QWidget()
        self.setWidget(main_widget)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        
        # Add title
        title_label = QtWidgets.QLabel(title_text)
        title_label.setAlignment(_align_center_flag())
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
        main_layout.addWidget(title_label)

        self._create_warnings_analysis_indicator(main_layout)
        
        # Add summary content
        self._create_summary_content(main_layout)
        
        # Add buttons
        self._create_buttons(main_layout)
        
        # Set size
        self.resize(400, 500)

    def _create_warnings_analysis_indicator(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Add an indeterminate progress row shown while warning detectors run."""
        self._warnings_analysis_running = False
        self._warnings_analysis_container = QtWidgets.QWidget()
        indicator_layout = QtWidgets.QHBoxLayout(self._warnings_analysis_container)
        indicator_layout.setContentsMargins(8, 4, 8, 4)

        self._warnings_analysis_progress = QtWidgets.QProgressBar()
        self._warnings_analysis_progress.setRange(0, 0)
        self._warnings_analysis_progress.setTextVisible(False)
        self._warnings_analysis_progress.setFixedHeight(18)
        self._warnings_analysis_progress.setMinimumWidth(120)

        self._warnings_analysis_label = QtWidgets.QLabel(
            self.tr("Analyzing warnings...")
        )
        self._warnings_analysis_label.setWordWrap(True)
        self._warnings_analysis_label.setStyleSheet("color: #555; font-style: italic;")

        indicator_layout.addWidget(self._warnings_analysis_progress)
        indicator_layout.addWidget(self._warnings_analysis_label, 1)
        self._warnings_analysis_container.setVisible(False)
        parent_layout.addWidget(self._warnings_analysis_container)

    def _set_warnings_analysis_busy(self, busy: bool, total_steps: int = 0) -> None:
        """
        Show or hide the in-panel busy indicator and guard action buttons.

        Args:
            busy: When True, display the progress bar and disable refresh/validate/cancel
                until analysis or validation completes.
            total_steps: When greater than zero, show determinate progress (0..total_steps).
        """
        self._warnings_analysis_running = busy
        self._validation_running = busy
        if hasattr(self, "_warnings_analysis_container"):
            self._warnings_analysis_container.setVisible(busy)
        if hasattr(self, "_warnings_analysis_progress"):
            if busy and total_steps > 0:
                self._warnings_analysis_progress.setRange(0, total_steps)
                self._warnings_analysis_progress.setValue(0)
                self._warnings_analysis_progress.setTextVisible(True)
            else:
                self._warnings_analysis_progress.setRange(0, 0)
                self._warnings_analysis_progress.setTextVisible(False)
        if hasattr(self, "_refresh_button"):
            self._refresh_button.setEnabled(not busy)
            self._validate_button.setEnabled(not busy)
            self._cancel_button.setEnabled(not busy)
        if busy:
            maybe_yield_to_ui(force=True)

    def _update_warnings_analysis_progress(self, completed_steps: int, status_text: str) -> None:
        """Update the in-panel progress label and bar between detection steps."""
        if hasattr(self, "_warnings_analysis_label"):
            self._warnings_analysis_label.setText(status_text)
        if (
            hasattr(self, "_warnings_analysis_progress")
            and self._warnings_analysis_progress.maximum() > 0
        ):
            self._warnings_analysis_progress.setValue(completed_steps)
        flush_ui_updates(self._warnings_analysis_container)
    
    def _create_summary_content(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the summary content section."""
        print("[DEBUG][UI] Creating summary content")
        # Create scroll area for content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(_scroll_bar_as_needed_policy())
        scroll_area.setVerticalScrollBarPolicy(_scroll_bar_as_needed_policy())
        
        # Create content widget
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)

        # Boundary warnings first so they stay visible without scrolling past long sections
        print(
            f"[DEBUG][UI] Summary UI: out_of_bounds_warnings count="
            f"{len(getattr(self._summary_data, 'out_of_bounds_warnings', None) or [])}"
        )
        self._append_out_of_bounds_warnings_section(content_layout)

        # CSV Points section
        if self._summary_data.csv_points_count > 0:
            csv_group = self._create_csv_section()
            content_layout.addWidget(csv_group)
        
        # Features section
        if self._summary_data.features_count > 0:
            features_group = self._create_features_section()
            content_layout.addWidget(features_group)
        
        # Objects section
        if self._summary_data.objects_count > 0:
            objects_group = self._create_objects_section()
            content_layout.addWidget(objects_group)
        
        # Small Finds section
        if self._summary_data.small_finds_count > 0:
            small_finds_group = self._create_small_finds_section()
            content_layout.addWidget(small_finds_group)

        # Distance warnings section
        if hasattr(self._summary_data, 'distance_warnings') and self._summary_data.distance_warnings:
            print(f"[DEBUG][UI] Displaying {len(self._summary_data.distance_warnings)} distance warnings")
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Distance Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #DC143C;")
            warnings_layout.addWidget(warnings_label)
            for i, warning in enumerate(self._summary_data.distance_warnings):
                warning_item_layout = QtWidgets.QHBoxLayout()
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #DC143C; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                if hasattr(warning, 'message') and self._iface:
                    button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                    button.setStyleSheet("background-color: #DC143C; color: white; border: none; padding: 5px; border-radius: 3px;")
                    button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    warning_item_layout.addWidget(button)
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            content_layout.addLayout(warnings_layout)
            print("[DEBUG][UI] Added distance warnings layout to content_layout")
        
        # Add stretch to push content to top
        content_layout.addStretch()
        
        # Set the content widget
        scroll_area.setWidget(content_widget)
        parent_layout.addWidget(scroll_area)
    
    def _create_csv_section(self) -> QtWidgets.QGroupBox:
        """Create the CSV points summary section."""
        group = QtWidgets.QGroupBox(self.tr("Total Station CSV Points"))
        layout = QtWidgets.QVBoxLayout(group)
        
        # Points count
        points_layout = QtWidgets.QHBoxLayout()
        points_label = QtWidgets.QLabel(self.tr("Points imported:"))
        points_count = QtWidgets.QLabel(str(self._summary_data.csv_points_count))
        points_count.setStyleSheet("font-weight: bold; color: #2E8B57;")
        points_layout.addWidget(points_label)
        points_layout.addStretch()
        points_layout.addWidget(points_count)
        layout.addLayout(points_layout)
        
        # Duplicates count
        if self._summary_data.csv_duplicates > 0:
            duplicates_layout = QtWidgets.QHBoxLayout()
            duplicates_label = QtWidgets.QLabel(self.tr("Duplicates detected:"))
            duplicates_count = QtWidgets.QLabel(str(self._summary_data.csv_duplicates))
            duplicates_count.setStyleSheet("font-weight: bold; color: #FF6B35;")
            duplicates_layout.addWidget(duplicates_label)
            duplicates_layout.addStretch()
            duplicates_layout.addWidget(duplicates_count)
            layout.addLayout(duplicates_layout)
        
        # Duplicate total station identifiers warnings
        if hasattr(self._summary_data, 'duplicate_total_station_identifiers_warnings') and self._summary_data.duplicate_total_station_identifiers_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Duplicate Identifiers Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF4500;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.duplicate_total_station_identifiers_warnings:
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF4500; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    if getattr(warning, "second_layer_name", None):
                        # Between-layer warning - open both tables
                        button = QtWidgets.QPushButton(self.tr("Select and Show Both Entities"))
                        button.setStyleSheet("background-color: #FF6B35; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    else:
                        # Single layer warning
                        button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                        button.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_filtered_attribute_table(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        
        # Height difference warnings
        if hasattr(self._summary_data, 'height_difference_warnings') and self._summary_data.height_difference_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Height Difference Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF4500;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.height_difference_warnings:
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF8C00; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    if getattr(warning, "second_layer_name", None):
                        # Between-layer warning - open both tables
                        button = QtWidgets.QPushButton(self.tr("Select and Show Both Entities"))
                        button.setStyleSheet("background-color: #FF6B35; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    else:
                        # Single layer warning
                        button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                        button.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_filtered_attribute_table(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        
        # Missing total station warnings
        if hasattr(self._summary_data, 'missing_total_station_warnings') and self._summary_data.missing_total_station_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Missing Total Station Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #8B0000;")
            warnings_layout.addWidget(warnings_label)
            
            for i, warning in enumerate(self._summary_data.missing_total_station_warnings):
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #8B0000; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                    button.setStyleSheet("background-color: #8B0000; color: white; border: none; padding: 5px; border-radius: 3px;")
                    button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        
        return group
    
    def _create_features_section(self) -> QtWidgets.QGroupBox:
        """Create the features summary section."""
        group = QtWidgets.QGroupBox(self.tr("Features"))
        layout = QtWidgets.QVBoxLayout(group)
        
        # Features count
        features_layout = QtWidgets.QHBoxLayout()
        features_label = QtWidgets.QLabel(self.tr("Features imported:"))
        features_count = QtWidgets.QLabel(str(self._summary_data.features_count))
        features_count.setStyleSheet("font-weight: bold; color: #2E8B57;")
        features_layout.addWidget(features_label)
        features_layout.addStretch()
        features_layout.addWidget(features_count)
        layout.addLayout(features_layout)
        
        # Duplicates count
        if self._summary_data.features_duplicates > 0:
            duplicates_layout = QtWidgets.QHBoxLayout()
            duplicates_label = QtWidgets.QLabel(self.tr("Duplicates detected:"))
            duplicates_count = QtWidgets.QLabel(str(self._summary_data.features_duplicates))
            duplicates_count.setStyleSheet("font-weight: bold; color: #FF6B35;")
            duplicates_layout.addWidget(duplicates_label)
            duplicates_layout.addStretch()
            duplicates_layout.addWidget(duplicates_count)
            layout.addLayout(duplicates_layout)
        
        return group
    
    def _create_objects_section(self) -> QtWidgets.QGroupBox:
        """Create the objects summary section."""
        group = QtWidgets.QGroupBox(self.tr("Objects"))
        layout = QtWidgets.QVBoxLayout(group)
        
        # Objects count
        objects_layout = QtWidgets.QHBoxLayout()
        objects_label = QtWidgets.QLabel(self.tr("Objects imported:"))
        objects_count = QtWidgets.QLabel(str(self._summary_data.objects_count))
        objects_count.setStyleSheet("font-weight: bold; color: #2E8B57;")
        objects_layout.addWidget(objects_label)
        objects_layout.addStretch()
        objects_layout.addWidget(objects_count)
        layout.addLayout(objects_layout)

        if getattr(self._summary_data, 'alternative_objects_merged_count', 0) > 0:
            alt_layout = QtWidgets.QHBoxLayout()
            alt_label = QtWidgets.QLabel(self.tr("Alternative objects merged (no geometry):"))
            alt_count = QtWidgets.QLabel(str(self._summary_data.alternative_objects_merged_count))
            alt_count.setStyleSheet("font-weight: bold; color: #2E8B57;")
            alt_layout.addWidget(alt_label)
            alt_layout.addStretch()
            alt_layout.addWidget(alt_count)
            layout.addLayout(alt_layout)
        
        # Duplicates count
        if self._summary_data.objects_duplicates > 0:
            duplicates_layout = QtWidgets.QHBoxLayout()
            duplicates_label = QtWidgets.QLabel(self.tr("Duplicates detected:"))
            duplicates_count = QtWidgets.QLabel(str(self._summary_data.objects_duplicates))
            duplicates_count.setStyleSheet("font-weight: bold; color: #FF6B35;")
            duplicates_layout.addWidget(duplicates_label)
            duplicates_layout.addStretch()
            duplicates_layout.addWidget(duplicates_count)
            layout.addLayout(duplicates_layout)
        
        # Duplicate objects warnings
        if hasattr(self._summary_data, 'duplicate_objects_warnings') and self._summary_data.duplicate_objects_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Duplicate Objects Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF4500;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.duplicate_objects_warnings:
                maybe_yield_to_ui()
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF4500; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    if getattr(warning, "second_layer_name", None):
                        # Between-layer warning - open both tables
                        button = QtWidgets.QPushButton(self.tr("Select and Show Both Entities"))
                        button.setStyleSheet("background-color: #FF6B35; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    else:
                        # Single layer warning
                        button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                        button.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_filtered_attribute_table(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        
        # Skipped numbers warnings
        if hasattr(self._summary_data, 'skipped_numbers_warnings') and self._summary_data.skipped_numbers_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Skipped Numbers Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF8C00;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.skipped_numbers_warnings:
                maybe_yield_to_ui()
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF8C00; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    if getattr(warning, "second_layer_name", None):
                        # Between-layer warning - open both tables
                        button = QtWidgets.QPushButton(self.tr("Select and Show Both Entities"))
                        button.setStyleSheet("background-color: #FF6B35; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    else:
                        # Single layer warning
                        button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                        button.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px; border-radius: 3px;")
                        button.clicked.connect(lambda checked, w=warning: self._open_filtered_attribute_table(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        
        return group
    
    def _create_small_finds_section(self) -> QtWidgets.QGroupBox:
        """Create the small finds summary section."""
        group = QtWidgets.QGroupBox(self.tr("Small Finds"))
        layout = QtWidgets.QVBoxLayout(group)
        
        # Small finds count
        small_finds_layout = QtWidgets.QHBoxLayout()
        small_finds_label = QtWidgets.QLabel(self.tr("Small finds imported:"))
        small_finds_count = QtWidgets.QLabel(str(self._summary_data.small_finds_count))
        small_finds_count.setStyleSheet("font-weight: bold; color: #2E8B57;")
        small_finds_layout.addWidget(small_finds_label)
        small_finds_layout.addStretch()
        small_finds_layout.addWidget(small_finds_count)
        layout.addLayout(small_finds_layout)
        
        # Duplicates count
        if self._summary_data.small_finds_duplicates > 0:
            duplicates_layout = QtWidgets.QHBoxLayout()
            duplicates_label = QtWidgets.QLabel(self.tr("Duplicates detected:"))
            duplicates_count = QtWidgets.QLabel(str(self._summary_data.small_finds_duplicates))
            duplicates_count.setStyleSheet("font-weight: bold; color: #FF6B35;")
            duplicates_layout.addWidget(duplicates_label)
            duplicates_layout.addStretch()
            duplicates_layout.addWidget(duplicates_count)
            layout.addLayout(duplicates_layout)
        
        return group
    
    def _create_buttons(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the button section."""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Create Refresh button for warnings
        self._refresh_button = QtWidgets.QPushButton(self.tr("Refresh Warnings"))
        
        # Create Cancel button
        self._cancel_button = QtWidgets.QPushButton(self.tr("Cancel Import"))
        
        # Create Validate button (instead of OK)
        self._validate_button = QtWidgets.QPushButton(self.tr("Validate"))
        self._validate_button.setDefault(True)
        
        # Add buttons to layout
        button_layout.addWidget(self._refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(self._cancel_button)
        button_layout.addWidget(self._validate_button)
        
        parent_layout.addLayout(button_layout)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Button connections
        self._refresh_button.clicked.connect(self._handle_refresh_warnings)
        self._cancel_button.clicked.connect(self._handle_cancel)
        self._validate_button.clicked.connect(self._handle_validate)

    def refresh_warnings_silently(self) -> None:
        """
        Refresh warning sections without blocking dialogs.

        Used by the plugin right after dock creation so the panel appears
        immediately while detectors run incrementally on the Qt event loop.
        """
        self._refresh_warnings(show_feedback=False)
    
    def _handle_validate(self) -> None:
        """Handle the validate button click - copy features from temporary to definitive layers."""
        if self._validation_running:
            return
        try:
            if self._has_warnings():
                if not self._confirm_validation_with_warnings():
                    return

            self._start_async_validation()
        except Exception as e:
            self._handle_validation_failure(e)

    def _start_async_validation(self) -> None:
        """
        Begin incremental validation on the Qt main thread.

        One feature is copied per ``QTimer`` tick so the progress bar can repaint
        between copies. Default value expressions are still evaluated per feature
        via ``QgsVectorLayerUtils.createFeature``.
        """
        from qgis.core import QgsProject

        project = QgsProject.instance()
        self._validation_jobs = build_layer_copy_jobs(
            project.mapLayers(),
            self._get_definitive_layer_id,
        )
        self._validation_job_index = 0
        self._validation_copied_counts = {}
        self._validation_missing_configurations = self._collect_missing_layer_configurations()

        total_features = self._validation_total_feature_count()
        if total_features <= 0:
            self._complete_validation_with_no_copied_features()
            return

        for job in self._validation_jobs:
            block_job_target_signals(job)

        self._set_map_canvas_rendering(False)
        self._set_warnings_analysis_busy(True, total_steps=total_features)
        self._update_warnings_analysis_progress(
            0,
            self.tr("Preparing validation... (0/{total})").format(total=total_features),
        )
        flush_ui_updates(self._warnings_analysis_container)
        QTimer.singleShot(0, self._run_validation_batch_step)

    def _collect_missing_layer_configurations(self) -> List[str]:
        """Return settings keys for import layers present but not configured."""
        from qgis.core import QgsProject

        project_layers = QgsProject.instance().mapLayers()
        temp_names = {layer.name() for layer in project_layers.values()}
        configured_keys = {job.definitive_layer_key for job in self._validation_jobs}
        missing: List[str] = []

        for temp_layer_name, definitive_layer_key in IMPORT_LAYER_MAPPINGS.items():
            if temp_layer_name not in temp_names:
                continue
            if definitive_layer_key in configured_keys:
                continue
            if not self._get_definitive_layer_id(definitive_layer_key):
                missing.append(definitive_layer_key)

        return missing

    def _validation_processed_feature_count(self) -> int:
        """Count features fully copied across finished and current jobs."""
        processed = 0
        for index, job in enumerate(self._validation_jobs):
            if index < self._validation_job_index:
                processed += job.feature_count
            elif index == self._validation_job_index:
                processed += job.feature_index
        return processed

    def _validation_progress_value(self) -> int:
        """
        Progress bar value including partial loading of the active job.

        While features are still being read from disk, advance the bar so the
        user sees movement before the first copy starts.
        """
        processed = self._validation_processed_feature_count()
        if self._validation_job_index < len(self._validation_jobs):
            job = self._validation_jobs[self._validation_job_index]
            if not job.load_complete and job.source_features is not None:
                processed += len(job.source_features)
        return processed

    def _validation_total_feature_count(self) -> int:
        return sum(job.feature_count for job in self._validation_jobs)

    def _sync_validation_progress_maximum(self) -> None:
        """Refresh the progress bar maximum when loaded counts differ from estimates."""
        if not hasattr(self, "_warnings_analysis_progress"):
            return
        total = self._validation_total_feature_count()
        if total > 0 and self._warnings_analysis_progress.maximum() != total:
            self._warnings_analysis_progress.setMaximum(total)

    def _set_map_canvas_rendering(self, enabled: bool) -> None:
        """Suspend map redraws during validation to keep the UI responsive."""
        if not self._iface:
            return
        try:
            canvas = self._iface.mapCanvas()
            if canvas is None:
                return
            if not enabled:
                self._validation_canvas_rendering_was_enabled = canvas.renderFlag()
                canvas.setRenderFlag(False)
            elif self._validation_canvas_rendering_was_enabled is not None:
                canvas.setRenderFlag(self._validation_canvas_rendering_was_enabled)
                self._validation_canvas_rendering_was_enabled = None
                canvas.refresh()
        except Exception:
            pass

    def _run_validation_batch_step(self) -> None:
        """Load or copy one small chunk, then yield back to the Qt event loop."""
        try:
            if self._validation_job_index >= len(self._validation_jobs):
                self._finalize_validation_success()
                return

            job = self._validation_jobs[self._validation_job_index]
            total = self._validation_total_feature_count()

            if not job.load_complete:
                load_job_source_features_chunk(job)
                loaded = len(job.source_features or [])
                self._sync_validation_progress_maximum()
                total = self._validation_total_feature_count()
                self._update_warnings_analysis_progress(
                    self._validation_progress_value(),
                    self.tr("Loading {layer}... ({current}/{total})").format(
                        layer=job.temp_layer_name,
                        current=loaded,
                        total=job.feature_count,
                    ),
                )
                QTimer.singleShot(0, self._run_validation_batch_step)
                return

            ensure_job_expression_context(job)

            processed = self._validation_processed_feature_count()
            self._update_warnings_analysis_progress(
                self._validation_progress_value(),
                self.tr("Validating import... ({current}/{total})").format(
                    current=processed,
                    total=total,
                ),
            )

            batch_result = self._feature_copier.copy_features_batch(
                source_features=job.source_features or [],
                target_layer=job.target_layer,
                start_index=job.feature_index,
                field_mapping=job.field_mapping,
                expression_context=job.expression_context,
            )

            job.feature_index = batch_result.next_index
            job.copied_count += batch_result.copied_count
            job.added_feature_ids.extend(batch_result.added_feature_ids)

            if batch_result.error_count > 0:
                print(
                    f"Validation copy on '{job.temp_layer_name}': "
                    f"{batch_result.error_count} feature error(s) in batch"
                )

            processed = self._validation_processed_feature_count()
            self._update_warnings_analysis_progress(
                self._validation_progress_value(),
                self.tr("Validating import... ({current}/{total})").format(
                    current=processed,
                    total=total,
                ),
            )

            if job.feature_index >= job.feature_count:
                unblock_job_target_signals(job)
                self._feature_copier.select_copied_features(
                    job.target_layer,
                    job.added_feature_ids,
                )
                self._validation_copied_counts[job.temp_layer_name] = job.copied_count
                print(
                    f"Copied {job.copied_count} features from "
                    f"'{job.temp_layer_name}' to '{job.target_layer.name()}'"
                )
                self._validation_job_index += 1
                self._sync_validation_progress_maximum()

            QTimer.singleShot(0, self._run_validation_batch_step)
        except Exception as e:
            self._handle_validation_failure(e)

    def _complete_validation_with_no_copied_features(self) -> None:
        """Show feedback when no features could be copied."""
        if self._validation_missing_configurations:
            QMessageBox.information(
                self,
                self.tr("No Layers to Validate"),
                self.tr(
                    "Note: Some layers could not be copied because definitive layers "
                    "are not configured.\n\n"
                    "Please configure the definitive layers in the settings dialog first."
                ),
            )
        else:
            QMessageBox.information(
                self,
                self.tr("No Layers to Validate"),
                self.tr("No temporary import layers with features were found to validate."),
            )

    def _unblock_all_validation_layer_signals(self) -> None:
        """Restore QgsVectorLayer signal delivery after validation."""
        for job in self._validation_jobs:
            unblock_job_target_signals(job)

    def _finalize_validation_success(self) -> None:
        """Show the success summary, then archive data and close the dock."""
        self._unblock_all_validation_layer_signals()
        self._set_map_canvas_rendering(True)
        self._set_warnings_analysis_busy(False)

        if self._validation_copied_counts:
            success_message = self.tr("Features copied successfully!\n\n")
            for layer_name, count in self._validation_copied_counts.items():
                success_message += f"• {layer_name}: {count} features\n"
            success_message += f"\n{self.tr('The definitive layers are now in edit mode.')}\n"
            success_message += (
                f"{self.tr('The newly copied features are selected for easy identification.')}\n"
            )
            success_message += f"{self.tr('Please review the copied features and:')}\n"
            success_message += f"• {self.tr('Save changes if you want to keep them')}\n"
            success_message += f"• {self.tr('Cancel changes if you want to discard them')}"

            QMessageBox.information(
                self,
                self.tr("Validation Complete"),
                success_message,
            )
        elif self._validation_missing_configurations:
            self._complete_validation_with_no_copied_features()

        self._delete_temporary_layers()
        self._archive_imported_data()

        if self._iface:
            self._iface.removeDockWidget(self)
        self.deleteLater()

    def _handle_validation_failure(self, error: Exception) -> None:
        """Roll back UI state and show a validation error."""
        self._unblock_all_validation_layer_signals()
        self._set_map_canvas_rendering(True)
        self._set_warnings_analysis_busy(False)
        print(f"Error during validation: {error}")
        import traceback

        traceback.print_exc()
        QMessageBox.critical(
            self,
            self.tr("Validation Error"),
            self.tr(f"An error occurred during validation: {str(error)}"),
        )
    
    def _has_warnings(self) -> bool:
        """Check if there are any warnings present in the summary data."""
        duplicate_warnings = getattr(self._summary_data, 'duplicate_objects_warnings', [])
        skipped_warnings = getattr(self._summary_data, 'skipped_numbers_warnings', [])
        out_of_bounds_warnings = getattr(self._summary_data, 'out_of_bounds_warnings', [])
        distance_warnings = getattr(self._summary_data, 'distance_warnings', [])
        
        return len(duplicate_warnings) > 0 or len(skipped_warnings) > 0 or len(out_of_bounds_warnings) > 0 or len(distance_warnings) > 0
    
    def _confirm_validation_with_warnings(self) -> bool:
        """Show confirmation dialog when warnings are present."""
        duplicate_count = len(getattr(self._summary_data, 'duplicate_objects_warnings', []))
        skipped_count = len(getattr(self._summary_data, 'skipped_numbers_warnings', []))
        out_of_bounds_count = len(getattr(self._summary_data, 'out_of_bounds_warnings', []))
        distance_count = len(getattr(self._summary_data, 'distance_warnings', []))
        
        # Build warning summary message
        warning_summary = []
        if duplicate_count > 0:
            warning_summary.append(self.tr(f"• {duplicate_count} duplicate object warning(s)"))
        if skipped_count > 0:
            warning_summary.append(self.tr(f"• {skipped_count} skipped numbers warning(s)"))
        if out_of_bounds_count > 0:
            warning_summary.append(self.tr(f"• {out_of_bounds_count} out-of-bounds warning(s)"))
        if distance_count > 0:
            warning_summary.append(self.tr(f"• {distance_count} distance warning(s)"))
        
        warning_message = "\n".join(warning_summary)
        
        # Show confirmation dialog (Qt5 vs Qt6 button enums)
        std_btns, default_btn, yes_val, _ = _qmessagebox_yes_no_dialog_args()
        reply = QMessageBox.question(
            self,
            self.tr("Validation with Warnings"),
            self.tr(f"The following warnings have been detected:\n\n{warning_message}\n\nDo you want to proceed with validation anyway?"),
            std_btns,
            default_btn,
        )
        
        return reply == yes_val
    
    def _handle_cancel(self) -> None:
        """Handle the cancel button click - delete temporary layers and delete the widget."""
        try:
            # Show confirmation dialog (Qt5 vs Qt6 button enums)
            std_btns, default_btn, yes_val, _ = _qmessagebox_yes_no_dialog_args()
            reply = QMessageBox.question(
                self,
                self.tr("Cancel Import"),
                self.tr("Are you sure you want to cancel the import? This will delete all temporary import layers and cannot be undone."),
                std_btns,
                default_btn,
            )
            
            if reply == yes_val:
                # Delete temporary layers
                self._delete_temporary_layers()
                
                # Delete the dock widget from the interface
                if self._iface:
                    self._iface.removeDockWidget(self)
                
                # Delete the widget
                self.deleteLater()
                
        except Exception as e:
            print(f"Error during cancel: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message to user
            QMessageBox.critical(
                self,
                self.tr("Cancel Error"),
                self.tr(f"An error occurred while canceling the import: {str(e)}")
            )
    
    def _sync_virtual_fields_to_temporary_import_layers(self) -> None:
        """
        Copy virtual (expression) fields from definitive layers onto pending import layers.

        Matches ``ArcheoSyncPlugin._show_import_summary`` so "Refresh warnings" runs detectors
        on the same layer field definitions as the initial summary; otherwise reads (e.g. of
        the configured object number field) can diverge and stale or spurious warnings reappear.
        """
        if not self._layer_service or not self._settings_manager:
            return
        # Objects
        temp_objects_layer = self._layer_service.get_layer_by_name("New Objects")
        definitive_objects_layer = None
        objects_layer_id = self._settings_manager.get_value("objects_layer")
        if objects_layer_id:
            definitive_objects_layer = self._layer_service.get_layer_by_id(objects_layer_id)
        if temp_objects_layer and definitive_objects_layer:
            self._layer_service.copy_virtual_fields(definitive_objects_layer, temp_objects_layer)
        # Features
        temp_features_layer = self._layer_service.get_layer_by_name("New Features")
        definitive_features_layer = None
        features_layer_id = self._settings_manager.get_value("features_layer")
        if features_layer_id:
            definitive_features_layer = self._layer_service.get_layer_by_id(features_layer_id)
        if temp_features_layer and definitive_features_layer:
            self._layer_service.copy_virtual_fields(definitive_features_layer, temp_features_layer)
        # Small Finds
        temp_small_finds_layer = self._layer_service.get_layer_by_name("New Small Finds")
        definitive_small_finds_layer = None
        small_finds_layer_id = self._settings_manager.get_value("small_finds_layer")
        if small_finds_layer_id:
            definitive_small_finds_layer = self._layer_service.get_layer_by_id(small_finds_layer_id)
        if temp_small_finds_layer and definitive_small_finds_layer:
            self._layer_service.copy_virtual_fields(definitive_small_finds_layer, temp_small_finds_layer)
        # Total Station Points
        temp_points_layer = self._layer_service.get_layer_by_name("Imported_CSV_Points")
        definitive_points_layer = None
        points_layer_id = self._settings_manager.get_value("total_station_points_layer")
        if points_layer_id:
            definitive_points_layer = self._layer_service.get_layer_by_id(points_layer_id)
        if temp_points_layer and definitive_points_layer:
            self._layer_service.copy_virtual_fields(definitive_points_layer, temp_points_layer)

    def _handle_refresh_warnings(self) -> None:
        """Handle explicit refresh button click and notify the user on completion."""
        self._refresh_warnings(show_feedback=True)

    def _refresh_warnings(self, show_feedback: bool) -> None:
        """
        Start incremental warning detection.

        Each detector step is scheduled as a QgsTask so the QGIS UI stays
        responsive; the virtual-field preparation step remains on the main thread.
        """
        if self._warnings_analysis_running:
            return
        if DuplicateObjectsDetectorService is None or SkippedNumbersDetectorService is None:
            if show_feedback:
                QMessageBox.warning(
                    self,
                    self.tr("Services Not Available"),
                    self.tr(
                        "Detection services are not available. Please ensure the plugin is properly installed."
                    ),
                )
            return

        self._warning_refresh_show_feedback = show_feedback
        self._warning_refresh_plan = self._build_warning_refresh_plan()
        self._warning_refresh_index = 0
        self._warning_refresh_results: Dict[str, List[Any]] = {}
        self._active_warning_detection_task = None

        total_steps = len(self._warning_refresh_plan)
        self._set_warnings_analysis_busy(True, total_steps=total_steps)
        self._update_warnings_analysis_progress(
            0,
            self.tr("Analyzing warnings... (0/{total})").format(total=total_steps),
        )
        QTimer.singleShot(1, self._run_next_warning_refresh_step)

    def _build_warning_refresh_plan(self) -> List[Tuple[Optional[str], str, Callable[[], List[Any]]]]:
        """
        Build ordered warning-detection steps for incremental execution.

        Returns:
            List of (summary_data attribute name or None, status label, runner).
        """
        steps: List[Tuple[Optional[str], str, Callable[[], List[Any]]]] = [
            (
                None,
                self.tr("Preparing layers..."),
                self._run_prepare_layers_for_warning_detection,
            ),
        ]
        if self._summary_data.objects_count > 0:
            steps.append(
                (
                    "duplicate_objects_warnings",
                    self.tr("Checking duplicate objects..."),
                    self._detect_duplicate_objects_warnings,
                )
            )
            steps.append(
                (
                    "skipped_numbers_warnings",
                    self.tr("Checking skipped numbers..."),
                    self._detect_skipped_numbers_warnings,
                )
            )
        if (
            self._summary_data.objects_count > 0
            or self._summary_data.features_count > 0
            or self._summary_data.small_finds_count > 0
            or self._summary_data.csv_points_count > 0
        ):
            steps.append(
                (
                    "out_of_bounds_warnings",
                    self.tr("Checking out-of-bounds features..."),
                    self._detect_out_of_bounds_warnings,
                )
            )
        if self._summary_data.csv_points_count > 0 or self._summary_data.objects_count > 0:
            steps.append(
                (
                    "distance_warnings",
                    self.tr("Checking distances..."),
                    self._detect_distance_warnings,
                )
            )
        if self._summary_data.csv_points_count > 0 and self._summary_data.objects_count > 0:
            steps.append(
                (
                    "missing_total_station_warnings",
                    self.tr("Checking missing total station points..."),
                    self._detect_missing_total_station_warnings,
                )
            )
        if self._summary_data.csv_points_count > 0:
            steps.append(
                (
                    "duplicate_total_station_identifiers_warnings",
                    self.tr("Checking duplicate total station identifiers..."),
                    self._detect_duplicate_total_station_identifiers_warnings,
                )
            )
            steps.append(
                (
                    "height_difference_warnings",
                    self.tr("Checking height differences..."),
                    self._detect_height_difference_warnings,
                )
            )
        return steps

    def _run_prepare_layers_for_warning_detection(self) -> List[Any]:
        """Sync virtual fields before running detectors."""
        self._sync_virtual_fields_to_temporary_import_layers()
        return []

    def _dispatch_warning_detection_step(
        self,
        description: str,
        runner: Callable[[], List[Any]],
        on_success: Callable[[List[Any]], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Schedule one detector step; overridable in tests for synchronous execution."""
        self._active_warning_detection_task = dispatch_warning_detection_step(
            description,
            runner,
            on_success,
            on_error,
        )

    def _run_next_warning_refresh_step(self) -> None:
        """Schedule a single warning-detection step off the main thread when possible."""
        if not self._warnings_analysis_running:
            return

        total_steps = len(self._warning_refresh_plan)
        if self._warning_refresh_index >= total_steps:
            self._finalize_warning_refresh()
            return

        result_key, status_label, runner = self._warning_refresh_plan[self._warning_refresh_index]
        step_number = self._warning_refresh_index + 1
        reset_yield_counter()
        self._update_warnings_analysis_progress(
            self._warning_refresh_index,
            self.tr("{task} ({current}/{total})").format(
                task=status_label,
                current=step_number,
                total=total_steps,
            ),
        )

        def on_success(warnings: List[Any]) -> None:
            if not self._warnings_analysis_running:
                return
            if result_key is not None:
                self._warning_refresh_results[result_key] = warnings
            self._warning_refresh_index += 1
            self._update_warnings_analysis_progress(
                self._warning_refresh_index,
                self.tr("Analyzing warnings... ({current}/{total})").format(
                    current=self._warning_refresh_index,
                    total=total_steps,
                ),
            )
            QTimer.singleShot(1, self._run_next_warning_refresh_step)

        def on_error(exc: Exception) -> None:
            self._handle_warning_refresh_error(exc)

        # Virtual-field sync mutates layers and must stay on the Qt main thread.
        if result_key is None:
            try:
                on_success(runner())
            except Exception as exc:
                on_error(exc)
            return

        self._dispatch_warning_detection_step(status_label, runner, on_success, on_error)

    def _finalize_warning_refresh(self) -> None:
        """Apply collected warnings and rebuild the summary panel on the next event-loop tick."""
        try:
            for result_key, warnings in self._warning_refresh_results.items():
                setattr(self._summary_data, result_key, warnings)
            for result_key in (
                "duplicate_objects_warnings",
                "skipped_numbers_warnings",
                "out_of_bounds_warnings",
                "distance_warnings",
                "missing_total_station_warnings",
                "duplicate_total_station_identifiers_warnings",
                "height_difference_warnings",
            ):
                if result_key not in self._warning_refresh_results:
                    setattr(self._summary_data, result_key, [])

            QTimer.singleShot(1, self._complete_warning_refresh_ui)
        except Exception as exc:
            self._handle_warning_refresh_error(exc)

    def _complete_warning_refresh_ui(self) -> None:
        """Rebuild summary widgets and clear the busy indicator."""
        try:
            self._recreate_summary_content()

            if self._warning_refresh_show_feedback:
                QMessageBox.information(
                    self,
                    self.tr("Warnings Refreshed"),
                    self.tr("Warnings have been refreshed successfully."),
                )
        except Exception as exc:
            self._handle_warning_refresh_error(exc)
        finally:
            self._set_warnings_analysis_busy(False)

    def _handle_warning_refresh_error(self, error: Exception) -> None:
        """Abort incremental refresh and surface errors to the user."""
        print(f"Error refreshing warnings: {error}")
        import traceback
        traceback.print_exc()
        self._set_warnings_analysis_busy(False)
        if self._warning_refresh_show_feedback:
            QMessageBox.critical(
                self,
                self.tr("Refresh Error"),
                self.tr("An error occurred while refreshing warnings: {error}").format(
                    error=str(error)
                ),
            )

    def _load_detector_service(self, module_name: str, class_name: str):
        """Import a detector service class from the services package."""
        try:
            module = __import__(f"services.{module_name}", fromlist=[class_name])
        except ImportError:
            import sys
            import os

            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            module = __import__(f"services.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)

    def _detect_duplicate_objects_warnings(self) -> List[Any]:
        detector = DuplicateObjectsDetectorService(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_duplicate_objects()

    def _detect_skipped_numbers_warnings(self) -> List[Any]:
        detector = SkippedNumbersDetectorService(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_skipped_numbers()

    def _detect_out_of_bounds_warnings(self) -> List[Any]:
        service_class = self._load_detector_service(
            "out_of_bounds_detector_service",
            "OutOfBoundsDetectorService",
        )
        detector = service_class(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_out_of_bounds_features()

    def _detect_distance_warnings(self) -> List[Any]:
        service_class = self._load_detector_service(
            "distance_detector_service",
            "DistanceDetectorService",
        )
        detector = service_class(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_distance_warnings()

    def _detect_missing_total_station_warnings(self) -> List[Any]:
        service_class = self._load_detector_service(
            "missing_total_station_detector_service",
            "MissingTotalStationDetectorService",
        )
        detector = service_class(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_missing_total_station_warnings()

    def _detect_duplicate_total_station_identifiers_warnings(self) -> List[Any]:
        service_class = self._load_detector_service(
            "duplicate_total_station_identifiers_detector_service",
            "DuplicateTotalStationIdentifiersDetectorService",
        )
        detector = service_class(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_duplicate_identifiers_warnings()

    def _detect_height_difference_warnings(self) -> List[Any]:
        service_class = self._load_detector_service(
            "height_difference_detector_service",
            "HeightDifferenceDetectorService",
        )
        detector = service_class(
            settings_manager=self._settings_manager,
            layer_service=self._layer_service,
        )
        return detector.detect_height_difference_warnings()
    
    def _recreate_summary_content(self) -> None:
        """Recreate the summary content to show updated warnings."""
        try:
            # Get the main widget and its layout
            main_widget = self.widget()
            if not main_widget:
                print("No main widget found")
                return
                
            main_layout = main_widget.layout()
            if not main_layout:
                print("No main layout found")
                return
            
            # Find and remove the existing scroll area (should be after title, before buttons)
            scroll_area_index = None
            for i in range(main_layout.count()):
                item = main_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QtWidgets.QScrollArea):
                    scroll_area = item.widget()
                    main_layout.removeWidget(scroll_area)
                    scroll_area.deleteLater()
                    scroll_area_index = i
                    break
            
            if scroll_area_index is None:
                print("No scroll area found to recreate")
                return
            
            # Recreate the summary content in the correct position (after title, before buttons)
            # Insert at the same index where the old scroll area was
            self._create_summary_content_at_index(main_layout, scroll_area_index)
            
            # Force a layout update
            main_widget.updateGeometry()
        
        except Exception as e:
            print(f"Error recreating summary content: {e}")
            import traceback
            traceback.print_exc()

    def _create_summary_content_at_index(self, parent_layout: QtWidgets.QVBoxLayout, insert_index: int) -> None:
        """Create the summary content section and insert at a specific index."""
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(_scroll_bar_as_needed_policy())
        scroll_area.setVerticalScrollBarPolicy(_scroll_bar_as_needed_policy())
        
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)

        print(
            f"[DEBUG][UI] Summary UI: out_of_bounds_warnings count="
            f"{len(getattr(self._summary_data, 'out_of_bounds_warnings', None) or [])}"
        )
        self._append_out_of_bounds_warnings_section(content_layout)

        # CSV Points section
        if self._summary_data.csv_points_count > 0:
            csv_group = self._create_csv_section()
            content_layout.addWidget(csv_group)
        
        # Features section
        if self._summary_data.features_count > 0:
            features_group = self._create_features_section()
            content_layout.addWidget(features_group)
        
        # Objects section
        if self._summary_data.objects_count > 0:
            objects_group = self._create_objects_section()
            content_layout.addWidget(objects_group)
        
        # Small Finds section
        if self._summary_data.small_finds_count > 0:
            small_finds_group = self._create_small_finds_section()
            content_layout.addWidget(small_finds_group)

        # Distance warnings section
        if hasattr(self._summary_data, 'distance_warnings') and self._summary_data.distance_warnings:
            print(f"[DEBUG][UI] Displaying {len(self._summary_data.distance_warnings)} distance warnings")
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Distance Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #DC143C;")
            warnings_layout.addWidget(warnings_label)
            for i, warning in enumerate(self._summary_data.distance_warnings):
                warning_item_layout = QtWidgets.QHBoxLayout()
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                else:
                    warning_text = str(warning)
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #DC143C; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                if hasattr(warning, 'message') and self._iface:
                    button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                    button.setStyleSheet("background-color: #DC143C; color: white; border: none; padding: 5px; border-radius: 3px;")
                    button.clicked.connect(lambda checked, w=warning: self._open_both_filtered_attribute_tables(w))
                    warning_item_layout.addWidget(button)
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            content_layout.addLayout(warnings_layout)
            print("[DEBUG][UI] Added distance warnings layout to content_layout")

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        parent_layout.insertWidget(insert_index, scroll_area)
    
    def _copy_temporary_to_definitive_layers(self) -> None:
        """
        Synchronously copy all temporary layers (used by unit tests).

        Production validation uses :meth:`_start_async_validation` instead.
        """
        from qgis.core import QgsProject

        project = QgsProject.instance()
        jobs = build_layer_copy_jobs(project.mapLayers(), self._get_definitive_layer_id)
        self._validation_jobs = jobs
        copied_counts: Dict[str, int] = {}
        missing_configurations = self._collect_missing_layer_configurations()

        for job in jobs:
            load_job_source_features(job)
            while job.feature_index < job.feature_count:
                batch_result = self._feature_copier.copy_features_batch(
                    source_features=job.source_features,
                    target_layer=job.target_layer,
                    start_index=job.feature_index,
                    field_mapping=job.field_mapping,
                )
                job.feature_index = batch_result.next_index
                job.copied_count += batch_result.copied_count
                job.added_feature_ids.extend(batch_result.added_feature_ids)

            self._feature_copier.select_copied_features(
                job.target_layer,
                job.added_feature_ids,
            )
            copied_counts[job.temp_layer_name] = job.copied_count
            print(
                f"Copied {job.copied_count} features from "
                f"'{job.temp_layer_name}' to '{job.target_layer.name()}'"
            )

        if copied_counts:
            success_message = self.tr("Features copied successfully!\n\n")
            for layer_name, count in copied_counts.items():
                success_message += f"• {layer_name}: {count} features\n"
            success_message += f"\n{self.tr('The definitive layers are now in edit mode.')}\n"
            success_message += (
                f"{self.tr('The newly copied features are selected for easy identification.')}\n"
            )
            success_message += f"{self.tr('Please review the copied features and:')}\n"
            success_message += f"• {self.tr('Save changes if you want to keep them')}\n"
            success_message += f"• {self.tr('Cancel changes if you want to discard them')}"

            QMessageBox.information(
                self,
                self.tr("Validation Complete"),
                success_message,
            )
        elif missing_configurations:
            QMessageBox.information(
                self,
                self.tr("No Layers to Validate"),
                self.tr(
                    "Note: Some layers could not be copied because definitive layers "
                    "are not configured.\n\n"
                    "Please configure the definitive layers in the settings dialog first."
                ),
            )
    
    def _delete_temporary_layers(self) -> None:
        """Delete temporary layers after features have been copied to definitive layers."""
        try:
            from qgis.core import QgsProject
            
            project = QgsProject.instance()
            
            # Define temporary layer names to delete
            temporary_layer_names = ["New Objects", "New Features", "New Small Finds", "Imported_CSV_Points"]
            
            layers_to_remove = []
            
            # Find temporary layers
            for layer in project.mapLayers().values():
                if layer.name() in temporary_layer_names:
                    layers_to_remove.append(layer.id())
                    print(f"Found temporary layer to delete: {layer.name()}")
            
            # Remove temporary layers from project
            for layer_id in layers_to_remove:
                project.removeMapLayer(layer_id)
                print(f"Deleted temporary layer: {layer_id}")
            
            if layers_to_remove:
                print(f"Successfully deleted {len(layers_to_remove)} temporary layer(s)")
            else:
                print("No temporary layers found to delete")
                
        except Exception as e:
            print(f"Error deleting temporary layers: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise the exception - this is not critical for the validation process
    
    def _archive_imported_data(self) -> None:
        """Archive imported files and folders after successful validation."""
        try:
            # Archive CSV files if CSV import service is available
            if self._csv_import_service:
                self._csv_import_service.archive_last_imported_files()
                print("Archived CSV files after validation")
            
            # Archive field projects if field project import service is available
            if self._field_project_import_service:
                self._field_project_import_service.archive_last_imported_projects()
                print("Archived field projects after validation")
                
        except Exception as e:
            print(f"Error archiving imported data: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise the exception - this is not critical for the validation process
    
    def _get_definitive_layer_id(self, layer_setting_key: str, default: Any = "") -> Optional[str]:
        """Get the definitive layer ID from settings."""
        try:
            if self._settings_manager:
                # Use the settings manager to get the layer ID
                layer_id = self._settings_manager.get_value(layer_setting_key, default)
                return layer_id if layer_id else None
            else:
                # Fallback to direct QSettings access if no settings manager is provided
                from qgis.PyQt.QtCore import QSettings
                settings = QSettings()
                settings.beginGroup('ArcheoSync')
                layer_id = settings.value(layer_setting_key, "")
                settings.endGroup()
                return layer_id if layer_id else None
                
        except Exception as e:
            print(f"Error getting definitive layer ID for {layer_setting_key}: {e}")
            return None
    
    def _copy_features_between_layers(self, source_layer, target_layer) -> int:
        """Copy all features between two layers (unit-test helper)."""
        source_features = list(source_layer.getFeatures())
        field_mapping = self._feature_copier.build_field_mapping(
            source_features[0].fields() if source_features else source_layer.fields(),
            target_layer,
        )
        added_ids: List[int] = []
        copied_count = 0
        start_index = 0

        while start_index < len(source_features):
            batch_result = self._feature_copier.copy_features_batch(
                source_features=source_features,
                target_layer=target_layer,
                start_index=start_index,
                field_mapping=field_mapping,
            )
            start_index = batch_result.next_index
            copied_count += batch_result.copied_count
            added_ids.extend(batch_result.added_feature_ids)

        self._feature_copier.select_copied_features(target_layer, added_ids)
        return copied_count

    def _create_feature_with_target_structure(self, source_feature, target_layer):
        """
        Create a new feature with the target layer's field structure.

        Delegates to :class:`ImportFeatureCopier` so validation and tests share the
        same default-value replay logic.
        """
        try:
            copier = self._feature_copier
        except (AttributeError, RuntimeError):
            copier = ImportFeatureCopier()
        field_mapping = copier.build_field_mapping(
            source_feature.fields(),
            target_layer,
        )
        return copier.create_feature_with_target_structure(
            source_feature,
            target_layer,
            field_mapping,
        )

    def _apply_default_values_from_target_layer(self, target_layer, feature) -> None:
        """
        Apply target-layer default expressions for missing feature attributes.

        Kept for compatibility with callers that already built a feature manually.
        Prefer :meth:`_create_feature_with_target_structure`, which delegates to
        ``QgsVectorLayerUtils.createFeature`` so QGIS applies defaults the same way
        as interactive digitizing.
        """
        try:
            if not hasattr(target_layer, "defaultValueDefinition") or not hasattr(target_layer, "defaultValue"):
                return

            context = None
            if hasattr(target_layer, "createExpressionContext"):
                try:
                    context = target_layer.createExpressionContext()
                    if context is not None:
                        context.setFeature(feature)
                except Exception:
                    context = None

            fields = target_layer.fields()
            for field_index in range(fields.count()):
                field_name = fields.at(field_index).name()
                current_value = feature[field_name]
                if not self._is_missing_attribute_value(current_value):
                    continue

                default_definition = target_layer.defaultValueDefinition(field_index)
                expression = ""
                if default_definition and hasattr(default_definition, "expression"):
                    expression = (default_definition.expression() or "").strip()
                if not expression:
                    continue

                if default_definition and hasattr(default_definition, "applyOnUpdate"):
                    try:
                        if default_definition.applyOnUpdate():
                            continue
                    except Exception:
                        pass

                computed_default = None
                try:
                    if context is not None:
                        computed_default = target_layer.defaultValue(field_index, feature, context)
                    else:
                        computed_default = target_layer.defaultValue(field_index, feature)
                except TypeError:
                    computed_default = target_layer.defaultValue(field_index)
                except Exception:
                    computed_default = None

                if self._is_missing_attribute_value(computed_default):
                    continue

                feature[field_name] = computed_default
        except Exception as e:
            print(f"Warning: could not apply layer default values: {e}")

    @staticmethod
    def _is_missing_attribute_value(value: Any) -> bool:
        """Return True when a field value should be considered empty for default injection."""
        return ImportFeatureCopier.is_missing_attribute_value(value)

    def _open_filtered_attribute_table(self, warning_data: WarningData) -> None:
        """
        Open the attribute table for the specified layer and select the concerned entities.
        Args:
            warning_data: Warning data containing layer and filter information
        """
        if not self._iface:
            return
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            # Find the layer by name
            target_layer = None
            for layer in project.mapLayers().values():
                if layer.name() == warning_data.layer_name:
                    target_layer = layer
                    break
            if not target_layer:
                print(f"Layer '{warning_data.layer_name}' not found in project")
                return
            
            # Apply the filter expression
            print(f"[DEBUG] Applying filter expression: {warning_data.filter_expression}")
            print(f"[DEBUG] Layer name: {warning_data.layer_name}")
            
            # Get the layer
            layer = self._layer_service.get_layer_by_name(warning_data.layer_name)
            if not layer:
                print(f"[DEBUG] ERROR: Layer '{warning_data.layer_name}' not found!")
                return
            
            print(f"[DEBUG] Found layer: {layer.name()}, feature count: {layer.featureCount()}")
            
            # Clear any existing selection
            layer.removeSelection()
            
            # Select the concerned entities
            print(f"[DEBUG] Selecting features with expression: {warning_data.filter_expression}")
            selected_count = layer.selectByExpression(warning_data.filter_expression)
            print(f"[DEBUG] Selected {selected_count} features")
            
            # Get the selected features to verify
            selected_features = layer.selectedFeatures()
            print(f"[DEBUG] Selected feature IDs: {[f.id() for f in selected_features]}")
            
            # Set the layer as active
            self._iface.setActiveLayer(layer)
            
            # Open the attribute table
            self._iface.actionOpenTable().trigger()
            
            # Show a message to inform the user about the selection
            QMessageBox.information(
                self,
                self.tr("Attribute Table Opened"),
                self.tr(f"Attribute table for '{warning_data.layer_name}' has been opened with selected entities matching:\n{warning_data.filter_expression}")
            )
        except Exception as e:
            print(f"Error opening attribute table with selection: {e}")
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr(f"Could not open attribute table: {str(e)}")
            )

    def _open_both_filtered_attribute_tables(self, warning_data: WarningData) -> None:
        """
        Open the attribute tables for both layers and select the concerned entities.
        """
        if not self._iface:
            return
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            
            for layer_name, filter_expr in [
                (warning_data.layer_name, warning_data.filter_expression),
                (warning_data.second_layer_name, warning_data.second_filter_expression)
            ]:
                if not layer_name or not filter_expr:
                    continue
                target_layer = None
                for layer in project.mapLayers().values():
                    if layer.name() == layer_name:
                        target_layer = layer
                        break
                if not target_layer:
                    print(f"Layer '{layer_name}' not found in project")
                    continue
                
                # Clear any existing selection
                target_layer.removeSelection()
                
                # Select the concerned entities
                target_layer.selectByExpression(filter_expr)
                
                # Set the layer as active
                self._iface.setActiveLayer(target_layer)
                
                # Open the attribute table
                self._iface.actionOpenTable().trigger()
            
            QMessageBox.information(
                self,
                self.tr("Attribute Tables Opened"),
                self.tr(f"Attribute tables for '{warning_data.layer_name}' and '{warning_data.second_layer_name}' have been opened with selected entities.")
            )
        except Exception as e:
            print(f"Error opening both attribute tables with selection: {e}")
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr(f"Could not open both attribute tables: {str(e)}")
            )


# Keep the old dialog class for backward compatibility
class ImportSummaryDialog(ImportSummaryDockWidget):
    """
    Import Summary dialog for ArcheoSync plugin (legacy).
    
    This is kept for backward compatibility. New code should use ImportSummaryDockWidget.
    Optional keyword ``translation_service`` is accepted for compatibility, stored as
    ``_translation_service``, and not forwarded to ``ImportSummaryDockWidget``.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the import summary dialog (legacy)."""
        translation_service = kwargs.pop("translation_service", None)
        super().__init__(*args, **kwargs)
        self._translation_service = translation_service 