"""
Import Summary Dialog for ArcheoSync plugin.

This module provides a dialog that displays a summary of imported data after
the import process is complete. It shows statistics about imported points,
features, objects, small finds, and detected duplicates.

Key Features:
- Displays import statistics in a clear, organized format
- Shows counts for different data types (CSV points, features, objects, small finds)
- Reports duplicate detection results
- Clean, user-friendly interface
- Supports translation
- Provides buttons to open attribute tables filtered to show concerned entities

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
    
    # Non-modal dialog (default) - allows interaction with other windows
    dialog = ImportSummaryDialog(summary_data, parent=parent_widget)
    dialog.exec_()
    
    # Modal dialog - blocks interaction with other windows
    dialog = ImportSummaryDialog(summary_data, parent=parent_widget, modal=True)
    dialog.exec_()
"""

from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt


@dataclass
class WarningData:
    """Data structure for warning information with filtering details."""
    message: str
    recording_area_name: str
    layer_name: str
    filter_expression: str
    # Additional fields for specific warning types
    object_number: Optional[int] = None
    skipped_numbers: Optional[List[int]] = None
    # Fields for between-layer warnings
    second_layer_name: Optional[str] = None
    second_filter_expression: Optional[str] = None


@dataclass
class ImportSummaryData:
    """Data structure for import summary information."""
    csv_points_count: int = 0
    features_count: int = 0
    objects_count: int = 0
    small_finds_count: int = 0
    csv_duplicates: int = 0
    features_duplicates: int = 0
    objects_duplicates: int = 0
    small_finds_duplicates: int = 0
    duplicate_objects_warnings: List[Union[str, WarningData]] = None
    skipped_numbers_warnings: List[Union[str, WarningData]] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.duplicate_objects_warnings is None:
            self.duplicate_objects_warnings = []
        if self.skipped_numbers_warnings is None:
            self.skipped_numbers_warnings = []


class ImportSummaryDialog(QtWidgets.QDialog):
    """
    Import Summary dialog for ArcheoSync plugin.
    
    Displays a summary of imported data after the import process is complete.
    By default, the dialog is non-modal, allowing users to interact with other
    windows (including attribute tables) while the summary is displayed.
    All user-facing strings are wrapped in self.tr() for translation.
    """
    
    def __init__(self, 
                 summary_data: ImportSummaryData,
                 iface=None,
                 settings_manager=None,
                 parent=None,
                 modal=False):
        """
        Initialize the import summary dialog.
        
        Args:
            summary_data: Data containing import statistics
            iface: QGIS interface for opening attribute tables
            settings_manager: Settings manager for accessing layer configurations
            parent: Parent widget for the dialog
            modal: Whether the dialog should be modal (default: False)
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._summary_data = summary_data
        self._iface = iface
        self._settings_manager = settings_manager
        self._modal = modal
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle(self.tr("Import Summary"))
        self.setGeometry(0, 0, 500, 400)
        self.setModal(self._modal)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel(self.tr("Import Summary"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Add description
        description_label = QtWidgets.QLabel(self.tr("The following data has been imported and added to your project:"))
        description_label.setWordWrap(True)
        description_label.setStyleSheet("margin: 5px; color: #666;")
        main_layout.addWidget(description_label)
        
        # Add summary content
        self._create_summary_content(main_layout)
        
        # Add button box
        self._create_button_box(main_layout)
    
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
        if self._summary_data.duplicate_objects_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Duplicate Objects Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF4500;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.duplicate_objects_warnings:
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text
                if isinstance(warning, WarningData):
                    warning_text = warning.message
                else:
                    warning_text = warning
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF4500; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if isinstance(warning, WarningData) and self._iface:
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
        if self._summary_data.skipped_numbers_warnings:
            warnings_layout = QtWidgets.QVBoxLayout()
            warnings_label = QtWidgets.QLabel(self.tr("Skipped Numbers Warnings:"))
            warnings_label.setStyleSheet("font-weight: bold; color: #FF8C00;")
            warnings_layout.addWidget(warnings_label)
            
            for warning in self._summary_data.skipped_numbers_warnings:
                warning_item_layout = QtWidgets.QHBoxLayout()
                
                # Warning text
                if isinstance(warning, WarningData):
                    warning_text = warning.message
                else:
                    warning_text = warning
                
                warning_item = QtWidgets.QLabel(f"• {warning_text}")
                warning_item.setStyleSheet("color: #FF8C00; margin-left: 10px;")
                warning_item.setWordWrap(True)
                warning_item_layout.addWidget(warning_item)
                
                # Add button if we have structured data and QGIS interface
                if isinstance(warning, WarningData) and self._iface:
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
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Create Validate button (instead of OK)
        self._validate_button = QtWidgets.QPushButton(self.tr("Validate"))
        self._validate_button.setDefault(True)
        
        # Add button to layout
        button_layout.addStretch()
        button_layout.addWidget(self._validate_button)
        
        parent_layout.addLayout(button_layout)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Button connections
        self._validate_button.clicked.connect(self._handle_validate)
    
    def _handle_validate(self) -> None:
        """Handle the validate button click - copy features from temporary to definitive layers."""
        try:
            # Copy features from temporary layers to definitive layers
            self._copy_temporary_to_definitive_layers()
            
            # Close the dialog
            self.accept()
            
        except Exception as e:
            print(f"Error during validation: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message to user
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                self.tr("Validation Error"),
                self.tr(f"An error occurred during validation: {str(e)}")
            )
    
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
                
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    self.tr("Validation Complete"),
                    success_message
                )
            else:
                # Show message if no layers were configured
                if missing_configurations:
                    from qgis.PyQt.QtWidgets import QMessageBox
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
            
            # Clear any existing selection
            target_layer.removeSelection()
            
            # Select the concerned entities
            target_layer.selectByExpression(warning_data.filter_expression)
            
            # Set the layer as active
            self._iface.setActiveLayer(target_layer)
            
            # Open the attribute table
            self._iface.actionOpenTable().trigger()
            
            # Show a message to inform the user about the selection
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                self.tr("Attribute Table Opened"),
                self.tr(f"Attribute table for '{warning_data.layer_name}' has been opened with selected entities matching:\n{warning_data.filter_expression}")
            )
        except Exception as e:
            print(f"Error opening attribute table with selection: {e}")
            from qgis.PyQt.QtWidgets import QMessageBox
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
            
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                self.tr("Attribute Tables Opened"),
                self.tr(f"Attribute tables for '{warning_data.layer_name}' and '{warning_data.second_layer_name}' have been opened with selected entities.")
            )
        except Exception as e:
            print(f"Error opening both attribute tables with selection: {e}")
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr(f"Could not open both attribute tables: {str(e)}")
            ) 