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
    
    if dialog.exec_() == QDialog.Accepted:
        # Recording preparation was confirmed
        pass
"""

from typing import Optional, List, Dict, Any
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt

try:
    from ..core.interfaces import ILayerService, ISettingsManager
except ImportError:
    from core.interfaces import ILayerService, ISettingsManager


class PrepareRecordingDialog(QtWidgets.QDialog):
    """
    Dialog for preparing recording data.
    
    This dialog shows the number of selected entities in the Recording areas layer
    and provides a clean interface for recording preparation.
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
        
        # Initialize UI
        self._setup_ui()
        self._update_selected_count()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle("Prepare Recording")
        self.setGeometry(0, 0, 400, 200)
        self.setModal(True)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel("Prepare Recording")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Add information section
        self._create_info_section(main_layout)
        
        # Add button box
        self._create_button_box(main_layout)
    
    def _create_info_section(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the information display section."""
        info_group = QtWidgets.QGroupBox("Recording Areas Information")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        # Recording areas layer info
        self._recording_areas_label = QtWidgets.QLabel("Recording Areas Layer: Not configured")
        info_layout.addWidget(self._recording_areas_label)
        
        # Selected features count
        self._selected_count_label = QtWidgets.QLabel("Selected Entities: 0")
        self._selected_count_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2E86AB;")
        info_layout.addWidget(self._selected_count_label)
        
        # Create table for selected entities
        self._create_entities_table(info_layout)
        
        # Instructions
        instructions = QtWidgets.QLabel(
            "To prepare recording:\n"
            "1. Select entities in the Recording areas layer\n"
            "2. Click 'Prepare Recording' to continue"
        )
        instructions.setStyleSheet("color: #666; margin-top: 10px;")
        info_layout.addWidget(instructions)
        
        parent_layout.addWidget(info_group)
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self
        )
        
        # Connect button signals
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        
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
        columns = ["Name"]
        if objects_layer_id and number_field:
            columns.append("Last object number")
        if objects_layer_id and level_field:
            columns.append("Last level")
        
        self._entities_table.setColumnCount(len(columns))
        self._entities_table.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self._entities_table.setAlternatingRowColors(True)
        self._entities_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._entities_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
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
                self._recording_areas_label.setText("Recording Areas Layer: Not configured")
                self._selected_count_label.setText("Selected Entities: 0")
                self._populate_entities_table([])
                self._button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
                return
            
            # Get layer info
            layer_info = self._layer_service.get_layer_info(recording_areas_layer_id)
            if layer_info is None:
                self._recording_areas_label.setText("Recording Areas Layer: Layer not found")
                self._selected_count_label.setText("Selected Entities: 0")
                self._populate_entities_table([])
                self._button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
                return
            
            # Update layer name
            self._recording_areas_label.setText(f"Recording Areas Layer: {layer_info['name']}")
            
            # Get the actual layer to access selected features
            recording_layer = self._layer_service.get_layer_by_id(recording_areas_layer_id)
            if recording_layer is None:
                self._recording_areas_label.setText("Recording Areas Layer: Layer not found")
                self._selected_count_label.setText("Selected Entities: 0")
                self._populate_entities_table([])
                self._button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
                return
            
            # Get selected features
            selected_features = recording_layer.selectedFeatures()
            selected_count = len(selected_features)
            
            # Update count label
            self._selected_count_label.setText(f"Selected Entities: {selected_count}")
            
            # Populate table with actual features
            self._populate_entities_table(selected_features)
            
            # Enable/disable OK button based on selection
            has_selection = selected_count > 0
            self._button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(has_selection)
            
            # Update button text based on selection
            ok_button = self._button_box.button(QtWidgets.QDialogButtonBox.Ok)
            if has_selection:
                ok_button.setText("Prepare Recording")
            else:
                ok_button.setText("No Selection")
                
        except Exception as e:
            print("PrepareRecordingDialog error:", e)
            self._recording_areas_label.setText("Recording Areas Layer: Error")
            self._selected_count_label.setText("Selected Entities: Error")
            self._populate_entities_table([])
            self._button_box.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
    
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
        
        # Add features to table
        for feature in features:
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
            self._entities_table.setItem(row, 0, name_item)
            
            # Add related objects information if configured
            col_index = 1
            
            if objects_layer_id and number_field:
                # Get related objects info
                related_info = self._layer_service.get_related_objects_info(
                    feature, objects_layer_id, number_field, level_field, recording_areas_layer_id
                )
                
                # Add last number
                number_item = QtWidgets.QTableWidgetItem(related_info['last_number'])
                self._entities_table.setItem(row, col_index, number_item)
                col_index += 1
            
            if objects_layer_id and level_field:
                # Get related objects info (if not already done)
                if not (objects_layer_id and number_field):
                    related_info = self._layer_service.get_related_objects_info(
                        feature, objects_layer_id, number_field, level_field, recording_areas_layer_id
                    )
                
                # Add last level
                level_item = QtWidgets.QTableWidgetItem(related_info['last_level'])
                self._entities_table.setItem(row, col_index, level_item)
        
        # Resize columns to content
        self._entities_table.resizeColumnsToContents()
    
    def showEvent(self, event) -> None:
        """Override show event to update the display when dialog is shown."""
        super().showEvent(event)
        self._update_selected_count() 