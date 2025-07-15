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
- QGIS layer selection for recording areas

Architecture Benefits:
- Single Responsibility: Only handles UI presentation
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: New services can be injected easily

Usage:
    settings_manager = QGISSettingsManager()
    file_system_service = QGISFileSystemService()
    layer_service = QGISLayerService()
    validator = ArcheoSyncConfigurationValidator(file_system_service, layer_service)
    
    dialog = SettingsDialog(
        settings_manager=settings_manager,
        file_system_service=file_system_service,
        layer_service=layer_service,
        configuration_validator=validator,
        parent=parent_widget
    )
    
    if dialog.exec_() == QDialog.Accepted:
        # Settings were saved successfully
        pass

The dialog provides:
- Intuitive folder selection with browse buttons
- QGIS layer selection for recording areas
- Real-time validation feedback
- Clear error messages
- Consistent user experience
- Proper state management
"""

from typing import Optional, Dict, Any, List
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt

try:
    from ..core.interfaces import ISettingsManager, IFileSystemService, ILayerService, IConfigurationValidator
except ImportError:
    from core.interfaces import ISettingsManager, IFileSystemService, ILayerService, IConfigurationValidator


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
                 layer_service: ILayerService,
                 configuration_validator: IConfigurationValidator,
                 parent=None):
        """
        Initialize the settings dialog.
        
        Args:
            settings_manager: Service for managing settings
            file_system_service: Service for file system operations
            layer_service: Service for QGIS layer operations
            configuration_validator: Service for validating configuration
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._settings_manager = settings_manager
        self._file_system_service = file_system_service
        self._layer_service = layer_service
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
        self.setGeometry(0, 0, 600, 500)
        
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
        
        # Archive folders section
        archive_label = QtWidgets.QLabel("Archive Folders")
        archive_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        settings_layout.addRow(archive_label)
        
        # CSV archive folder
        self._csv_archive_widget = self._create_folder_selector(
            "Select folder to archive imported CSV files..."
        )
        settings_layout.addRow("CSV Archive Folder:", self._csv_archive_widget)
        

        
        # Recording areas layer
        self._recording_areas_widget = self._create_layer_selector()
        settings_layout.addRow("Recording Areas Layer:", self._recording_areas_widget)
        
        # Objects layer
        self._objects_widget = self._create_layer_selector()
        settings_layout.addRow("Objects Layer:", self._objects_widget)
        
        # Objects layer field selections (initially hidden)
        self._objects_fields_widget = self._create_objects_fields_widget()
        settings_layout.addRow("", self._objects_fields_widget)  # Empty label for indentation
        
        # Features layer
        self._features_widget = self._create_layer_selector()
        settings_layout.addRow("Features Layer:", self._features_widget)
        

        
        # Raster clipping offset for field projects
        self._raster_offset_widget = self._create_raster_offset_widget()
        settings_layout.addRow("Raster Clipping Offset:", self._raster_offset_widget)
        
        # Extra layers for field projects
        self._extra_layers_widget = self._create_extra_layers_widget()
        settings_layout.addRow("Extra Field Layers:", self._extra_layers_widget)
        

        
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
    
    def _create_layer_selector(self) -> QtWidgets.QWidget:
        """Create a layer selection widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Combo box for layer selection
        combo_box = QtWidgets.QComboBox()
        combo_box.setMinimumWidth(300)
        combo_box.addItem("-- Select a polygon layer --", "")
        
        # Refresh button
        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.setToolTip("Refresh the list of available polygon layers")
        
        layout.addWidget(combo_box)
        layout.addWidget(refresh_button)
        
        # Store references
        widget.combo_box = combo_box
        widget.refresh_button = refresh_button
        
        return widget
    
    def _create_objects_fields_widget(self) -> QtWidgets.QWidget:
        """Create a widget for selecting objects layer fields."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 0, 0, 0)  # Indent to show hierarchy
        
        # Number field selection
        number_layout = QtWidgets.QHBoxLayout()
        number_label = QtWidgets.QLabel("Number Field:")
        self._number_field_combo = QtWidgets.QComboBox()
        self._number_field_combo.addItem("-- Select number field --", "")
        self._number_field_combo.setMinimumWidth(200)
        number_layout.addWidget(number_label)
        number_layout.addWidget(self._number_field_combo)
        number_layout.addStretch()
        
        # Level field selection
        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel("Level Field:")
        self._level_field_combo = QtWidgets.QComboBox()
        self._level_field_combo.addItem("-- Select level field --", "")
        self._level_field_combo.setMinimumWidth(200)
        level_layout.addWidget(level_label)
        level_layout.addWidget(self._level_field_combo)
        level_layout.addStretch()
        
        layout.addLayout(number_layout)
        layout.addLayout(level_layout)
        
        # Initially hide the widget
        widget.setVisible(False)
        
        return widget
    
    def _create_extra_layers_widget(self) -> QtWidgets.QWidget:
        """Create a widget for selecting extra vector layers to include in QField projects."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Description label
        description_label = QtWidgets.QLabel(
            "Select additional vector layers to include in field projects. "
            "The recording areas layer is always included and cannot be modified."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(description_label)
        
        # List widget for layer selection (with checkboxes)
        self._extra_layers_list = QtWidgets.QListWidget()
        self._extra_layers_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._extra_layers_list.setMaximumHeight(150)
        layout.addWidget(self._extra_layers_list)
        
        # Refresh button
        refresh_button = QtWidgets.QPushButton("Refresh Layers")
        refresh_button.setToolTip("Refresh the list of available vector layers")
        layout.addWidget(refresh_button)
        
        # Store reference to refresh button
        widget.refresh_button = refresh_button
        
        return widget
    
    def _create_raster_offset_widget(self) -> QtWidgets.QWidget:
        """Create a widget for configuring raster clipping offset."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Description label
        description_label = QtWidgets.QLabel(
            "Offset in meters to expand the clipping area around recording areas when creating field projects. "
            "This ensures the background image extends slightly beyond the recording area boundary."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(description_label)
        
        # Spacer
        layout.addStretch()
        
        # Spin box for offset value
        self._raster_offset_spinbox = QtWidgets.QDoubleSpinBox()
        self._raster_offset_spinbox.setMinimum(0.0)
        self._raster_offset_spinbox.setMaximum(100.0)
        self._raster_offset_spinbox.setSingleStep(0.1)
        self._raster_offset_spinbox.setDecimals(2)
        self._raster_offset_spinbox.setSuffix(" m")
        self._raster_offset_spinbox.setValue(0.2)  # Default 20 cm
        self._raster_offset_spinbox.setMinimumWidth(100)
        layout.addWidget(self._raster_offset_spinbox)
        
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
        self._csv_archive_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._csv_archive_widget.input_field,
                                      "Select Folder for CSV Archive")
        )


        
        # Layer selector connections
        self._recording_areas_widget.refresh_button.clicked.connect(self._refresh_layer_list)
        self._objects_widget.refresh_button.clicked.connect(self._refresh_objects_layer_list)
        self._objects_widget.combo_box.currentIndexChanged.connect(self._on_objects_layer_changed)
        self._features_widget.refresh_button.clicked.connect(self._refresh_features_layer_list)
        
        # Extra layers connections
        self._extra_layers_widget.refresh_button.clicked.connect(self._refresh_extra_layers_list)
        

    
    def _browse_folder(self, input_field: QtWidgets.QLineEdit, title: str) -> None:
        """Browse for a folder and update the input field."""
        folder_path = self._file_system_service.select_directory(
            title, 
            input_field.text() if input_field.text() else None
        )
        
        if folder_path:
            input_field.setText(folder_path)
    
    def _refresh_layer_list(self) -> None:
        """Refresh the list of available polygon layers."""
        try:
            combo_box = self._recording_areas_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem("-- Select a polygon layer --", "")
            
            # Get polygon layers from the service
            polygon_layers = self._layer_service.get_polygon_layers()
            
            # Add layers to combo box
            for layer_info in polygon_layers:
                display_text = f"{layer_info['name']} ({layer_info['feature_count']} features)"
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error("Layer Error", f"Failed to refresh layer list: {str(e)}")
    
    def _refresh_objects_layer_list(self) -> None:
        """Refresh the list of available polygon and multipolygon layers for objects."""
        try:
            combo_box = self._objects_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem("-- Select a polygon or multipolygon layer --", "")
            
            # Get polygon and multipolygon layers from the service
            layers = self._layer_service.get_polygon_and_multipolygon_layers()
            
            # Add layers to combo box
            for layer_info in layers:
                display_text = f"{layer_info['name']} ({layer_info['feature_count']} features)"
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error("Layer Error", f"Failed to refresh objects layer list: {str(e)}")
    
    def _refresh_features_layer_list(self) -> None:
        """Refresh the list of available polygon and multipolygon layers for features."""
        try:
            combo_box = self._features_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem("-- Select a polygon or multipolygon layer --", "")
            
            # Get polygon and multipolygon layers from the service
            layers = self._layer_service.get_polygon_and_multipolygon_layers()
            
            # Add layers to combo box
            for layer_info in layers:
                display_text = f"{layer_info['name']} ({layer_info['feature_count']} features)"
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error("Layer Error", f"Failed to refresh features layer list: {str(e)}")
    
    def _refresh_extra_layers_list(self) -> None:
        """Refresh the list of available vector layers for extra QField layers."""
        try:
            # Get current checked state by layer id
            checked_layer_ids = set()
            for i in range(self._extra_layers_list.count()):
                item = self._extra_layers_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_layer_ids.add(item.data(Qt.UserRole))
            
            # Get the current recording areas layer id
            recording_areas_layer_id = self._recording_areas_widget.combo_box.currentData()
            
            # Clear existing items
            self._extra_layers_list.clear()
            
            # Get vector layers from the service
            vector_layers = self._layer_service.get_vector_layers()
            
            for layer_info in vector_layers:
                item = QtWidgets.QListWidgetItem()
                display_text = f"{layer_info['name']} ({layer_info['feature_count']} features)"
                item.setText(display_text)
                item.setData(Qt.UserRole, layer_info['id'])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                # Recording areas layer: always checked and disabled
                if layer_info['id'] == recording_areas_layer_id:
                    item.setCheckState(Qt.Checked)
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                else:
                    # Restore checked state if previously checked
                    item.setCheckState(Qt.Checked if layer_info['id'] in checked_layer_ids else Qt.Unchecked)
                self._extra_layers_list.addItem(item)
        except Exception as e:
            self._show_error("Layer Error", f"Failed to refresh extra layers list: {str(e)}")
    
    def _get_selected_extra_layers(self) -> List[str]:
        """Get the list of checked extra layer IDs (excluding the recording areas layer)."""
        selected_layers = []
        recording_areas_layer_id = self._recording_areas_widget.combo_box.currentData()
        for i in range(self._extra_layers_list.count()):
            item = self._extra_layers_list.item(i)
            if item.checkState() == Qt.Checked and item.data(Qt.UserRole) != recording_areas_layer_id:
                selected_layers.append(item.data(Qt.UserRole))
        return selected_layers
    
    def _on_objects_layer_changed(self) -> None:
        """Handle changes to the objects layer selection."""
        layer_id = self._objects_widget.combo_box.currentData()
        
        if layer_id:
            # Show field selection widgets and populate them
            self._objects_fields_widget.setVisible(True)
            self._populate_objects_fields(layer_id)
        else:
            # Hide field selection widgets
            self._objects_fields_widget.setVisible(False)
    
    def _populate_objects_fields(self, layer_id: str) -> None:
        """Populate the field selection combo boxes for the objects layer."""
        try:
            # Get fields from the layer
            fields = self._layer_service.get_layer_fields(layer_id)
            if fields is None:
                self._show_error("Field Error", f"Could not retrieve fields for layer {layer_id}")
                return
            
            # Clear existing items
            self._number_field_combo.clear()
            self._level_field_combo.clear()
            
            # Add placeholder items
            self._number_field_combo.addItem("-- Select number field --", "")
            self._level_field_combo.addItem("-- Select level field --", "")
            
            # Add fields to number field combo (only integer fields)
            integer_fields = [field for field in fields if field['is_integer']]
            for field in integer_fields:
                display_text = f"{field['name']} ({field['type']})"
                self._number_field_combo.addItem(display_text, field['name'])
            
            # Add all fields to level field combo
            for field in fields:
                display_text = f"{field['name']} ({field['type']})"
                self._level_field_combo.addItem(display_text, field['name'])
            
        except Exception as e:
            self._show_error("Field Error", f"Failed to populate field lists: {str(e)}")
    
    def _update_ui_state(self) -> None:
        """Update UI state based on current settings."""
        # No longer needed since QField checkbox is removed
        pass
    
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
            
            # Load CSV archive folder
            csv_archive_path = self._settings_manager.get_value('csv_archive_folder', '')
            self._csv_archive_widget.input_field.setText(csv_archive_path)
            

            
            # Load recording areas layer
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
            self._refresh_layer_list()  # Populate the combo box
            if recording_areas_layer_id:
                index = self._recording_areas_widget.combo_box.findData(recording_areas_layer_id)
                if index >= 0:
                    self._recording_areas_widget.combo_box.setCurrentIndex(index)
            
            # Load objects layer
            objects_layer_id = self._settings_manager.get_value('objects_layer', '')
            self._refresh_objects_layer_list()  # Populate the combo box
            if objects_layer_id:
                index = self._objects_widget.combo_box.findData(objects_layer_id)
                if index >= 0:
                    self._objects_widget.combo_box.setCurrentIndex(index)
                    # Load field selections after layer is set
                    number_field = self._settings_manager.get_value('objects_number_field', '')
                    level_field = self._settings_manager.get_value('objects_level_field', '')
                    if number_field:
                        index = self._number_field_combo.findData(number_field)
                        if index >= 0:
                            self._number_field_combo.setCurrentIndex(index)
                    if level_field:
                        index = self._level_field_combo.findData(level_field)
                        if index >= 0:
                            self._level_field_combo.setCurrentIndex(index)
            
            # Load features layer
            features_layer_id = self._settings_manager.get_value('features_layer', '')
            self._refresh_features_layer_list()  # Populate the combo box
            if features_layer_id:
                index = self._features_widget.combo_box.findData(features_layer_id)
                if index >= 0:
                    self._features_widget.combo_box.setCurrentIndex(index)
            

            
            # Load raster clipping offset
            raster_offset = self._settings_manager.get_value('raster_clipping_offset', 0.2)
            self._raster_offset_spinbox.setValue(float(raster_offset))
            
            # Load extra layers for field projects
            extra_layers = self._settings_manager.get_value('extra_field_layers', [])
            self._refresh_extra_layers_list()  # Populate the list
            # Set checked state for extra layers (recording areas handled in refresh)
            for i in range(self._extra_layers_list.count()):
                item = self._extra_layers_list.item(i)
                layer_id = item.data(Qt.UserRole)
                if layer_id in extra_layers:
                    item.setCheckState(Qt.Checked)
                elif item.flags() & Qt.ItemIsEnabled:
                    item.setCheckState(Qt.Unchecked)
            

            
            # Store original values
            self._original_values = {
                'field_projects_folder': field_projects_path,
                'total_station_folder': total_station_path,
                'completed_projects_folder': completed_projects_path,
                'csv_archive_folder': csv_archive_path,
                'recording_areas_layer': recording_areas_layer_id,
                'objects_layer': objects_layer_id,
                'objects_number_field': self._settings_manager.get_value('objects_number_field', ''),
                'objects_level_field': self._settings_manager.get_value('objects_level_field', ''),
                'features_layer': features_layer_id,

                'raster_clipping_offset': float(raster_offset),
                'extra_field_layers': extra_layers,

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
                'csv_archive_folder': self._csv_archive_widget.input_field.text(),
                'recording_areas_layer': self._recording_areas_widget.combo_box.currentData(),
                'objects_layer': self._objects_widget.combo_box.currentData(),
                'objects_number_field': self._number_field_combo.currentData(),
                'objects_level_field': self._level_field_combo.currentData(),
                'features_layer': self._features_widget.combo_box.currentData(),

                'raster_clipping_offset': self._raster_offset_spinbox.value(),
                'extra_field_layers': self._get_selected_extra_layers(),

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
            self._csv_archive_widget.input_field.setText(
                self._original_values.get('csv_archive_folder', '')
            )


            self._raster_offset_spinbox.setValue(
                self._original_values.get('raster_clipping_offset', 0.2)
            )

            
            # Revert recording areas layer selection
            recording_areas_layer_id = self._original_values.get('recording_areas_layer', '')
            if recording_areas_layer_id:
                index = self._recording_areas_widget.combo_box.findData(recording_areas_layer_id)
                if index >= 0:
                    self._recording_areas_widget.combo_box.setCurrentIndex(index)
                else:
                    self._recording_areas_widget.combo_box.setCurrentIndex(0)
            else:
                self._recording_areas_widget.combo_box.setCurrentIndex(0)
            
            # Revert objects layer selection
            objects_layer_id = self._original_values.get('objects_layer', '')
            if objects_layer_id:
                index = self._objects_widget.combo_box.findData(objects_layer_id)
                if index >= 0:
                    self._objects_widget.combo_box.setCurrentIndex(index)
                    # Revert field selections
                    number_field = self._original_values.get('objects_number_field', '')
                    level_field = self._original_values.get('objects_level_field', '')
                    if number_field:
                        index = self._number_field_combo.findData(number_field)
                        if index >= 0:
                            self._number_field_combo.setCurrentIndex(index)
                    if level_field:
                        index = self._level_field_combo.findData(level_field)
                        if index >= 0:
                            self._level_field_combo.setCurrentIndex(index)
                else:
                    self._objects_widget.combo_box.setCurrentIndex(0)
            else:
                self._objects_widget.combo_box.setCurrentIndex(0)
            
            # Revert features layer selection
            features_layer_id = self._original_values.get('features_layer', '')
            if features_layer_id:
                index = self._features_widget.combo_box.findData(features_layer_id)
                if index >= 0:
                    self._features_widget.combo_box.setCurrentIndex(index)
                else:
                    self._features_widget.combo_box.setCurrentIndex(0)
            else:
                self._features_widget.combo_box.setCurrentIndex(0)
            
            # Revert settings in manager
            for key, value in self._original_values.items():
                self._settings_manager.set_value(key, value)
                
        except Exception as e:
            self._show_error("Settings Error", f"Failed to revert settings: {str(e)}")
        
        super().reject()
    
    def _show_error(self, title: str, message: str) -> None:
        """Show an error message to the user."""
        QtWidgets.QMessageBox.critical(self, title, message) 