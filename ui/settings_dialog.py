"""
Settings dialog for ArcheoSync plugin.

This module provides a clean, testable settings dialog that follows SOLID principles
and uses dependency injection for better separation of concerns. The dialog is
responsible only for UI presentation and user interaction, delegating all business
logic to injected services.

Key Features:
- Dependency injection for all services
- Clean separation of UI and business logic
- Comprehensive validation with user feedback
- Revert functionality for cancelled changes
- Responsive UI with conditional visibility

Architecture Benefits:
- Single Responsibility: Only handles UI presentation
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: New services can be injected easily

Usage:
    settings_manager = QGISSettingsManager()
    file_system_service = QGISFileSystemService()
    validator = ArcheoSyncConfigurationValidator(file_system_service)
    
    dialog = SettingsDialog(
        settings_manager=settings_manager,
        file_system_service=file_system_service,
        configuration_validator=validator,
        parent=parent_widget
    )
    
    if dialog.exec_() == QDialog.Accepted:
        # Settings were saved successfully
        pass

The dialog provides:
- Intuitive folder selection with browse buttons
- Real-time validation feedback
- Clear error messages
- Consistent user experience
- Proper state management
"""

from typing import Optional, Dict, Any
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt

try:
    from ..core.interfaces import ISettingsManager, IFileSystemService, IConfigurationValidator
except ImportError:
    from core.interfaces import ISettingsManager, IFileSystemService, IConfigurationValidator


class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog for ArcheoSync plugin.
    
    This dialog provides a clean interface for managing plugin settings,
    following the Single Responsibility Principle by focusing only on UI presentation
    and delegating business logic to injected services.
    """
    
    def __init__(self, 
                 settings_manager: ISettingsManager,
                 file_system_service: IFileSystemService,
                 configuration_validator: IConfigurationValidator,
                 parent=None):
        """
        Initialize the settings dialog.
        
        Args:
            settings_manager: Service for managing settings
            file_system_service: Service for file system operations
            configuration_validator: Service for validating configuration
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._settings_manager = settings_manager
        self._file_system_service = file_system_service
        self._configuration_validator = configuration_validator
        
        # Store original values for cancel functionality
        self._original_values: Dict[str, Any] = {}
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
        self._load_settings()
        self._update_ui_state()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle("ArcheoSync Settings")
        self.setGeometry(0, 0, 600, 450)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel("ArcheoSync Plugin Settings")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Add settings section
        self._create_settings_section(main_layout)
        
        # Add button box
        self._create_button_box(main_layout)
    
    def _create_settings_section(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the settings configuration section."""
        settings_group = QtWidgets.QGroupBox("Configuration Settings")
        settings_layout = QtWidgets.QFormLayout(settings_group)
        
        # Field projects destination
        self._field_projects_widget = self._create_folder_selector(
            "Select destination folder for new field projects..."
        )
        settings_layout.addRow("Field Projects Destination:", self._field_projects_widget)
        
        # Total station CSV files
        self._total_station_widget = self._create_folder_selector(
            "Select folder containing total station CSV files..."
        )
        settings_layout.addRow("Total Station CSV Files:", self._total_station_widget)
        
        # Completed field projects
        self._completed_projects_widget = self._create_folder_selector(
            "Select folder containing completed field projects..."
        )
        settings_layout.addRow("Completed Field Projects:", self._completed_projects_widget)
        
        # QField integration
        self._qfield_checkbox = QtWidgets.QCheckBox("Use QField for field data collection")
        settings_layout.addRow("QField Integration:", self._qfield_checkbox)
        
        # Template QGIS project (conditional)
        self._template_project_widget = self._create_folder_selector(
            "Select folder containing template QGIS project..."
        )
        self._template_project_label = QtWidgets.QLabel("Template QGIS Project:")
        settings_layout.addRow(self._template_project_label, self._template_project_widget)
        
        parent_layout.addWidget(settings_group)
    
    def _create_folder_selector(self, placeholder: str) -> QtWidgets.QWidget:
        """Create a folder selection widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Input field
        input_field = QtWidgets.QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setReadOnly(True)
        
        # Browse button
        browse_button = QtWidgets.QPushButton("Browse...")
        
        layout.addWidget(input_field)
        layout.addWidget(browse_button)
        
        # Store references
        widget.input_field = input_field
        widget.browse_button = browse_button
        
        return widget
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self
        )
        parent_layout.addWidget(self._button_box)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Button box connections
        self._button_box.accepted.connect(self._save_and_accept)
        self._button_box.rejected.connect(self._reject)
        
        # Browse button connections
        self._field_projects_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._field_projects_widget.input_field, 
                                      "Select Destination Folder for New Field Projects")
        )
        self._total_station_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._total_station_widget.input_field,
                                      "Select Folder for Total Station CSV Files")
        )
        self._completed_projects_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._completed_projects_widget.input_field,
                                      "Select Folder for Completed Field Projects")
        )
        self._template_project_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._template_project_widget.input_field,
                                      "Select Folder for Template QGIS Project")
        )
        
        # QField checkbox connection
        self._qfield_checkbox.stateChanged.connect(self._update_ui_state)
    
    def _browse_folder(self, input_field: QtWidgets.QLineEdit, title: str) -> None:
        """Browse for a folder and update the input field."""
        folder_path = self._file_system_service.select_directory(
            title, 
            input_field.text() if input_field.text() else None
        )
        
        if folder_path:
            input_field.setText(folder_path)
    
    def _update_ui_state(self) -> None:
        """Update UI state based on current settings."""
        use_qfield = self._qfield_checkbox.isChecked()
        
        # Show/hide template project widgets
        should_show_template = not use_qfield
        self._template_project_label.setVisible(should_show_template)
        self._template_project_widget.setVisible(should_show_template)
    
    def _load_settings(self) -> None:
        """Load settings into the UI."""
        try:
            # Load field projects folder
            field_projects_path = self._settings_manager.get_value('field_projects_folder', '')
            self._field_projects_widget.input_field.setText(field_projects_path)
            
            # Load total station folder
            total_station_path = self._settings_manager.get_value('total_station_folder', '')
            self._total_station_widget.input_field.setText(total_station_path)
            
            # Load completed projects folder
            completed_projects_path = self._settings_manager.get_value('completed_projects_folder', '')
            self._completed_projects_widget.input_field.setText(completed_projects_path)
            
            # Load QField setting
            use_qfield = self._settings_manager.get_value('use_qfield', False)
            self._qfield_checkbox.setChecked(bool(use_qfield))
            
            # Load template project folder
            template_project_path = self._settings_manager.get_value('template_project_folder', '')
            self._template_project_widget.input_field.setText(template_project_path)
            
            # Store original values
            self._original_values = {
                'field_projects_folder': field_projects_path,
                'total_station_folder': total_station_path,
                'completed_projects_folder': completed_projects_path,
                'use_qfield': bool(use_qfield),
                'template_project_folder': template_project_path
            }
            
        except Exception as e:
            self._show_error("Settings Error", f"Failed to load settings: {str(e)}")
    
    def _save_and_accept(self) -> None:
        """Save settings and accept the dialog."""
        try:
            # Collect current values
            current_settings = {
                'field_projects_folder': self._field_projects_widget.input_field.text(),
                'total_station_folder': self._total_station_widget.input_field.text(),
                'completed_projects_folder': self._completed_projects_widget.input_field.text(),
                'use_qfield': self._qfield_checkbox.isChecked(),
                'template_project_folder': self._template_project_widget.input_field.text()
            }
            
            # Validate settings
            validation_results = self._configuration_validator.validate_all_settings(current_settings)
            
            if self._configuration_validator.has_validation_errors(validation_results):
                errors = self._configuration_validator.get_all_errors(validation_results)
                error_message = "\n".join(errors)
                self._show_error("Validation Error", f"Please fix the following issues:\n\n{error_message}")
                return
            
            # Save settings
            for key, value in current_settings.items():
                self._settings_manager.set_value(key, value)
            
            self.accept()
            
        except Exception as e:
            self._show_error("Settings Error", f"Failed to save settings: {str(e)}")
    
    def _reject(self) -> None:
        """Handle dialog rejection by reverting to original values."""
        try:
            # Revert UI to original values
            self._field_projects_widget.input_field.setText(
                self._original_values.get('field_projects_folder', '')
            )
            self._total_station_widget.input_field.setText(
                self._original_values.get('total_station_folder', '')
            )
            self._completed_projects_widget.input_field.setText(
                self._original_values.get('completed_projects_folder', '')
            )
            self._qfield_checkbox.setChecked(
                self._original_values.get('use_qfield', False)
            )
            self._template_project_widget.input_field.setText(
                self._original_values.get('template_project_folder', '')
            )
            
            # Revert settings in manager
            for key, value in self._original_values.items():
                self._settings_manager.set_value(key, value)
                
        except Exception as e:
            self._show_error("Settings Error", f"Failed to revert settings: {str(e)}")
        
        super().reject()
    
    def _show_error(self, title: str, message: str) -> None:
        """Show an error message to the user."""
        QtWidgets.QMessageBox.critical(self, title, message) 