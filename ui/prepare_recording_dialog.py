"""
Prepare recording dialog for ArcheoSync plugin.

This module provides a dialog for preparing recording data, showing the number
of selected entities in the Recording areas layer.

Key Features:
- Display selected features count from Recording areas layer
- Clean, simple interface
- Integration with layer service for real-time data

Architecture Benefits:
- Single Responsibility: Only handles recording preparation UI
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add more recording preparation features

Usage:
    layer_service = QGISLayerService()
    settings_manager = QGISSettingsManager()
    
    dialog = PrepareRecordingDialog(
        layer_service=layer_service,
        settings_manager=settings_manager,
        parent=parent_widget
    )
    
    if dialog.exec() == QDialog.Accepted:
        # Recording preparation was confirmed
        pass
"""

from typing import Optional, List, Dict, Any, Tuple
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, QTimer

try:
    from ..core.interfaces import ILayerService, ISettingsManager
    from ..core.ui_responsiveness import maybe_yield_to_ui
except ImportError:
    from core.interfaces import ILayerService, ISettingsManager
    from core.ui_responsiveness import maybe_yield_to_ui


def _align_center_flag():
    """Return a center-alignment flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "AlignCenter"):
        return Qt.AlignCenter
    alignment_flag = getattr(Qt, "AlignmentFlag", None)
    if alignment_flag is not None and hasattr(alignment_flag, "AlignCenter"):
        return alignment_flag.AlignCenter
    raise AttributeError("Qt center alignment flag is not available.")


def _horizontal_orientation():
    """Return horizontal orientation flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "Horizontal"):
        return Qt.Horizontal
    orientation = getattr(Qt, "Orientation", None)
    if orientation is not None and hasattr(orientation, "Horizontal"):
        return orientation.Horizontal
    raise AttributeError("Qt horizontal orientation flag is not available.")


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
    """Return QDialogButtonBox OK identifier compatible with Qt5 and Qt6."""
    button_box = QtWidgets.QDialogButtonBox
    if hasattr(button_box, "Ok"):
        return button_box.Ok
    standard_button = getattr(button_box, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Ok"):
        return standard_button.Ok
    raise AttributeError("QDialogButtonBox OK button identifier is not available.")


def _dialog_button_cancel():
    """Return QDialogButtonBox Cancel identifier compatible with Qt5 and Qt6."""
    button_box = QtWidgets.QDialogButtonBox
    if hasattr(button_box, "Cancel"):
        return button_box.Cancel
    standard_button = getattr(button_box, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Cancel"):
        return standard_button.Cancel
    raise AttributeError("QDialogButtonBox Cancel button identifier is not available.")


def _select_rows_behavior():
    """Return SelectRows behavior compatible with Qt5 and Qt6."""
    item_view = QtWidgets.QAbstractItemView
    if hasattr(item_view, "SelectRows"):
        return item_view.SelectRows
    selection_behavior = getattr(item_view, "SelectionBehavior", None)
    if selection_behavior is not None and hasattr(selection_behavior, "SelectRows"):
        return selection_behavior.SelectRows
    raise AttributeError("QAbstractItemView SelectRows behavior is not available.")


def _edit_triggers_flags():
    """Return edit trigger flags compatible with Qt5 and Qt6."""
    item_view = QtWidgets.QAbstractItemView
    if hasattr(item_view, "DoubleClicked") and hasattr(item_view, "EditKeyPressed"):
        return item_view.DoubleClicked | item_view.EditKeyPressed
    edit_trigger = getattr(item_view, "EditTrigger", None)
    if edit_trigger is not None and hasattr(edit_trigger, "DoubleClicked") and hasattr(edit_trigger, "EditKeyPressed"):
        return edit_trigger.DoubleClicked | edit_trigger.EditKeyPressed
    raise AttributeError("QAbstractItemView edit trigger flags are not available.")


def _item_is_editable_flag():
    """Return ItemIsEditable flag compatible with Qt5 and Qt6."""
    if hasattr(Qt, "ItemIsEditable"):
        return Qt.ItemIsEditable
    item_flag = getattr(Qt, "ItemFlag", None)
    if item_flag is not None and hasattr(item_flag, "ItemIsEditable"):
        return item_flag.ItemIsEditable
    raise AttributeError("Qt ItemIsEditable flag is not available.")


PREPARATION_MODE_RECORDING_AREA = "recording_area"
PREPARATION_MODE_GLOBAL = "global"
EXTENT_SOURCE_MANUAL = "manual"
EXTENT_SOURCE_LAYER = "layer"


class PrepareRecordingDialog(QtWidgets.QDialog):
    """
    Dialog for preparing recording data.
    
    All user-facing strings are wrapped in self.tr() for translation.
    """
    
    def __init__(self, 
                 layer_service: ILayerService,
                 settings_manager: ISettingsManager,
                 parent=None):
        """
        Initialize the prepare recording dialog.
        
        Args:
            layer_service: Service for QGIS layer operations
            settings_manager: Service for managing settings
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._layer_service = layer_service
        self._settings_manager = settings_manager
        self._selected_entity_count = 0
        self._selected_count_update_scheduled = False
        
        # Initialize UI
        self._setup_ui()
        self._schedule_selected_count_update()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle(self.tr("Prepare Recording"))
        self.setGeometry(0, 0, 520, 480)
        self.setModal(True)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel(self.tr("Prepare Recording"))
        title_label.setAlignment(_align_center_flag())
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        self._create_mode_selector(main_layout)
        self._create_info_section(main_layout)
        self._create_global_section(main_layout)
        self._create_button_box(main_layout)
        self._on_preparation_mode_changed()

    def _create_mode_selector(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create preparation mode radio buttons."""
        mode_group_box = QtWidgets.QGroupBox(self.tr("Preparation Mode"))
        mode_layout = QtWidgets.QVBoxLayout(mode_group_box)

        self._mode_recording_area_radio = QtWidgets.QRadioButton(self.tr("Per recording area"))
        self._mode_global_radio = QtWidgets.QRadioButton(self.tr("Global project"))
        self._mode_recording_area_radio.setChecked(True)

        self._mode_button_group = QtWidgets.QButtonGroup(self)
        self._mode_button_group.addButton(self._mode_recording_area_radio)
        self._mode_button_group.addButton(self._mode_global_radio)

        mode_layout.addWidget(self._mode_recording_area_radio)
        mode_layout.addWidget(self._mode_global_radio)
        self._mode_recording_area_radio.toggled.connect(self._on_preparation_mode_changed)
        parent_layout.addWidget(mode_group_box)
    
    def _create_info_section(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the per-recording-area information display section."""
        info_group = QtWidgets.QGroupBox(self.tr("Recording Areas Information"))
        self._zone_group = info_group
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        # Recording areas layer info
        self._recording_areas_label = QtWidgets.QLabel(self.tr("Recording Areas Layer: Not configured"))
        info_layout.addWidget(self._recording_areas_label)
        
        # Selected features count
        self._selected_count_label = QtWidgets.QLabel(self.tr("Selected Entities: 0"))
        self._selected_count_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2E86AB;")
        info_layout.addWidget(self._selected_count_label)
        
        # Create table for selected entities
        self._create_entities_table(info_layout)
        
        # Instructions
        instructions = QtWidgets.QLabel(
            self.tr("To prepare recording:\n1. Select entities in the Recording areas layer\n2. Click 'Prepare Recording' to continue")
        )
        instructions.setStyleSheet("color: #666; margin-top: 10px;")
        info_layout.addWidget(instructions)
        
        parent_layout.addWidget(info_group)

    def _create_global_section(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the global project preparation section."""
        global_group = QtWidgets.QGroupBox(self.tr("Global Project"))
        self._global_group = global_group
        layout = QtWidgets.QVBoxLayout(global_group)

        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel(self.tr("Project name:")))
        self._global_project_name_edit = QtWidgets.QLineEdit()
        self._global_project_name_edit.textChanged.connect(self._update_ok_button_state)
        name_layout.addWidget(self._global_project_name_edit)
        layout.addLayout(name_layout)

        extent_group = QtWidgets.QGroupBox(self.tr("Extent"))
        extent_layout = QtWidgets.QVBoxLayout(extent_group)

        self._extent_manual_radio = QtWidgets.QRadioButton(self.tr("Enter coordinates"))
        self._extent_layer_radio = QtWidgets.QRadioButton(self.tr("From map layer"))
        self._extent_manual_radio.setChecked(True)
        extent_layout.addWidget(self._extent_manual_radio)
        extent_layout.addWidget(self._extent_layer_radio)

        manual_widget = QtWidgets.QWidget()
        manual_layout = QtWidgets.QFormLayout(manual_widget)
        self._extent_xmin = QtWidgets.QDoubleSpinBox()
        self._extent_ymin = QtWidgets.QDoubleSpinBox()
        self._extent_xmax = QtWidgets.QDoubleSpinBox()
        self._extent_ymax = QtWidgets.QDoubleSpinBox()
        for spin in (self._extent_xmin, self._extent_ymin, self._extent_xmax, self._extent_ymax):
            spin.setDecimals(6)
            spin.setRange(-1e12, 1e12)
            spin.valueChanged.connect(self._update_ok_button_state)
        manual_layout.addRow(self.tr("X min:"), self._extent_xmin)
        manual_layout.addRow(self.tr("Y min:"), self._extent_ymin)
        manual_layout.addRow(self.tr("X max:"), self._extent_xmax)
        manual_layout.addRow(self.tr("Y max:"), self._extent_ymax)
        extent_layout.addWidget(manual_widget)
        self._extent_manual_widget = manual_widget

        layer_widget = QtWidgets.QWidget()
        layer_layout = QtWidgets.QHBoxLayout(layer_widget)
        layer_layout.addWidget(QtWidgets.QLabel(self.tr("Layer:")))
        self._extent_layer_combo = QtWidgets.QComboBox()
        self._refresh_extent_layer_combo()
        self._extent_layer_combo.currentIndexChanged.connect(self._update_ok_button_state)
        layer_layout.addWidget(self._extent_layer_combo)
        extent_layout.addWidget(layer_widget)
        self._extent_layer_widget = layer_widget
        self._extent_layer_widget.setVisible(False)

        self._extent_manual_radio.toggled.connect(self._on_extent_source_changed)
        self._extent_layer_radio.toggled.connect(self._on_extent_source_changed)

        help_label = QtWidgets.QLabel(
            self.tr(
                "If the layer has a selection, the extent is the union of selected "
                "geometries; otherwise the union of all features on that layer."
            )
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666;")
        extent_layout.addWidget(help_label)
        layout.addWidget(extent_group)

        self._global_context_label = QtWidgets.QLabel()
        self._global_context_label.setWordWrap(True)
        self._global_context_label.setStyleSheet("color: #666;")
        layout.addWidget(self._global_context_label)
        self._refresh_global_context_label()

        parent_layout.addWidget(global_group)

    def _refresh_extent_layer_combo(self) -> None:
        """Populate extent layer combo with vector layers from the project."""
        current = self._extent_layer_combo.currentData() if hasattr(self, "_extent_layer_combo") else None
        self._extent_layer_combo.clear()
        self._extent_layer_combo.addItem(self.tr("-- Select a layer --"), "")
        for layer_info in self._layer_service.get_vector_layers():
            self._extent_layer_combo.addItem(layer_info['name'], layer_info['id'])
        if current:
            index = self._extent_layer_combo.findData(current)
            if index >= 0:
                self._extent_layer_combo.setCurrentIndex(index)

    def _refresh_global_context_label(self) -> None:
        """Show read-only context about extra and alternative layers."""
        extra_layers = self._settings_manager.get_value('extra_field_layers', []) or []
        extra_names = []
        for layer_id in extra_layers:
            info = self._layer_service.get_layer_info(layer_id)
            if info:
                extra_names.append(info['name'])
        alt_layer_id = self._settings_manager.get_value('alternative_objects_layer', '')
        alt_text = ""
        if alt_layer_id:
            alt_info = self._layer_service.get_layer_info(alt_layer_id)
            if alt_info:
                alt_text = self.tr("Alternative objects layer: {name}").format(name=alt_info['name'])
        extras_text = ", ".join(extra_names) if extra_names else self.tr("(none)")
        self._global_context_label.setText(
            self.tr("Read-only context layers: {extras}\n{alt}").format(
                extras=extras_text,
                alt=alt_text,
            )
        )

    def _on_preparation_mode_changed(self) -> None:
        """Toggle UI between per-area and global preparation."""
        is_global = self._mode_global_radio.isChecked()
        self._zone_group.setVisible(not is_global)
        self._global_group.setVisible(is_global)
        if is_global:
            self._refresh_extent_layer_combo()
            self._refresh_global_context_label()
        else:
            self._schedule_selected_count_update()
        self._update_ok_button_state()

    def _on_extent_source_changed(self) -> None:
        """Toggle manual vs layer extent widgets."""
        manual = self._extent_manual_radio.isChecked()
        self._extent_manual_widget.setVisible(manual)
        self._extent_layer_widget.setVisible(not manual)
        self._update_ok_button_state()

    def _update_ok_button_state(self) -> None:
        """Enable the OK button when the current mode has valid inputs."""
        ok_button = self._button_box.button(_dialog_button_ok())
        if self._mode_global_radio.isChecked():
            has_name = bool(self._global_project_name_edit.text().strip())
            has_extent = self._global_extent_is_valid()
            ok_button.setVisible(True)
            ok_button.setEnabled(has_name and has_extent)
            ok_button.setText(self.tr("Prepare Global Project"))
            return
        self._update_recording_area_ok_button_state()

    def _schedule_selected_count_update(self) -> None:
        """Defer per-recording-area preparation so the dialog can paint first."""
        if self._selected_count_update_scheduled:
            return
        self._selected_count_update_scheduled = True
        self._selected_count_label.setText(self.tr("Selected Entities: …"))
        QTimer.singleShot(0, self._run_selected_count_update)

    def _run_selected_count_update(self) -> None:
        """Run the deferred selected-entity refresh."""
        self._selected_count_update_scheduled = False
        self._update_selected_count()

    def _update_recording_area_ok_button_state(self) -> None:
        """Enable the OK button from the last known recording-area selection count."""
        ok_button = self._button_box.button(_dialog_button_ok())
        has_selection = self._selected_entity_count > 0
        if has_selection:
            ok_button.setVisible(True)
            ok_button.setEnabled(True)
            ok_button.setText(self.tr("Prepare Recording"))
        else:
            ok_button.setVisible(False)
            ok_button.setEnabled(False)

    def _global_extent_is_valid(self) -> bool:
        """Return True when global extent inputs are valid."""
        if self._extent_layer_radio.isChecked():
            return bool(self._extent_layer_combo.currentData())
        xmin = self._extent_xmin.value()
        ymin = self._extent_ymin.value()
        xmax = self._extent_xmax.value()
        ymax = self._extent_ymax.value()
        return xmin < xmax and ymin < ymax

    def get_preparation_mode(self) -> str:
        """Return the selected preparation mode identifier."""
        if self._mode_global_radio.isChecked():
            return PREPARATION_MODE_GLOBAL
        return PREPARATION_MODE_RECORDING_AREA

    def get_global_project_options(self) -> Dict[str, Any]:
        """
        Return global project options entered in the dialog.

        Returns:
            Dictionary with project_name, extent_source, extent_geometry_wkt, extent_layer_id
        """
        options = {
            'project_name': self._global_project_name_edit.text().strip(),
            'extent_source': EXTENT_SOURCE_LAYER if self._extent_layer_radio.isChecked() else EXTENT_SOURCE_MANUAL,
            'extent_geometry_wkt': '',
            'extent_layer_id': '',
            'manual_bounds': None,
        }
        if options['extent_source'] == EXTENT_SOURCE_LAYER:
            options['extent_layer_id'] = self._extent_layer_combo.currentData() or ''
        else:
            options['manual_bounds'] = {
                'xmin': self._extent_xmin.value(),
                'ymin': self._extent_ymin.value(),
                'xmax': self._extent_xmax.value(),
                'ymax': self._extent_ymax.value(),
            }
        return options
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        self._button_box = QtWidgets.QDialogButtonBox(
            _dialog_button_ok_cancel(),
            _horizontal_orientation(),
            self
        )
        
        # Connect button signals
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        
        # Set button texts for translation
        self._button_box.button(_dialog_button_cancel()).setText(self.tr("Cancel"))
        
        # Initially hide the OK button - it will be shown when features are selected
        self._button_box.button(_dialog_button_ok()).setVisible(False)
        
        parent_layout.addWidget(self._button_box)
    
    def _create_entities_table(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the table for displaying selected entities."""
        # Create table widget
        self._entities_table = QtWidgets.QTableWidget()
        
        # Get configuration to determine which columns to show
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        number_field = self._settings_manager.get_value('objects_number_field', '')
        level_field = self._settings_manager.get_value('objects_level_field', '')
        
        # Set up columns
        columns = [self.tr("Name")]
        if objects_layer_id and number_field:
            columns.append(self.tr("Last object number"))
            columns.append(self.tr("Next object number"))
        if objects_layer_id and level_field:
            columns.append(self.tr("Last level"))
            columns.append(self.tr("Next level"))
        # Always add Background image column
        columns.append(self.tr("Background image"))
        
        self._entities_table.setColumnCount(len(columns))
        self._entities_table.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self._entities_table.setAlternatingRowColors(True)
        self._entities_table.setSelectionBehavior(_select_rows_behavior())
        # Allow editing for next number and next level columns
        self._entities_table.setEditTriggers(_edit_triggers_flags())
        self._entities_table.horizontalHeader().setStretchLastSection(True)
        self._entities_table.setMaximumHeight(200)
        
        # Add table to layout
        parent_layout.addWidget(self._entities_table)
    
    def _update_selected_count(self) -> None:
        """Update the display with current selected features count and table."""
        try:
            # Get the recording areas layer ID from settings
            recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
            
            if not recording_areas_layer_id:
                self._recording_areas_label.setText(self.tr("Recording Areas Layer: Not configured"))
                self._selected_count_label.setText(self.tr("Selected Entities: 0"))
                self._populate_entities_table([])
                self._button_box.button(_dialog_button_ok()).setVisible(False)
                return
            
            # Get layer info
            layer_info = self._layer_service.get_layer_info(recording_areas_layer_id)
            if layer_info is None:
                self._recording_areas_label.setText(self.tr("Recording Areas Layer: Layer not found"))
                self._selected_count_label.setText(self.tr("Selected Entities: 0"))
                self._populate_entities_table([])
                self._button_box.button(_dialog_button_ok()).setVisible(False)
                return
            
            # Update layer name
            self._recording_areas_label.setText(self.tr("Recording Areas Layer: {name}").format(name=layer_info['name']))
            
            # Get the actual layer to access selected features
            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_layer is None:
                self._recording_areas_label.setText(self.tr("Recording Areas Layer: Layer not found"))
                self._selected_count_label.setText(self.tr("Selected Entities: 0"))
                self._populate_entities_table([])
                self._button_box.button(_dialog_button_ok()).setVisible(False)
                return
            
            # Get selected features
            selected_features = recording_layer.selectedFeatures()
            selected_count = len(selected_features)
            self._selected_entity_count = selected_count
            
            # Update count label
            self._selected_count_label.setText(self.tr(f"Selected Entities: {selected_count}"))
            
            # Populate table with actual features
            self._populate_entities_table(selected_features)
            
            self._update_recording_area_ok_button_state()
                
        except Exception as e:
            print("PrepareRecordingDialog error:", e)
            self._recording_areas_label.setText(self.tr("Recording Areas Layer: Error"))
            self._selected_count_label.setText(self.tr("Selected Entities: Error"))
            self._populate_entities_table([])
            self._button_box.button(_dialog_button_ok()).setVisible(False)
    
    def _populate_entities_table(self, features) -> None:
        """Populate the entities table with feature information."""
        # Clear existing rows
        self._entities_table.setRowCount(0)
        
        # Get configuration
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        number_field = self._settings_manager.get_value('objects_number_field', '')
        level_field = self._settings_manager.get_value('objects_level_field', '')
        
        # Get the recording areas layer for display expression
        recording_areas_layer_id = self._settings_manager.get_value('recording_areas_layer', '')
        recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id) if recording_areas_layer_id else None
        related_features_cache: Dict[Tuple[str, int], List[Any]] = {}
        project_rasters = self._layer_service.get_raster_layers() if recording_areas_layer_id else []
        
        # Add features to table
        for feature in features:
            maybe_yield_to_ui(every=1)
            row = self._entities_table.rowCount()
            self._entities_table.insertRow(row)
            
            # Get feature name
            feature_name = str(feature.id())
            
            # Try to get name from display expression
            if recording_layer:
                expr_str = recording_layer.displayExpression()
                if expr_str:
                    from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
                    expr = QgsExpression(expr_str)
                    context = QgsExpressionContext()
                    context.appendScope(QgsExpressionContextUtils.layerScope(recording_layer))
                    context.setFeature(feature)
                    try:
                        result = expr.evaluate(context)
                        if result and str(result) != 'NULL':
                            feature_name = str(result)
                    except:
                        pass
                
                # Try to get name from common name fields
                if feature_name == str(feature.id()):
                    name_fields = ['name', 'title', 'label', 'description', 'comment']
                    for field_name in name_fields:
                        field_idx = recording_layer.fields().indexOf(field_name)
                        if field_idx >= 0:
                            value = feature.attribute(field_idx)
                            if value and str(value) != 'NULL':
                                feature_name = str(value)
                                break
            
            # Add name to the table
            name_item = QtWidgets.QTableWidgetItem(feature_name)
            name_item.setFlags(name_item.flags() & ~_item_is_editable_flag())  # Make read-only
            self._entities_table.setItem(row, 0, name_item)
            
            # Add related objects information if configured
            col_index = 1
            
            if objects_layer_id and number_field:
                # Get related objects info
                related_info = self._layer_service.get_related_objects_info(
                    feature,
                    objects_layer_id,
                    number_field,
                    level_field,
                    recording_areas_layer_id,
                    related_features_cache=related_features_cache,
                    unfiltered=True,
                )
                
                # Add last number
                number_item = QtWidgets.QTableWidgetItem(related_info['last_number'])
                number_item.setFlags(number_item.flags() & ~_item_is_editable_flag())  # Make read-only
                self._entities_table.setItem(row, col_index, number_item)
                col_index += 1
                
                # Add first number (editable)
                first_number = '1'  # Default value
                if related_info['last_number']:
                    try:
                        last_num = int(related_info['last_number'])
                        first_number = str(last_num + 1)
                    except (ValueError, TypeError):
                        first_number = '1'
                
                first_number_item = QtWidgets.QTableWidgetItem(first_number)
                self._entities_table.setItem(row, col_index, first_number_item)
                col_index += 1
            
            if objects_layer_id and level_field:
                # Get related objects info (if not already done)
                if not (objects_layer_id and number_field):
                    related_info = self._layer_service.get_related_objects_info(
                        feature,
                        objects_layer_id,
                        number_field,
                        level_field,
                        recording_areas_layer_id,
                        related_features_cache=related_features_cache,
                        unfiltered=True,
                    )
                highest_last_level = self._get_highest_last_level_across_configured_layers(
                    feature=feature,
                    recording_areas_layer_id=recording_areas_layer_id,
                    default_last_level=related_info['last_level'],
                    related_features_cache=related_features_cache,
                )
                
                # Add last level
                level_item = QtWidgets.QTableWidgetItem(highest_last_level)
                level_item.setFlags(level_item.flags() & ~_item_is_editable_flag())  # Make read-only
                self._entities_table.setItem(row, col_index, level_item)
                col_index += 1
                
                # Add level (editable)
                level = self._layer_service.calculate_next_level(
                    highest_last_level, level_field, objects_layer_id
                )
                level_item = QtWidgets.QTableWidgetItem(level)
                self._entities_table.setItem(row, col_index, level_item)
                col_index += 1
            
            # Add background image dropdown
            self._add_background_image_dropdown(
                row,
                col_index,
                feature,
                recording_areas_layer_id,
                project_rasters=project_rasters,
            )
        
        # Resize columns to content
        self._entities_table.resizeColumnsToContents()

    def _get_highest_last_level_across_configured_layers(
        self,
        feature,
        recording_areas_layer_id: str,
        default_last_level: str,
        related_features_cache: Optional[Dict[Tuple[str, int], List[Any]]] = None,
    ) -> str:
        """
        Return highest last level among configured objects/features/small_finds layers.

        When multiple layers contribute level values, preparation must continue from the
        highest already-used level across all configured layers.
        """
        layer_settings = [
            ("objects_layer", "objects_level_field"),
            ("features_layer", "features_level_field"),
            ("small_finds_layer", "small_finds_level_field"),
        ]
        level_values: List[str] = []

        for layer_setting_key, level_setting_key in layer_settings:
            layer_id = self._settings_manager.get_value(layer_setting_key, '')
            configured_level_field = self._settings_manager.get_value(level_setting_key, '')
            if not layer_id or not configured_level_field:
                continue
            layer_info = self._layer_service.get_related_objects_info(
                feature,
                layer_id,
                None,
                configured_level_field,
                recording_areas_layer_id,
                related_features_cache=related_features_cache,
                unfiltered=(layer_setting_key == 'objects_layer'),
            )
            last_level = str(layer_info.get('last_level', '') or '')
            if last_level:
                level_values.append(last_level)

        if not level_values:
            return default_last_level
        return max(level_values)
    
    def _add_background_image_dropdown(
        self,
        row: int,
        col: int,
        feature,
        recording_areas_layer_id: str,
        project_rasters: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add a background image dropdown widget to the specified table cell.
        
        Args:
            row: Table row index
            col: Table column index
            feature: The feature to get overlapping raster layers for
            recording_areas_layer_id: The recording areas layer ID
            project_rasters: Optional precomputed raster metadata for the project
        """
        # Create combo box widget
        combo_box = QtWidgets.QComboBox()
        
        # Add "No image" option
        combo_box.addItem("No image", "")
        
        # Get overlapping raster layers
        if recording_areas_layer_id:
            overlapping_raster_layers = self._filter_rasters_overlapping_feature(
                feature,
                project_rasters or [],
            )
            
            # Add raster layers to dropdown
            for raster_layer in overlapping_raster_layers:
                display_text = f"{raster_layer['name']} ({raster_layer['width']}x{raster_layer['height']})"
                combo_box.addItem(display_text, raster_layer['id'])
        
        # Set the combo box as the cell widget
        self._entities_table.setCellWidget(row, col, combo_box)

    def _filter_rasters_overlapping_feature(
        self,
        feature,
        project_rasters: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return raster layers whose extent intersects the feature bounding box."""
        feature_geometry = feature.geometry()
        if not feature_geometry:
            return []

        feature_extent = feature_geometry.boundingBox()
        overlapping = []
        for raster_layer in project_rasters:
            raster_extent = raster_layer.get('extent')
            if raster_extent is None:
                continue
            if feature_extent.intersects(raster_extent):
                overlapping.append(raster_layer)
        return overlapping
    
    def get_next_values_for_feature(self, feature_index: int) -> Dict[str, str]:
        """
        Get the first object number, level, and background image values for a specific feature.
        
        Args:
            feature_index: The index of the feature in the features list
            
        Returns:
            Dictionary with 'first_number', 'level', and 'background_image' values
        """
        if feature_index >= self._entities_table.rowCount():
            return {'first_number': '', 'level': '', 'background_image': ''}
        
        # Get configuration
        objects_layer_id = self._settings_manager.get_value('objects_layer', '')
        number_field = self._settings_manager.get_value('objects_number_field', '')
        level_field = self._settings_manager.get_value('objects_level_field', '')
        
        result = {'first_number': '', 'level': '', 'background_image': ''}
        
        # Get first number if configured
        if objects_layer_id and number_field:
            # Find the first number column (should be column 2 if both number and level are configured)
            col_index = 1  # Start after Name column
            if objects_layer_id and number_field:
                col_index += 1  # Skip last number column
                if col_index < self._entities_table.columnCount():
                    item = self._entities_table.item(feature_index, col_index)
                    if item:
                        result['first_number'] = item.text()
        
        # Get level if configured
        if objects_layer_id and level_field:
            # Find the level column
            col_index = 1  # Start after Name column
            if objects_layer_id and number_field:
                col_index += 2  # Skip last number and first number columns
            if objects_layer_id and level_field:
                col_index += 1  # Skip last level column
                if col_index < self._entities_table.columnCount():
                    item = self._entities_table.item(feature_index, col_index)
                    if item:
                        result['level'] = item.text()
        
        # Get background image (always the last column)
        background_col = self._entities_table.columnCount() - 1
        if background_col >= 0:
            widget = self._entities_table.cellWidget(feature_index, background_col)
            if isinstance(widget, QtWidgets.QComboBox):
                background_data = widget.currentData()
                result['background_image'] = background_data if background_data is not None else ''
        
        return result
    
    def get_all_next_values(self) -> List[Dict[str, str]]:
        """
        Get the first object number, level, and background image values for all features.
        
        Returns:
            List of dictionaries with 'first_number', 'level', and 'background_image' values for each feature
        """
        results = []
        for row in range(self._entities_table.rowCount()):
            results.append(self.get_next_values_for_feature(row))
        return results
    
    def showEvent(self, event) -> None:
        """Override show event to update the display when dialog is shown."""
        super().showEvent(event)
        self._refresh_extent_layer_combo()
        self._refresh_global_context_label()
        if self._mode_global_radio.isChecked():
            self._update_ok_button_state()
        else:
            self._schedule_selected_count_update() 