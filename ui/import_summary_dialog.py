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
    iface.addDockWidget(Qt.RightDockWidgetArea, dock_widget)
"""

from typing import Optional, List, Dict, Any, Union
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox, QDockWidget
from qgis.PyQt.QtCore import Qt

try:
    from ..core.interfaces import ISettingsManager, ILayerService, ITranslationService
    from ..core.data_structures import WarningData, ImportSummaryData
except ImportError:
    from core.interfaces import ISettingsManager, ILayerService, ITranslationService
    from core.data_structures import WarningData, ImportSummaryData

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
                 translation_service=None,
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
            translation_service: Translation service for internationalization
            parent: Parent widget for the dock widget
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._summary_data = summary_data
        self._iface = iface
        self._settings_manager = settings_manager
        self._csv_import_service = csv_import_service
        self._field_project_import_service = field_project_import_service
        self._layer_service = layer_service
        self._translation_service = translation_service
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle(self.tr("Import Summary"))
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # Create the main widget
        main_widget = QtWidgets.QWidget()
        self.setWidget(main_widget)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        
        # Add title
        title_label = QtWidgets.QLabel(self.tr("Import Summary"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
        main_layout.addWidget(title_label)
        
        # Add summary content
        self._create_summary_content(main_layout)
        
        # Add buttons
        self._create_buttons(main_layout)
        
        # Set size
        self.resize(400, 500)
    
    def _create_summary_content(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the summary content section."""
        # Create scroll area for content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create content widget
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        
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
        else:
            print(f"Debug: No skipped numbers warnings found. hasattr: {hasattr(self._summary_data, 'skipped_numbers_warnings')}, warnings: {getattr(self._summary_data, 'skipped_numbers_warnings', None)}")
        
        # Out-of-bounds warnings
        print(f"[DEBUG] Checking out-of-bounds warnings. hasattr: {hasattr(self._summary_data, 'out_of_bounds_warnings')}, warnings: {getattr(self._summary_data, 'out_of_bounds_warnings', None)}")
        if hasattr(self._summary_data, 'out_of_bounds_warnings') and self._summary_data.out_of_bounds_warnings:
            print(f"[DEBUG] Displaying {len(self._summary_data.out_of_bounds_warnings)} out-of-bounds warnings")
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Out-of-Bounds Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #DC143C;")
            warnings_layout.addWidget(warnings_label)
            
            for i, warning in enumerate(self._summary_data.out_of_bounds_warnings):
                print(f"[DEBUG] Processing out-of-bounds warning {i+1}: {warning}")
                print(f"[DEBUG] Warning type: {type(warning)}")
                print(f"[DEBUG] Warning attributes: {dir(warning)}")
                
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text - check if it has the expected attributes
                if hasattr(warning, 'message'):
                    warning_text = warning.message
                    print(f"[DEBUG] Using warning.message: {warning_text}")
                else:
                    warning_text = str(warning)
                    print(f"[DEBUG] Using str(warning): {warning_text}")
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #DC143C; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if hasattr(warning, 'message') and self._iface:
                    button = QtWidgets.QPushButton(self.tr("Select and Show Entities"))
                    button.setStyleSheet("background-color: #DC143C; color: white; border: none; padding: 5px; border-radius: 3px;")
                    button.clicked.connect(lambda checked, w=warning: self._open_filtered_attribute_table(w))
                    warning_item_layout.addWidget(button)
                
                warning_item_layout.addStretch()
                warnings_layout.addLayout(warning_item_layout)
            
            layout.addLayout(warnings_layout)
        else:
            print(f"[DEBUG] No out-of-bounds warnings to display")
            print(f"[DEBUG] Summary data attributes: {dir(self._summary_data)}")
            print(f"[DEBUG] Summary data dict: {self._summary_data.__dict__}")
        
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
    
    def _handle_validate(self) -> None:
        """Handle the validate button click - copy features from temporary to definitive layers."""
        try:
            # Check for warnings and ask for confirmation if any exist
            if self._has_warnings():
                if not self._confirm_validation_with_warnings():
                    return  # User cancelled validation
            
            # Copy features from temporary layers to definitive layers
            self._copy_temporary_to_definitive_layers()
            
            # Delete temporary layers after successful copying
            self._delete_temporary_layers()
            
            # Archive imported files and folders after successful validation
            self._archive_imported_data()
            
            # Delete the dock widget from the interface
            if self._iface:
                self._iface.removeDockWidget(self)
            
            # Delete the widget
            self.deleteLater()
            
        except Exception as e:
            print(f"Error during validation: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message to user
            QMessageBox.critical(
                self,
                self.tr("Validation Error"),
                self.tr(f"An error occurred during validation: {str(e)}")
            )
    
    def _has_warnings(self) -> bool:
        """Check if there are any warnings present in the summary data."""
        duplicate_warnings = getattr(self._summary_data, 'duplicate_objects_warnings', [])
        skipped_warnings = getattr(self._summary_data, 'skipped_numbers_warnings', [])
        out_of_bounds_warnings = getattr(self._summary_data, 'out_of_bounds_warnings', [])
        
        return len(duplicate_warnings) > 0 or len(skipped_warnings) > 0 or len(out_of_bounds_warnings) > 0
    
    def _confirm_validation_with_warnings(self) -> bool:
        """Show confirmation dialog when warnings are present."""
        duplicate_count = len(getattr(self._summary_data, 'duplicate_objects_warnings', []))
        skipped_count = len(getattr(self._summary_data, 'skipped_numbers_warnings', []))
        out_of_bounds_count = len(getattr(self._summary_data, 'out_of_bounds_warnings', []))
        
        # Build warning summary message
        warning_summary = []
        if duplicate_count > 0:
            warning_summary.append(self.tr(f"• {duplicate_count} duplicate object warning(s)"))
        if skipped_count > 0:
            warning_summary.append(self.tr(f"• {skipped_count} skipped numbers warning(s)"))
        if out_of_bounds_count > 0:
            warning_summary.append(self.tr(f"• {out_of_bounds_count} out-of-bounds warning(s)"))
        
        warning_message = "\n".join(warning_summary)
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            self.tr("Validation with Warnings"),
            self.tr(f"The following warnings have been detected:\n\n{warning_message}\n\nDo you want to proceed with validation anyway?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        return reply == QMessageBox.Yes
    
    def _handle_cancel(self) -> None:
        """Handle the cancel button click - delete temporary layers and delete the widget."""
        try:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                self.tr("Cancel Import"),
                self.tr("Are you sure you want to cancel the import? This will delete all temporary import layers and cannot be undone."),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
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
    
    def _handle_refresh_warnings(self) -> None:
        """Handle the refresh warnings button click - re-run detection services to refresh warnings."""
        try:
            print("Debug: Starting refresh warnings")
            # Check if detection services are available
            if DuplicateObjectsDetectorService is None or SkippedNumbersDetectorService is None:
                print("Debug: Detection services not available")
                QMessageBox.warning(
                    self,
                    self.tr("Services Not Available"),
                    self.tr("Detection services are not available. Please ensure the plugin is properly installed.")
                )
                return
            
            # Re-run duplicate objects detection if objects were imported
            duplicate_objects_warnings = []
            if self._summary_data.objects_count > 0:
                print(f"Debug: Running duplicate detection for {self._summary_data.objects_count} objects")
                detector = DuplicateObjectsDetectorService(
                    settings_manager=self._settings_manager,
                    layer_service=self._layer_service,
                    translation_service=self._translation_service
                )
                duplicate_objects_warnings = detector.detect_duplicate_objects()
                print(f"Debug: Detected {len(duplicate_objects_warnings)} duplicate warnings")
                for warning in duplicate_objects_warnings:
                    print(f"Debug: Duplicate warning: {warning}")
            
            # Re-run skipped numbers detection if objects were imported
            skipped_numbers_warnings = []
            if self._summary_data.objects_count > 0:
                print(f"Debug: Running skipped numbers detection for {self._summary_data.objects_count} objects")
                skipped_detector = SkippedNumbersDetectorService(
                    settings_manager=self._settings_manager,
                    layer_service=self._layer_service,
                    translation_service=self._translation_service
                )
                skipped_numbers_warnings = skipped_detector.detect_skipped_numbers()
                print(f"Debug: Detected {len(skipped_numbers_warnings)} skipped warnings")
                for warning in skipped_numbers_warnings:
                    print(f"Debug: Skipped warning: {warning}")
            
            # Re-run out-of-bounds detection if any features were imported
            out_of_bounds_warnings = []
            if (self._summary_data.objects_count > 0 or 
                self._summary_data.features_count > 0 or 
                self._summary_data.small_finds_count > 0):
                print(f"[DEBUG] Running out-of-bounds detection")
                try:
                    from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
                except ImportError:
                    # Fallback for relative import
                    import sys
                    import os
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from services.out_of_bounds_detector_service import OutOfBoundsDetectorService
                
                out_of_bounds_detector = OutOfBoundsDetectorService(
                    settings_manager=self._settings_manager,
                    layer_service=self._layer_service,
                    translation_service=self._translation_service
                )
                out_of_bounds_warnings = out_of_bounds_detector.detect_out_of_bounds_features()
                print(f"[DEBUG] Detected {len(out_of_bounds_warnings)} out-of-bounds warnings")
                for i, warning in enumerate(out_of_bounds_warnings):
                    print(f"[DEBUG] Out-of-bounds warning {i+1}: {warning}")
                    if hasattr(warning, 'message'):
                        print(f"[DEBUG]   Message: {warning.message}")
            else:
                print(f"[DEBUG] Skipping out-of-bounds detection - no features imported")
            
            # Update the summary data with new warnings
            print(f"[DEBUG] Updating summary data with {len(duplicate_objects_warnings)} duplicates, {len(skipped_numbers_warnings)} skipped, and {len(out_of_bounds_warnings)} out-of-bounds")
            self._summary_data.duplicate_objects_warnings = duplicate_objects_warnings
            self._summary_data.skipped_numbers_warnings = skipped_numbers_warnings
            self._summary_data.out_of_bounds_warnings = out_of_bounds_warnings
            print(f"[DEBUG] Summary data now has {len(self._summary_data.duplicate_objects_warnings)} duplicates, {len(self._summary_data.skipped_numbers_warnings)} skipped, and {len(self._summary_data.out_of_bounds_warnings)} out-of-bounds")
            
            # Recreate the UI to show updated warnings
            print("[DEBUG] Recreating summary content")
            self._recreate_summary_content()
            
            # Show success message
            QMessageBox.information(
                self,
                self.tr("Warnings Refreshed"),
                self.tr("Warnings have been refreshed successfully.")
            )
            
        except Exception as e:
            print(f"Error refreshing warnings: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message to user
            QMessageBox.critical(
                self,
                self.tr("Refresh Error"),
                self.tr(f"An error occurred while refreshing warnings: {str(e)}")
            )
    
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
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        
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
        
        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        parent_layout.insertWidget(insert_index, scroll_area)
    
    def _copy_temporary_to_definitive_layers(self) -> None:
        """Copy features from temporary layers to definitive layers and keep them in edit mode."""
        try:
            from qgis.core import QgsProject
            
            project = QgsProject.instance()
            
            # Define layer mappings: temporary layer name -> definitive layer setting key
            layer_mappings = {
                "New Objects": "objects_layer",
                "New Features": "features_layer", 
                "New Small Finds": "small_finds_layer"
            }
            
            copied_counts = {}
            missing_configurations = []
            
            for temp_layer_name, definitive_layer_key in layer_mappings.items():
                # Find the temporary layer
                temp_layer = None
                for layer in project.mapLayers().values():
                    if layer.name() == temp_layer_name:
                        temp_layer = layer
                        break
                
                if not temp_layer:
                    print(f"Temporary layer '{temp_layer_name}' not found")
                    continue
                
                # Get the definitive layer ID from settings
                definitive_layer_id = self._get_definitive_layer_id(definitive_layer_key)
                if not definitive_layer_id:
                    print(f"Definitive layer setting '{definitive_layer_key}' not configured")
                    missing_configurations.append(definitive_layer_key)
                    continue
                
                # Find the definitive layer
                definitive_layer = None
                for layer in project.mapLayers().values():
                    if layer.id() == definitive_layer_id:
                        definitive_layer = layer
                        break
                
                if not definitive_layer:
                    print(f"Definitive layer with ID '{definitive_layer_id}' not found")
                    continue
                
                # Copy features from temporary to definitive layer
                copied_count = self._copy_features_between_layers(temp_layer, definitive_layer)
                copied_counts[temp_layer_name] = copied_count
                
                print(f"Copied {copied_count} features from '{temp_layer_name}' to '{definitive_layer.name()}'")
            
            # Show success message with information about edit mode
            if copied_counts:
                success_message = self.tr("Features copied successfully!\n\n")
                for layer_name, count in copied_counts.items():
                    success_message += f"• {layer_name}: {count} features\n"
                success_message += f"\n{self.tr('The definitive layers are now in edit mode.')}\n"
                success_message += f"{self.tr('The newly copied features are selected for easy identification.')}\n"
                success_message += f"{self.tr('Please review the copied features and:')}\n"
                success_message += f"• {self.tr('Save changes if you want to keep them')}\n"
                success_message += f"• {self.tr('Cancel changes if you want to discard them')}"
                
                QMessageBox.information(
                    self,
                    self.tr("Validation Complete"),
                    success_message
                )
            else:
                # Show message if no layers were configured
                if missing_configurations:
                    QMessageBox.information(
                        self,
                        self.tr("No Layers to Validate"),
                        self.tr("Note: Some layers could not be copied because definitive layers are not configured.\n\n"
                               "Please configure the definitive layers in the settings dialog first.")
                    )
            
        except Exception as e:
            print(f"Error copying temporary to definitive layers: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
    
    def _get_definitive_layer_id(self, layer_setting_key: str) -> Optional[str]:
        """Get the definitive layer ID from settings."""
        try:
            if self._settings_manager:
                # Use the settings manager to get the layer ID
                layer_id = self._settings_manager.get_value(layer_setting_key, "")
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
        """Copy features from source layer to target layer and keep target in edit mode without committing."""
        try:
            # Start editing the target layer
            if not target_layer.isEditable():
                target_layer.startEditing()
            
            copied_count = 0
            error_count = 0
            newly_added_features = []  # Track newly added features for selection
            
            # Get all features from source layer
            source_features = list(source_layer.getFeatures())
            
            for i, source_feature in enumerate(source_features):
                try:
                    # Create a new feature with the target layer's field structure
                    new_feature = self._create_feature_with_target_structure(source_feature, target_layer)
                    
                    if new_feature:
                        # Add the feature to the target layer
                        success = target_layer.addFeature(new_feature)
                        if success:
                            copied_count += 1
                            # Store the newly added feature for selection
                            newly_added_features.append(new_feature)
                        else:
                            error_count += 1
                            error_msg = target_layer.lastError()
                            print(f"Failed to add feature {i+1} to {target_layer.name()}: {error_msg}")
                    else:
                        error_count += 1
                        print(f"Failed to create feature {i+1} for {target_layer.name()}")
                        
                except Exception as e:
                    error_count += 1
                    print(f"Error processing feature {i+1}: {e}")
            
            # Select the newly added features
            if newly_added_features:
                try:
                    # Clear any existing selection
                    target_layer.removeSelection()
                    
                    # Select all newly added features
                    for feature in newly_added_features:
                        target_layer.select(feature.id())
                    
                    print(f"Selected {len(newly_added_features)} newly copied features in {target_layer.name()}")
                except Exception as e:
                    print(f"Warning: Could not select newly added features: {e}")
            
            # DO NOT commit changes - keep the layer in edit mode for user review
            # The user can decide whether to save or cancel the changes
            
            # Log summary
            if error_count > 0:
                print(f"Copied {copied_count} features to {target_layer.name()}, {error_count} errors occurred")
                print(f"Layer {target_layer.name()} is in edit mode - review changes and save/cancel as needed")
            else:
                print(f"Successfully copied {copied_count} features to {target_layer.name()}")
                print(f"Layer {target_layer.name()} is in edit mode - review changes and save/cancel as needed")
            
            return copied_count
            
        except Exception as e:
            print(f"Error copying features between layers: {e}")
            # Try to rollback changes if there was an error
            if target_layer.isEditable():
                target_layer.rollBack()
            raise
    
    def _create_feature_with_target_structure(self, source_feature, target_layer):
        """Create a new feature with the target layer's field structure."""
        try:
            from qgis.core import QgsFeature
            
            # Create a new feature with the target layer's fields
            # This automatically assigns a new FID, avoiding conflicts
            new_feature = QgsFeature(target_layer.fields())
            
            # Copy geometry if both layers have geometry
            if source_feature.geometry() and not source_feature.geometry().isEmpty():
                new_feature.setGeometry(source_feature.geometry())
            
            # Copy attributes by field name, excluding FID fields
            for field in target_layer.fields():
                field_name = field.name()
                
                # Skip FID-related fields to avoid conflicts
                if field_name.lower() in ['fid', 'id', 'gid', 'objectid', 'featureid']:
                    continue
                
                source_field_idx = source_feature.fields().indexOf(field_name)
                
                if source_field_idx >= 0:
                    # Field exists in source, copy the value
                    source_value = source_feature[field_name]
                    # Handle NULL values properly
                    if source_value is None or str(source_value).lower() == 'null':
                        new_feature[field_name] = None
                    else:
                        new_feature[field_name] = source_value
                else:
                    # Field doesn't exist in source, set to NULL
                    new_feature[field_name] = None
            
            return new_feature
            
        except Exception as e:
            print(f"Error creating feature with target structure: {e}")
            return None

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
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the import summary dialog (legacy)."""
        super().__init__(*args, **kwargs) 