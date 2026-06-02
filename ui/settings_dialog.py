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
- Organized into 3 tabs: Folders, Layers & Fields, and Raster

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
    
    if dialog.exec() == QDialog.Accepted:
        # Settings were saved successfully
        pass

The dialog provides:
- Intuitive folder selection with browse buttons
- QGIS layer selection for recording areas
- Real-time validation feedback
- Clear error messages
- Consistent user experience
- Proper state management
- Organized tabbed interface for better UX
"""

from typing import Optional, Dict, Any, List
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
import functools

try:
    from ..core.interfaces import ISettingsManager, IFileSystemService, ILayerService, IConfigurationValidator
except ImportError:
    from core.interfaces import ISettingsManager, IFileSystemService, ILayerService, IConfigurationValidator


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == 'true'
    return bool(value)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _align_center_flag():
    """Return a center-alignment flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "AlignCenter"):
        return Qt.AlignCenter
    alignment_flag = getattr(Qt, "AlignmentFlag", None)
    if alignment_flag is not None and hasattr(alignment_flag, "AlignCenter"):
        return alignment_flag.AlignCenter
    raise AttributeError("Qt center alignment flag is not available.")


def _no_selection_mode():
    """Return the QAbstractItemView no-selection mode for Qt5 and Qt6."""
    item_view = QtWidgets.QAbstractItemView
    if hasattr(item_view, "NoSelection"):
        return item_view.NoSelection

    selection_mode = getattr(item_view, "SelectionMode", None)
    if selection_mode is not None and hasattr(selection_mode, "NoSelection"):
        return selection_mode.NoSelection

    raise AttributeError("QAbstractItemView no-selection mode is not available.")


def _dialog_button_ok_cancel():
    """Return QDialogButtonBox OK/Cancel flags compatible with Qt5 and Qt6."""
    button_box = QtWidgets.QDialogButtonBox
    if hasattr(button_box, "Ok") and hasattr(button_box, "Cancel"):
        return button_box.Ok | button_box.Cancel

    standard_button = getattr(button_box, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Ok") and hasattr(standard_button, "Cancel"):
        return standard_button.Ok | standard_button.Cancel

    raise AttributeError("QDialogButtonBox OK/Cancel flags are not available.")


def _dialog_button_ok():
    """Return QDialogButtonBox OK button identifier for Qt5 and Qt6."""
    button_box = QtWidgets.QDialogButtonBox
    if hasattr(button_box, "Ok"):
        return button_box.Ok

    standard_button = getattr(button_box, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Ok"):
        return standard_button.Ok

    raise AttributeError("QDialogButtonBox OK button identifier is not available.")


def _dialog_button_cancel():
    """Return QDialogButtonBox Cancel button identifier for Qt5 and Qt6."""
    button_box = QtWidgets.QDialogButtonBox
    if hasattr(button_box, "Cancel"):
        return button_box.Cancel

    standard_button = getattr(button_box, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Cancel"):
        return standard_button.Cancel

    raise AttributeError("QDialogButtonBox Cancel button identifier is not available.")


def _horizontal_orientation():
    """Return horizontal orientation flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "Horizontal"):
        return Qt.Horizontal

    orientation = getattr(Qt, "Orientation", None)
    if orientation is not None and hasattr(orientation, "Horizontal"):
        return orientation.Horizontal

    raise AttributeError("Qt horizontal orientation flag is not available.")


def _user_role_item_data_role():
    """Return Qt item-data UserRole compatible with Qt5 and Qt6."""
    if hasattr(Qt, "UserRole"):
        return Qt.UserRole
    item_data_role = getattr(Qt, "ItemDataRole", None)
    if item_data_role is not None and hasattr(item_data_role, "UserRole"):
        return item_data_role.UserRole
    raise AttributeError("Qt UserRole item-data role is not available.")


def _item_is_user_checkable_flag():
    """Return the item-flag for user-checkable items (Qt5/Qt6 compatible)."""
    if hasattr(Qt, "ItemIsUserCheckable"):
        return Qt.ItemIsUserCheckable
    item_flag = getattr(Qt, "ItemFlag", None)
    if item_flag is not None and hasattr(item_flag, "ItemIsUserCheckable"):
        return item_flag.ItemIsUserCheckable
    raise AttributeError("Qt ItemIsUserCheckable flag is not available.")


def _item_is_enabled_flag():
    """Return the item-flag for enabled items (Qt5/Qt6 compatible)."""
    if hasattr(Qt, "ItemIsEnabled"):
        return Qt.ItemIsEnabled
    item_flag = getattr(Qt, "ItemFlag", None)
    if item_flag is not None and hasattr(item_flag, "ItemIsEnabled"):
        return item_flag.ItemIsEnabled
    raise AttributeError("Qt ItemIsEnabled flag is not available.")


def _checked_check_state():
    """Return the check-state value for checked items (Qt5/Qt6 compatible)."""
    if hasattr(Qt, "Checked"):
        return Qt.Checked
    check_state = getattr(Qt, "CheckState", None)
    if check_state is not None and hasattr(check_state, "Checked"):
        return check_state.Checked
    raise AttributeError("Qt Checked check-state is not available.")


def _unchecked_check_state():
    """Return the check-state value for unchecked items (Qt5/Qt6 compatible)."""
    if hasattr(Qt, "Unchecked"):
        return Qt.Unchecked
    check_state = getattr(Qt, "CheckState", None)
    if check_state is not None and hasattr(check_state, "Unchecked"):
        return check_state.Unchecked
    raise AttributeError("Qt Unchecked check-state is not available.")


class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog for ArcheoSync plugin.
    
    This dialog provides a clean interface for managing plugin settings,
    following the Single Responsibility Principle by focusing only on UI presentation
    and delegating business logic to injected services. The interface is organized
    into three tabs for better user experience.
    
    All user-facing strings are wrapped in self.tr() for translation.
    """
    
    def __init__(self, settings_manager: ISettingsManager, 
                 file_system_service: IFileSystemService,
                 layer_service: ILayerService,
                 configuration_validator: IConfigurationValidator,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize the settings dialog."""
        super().__init__(parent)
        
        # Initialize services
        self._settings_manager = settings_manager
        self._file_system_service = file_system_service
        self._layer_service = layer_service
        self._configuration_validator = configuration_validator
        
        # Flag to track programmatic changes
        self._programmatic_change = False
        
        # Initialize UI components
        self._sliders = {}
        self._value_labels = {}
        self._button_box = None
        self._field_projects_widget = None
        self._total_station_widget = None
        self._raster_enhancement_group = None
        
        # Set up UI
        self._setup_ui()
        self._setup_connections()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle(self.tr("ArcheoSync Settings"))
        self.setGeometry(0, 0, 700, 600)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel(self.tr("ArcheoSync Plugin Settings"))
        title_label.setAlignment(_align_center_flag())
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Create tab widget
        self._tab_widget = QtWidgets.QTabWidget()
        main_layout.addWidget(self._tab_widget)
        
        # Create tabs
        self._create_folders_tab()
        self._create_layers_fields_tab()
        self._create_warnings_tab()
        self._create_raster_tab()
        
        # Add button box
        self._create_button_box(main_layout)

        # Debug: print slider ids
        print("Slider object ids:")
        for name, slider in self._sliders.items():
            print(f"  {name}: id={id(slider)}")
    
    def _create_folders_tab(self) -> None:
        """Create the folders configuration tab."""
        folders_widget = QtWidgets.QWidget()
        folders_layout = QtWidgets.QVBoxLayout(folders_widget)
        
        # Add description
        description_label = QtWidgets.QLabel(
            self.tr("Configure the folders used by ArcheoSync for managing field projects and data.")
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        folders_layout.addWidget(description_label)
        
        # Create form layout for folder settings
        form_layout = QtWidgets.QFormLayout()
        
        # Field projects destination
        self._field_projects_widget = self._create_folder_selector(
            self.tr("Select destination folder for new field projects...")
        )
        form_layout.addRow(self.tr("Field Projects Destination:"), self._field_projects_widget)
        
        # Total station CSV files
        self._total_station_widget = self._create_folder_selector(
            self.tr("Select folder containing total station CSV files...")
        )
        form_layout.addRow(self.tr("Total Station CSV Files:"), self._total_station_widget)
        
        # Completed field projects
        self._completed_projects_widget = self._create_folder_selector(
            self.tr("Select folder containing completed field projects...")
        )
        form_layout.addRow(self.tr("Completed Field Projects:"), self._completed_projects_widget)
        
        # Archive folders section
        archive_label = QtWidgets.QLabel(self.tr("Archive Folders"))
        archive_label.setStyleSheet("font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
        form_layout.addRow(archive_label)
        
        # CSV archive folder
        self._csv_archive_widget = self._create_folder_selector(
            self.tr("Select folder to archive imported CSV files...")
        )
        form_layout.addRow(self.tr("CSV Archive Folder:"), self._csv_archive_widget)

        self._csv_topo_identifier_column = QtWidgets.QLineEdit()
        self._csv_topo_identifier_column.setPlaceholderText(
            self.tr('Example: PtID — leave empty if the CSV has an "identifier" column or a single text column')
        )
        form_layout.addRow(
            self.tr("Topo CSV identifier column (mapping key):"),
            self._csv_topo_identifier_column,
        )
        
        # Field project archive folder
        self._field_project_archive_widget = self._create_folder_selector(
            self.tr("Select folder to archive imported field projects...")
        )
        form_layout.addRow(self.tr("Field Project Archive Folder:"), self._field_project_archive_widget)
        
        folders_layout.addLayout(form_layout)
        folders_layout.addStretch()
        
        # Add tab to widget
        self._tab_widget.addTab(folders_widget, self.tr("Folders"))
    
    def _create_layers_fields_tab(self) -> None:
        """Create the layers and fields configuration tab."""
        layers_widget = QtWidgets.QWidget()
        layers_layout = QtWidgets.QVBoxLayout(layers_widget)
        
        # Add description
        description_label = QtWidgets.QLabel(
            self.tr("Configure the QGIS layers and fields used for recording areas, objects, and features.")
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        layers_layout.addWidget(description_label)
        
        # Create form layout for layer settings
        form_layout = QtWidgets.QFormLayout()
        
        # Recording areas layer
        self._recording_areas_widget = self._create_layer_selector(self.tr("-- Select a polygon layer --"))
        form_layout.addRow(self.tr("Recording Areas Layer:"), self._recording_areas_widget)
        self._recording_area_variable_source_combo = QtWidgets.QComboBox()
        self._recording_area_variable_source_combo.setMinimumWidth(300)
        form_layout.addRow(self.tr("Recording Area Variable Source:"), self._recording_area_variable_source_combo)
        
        # Objects layer
        self._objects_widget = self._create_layer_selector(self.tr("-- Select a polygon or multipolygon layer --"))
        form_layout.addRow(self.tr("Objects Layer:"), self._objects_widget)
        
        # Objects layer field selections (initially hidden)
        self._objects_fields_widget = self._create_objects_fields_widget()
        form_layout.addRow("", self._objects_fields_widget)  # Empty label for indentation
        
        # Features layer
        self._features_widget = self._create_layer_selector(self.tr("-- Select a polygon or multipolygon layer --"))
        form_layout.addRow(self.tr("Features Layer:"), self._features_widget)
        self._features_fields_widget = self._create_child_fields_widget()
        form_layout.addRow("", self._features_fields_widget)
        
        # Small finds layer
        self._small_finds_widget = self._create_layer_selector(self.tr("-- Select a point, multipoint, or no geometry layer --"))
        form_layout.addRow(self.tr("Small Finds Layer:"), self._small_finds_widget)
        self._small_finds_fields_widget = self._create_child_fields_widget(is_small_finds=True)
        form_layout.addRow("", self._small_finds_fields_widget)

        # Alternative objects layer (no geometry, global field projects only)
        self._alternative_objects_widget = self._create_layer_selector(
            self.tr("-- Select a no geometry layer --")
        )
        form_layout.addRow(self.tr("Alternative Objects Layer:"), self._alternative_objects_widget)
        self._alternative_objects_fields_widget = self._create_alternative_objects_fields_widget()
        form_layout.addRow("", self._alternative_objects_fields_widget)
        
        # Total station points layer
        self._total_station_points_widget = self._create_layer_selector(self.tr("-- Select a point or multipoint layer --"))
        form_layout.addRow(self.tr("Total Station Points Layer:"), self._total_station_points_widget)
        
        # Extra layers for field projects
        self._extra_layers_widget = self._create_extra_layers_widget()
        form_layout.addRow(self.tr("Extra Field Layers:"), self._extra_layers_widget)
        
        layers_layout.addLayout(form_layout)
        layers_layout.addStretch()
        
        # Add tab to widget
        self._tab_widget.addTab(layers_widget, self.tr("Layers & Fields"))
    
    def _create_warnings_tab(self) -> None:
        """Create the warnings configuration tab."""
        warnings_widget = QtWidgets.QWidget()
        warnings_layout = QtWidgets.QVBoxLayout(warnings_widget)
        
        # Add description
        description_label = QtWidgets.QLabel(
            self.tr("Configure warning settings for data quality checks in ArcheoSync.")
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        warnings_layout.addWidget(description_label)
        
        # Create form layout for warning settings
        form_layout = QtWidgets.QFormLayout()
        
        # Distance Detection Settings
        distance_group = QtWidgets.QGroupBox(self.tr("Distance Detection"))
        distance_layout = QtWidgets.QFormLayout(distance_group)
        
        # Enable distance warnings
        self._enable_distance_warnings = QtWidgets.QCheckBox()
        self._enable_distance_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_distance_warnings', True)))
        distance_layout.addRow(self.tr("Enable Distance Warnings:"), self._enable_distance_warnings)
        
        # Maximum distance for distance warnings (between total station points and objects)
        self._distance_max_distance = QtWidgets.QDoubleSpinBox()
        self._distance_max_distance.setMinimum(0.01)
        self._distance_max_distance.setMaximum(10.0)
        self._distance_max_distance.setSingleStep(0.01)
        self._distance_max_distance.setDecimals(2)
        self._distance_max_distance.setSuffix(self.tr(" m"))
        self._distance_max_distance.setValue(_to_float(self._settings_manager.get_value('distance_max_distance', 0.05)))
        self._distance_max_distance.setMinimumWidth(100)
        distance_layout.addRow(self.tr("Maximum Distance (Total Station to Objects):"), self._distance_max_distance)
        
        warnings_layout.addWidget(distance_group)
        
        # Height Difference Detection Settings
        height_group = QtWidgets.QGroupBox(self.tr("Height Difference Detection"))
        height_layout = QtWidgets.QFormLayout(height_group)
        
        # Enable height difference warnings
        self._enable_height_warnings = QtWidgets.QCheckBox()
        self._enable_height_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_height_warnings', True)))
        height_layout.addRow(self.tr("Enable Height Difference Warnings:"), self._enable_height_warnings)
        
        # Maximum distance for height difference detection
        self._height_max_distance = QtWidgets.QDoubleSpinBox()
        self._height_max_distance.setMinimum(0.1)
        self._height_max_distance.setMaximum(10.0)
        self._height_max_distance.setSingleStep(0.1)
        self._height_max_distance.setDecimals(1)
        self._height_max_distance.setSuffix(self.tr(" m"))
        self._height_max_distance.setValue(_to_float(self._settings_manager.get_value('height_max_distance', 1.0)))
        self._height_max_distance.setMinimumWidth(100)
        height_layout.addRow(self.tr("Maximum Distance (Close Points):"), self._height_max_distance)
        
        # Maximum height difference
        self._height_max_difference = QtWidgets.QDoubleSpinBox()
        self._height_max_difference.setMinimum(0.01)
        self._height_max_difference.setMaximum(5.0)
        self._height_max_difference.setSingleStep(0.01)
        self._height_max_difference.setDecimals(2)
        self._height_max_difference.setSuffix(self.tr(" m"))
        self._height_max_difference.setValue(_to_float(self._settings_manager.get_value('height_max_difference', 0.2)))
        self._height_max_difference.setMinimumWidth(100)
        height_layout.addRow(self.tr("Maximum Height Difference:"), self._height_max_difference)
        
        warnings_layout.addWidget(height_group)
        
        # Out of Bounds Detection Settings
        bounds_group = QtWidgets.QGroupBox(self.tr("Out of Bounds Detection"))
        bounds_layout = QtWidgets.QFormLayout(bounds_group)
        
        # Enable out of bounds warnings
        self._enable_bounds_warnings = QtWidgets.QCheckBox()
        self._enable_bounds_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_bounds_warnings', True)))
        bounds_layout.addRow(self.tr("Enable Out of Bounds Warnings:"), self._enable_bounds_warnings)
        
        # Maximum distance outside recording area
        self._bounds_max_distance = QtWidgets.QDoubleSpinBox()
        self._bounds_max_distance.setMinimum(0.01)
        self._bounds_max_distance.setMaximum(10.0)
        self._bounds_max_distance.setSingleStep(0.01)
        self._bounds_max_distance.setDecimals(2)
        self._bounds_max_distance.setSuffix(self.tr(" m"))
        self._bounds_max_distance.setValue(_to_float(self._settings_manager.get_value('bounds_max_distance', 0.2)))
        self._bounds_max_distance.setMinimumWidth(100)
        bounds_layout.addRow(self.tr("Maximum Distance Outside Recording Area:"), self._bounds_max_distance)
        
        warnings_layout.addWidget(bounds_group)
        
        # Other Warnings (non-distance-based)
        other_group = QtWidgets.QGroupBox(self.tr("Other Warnings"))
        other_layout = QtWidgets.QFormLayout(other_group)
        
        # Enable duplicate objects warnings
        self._enable_duplicate_objects_warnings = QtWidgets.QCheckBox()
        self._enable_duplicate_objects_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_duplicate_objects_warnings', True)))
        other_layout.addRow(self.tr("Enable Duplicate Objects Warnings:"), self._enable_duplicate_objects_warnings)
        
        # Enable duplicate total station identifiers warnings
        self._enable_duplicate_total_station_identifiers_warnings = QtWidgets.QCheckBox()
        self._enable_duplicate_total_station_identifiers_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_duplicate_total_station_identifiers_warnings', True)))
        other_layout.addRow(self.tr("Enable Duplicate Total Station Identifiers Warnings:"), self._enable_duplicate_total_station_identifiers_warnings)
        
        # Enable skipped numbers warnings
        self._enable_skipped_numbers_warnings = QtWidgets.QCheckBox()
        self._enable_skipped_numbers_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_skipped_numbers_warnings', True)))
        other_layout.addRow(self.tr("Enable Skipped Numbers Warnings:"), self._enable_skipped_numbers_warnings)
        
        # Enable missing total station warnings
        self._enable_missing_total_station_warnings = QtWidgets.QCheckBox()
        self._enable_missing_total_station_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_missing_total_station_warnings', True)))
        other_layout.addRow(self.tr("Enable Missing Total Station Warnings:"), self._enable_missing_total_station_warnings)
        
        warnings_layout.addWidget(other_group)
        
        warnings_layout.addStretch()
        
        # Add tab to widget
        self._tab_widget.addTab(warnings_widget, self.tr("Error detection"))
    
    def _create_raster_tab(self) -> None:
        """Create the raster configuration tab."""
        raster_widget = QtWidgets.QWidget()
        raster_layout = QtWidgets.QVBoxLayout(raster_widget)
        
        # Add description
        description_label = QtWidgets.QLabel(
            self.tr("Configure raster processing settings for field project creation.")
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        raster_layout.addWidget(description_label)
        
        # Create form layout for raster settings
        form_layout = QtWidgets.QFormLayout()
        
        # Raster clipping offset for field projects
        self._raster_offset_widget = self._create_raster_offset_widget()
        form_layout.addRow(self.tr("Raster Clipping Offset:"), self._raster_offset_widget)
        
        # Raster enhancement settings section
        enhancement_label = QtWidgets.QLabel(self.tr("Raster Enhancement Settings"))
        enhancement_label.setStyleSheet("font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
        form_layout.addRow(enhancement_label)
        
        # Brightness slider
        self._brightness_widget = self._create_slider_widget(
            "Brightness", -255, 255, 0, self.tr("Adjust the brightness of clipped raster layers")
        )
        form_layout.addRow(self.tr("Brightness:"), self._brightness_widget)
        
        # Contrast slider
        self._contrast_widget = self._create_slider_widget(
            "Contrast", -100, 100, 0, self.tr("Adjust the contrast of clipped raster layers")
        )
        form_layout.addRow(self.tr("Contrast:"), self._contrast_widget)
        
        # Saturation slider
        self._saturation_widget = self._create_slider_widget(
            "Saturation", -100, 100, 0, self.tr("Adjust the saturation of clipped raster layers")
        )
        form_layout.addRow(self.tr("Saturation:"), self._saturation_widget)
        
        raster_layout.addLayout(form_layout)
        raster_layout.addStretch()
        
        # Add tab to widget
        self._tab_widget.addTab(raster_widget, self.tr("Raster"))
    
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
        browse_button = QtWidgets.QPushButton(self.tr("Browse..."))
        
        layout.addWidget(input_field)
        layout.addWidget(browse_button)
        
        # Store references
        widget.input_field = input_field
        widget.browse_button = browse_button
        
        return widget
    
    def _create_layer_selector(self, placeholder: str = None) -> QtWidgets.QWidget:
        """Create a layer selection widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Combo box for layer selection
        combo_box = QtWidgets.QComboBox()
        combo_box.setMinimumWidth(300)
        if placeholder:
            combo_box.addItem(placeholder, "")
        else:
            combo_box.addItem(self.tr("-- Select a polygon layer --"), "")
        
        # Refresh button
        refresh_button = QtWidgets.QPushButton(self.tr("Refresh"))
        refresh_button.setToolTip(self.tr("Refresh the list of available layers"))
        
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
        number_label = QtWidgets.QLabel(self.tr("Number Field:"))
        self._number_field_combo = QtWidgets.QComboBox()
        self._number_field_combo.addItem(self.tr("-- Select number field --"), "")
        self._number_field_combo.setMinimumWidth(200)
        number_layout.addWidget(number_label)
        number_layout.addWidget(self._number_field_combo)
        number_layout.addStretch()
        
        # Level field selection
        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel(self.tr("Level Field:"))
        self._level_field_combo = QtWidgets.QComboBox()
        self._level_field_combo.addItem(self.tr("-- Select level field --"), "")
        self._level_field_combo.setMinimumWidth(200)
        level_layout.addWidget(level_label)
        level_layout.addWidget(self._level_field_combo)
        level_layout.addStretch()

        recording_area_layout = QtWidgets.QHBoxLayout()
        recording_area_label = QtWidgets.QLabel(self.tr("Recording Area Field:"))
        self._objects_recording_area_field_combo = QtWidgets.QComboBox()
        self._objects_recording_area_field_combo.addItem(self.tr("-- Select recording area field --"), "")
        self._objects_recording_area_field_combo.setMinimumWidth(200)
        recording_area_layout.addWidget(recording_area_label)
        recording_area_layout.addWidget(self._objects_recording_area_field_combo)
        recording_area_layout.addStretch()
        
        layout.addLayout(number_layout)
        layout.addLayout(level_layout)
        layout.addLayout(recording_area_layout)
        
        # Initially hide the widget
        widget.setVisible(False)
        
        return widget

    def _create_child_fields_widget(self, is_small_finds: bool = False) -> QtWidgets.QWidget:
        """Create field selectors for features/small finds layers."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 0, 0, 0)

        recording_area_layout = QtWidgets.QHBoxLayout()
        recording_area_label = QtWidgets.QLabel(self.tr("Recording Area Field:"))
        recording_area_combo = QtWidgets.QComboBox()
        recording_area_combo.addItem(self.tr("-- Select recording area field --"), "")
        recording_area_combo.setMinimumWidth(200)
        recording_area_layout.addWidget(recording_area_label)
        recording_area_layout.addWidget(recording_area_combo)
        recording_area_layout.addStretch()

        level_layout = QtWidgets.QHBoxLayout()
        level_label = QtWidgets.QLabel(self.tr("Level Field:"))
        level_combo = QtWidgets.QComboBox()
        level_combo.addItem(self.tr("-- Select level field --"), "")
        level_combo.setMinimumWidth(200)
        level_layout.addWidget(level_label)
        level_layout.addWidget(level_combo)
        level_layout.addStretch()

        layout.addLayout(recording_area_layout)
        layout.addLayout(level_layout)
        widget.setVisible(False)

        if is_small_finds:
            self._small_finds_recording_area_field_combo = recording_area_combo
            self._small_finds_level_field_combo = level_combo
        else:
            self._features_recording_area_field_combo = recording_area_combo
            self._features_level_field_combo = level_combo

        return widget

    def _create_alternative_objects_fields_widget(self) -> QtWidgets.QWidget:
        """Create recording-area field selector for the alternative objects layer."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(20, 0, 0, 0)

        self._alternative_objects_recording_area_field_combo = QtWidgets.QComboBox()
        self._alternative_objects_recording_area_field_combo.setMinimumWidth(250)
        layout.addRow(self.tr("Recording Area Field:"), self._alternative_objects_recording_area_field_combo)

        widget.setVisible(False)
        return widget
    
    def _create_extra_layers_widget(self) -> QtWidgets.QWidget:
        """Create a widget for selecting extra vector layers to include in QField projects."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Description label
        description_label = QtWidgets.QLabel(
            self.tr("Select additional vector layers to include in field projects. ") +
            self.tr("The recording areas layer is always included and cannot be modified.")
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(description_label)
        
        # List widget for layer selection (with checkboxes)
        self._extra_layers_list = QtWidgets.QListWidget()
        self._extra_layers_list.setSelectionMode(_no_selection_mode())
        self._extra_layers_list.setMaximumHeight(150)
        layout.addWidget(self._extra_layers_list)
        
        # Refresh button
        refresh_button = QtWidgets.QPushButton(self.tr("Refresh Layers"))
        refresh_button.setToolTip(self.tr("Refresh the list of available vector layers"))
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
            self.tr("Offset in meters to expand the clipping area around recording areas when creating field projects. ") +
            self.tr("This ensures the background image extends slightly beyond the recording area boundary.")
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
        self._raster_offset_spinbox.setSuffix(self.tr(" m"))
        self._raster_offset_spinbox.setValue(0.2)  # Default 20 cm
        self._raster_offset_spinbox.setMinimumWidth(100)
        layout.addWidget(self._raster_offset_spinbox)
        
        return widget
    
    def _create_slider_widget(self, title: str, min_val: int, max_val: int, default_val: int, tooltip: str) -> QtWidgets.QWidget:
        """Create an integer spinbox widget for raster enhancement settings (replaces slider)."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # SpinBox
        spinbox = QtWidgets.QSpinBox()
        spinbox.setMinimum(min_val)
        spinbox.setMaximum(max_val)
        spinbox.setValue(default_val)
        spinbox.setToolTip(tooltip)
        layout.addWidget(spinbox)

        # Store reference with English key for consistent access
        self._sliders[title] = spinbox
        # Remove value label, not needed for spinbox
        return widget
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        self._button_box = QtWidgets.QDialogButtonBox(
            _dialog_button_ok_cancel(),
            _horizontal_orientation(),
            self
        )
        
        # Set button texts for translation
        self._button_box.button(_dialog_button_ok()).setText(self.tr("OK"))
        self._button_box.button(_dialog_button_cancel()).setText(self.tr("Cancel"))
        
        parent_layout.addWidget(self._button_box)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Button box connections
        self._button_box.accepted.connect(self._save_and_accept)
        self._button_box.rejected.connect(self._reject)
        
        # Browse button connections
        self._field_projects_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._field_projects_widget.input_field, 
                                      self.tr("Select Destination Folder for New Field Projects"))
        )
        self._total_station_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._total_station_widget.input_field,
                                      self.tr("Select Folder for Total Station CSV Files"))
        )
        self._completed_projects_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._completed_projects_widget.input_field,
                                      self.tr("Select Folder for Completed Field Projects"))
        )
        self._csv_archive_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._csv_archive_widget.input_field,
                                      self.tr("Select Folder for CSV Archive"))
        )
        self._field_project_archive_widget.browse_button.clicked.connect(
            lambda: self._browse_folder(self._field_project_archive_widget.input_field,
                                      self.tr("Select Folder for Field Project Archive"))
        )
        # Layer selector connections
        self._recording_areas_widget.refresh_button.clicked.connect(self._refresh_layer_list)
        self._recording_areas_widget.combo_box.currentIndexChanged.connect(self._on_recording_areas_layer_changed)
        self._recording_area_variable_source_combo.currentIndexChanged.connect(
            self._on_recording_area_variable_source_changed
        )
        self._objects_widget.refresh_button.clicked.connect(self._refresh_objects_layer_list)
        self._objects_widget.combo_box.currentIndexChanged.connect(self._on_objects_layer_changed)
        self._level_field_combo.currentIndexChanged.connect(self._on_objects_level_field_changed)
        self._features_widget.refresh_button.clicked.connect(self._refresh_features_layer_list)
        self._features_widget.combo_box.currentIndexChanged.connect(self._on_features_layer_changed)
        self._small_finds_widget.refresh_button.clicked.connect(self._refresh_small_finds_layer_list)
        self._small_finds_widget.combo_box.currentIndexChanged.connect(self._on_small_finds_layer_changed)
        self._alternative_objects_widget.refresh_button.clicked.connect(self._refresh_alternative_objects_layer_list)
        self._alternative_objects_widget.combo_box.currentIndexChanged.connect(self._on_alternative_objects_layer_changed)
        self._total_station_points_widget.refresh_button.clicked.connect(self._refresh_total_station_points_layer_list)
        # Extra layers connections
        self._extra_layers_widget.refresh_button.clicked.connect(self._refresh_extra_layers_list)
        # No slider signal connections needed for spinboxes

    def _browse_folder(self, input_field: QtWidgets.QLineEdit, title: str) -> None:
        """Browse for a folder and update the input field."""
        folder_path = self._file_system_service.select_directory(
            self.tr(title), 
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
            combo_box.addItem(self.tr("-- Select a polygon layer --"), "")
            
            # Get polygon layers from the service
            polygon_layers = self._layer_service.get_polygon_layers()
            
            # Add layers to combo box
            for layer_info in polygon_layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)

            self._refresh_recording_area_variable_source_options()
            
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh layer list: {str(e)}"))

    def _on_recording_areas_layer_changed(self) -> None:
        """Update recording-area variable source options when recording layer changes."""
        self._refresh_recording_area_variable_source_options()
        self._refresh_recording_area_field_combos()

    def _on_recording_area_variable_source_changed(self) -> None:
        """Update recording-area field combos when source selection changes."""
        self._refresh_recording_area_field_combos()

    def _on_objects_level_field_changed(self) -> None:
        """Update child level-field combos when objects level field changes."""
        self._refresh_child_level_field_combos()

    def _refresh_recording_area_variable_source_options(self) -> None:
        """
        Refresh available sources for the project `recording_area` variable.

        Users can choose:
        - the display value (default),
        - the feature id,
        - or one of the recording-area layer fields.
        """
        current_value = self._recording_area_variable_source_combo.currentData()
        self._recording_area_variable_source_combo.clear()
        self._recording_area_variable_source_combo.addItem(self.tr("Display value"), "display")
        self._recording_area_variable_source_combo.addItem(self.tr("Feature ID"), "id")

        recording_areas_layer_id = self._recording_areas_widget.combo_box.currentData()
        if recording_areas_layer_id:
            fields = self._layer_service.get_layer_fields(recording_areas_layer_id)
            if not isinstance(fields, list):
                fields = []
            for field in fields:
                field_name = field.get("name")
                if not field_name:
                    continue
                label = self.tr(f"Field: {field_name}")
                self._recording_area_variable_source_combo.addItem(label, f"field:{field_name}")

        selected_value = current_value if current_value else "display"
        index = self._recording_area_variable_source_combo.findData(selected_value)
        self._recording_area_variable_source_combo.setCurrentIndex(index if index >= 0 else 0)
    
    def _refresh_objects_layer_list(self) -> None:
        """Refresh the list of available polygon and multipolygon layers for objects."""
        try:
            combo_box = self._objects_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem(self.tr("-- Select a polygon or multipolygon layer --"), "")
            
            # Get polygon and multipolygon layers from the service
            layers = self._layer_service.get_polygon_and_multipolygon_layers()
            
            # Add layers to combo box
            for layer_info in layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh objects layer list: {str(e)}"))
    
    def _refresh_features_layer_list(self) -> None:
        """Refresh the list of available polygon and multipolygon layers for features."""
        try:
            combo_box = self._features_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem(self.tr("-- Select a polygon or multipolygon layer --"), "")
            
            # Get polygon and multipolygon layers from the service
            layers = self._layer_service.get_polygon_and_multipolygon_layers()
            
            # Add layers to combo box
            for layer_info in layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh features layer list: {str(e)}"))
    
    def _refresh_small_finds_layer_list(self) -> None:
        """Refresh the list of available point, multipoint, and no geometry layers for small finds."""
        try:
            combo_box = self._small_finds_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem(self.tr("-- Select a point, multipoint, or no geometry layer --"), "")
            
            # Get point and multipoint layers from the service
            point_layers = self._layer_service.get_point_and_multipoint_layers()
            
            # Get no geometry layers from the service
            no_geom_layers = self._layer_service.get_no_geometry_layers()
            
            # Combine and sort all layers
            all_layers = point_layers + no_geom_layers
            all_layers.sort(key=lambda x: x['name'].lower())
            
            # Add layers to combo box
            for layer_info in all_layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh small finds layer list: {str(e)}"))

    def _refresh_alternative_objects_layer_list(self) -> None:
        """Refresh no-geometry layers available for alternative objects."""
        try:
            combo_box = self._alternative_objects_widget.combo_box
            current_layer_id = combo_box.currentData()

            combo_box.clear()
            combo_box.addItem(self.tr("-- Select a no geometry layer --"), "")

            layers = self._layer_service.get_no_geometry_layers()
            layers.sort(key=lambda item: item['name'].lower())
            for layer_info in layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])

            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
        except Exception as e:
            self._show_error(
                self.tr("Layer Error"),
                self.tr(f"Failed to refresh alternative objects layer list: {str(e)}"),
            )

    def _refresh_total_station_points_layer_list(self) -> None:
        """Refresh the list of available point and multipoint layers for total station points."""
        try:
            combo_box = self._total_station_points_widget.combo_box
            current_layer_id = combo_box.currentData()
            
            # Clear existing items except the first placeholder
            combo_box.clear()
            combo_box.addItem(self.tr("-- Select a point or multipoint layer --"), "")
            
            # Get point and multipoint layers from the service
            point_layers = self._layer_service.get_point_and_multipoint_layers()
            
            # Sort layers by name
            point_layers.sort(key=lambda x: x['name'].lower())
            
            # Add layers to combo box
            for layer_info in point_layers:
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                combo_box.addItem(display_text, layer_info['id'])
            
            # Restore previously selected layer if it still exists
            if current_layer_id:
                index = combo_box.findData(current_layer_id)
                if index >= 0:
                    combo_box.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh total station points layer list: {str(e)}"))
    
    def _refresh_extra_layers_list(self) -> None:
        """Refresh the list of available vector layers for extra QField layers."""
        try:
            user_role = _user_role_item_data_role()
            item_is_user_checkable = _item_is_user_checkable_flag()
            item_is_enabled = _item_is_enabled_flag()
            checked_state = _checked_check_state()
            unchecked_state = _unchecked_check_state()
            # Get current checked state by layer id
            checked_layer_ids = set()
            for i in range(self._extra_layers_list.count()):
                item = self._extra_layers_list.item(i)
                if item.checkState() == checked_state:
                    checked_layer_ids.add(item.data(user_role))
            
            # Get the current recording areas layer id
            recording_areas_layer_id = self._recording_areas_widget.combo_box.currentData()
            
            # Clear existing items
            self._extra_layers_list.clear()
            
            # Get vector layers from the service
            vector_layers = self._layer_service.get_vector_layers()
            
            for layer_info in vector_layers:
                item = QtWidgets.QListWidgetItem()
                display_text = self.tr(f"{layer_info['name']} ({layer_info['feature_count']} features)")
                item.setText(display_text)
                item.setData(user_role, layer_info['id'])
                item.setFlags(item.flags() | item_is_user_checkable)
                # Recording areas layer: always checked and disabled
                if layer_info['id'] == recording_areas_layer_id:
                    item.setCheckState(checked_state)
                    item.setFlags(item.flags() & ~item_is_enabled)
                else:
                    # Restore checked state if previously checked
                    item.setCheckState(checked_state if layer_info['id'] in checked_layer_ids else unchecked_state)
                self._extra_layers_list.addItem(item)
        except Exception as e:
            self._show_error(self.tr("Layer Error"), self.tr(f"Failed to refresh extra layers list: {str(e)}"))
    
    def _get_selected_extra_layers(self) -> List[str]:
        """Get the list of checked extra layer IDs (excluding the recording areas layer)."""
        user_role = _user_role_item_data_role()
        checked_state = _checked_check_state()
        selected_layers = []
        recording_areas_layer_id = self._recording_areas_widget.combo_box.currentData()
        for i in range(self._extra_layers_list.count()):
            item = self._extra_layers_list.item(i)
            if item.checkState() == checked_state and item.data(user_role) != recording_areas_layer_id:
                selected_layers.append(item.data(user_role))
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
            previous_number = self._number_field_combo.currentData()
            previous_level = self._level_field_combo.currentData()
            previous_recording_area = self._objects_recording_area_field_combo.currentData()
            # Get fields from the layer
            fields = self._layer_service.get_layer_fields(layer_id)
            if fields is None:
                self._show_error(self.tr("Field Error"), self.tr(f"Could not retrieve fields for layer {layer_id}"))
                return
            
            # Clear existing items
            self._number_field_combo.clear()
            self._level_field_combo.clear()
            self._objects_recording_area_field_combo.clear()
            
            # Add placeholder items
            self._number_field_combo.addItem(self.tr("-- Select number field --"), "")
            self._level_field_combo.addItem(self.tr("-- Select level field --"), "")
            self._objects_recording_area_field_combo.addItem(self.tr("-- Select recording area field --"), "")
            
            # Add fields to number field combo (only integer fields)
            integer_fields = [field for field in fields if field['is_integer']]
            for field in integer_fields:
                display_text = self.tr(f"{field['name']} ({field['type']})")
                self._number_field_combo.addItem(display_text, field['name'])
            
            # Add all fields to level field combo
            for field in fields:
                display_text = self.tr(f"{field['name']} ({field['type']})")
                self._level_field_combo.addItem(display_text, field['name'])
                if self._is_field_compatible_with_recording_area_source(field):
                    self._objects_recording_area_field_combo.addItem(display_text, field['name'])

            if previous_number:
                index = self._number_field_combo.findData(previous_number)
                if index >= 0:
                    self._number_field_combo.setCurrentIndex(index)
            if previous_level:
                index = self._level_field_combo.findData(previous_level)
                if index >= 0:
                    self._level_field_combo.setCurrentIndex(index)
            if previous_recording_area:
                index = self._objects_recording_area_field_combo.findData(previous_recording_area)
                if index >= 0:
                    self._objects_recording_area_field_combo.setCurrentIndex(index)
            
        except Exception as e:
            self._show_error(self.tr("Field Error"), self.tr(f"Failed to populate field lists: {str(e)}"))

    def _on_features_layer_changed(self) -> None:
        """Handle changes to the features layer selection."""
        layer_id = self._features_widget.combo_box.currentData()
        if layer_id:
            self._features_fields_widget.setVisible(True)
            self._populate_child_fields(layer_id, self._features_recording_area_field_combo, self._features_level_field_combo)
        else:
            self._features_fields_widget.setVisible(False)

    def _on_small_finds_layer_changed(self) -> None:
        """Handle changes to the small finds layer selection."""
        layer_id = self._small_finds_widget.combo_box.currentData()
        if layer_id:
            self._small_finds_fields_widget.setVisible(True)
            self._populate_child_fields(
                layer_id,
                self._small_finds_recording_area_field_combo,
                self._small_finds_level_field_combo
            )
        else:
            self._small_finds_fields_widget.setVisible(False)

    def _on_alternative_objects_layer_changed(self) -> None:
        """Handle changes to the alternative objects layer selection."""
        layer_id = self._alternative_objects_widget.combo_box.currentData()
        if layer_id:
            self._alternative_objects_fields_widget.setVisible(True)
            self._populate_alternative_objects_fields(layer_id)
        else:
            self._alternative_objects_fields_widget.setVisible(False)

    def _populate_alternative_objects_fields(self, layer_id: str) -> None:
        """Populate recording-area field choices for alternative objects."""
        try:
            previous = self._alternative_objects_recording_area_field_combo.currentData()
            fields = self._layer_service.get_layer_fields(layer_id)
            if fields is None:
                return
            combo = self._alternative_objects_recording_area_field_combo
            combo.clear()
            combo.addItem(self.tr("-- Select recording area field --"), "")
            for field in fields:
                if self._is_field_compatible_with_recording_area_source(field):
                    combo.addItem(self.tr(f"{field['name']} ({field['type']})"), field['name'])
            if previous:
                index = combo.findData(previous)
                if index >= 0:
                    combo.setCurrentIndex(index)
        except Exception as e:
            self._show_error(self.tr("Field Error"), self.tr(f"Failed to populate alternative objects fields: {str(e)}"))

    def _populate_child_fields(self, layer_id: str, recording_area_combo: QtWidgets.QComboBox, level_combo: QtWidgets.QComboBox) -> None:
        """Populate recording-area and level fields for features/small finds."""
        try:
            previous_recording_area = recording_area_combo.currentData()
            previous_level = level_combo.currentData()
            fields = self._layer_service.get_layer_fields(layer_id)
            if fields is None:
                self._show_error(self.tr("Field Error"), self.tr(f"Could not retrieve fields for layer {layer_id}"))
                return

            recording_area_combo.clear()
            level_combo.clear()
            recording_area_combo.addItem(self.tr("-- Select recording area field --"), "")
            level_combo.addItem(self.tr("-- Select level field --"), "")

            for field in fields:
                display_text = self.tr(f"{field['name']} ({field['type']})")
                if self._is_field_compatible_with_recording_area_source(field):
                    recording_area_combo.addItem(display_text, field['name'])
                if self._is_field_compatible_with_level_type(field):
                    level_combo.addItem(display_text, field['name'])

            if previous_recording_area:
                index = recording_area_combo.findData(previous_recording_area)
                if index >= 0:
                    recording_area_combo.setCurrentIndex(index)
            if previous_level:
                index = level_combo.findData(previous_level)
                if index >= 0:
                    level_combo.setCurrentIndex(index)
        except Exception as e:
            self._show_error(self.tr("Field Error"), self.tr(f"Failed to populate field lists: {str(e)}"))

    def _is_field_compatible_with_recording_area_source(self, field: dict) -> bool:
        """Return True if a field type is compatible with the selected recording_area source."""
        expected_is_integer = self._get_recording_area_source_integer_type()
        if expected_is_integer is None:
            return True
        return bool(field.get('is_integer', False)) == expected_is_integer

    def _is_field_compatible_with_level_type(self, field: dict) -> bool:
        """Return True if a field type matches the selected objects level field type."""
        expected_is_integer = self._get_objects_level_integer_type()
        if expected_is_integer is None:
            return True
        return bool(field.get('is_integer', False)) == expected_is_integer

    def _get_recording_area_source_integer_type(self):
        """Return expected integer type for recording_area source, or None if unconstrained."""
        source = self._recording_area_variable_source_combo.currentData()
        if source == "id":
            return True
        if isinstance(source, str) and source.startswith("field:"):
            source_field_name = source.split(":", 1)[1]
            recording_layer_id = self._recording_areas_widget.combo_box.currentData()
            if not recording_layer_id or not source_field_name:
                return None
            fields = self._layer_service.get_layer_fields(recording_layer_id)
            if not isinstance(fields, list):
                return None
            for field in fields:
                if field.get('name') == source_field_name:
                    return bool(field.get('is_integer', False))
        return None

    def _get_objects_level_integer_type(self):
        """Return selected objects-level field integer type, or None if not constrained."""
        objects_layer_id = self._objects_widget.combo_box.currentData()
        level_field_name = self._level_field_combo.currentData()
        if not objects_layer_id or not level_field_name:
            return None
        fields = self._layer_service.get_layer_fields(objects_layer_id)
        if not isinstance(fields, list):
            return None
        for field in fields:
            if field.get('name') == level_field_name:
                return bool(field.get('is_integer', False))
        return None

    def _refresh_recording_area_field_combos(self) -> None:
        """Refresh recording-area field choices according to selected source type."""
        objects_layer_id = self._objects_widget.combo_box.currentData()
        if objects_layer_id:
            self._populate_objects_fields(objects_layer_id)
        features_layer_id = self._features_widget.combo_box.currentData()
        if features_layer_id:
            self._populate_child_fields(
                features_layer_id,
                self._features_recording_area_field_combo,
                self._features_level_field_combo
            )
        small_finds_layer_id = self._small_finds_widget.combo_box.currentData()
        if small_finds_layer_id:
            self._populate_child_fields(
                small_finds_layer_id,
                self._small_finds_recording_area_field_combo,
                self._small_finds_level_field_combo
            )

    def _refresh_child_level_field_combos(self) -> None:
        """Refresh child level choices according to selected objects-level type."""
        features_layer_id = self._features_widget.combo_box.currentData()
        if features_layer_id:
            self._populate_child_fields(
                features_layer_id,
                self._features_recording_area_field_combo,
                self._features_level_field_combo
            )
        small_finds_layer_id = self._small_finds_widget.combo_box.currentData()
        if small_finds_layer_id:
            self._populate_child_fields(
                small_finds_layer_id,
                self._small_finds_recording_area_field_combo,
                self._small_finds_level_field_combo
            )
    
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

            csv_topo_identifier_column = self._settings_manager.get_value('csv_topo_identifier_column', '')
            self._csv_topo_identifier_column.setText(csv_topo_identifier_column)

            # Load Field Project Archive Folder
            field_project_archive_path = self._settings_manager.get_value('field_project_archive_folder', '')
            self._field_project_archive_widget.input_field.setText(field_project_archive_path)

            
            # Load recording areas layer
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
            self._refresh_layer_list()  # Populate the combo box
            if recording_areas_layer_id:
                index = self._recording_areas_widget.combo_box.findData(recording_areas_layer_id)
                if index >= 0:
                    self._recording_areas_widget.combo_box.setCurrentIndex(index)

            recording_area_variable_source = self._settings_manager.get_value(
                'recording_area_variable_source',
                'display'
            )
            self._refresh_recording_area_variable_source_options()
            variable_source_index = self._recording_area_variable_source_combo.findData(
                recording_area_variable_source
            )
            if variable_source_index >= 0:
                self._recording_area_variable_source_combo.setCurrentIndex(variable_source_index)
            
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
                    recording_area_field = self._settings_manager.get_value('objects_recording_area_field', '')
                    if number_field:
                        index = self._number_field_combo.findData(number_field)
                        if index >= 0:
                            self._number_field_combo.setCurrentIndex(index)
                    if level_field:
                        index = self._level_field_combo.findData(level_field)
                        if index >= 0:
                            self._level_field_combo.setCurrentIndex(index)
                    if recording_area_field:
                        index = self._objects_recording_area_field_combo.findData(recording_area_field)
                        if index >= 0:
                            self._objects_recording_area_field_combo.setCurrentIndex(index)
            
            # Load features layer
            features_layer_id = self._settings_manager.get_value('features_layer', '')
            self._refresh_features_layer_list()  # Populate the combo box
            if features_layer_id:
                index = self._features_widget.combo_box.findData(features_layer_id)
                if index >= 0:
                    self._features_widget.combo_box.setCurrentIndex(index)
                    features_recording_area_field = self._settings_manager.get_value('features_recording_area_field', '')
                    features_level_field = self._settings_manager.get_value('features_level_field', '')
                    if features_recording_area_field:
                        index = self._features_recording_area_field_combo.findData(features_recording_area_field)
                        if index >= 0:
                            self._features_recording_area_field_combo.setCurrentIndex(index)
                    if features_level_field:
                        index = self._features_level_field_combo.findData(features_level_field)
                        if index >= 0:
                            self._features_level_field_combo.setCurrentIndex(index)
            
            # Load alternative objects layer
            alternative_objects_layer_id = self._settings_manager.get_value('alternative_objects_layer', '')
            self._refresh_alternative_objects_layer_list()
            if alternative_objects_layer_id:
                index = self._alternative_objects_widget.combo_box.findData(alternative_objects_layer_id)
                if index >= 0:
                    self._alternative_objects_widget.combo_box.setCurrentIndex(index)
                    alt_recording_field = self._settings_manager.get_value(
                        'alternative_objects_recording_area_field', ''
                    )
                    if alt_recording_field:
                        field_index = self._alternative_objects_recording_area_field_combo.findData(alt_recording_field)
                        if field_index >= 0:
                            self._alternative_objects_recording_area_field_combo.setCurrentIndex(field_index)

            # Load small finds layer
            small_finds_layer_id = self._settings_manager.get_value('small_finds_layer', '')
            self._refresh_small_finds_layer_list()  # Populate the combo box
            if small_finds_layer_id:
                index = self._small_finds_widget.combo_box.findData(small_finds_layer_id)
                if index >= 0:
                    self._small_finds_widget.combo_box.setCurrentIndex(index)
                    small_finds_recording_area_field = self._settings_manager.get_value('small_finds_recording_area_field', '')
                    small_finds_level_field = self._settings_manager.get_value('small_finds_level_field', '')
                    if small_finds_recording_area_field:
                        index = self._small_finds_recording_area_field_combo.findData(small_finds_recording_area_field)
                        if index >= 0:
                            self._small_finds_recording_area_field_combo.setCurrentIndex(index)
                    if small_finds_level_field:
                        index = self._small_finds_level_field_combo.findData(small_finds_level_field)
                        if index >= 0:
                            self._small_finds_level_field_combo.setCurrentIndex(index)
            
            # Load total station points layer
            total_station_points_layer_id = self._settings_manager.get_value('total_station_points_layer', '')
            self._refresh_total_station_points_layer_list()  # Populate the combo box
            if total_station_points_layer_id:
                index = self._total_station_points_widget.combo_box.findData(total_station_points_layer_id)
                if index >= 0:
                    self._total_station_points_widget.combo_box.setCurrentIndex(index)
            

            
            # Load raster clipping offset
            raster_offset = self._settings_manager.get_value('raster_clipping_offset', 0.2)
            self._raster_offset_spinbox.setValue(float(raster_offset))
            
            # Load raster enhancement settings
            brightness = self._settings_manager.get_value('raster_brightness', 0)
            contrast = self._settings_manager.get_value('raster_contrast', 0)
            saturation = self._settings_manager.get_value('raster_saturation', 0)
            self._programmatic_change = True
            self._sliders['Brightness'].setValue(int(brightness))
            self._sliders['Contrast'].setValue(int(contrast))
            self._sliders['Saturation'].setValue(int(saturation))
            self._programmatic_change = False
            
            # Load extra layers for field projects
            extra_layers = self._settings_manager.get_value('extra_field_layers', [])
            self._refresh_extra_layers_list()  # Populate the list
            # Set checked state for extra layers (recording areas handled in refresh)
            for i in range(self._extra_layers_list.count()):
                item = self._extra_layers_list.item(i)
                layer_id = item.data(_user_role_item_data_role())
                if layer_id in extra_layers:
                    item.setCheckState(_checked_check_state())
                elif item.flags() & _item_is_enabled_flag():
                    item.setCheckState(_unchecked_check_state())
            
            # Load warning settings
            self._enable_distance_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_distance_warnings', True)))
            self._distance_max_distance.setValue(_to_float(self._settings_manager.get_value('distance_max_distance', 0.05)))
            self._enable_height_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_height_warnings', True)))
            self._height_max_distance.setValue(_to_float(self._settings_manager.get_value('height_max_distance', 1.0)))
            self._height_max_difference.setValue(_to_float(self._settings_manager.get_value('height_max_difference', 0.2)))
            self._enable_bounds_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_bounds_warnings', True)))
            self._bounds_max_distance.setValue(_to_float(self._settings_manager.get_value('bounds_max_distance', 0.2)))
            self._enable_duplicate_objects_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_duplicate_objects_warnings', True)))
            self._enable_duplicate_total_station_identifiers_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_duplicate_total_station_identifiers_warnings', True)))
            self._enable_skipped_numbers_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_skipped_numbers_warnings', True)))
            self._enable_missing_total_station_warnings.setChecked(_to_bool(self._settings_manager.get_value('enable_missing_total_station_warnings', True)))
            
            # Store original values
            self._original_values = {
                'field_projects_folder': field_projects_path,
                'total_station_folder': total_station_path,
                'completed_projects_folder': completed_projects_path,
                'csv_archive_folder': csv_archive_path,
                'csv_topo_identifier_column': csv_topo_identifier_column,
                'field_project_archive_folder': field_project_archive_path,
                'recording_areas_layer': recording_areas_layer_id,
                'recording_area_variable_source': recording_area_variable_source,
                'objects_layer': objects_layer_id,
                'objects_number_field': self._settings_manager.get_value('objects_number_field', ''),
                'objects_level_field': self._settings_manager.get_value('objects_level_field', ''),
                'objects_recording_area_field': self._settings_manager.get_value('objects_recording_area_field', ''),
                'features_layer': features_layer_id,
                'features_recording_area_field': self._settings_manager.get_value('features_recording_area_field', ''),
                'features_level_field': self._settings_manager.get_value('features_level_field', ''),
                'small_finds_layer': small_finds_layer_id,
                'small_finds_recording_area_field': self._settings_manager.get_value('small_finds_recording_area_field', ''),
                'small_finds_level_field': self._settings_manager.get_value('small_finds_level_field', ''),
                'alternative_objects_layer': alternative_objects_layer_id,
                'alternative_objects_recording_area_field': self._settings_manager.get_value(
                    'alternative_objects_recording_area_field', ''
                ),
                'total_station_points_layer': total_station_points_layer_id,

                'raster_clipping_offset': float(raster_offset),
                'raster_brightness': int(brightness),
                'raster_contrast': int(contrast),
                'raster_saturation': int(saturation),
                'extra_field_layers': extra_layers,
                'enable_distance_warnings': self._settings_manager.get_value('enable_distance_warnings', True),
                'distance_max_distance': self._settings_manager.get_value('distance_max_distance', 0.05),
                'enable_height_warnings': self._settings_manager.get_value('enable_height_warnings', True),
                'height_max_distance': self._settings_manager.get_value('height_max_distance', 1.0),
                'height_max_difference': self._settings_manager.get_value('height_max_difference', 0.2),
                'enable_bounds_warnings': self._settings_manager.get_value('enable_bounds_warnings', True),
                'bounds_max_distance': self._settings_manager.get_value('bounds_max_distance', 0.2),
                'enable_duplicate_objects_warnings': self._settings_manager.get_value('enable_duplicate_objects_warnings', True),
                'enable_duplicate_total_station_identifiers_warnings': self._settings_manager.get_value('enable_duplicate_total_station_identifiers_warnings', True),
                'enable_skipped_numbers_warnings': self._settings_manager.get_value('enable_skipped_numbers_warnings', True),
                'enable_missing_total_station_warnings': self._settings_manager.get_value('enable_missing_total_station_warnings', True),

            }
            
        except Exception as e:
            self._show_error(self.tr("Settings Error"), self.tr(f"Failed to load settings: {str(e)}"))
    
    def _save_and_accept(self) -> None:
        """Save settings and accept the dialog."""
        try:
            # Collect current values
            current_settings = {
                'field_projects_folder': self._field_projects_widget.input_field.text(),
                'total_station_folder': self._total_station_widget.input_field.text(),
                'completed_projects_folder': self._completed_projects_widget.input_field.text(),
                'csv_archive_folder': self._csv_archive_widget.input_field.text(),
                'csv_topo_identifier_column': self._csv_topo_identifier_column.text().strip(),
                'field_project_archive_folder': self._field_project_archive_widget.input_field.text(),
                'recording_areas_layer': self._recording_areas_widget.combo_box.currentData(),
                'recording_area_variable_source': self._recording_area_variable_source_combo.currentData(),
                'objects_layer': self._objects_widget.combo_box.currentData(),
                'objects_number_field': self._number_field_combo.currentData(),
                'objects_level_field': self._level_field_combo.currentData(),
                'objects_recording_area_field': self._objects_recording_area_field_combo.currentData(),
                'features_layer': self._features_widget.combo_box.currentData(),
                'features_recording_area_field': self._features_recording_area_field_combo.currentData(),
                'features_level_field': self._features_level_field_combo.currentData(),
                'small_finds_layer': self._small_finds_widget.combo_box.currentData(),
                'small_finds_recording_area_field': self._small_finds_recording_area_field_combo.currentData(),
                'small_finds_level_field': self._small_finds_level_field_combo.currentData(),
                'alternative_objects_layer': self._alternative_objects_widget.combo_box.currentData(),
                'alternative_objects_recording_area_field': (
                    self._alternative_objects_recording_area_field_combo.currentData()
                ),
                'total_station_points_layer': self._total_station_points_widget.combo_box.currentData(),

                'raster_clipping_offset': self._raster_offset_spinbox.value(),
                'raster_brightness': self._sliders['Brightness'].value(),
                'raster_contrast': self._sliders['Contrast'].value(),
                'raster_saturation': self._sliders['Saturation'].value(),
                'extra_field_layers': self._get_selected_extra_layers(),
                'enable_distance_warnings': self._enable_distance_warnings.isChecked(),
                'distance_max_distance': self._distance_max_distance.value(),
                'enable_height_warnings': self._enable_height_warnings.isChecked(),
                'height_max_distance': self._height_max_distance.value(),
                'height_max_difference': self._height_max_difference.value(),
                'enable_bounds_warnings': self._enable_bounds_warnings.isChecked(),
                'bounds_max_distance': self._bounds_max_distance.value(),
                'enable_duplicate_objects_warnings': self._enable_duplicate_objects_warnings.isChecked(),
                'enable_duplicate_total_station_identifiers_warnings': self._enable_duplicate_total_station_identifiers_warnings.isChecked(),
                'enable_skipped_numbers_warnings': self._enable_skipped_numbers_warnings.isChecked(),
                'enable_missing_total_station_warnings': self._enable_missing_total_station_warnings.isChecked(),

            }
            
            # Validate settings
            validation_results = self._configuration_validator.validate_all_settings(current_settings)
            
            if self._configuration_validator.has_validation_errors(validation_results):
                errors = self._configuration_validator.get_all_errors(validation_results)
                error_message = "\n".join(errors)
                self._show_error(self.tr("Validation Error"), self.tr(f"Please fix the following issues:\n\n{error_message}"))
                return
            
            # Save settings
            for key, value in current_settings.items():
                self._settings_manager.set_value(key, value)
            
            self.accept()
            
        except Exception as e:
            self._show_error(self.tr("Settings Error"), self.tr(f"Failed to save settings: {str(e)}"))
    
    def _reject(self) -> None:
        """Handle dialog rejection by resetting to original values."""
        try:
            # Reset raster enhancement settings to original values
            brightness = self._original_values.get('raster_brightness', 0)
            contrast = self._original_values.get('raster_contrast', 0)
            saturation = self._original_values.get('raster_saturation', 0)
            self._programmatic_change = True
            self._sliders['Brightness'].setValue(int(brightness))
            self._sliders['Contrast'].setValue(int(contrast))
            self._sliders['Saturation'].setValue(int(saturation))
            self._programmatic_change = False
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
            self._csv_topo_identifier_column.setText(
                self._original_values.get('csv_topo_identifier_column', '')
            )
            self._field_project_archive_widget.input_field.setText(
                self._original_values.get('field_project_archive_folder', '')
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

            recording_area_variable_source = self._original_values.get('recording_area_variable_source', 'display')
            self._refresh_recording_area_variable_source_options()
            variable_source_index = self._recording_area_variable_source_combo.findData(recording_area_variable_source)
            self._recording_area_variable_source_combo.setCurrentIndex(variable_source_index if variable_source_index >= 0 else 0)
            
            # Revert objects layer selection
            objects_layer_id = self._original_values.get('objects_layer', '')
            if objects_layer_id:
                index = self._objects_widget.combo_box.findData(objects_layer_id)
                if index >= 0:
                    self._objects_widget.combo_box.setCurrentIndex(index)
                    # Revert field selections
                    number_field = self._original_values.get('objects_number_field', '')
                    level_field = self._original_values.get('objects_level_field', '')
                    recording_area_field = self._original_values.get('objects_recording_area_field', '')
                    if number_field:
                        index = self._number_field_combo.findData(number_field)
                        if index >= 0:
                            self._number_field_combo.setCurrentIndex(index)
                    if level_field:
                        index = self._level_field_combo.findData(level_field)
                        if index >= 0:
                            self._level_field_combo.setCurrentIndex(index)
                    if recording_area_field:
                        index = self._objects_recording_area_field_combo.findData(recording_area_field)
                        if index >= 0:
                            self._objects_recording_area_field_combo.setCurrentIndex(index)
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
                    features_recording_area_field = self._original_values.get('features_recording_area_field', '')
                    features_level_field = self._original_values.get('features_level_field', '')
                    if features_recording_area_field:
                        index = self._features_recording_area_field_combo.findData(features_recording_area_field)
                        if index >= 0:
                            self._features_recording_area_field_combo.setCurrentIndex(index)
                    if features_level_field:
                        index = self._features_level_field_combo.findData(features_level_field)
                        if index >= 0:
                            self._features_level_field_combo.setCurrentIndex(index)
                else:
                    self._features_widget.combo_box.setCurrentIndex(0)
            else:
                self._features_widget.combo_box.setCurrentIndex(0)
            
            # Revert small finds layer selection
            small_finds_layer_id = self._original_values.get('small_finds_layer', '')
            if small_finds_layer_id:
                index = self._small_finds_widget.combo_box.findData(small_finds_layer_id)
                if index >= 0:
                    self._small_finds_widget.combo_box.setCurrentIndex(index)
                    small_finds_recording_area_field = self._original_values.get('small_finds_recording_area_field', '')
                    small_finds_level_field = self._original_values.get('small_finds_level_field', '')
                    if small_finds_recording_area_field:
                        index = self._small_finds_recording_area_field_combo.findData(small_finds_recording_area_field)
                        if index >= 0:
                            self._small_finds_recording_area_field_combo.setCurrentIndex(index)
                    if small_finds_level_field:
                        index = self._small_finds_level_field_combo.findData(small_finds_level_field)
                        if index >= 0:
                            self._small_finds_level_field_combo.setCurrentIndex(index)
                else:
                    self._small_finds_widget.combo_box.setCurrentIndex(0)
            else:
                self._small_finds_widget.combo_box.setCurrentIndex(0)
            
            # Revert total station points layer selection
            total_station_points_layer_id = self._original_values.get('total_station_points_layer', '')
            if total_station_points_layer_id:
                index = self._total_station_points_widget.combo_box.findData(total_station_points_layer_id)
                if index >= 0:
                    self._total_station_points_widget.combo_box.setCurrentIndex(index)
                else:
                    self._total_station_points_widget.combo_box.setCurrentIndex(0)
            else:
                self._total_station_points_widget.combo_box.setCurrentIndex(0)
            
            # Revert warning settings
            self._enable_distance_warnings.setChecked(_to_bool(self._original_values.get('enable_distance_warnings', True)))
            self._distance_max_distance.setValue(_to_float(self._original_values.get('distance_max_distance', 0.05)))
            
            self._enable_height_warnings.setChecked(_to_bool(self._original_values.get('enable_height_warnings', True)))
            self._height_max_distance.setValue(_to_float(self._original_values.get('height_max_distance', 1.0)))
            self._height_max_difference.setValue(_to_float(self._original_values.get('height_max_difference', 0.2)))
            
            self._enable_bounds_warnings.setChecked(_to_bool(self._original_values.get('enable_bounds_warnings', True)))
            self._bounds_max_distance.setValue(_to_float(self._original_values.get('bounds_max_distance', 0.2)))
            self._enable_duplicate_objects_warnings.setChecked(_to_bool(self._original_values.get('enable_duplicate_objects_warnings', True)))
            self._enable_duplicate_total_station_identifiers_warnings.setChecked(_to_bool(self._original_values.get('enable_duplicate_total_station_identifiers_warnings', True)))
            self._enable_skipped_numbers_warnings.setChecked(_to_bool(self._original_values.get('enable_skipped_numbers_warnings', True)))
            self._enable_missing_total_station_warnings.setChecked(_to_bool(self._original_values.get('enable_missing_total_station_warnings', True)))
            
            # Revert settings in manager
            for key, value in self._original_values.items():
                self._settings_manager.set_value(key, value)
                
        except Exception as e:
            self._show_error(self.tr("Settings Error"), self.tr(f"Failed to revert settings: {str(e)}"))
        
        super().reject()
    
    def _show_error(self, title: str, message: str) -> None:
        """Show an error message to the user."""
        QtWidgets.QMessageBox.critical(self, self.tr(title), self.tr(message)) 

        