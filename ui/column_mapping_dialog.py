"""
Column Mapping Dialog for ArcheoSync plugin.

This module provides a dialog for mapping columns across multiple CSV files
when they have different column names. The dialog allows users to specify
how columns should be matched and combined.

Key Features:
- Shows column mapping across multiple CSV files
- Allows users to select which columns to include
- Provides dropdown selection for column matching
- Clean separation of UI and business logic
- Responsive UI with validation

Architecture Benefits:
- Single Responsibility: Only handles column mapping UI
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: Easy to add new mapping options

Usage:
    dialog = ColumnMappingDialog(
        column_mapping=column_mapping,
        csv_files=csv_files,
        parent=parent_widget
    )
    
    if dialog.exec_() == QDialog.Accepted:
        final_mapping = dialog.get_final_mapping()
"""

from typing import Dict, List, Optional
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt


class ColumnMappingDialog(QtWidgets.QDialog):
    """
    Column Mapping dialog for ArcheoSync plugin.
    
    All user-facing strings are wrapped in self.tr() for translation.
    """
    
    def __init__(self, column_mapping: Dict[str, List[Optional[str]]], 
                 csv_files: List[str], file_columns: List[List[str]], parent=None):
        """
        Initialize the column mapping dialog.
        
        Args:
            column_mapping: Dictionary mapping unified column names to lists of column names from each file
            csv_files: List of CSV file paths
            file_columns: List of lists of column names for each file
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        
        # Store data
        self._column_mapping = column_mapping
        self._csv_files = csv_files
        self._file_columns = file_columns
        self._final_mapping = {}
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
        self._populate_mapping_table()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle(self.tr("Column Mapping"))
        self.setGeometry(0, 0, 800, 600)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel(self.tr("Map Columns Across CSV Files"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Add description
        description_label = QtWidgets.QLabel(self.tr("Your CSV files have different column names. Please specify how columns should be matched:"))
        description_label.setWordWrap(True)
        description_label.setStyleSheet("margin: 5px; color: #666;")
        main_layout.addWidget(description_label)
        
        # Add mapping table
        self._create_mapping_table(main_layout)
        
        # Add button box
        self._create_button_box(main_layout)
    
    def _create_mapping_table(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the column mapping table."""
        # Create table widget
        self._mapping_table = QtWidgets.QTableWidget()
        self._mapping_table.setAlternatingRowColors(True)
        self._mapping_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        # Set up table headers
        headers = ["Unified Column Name", "Include"]
        for i, csv_file in enumerate(self._csv_files):
            filename = csv_file.split('/')[-1] if '/' in csv_file else csv_file.split('\\')[-1]
            headers.append(f"File {i+1}: {filename}")
        
        self._mapping_table.setColumnCount(len(headers))
        self._mapping_table.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        self._mapping_table.setColumnWidth(0, 200)  # Unified column name
        self._mapping_table.setColumnWidth(1, 80)   # Include checkbox
        
        parent_layout.addWidget(self._mapping_table)
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the button box."""
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        
        parent_layout.addWidget(button_box)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Connect table cell changed signal
        self._mapping_table.cellChanged.connect(self._on_cell_changed)
    
    def _populate_mapping_table(self) -> None:
        """Populate the mapping table with column data."""
        # Set number of rows
        self._mapping_table.setRowCount(len(self._column_mapping))
        
        # Populate each row
        for row, (unified_name, column_list) in enumerate(self._column_mapping.items()):
            # Unified column name (read-only)
            name_item = QtWidgets.QTableWidgetItem(unified_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self._mapping_table.setItem(row, 0, name_item)
            
            # Include checkbox
            include_checkbox = QtWidgets.QCheckBox()
            include_checkbox.setChecked(True)  # Include by default
            self._mapping_table.setCellWidget(row, 1, include_checkbox)
            
            # Column mapping dropdowns
            for col_index, column_name in enumerate(column_list):
                dropdown = QtWidgets.QComboBox()
                dropdown.addItem(self.tr("-- No mapping --"), None)
                # Add all available columns from this file
                available_columns = self._file_columns[col_index] if col_index < len(self._file_columns) else []
                for col in available_columns:
                    dropdown.addItem(self.tr(col), col)
                # Set current selection to the value from column_mapping if present
                if column_name:
                    index = dropdown.findData(column_name)
                    if index != -1:
                        dropdown.setCurrentIndex(index)
                self._mapping_table.setCellWidget(row, col_index + 2, dropdown)
    
    def _on_cell_changed(self, row: int, column: int) -> None:
        """Handle cell changes in the mapping table."""
        # This method can be used for validation or real-time updates
        pass
    
    def _accept(self) -> None:
        """Handle dialog acceptance."""
        # Build final mapping
        self._final_mapping = {}
        
        for row in range(self._mapping_table.rowCount()):
            # Get unified column name
            unified_name = self._mapping_table.item(row, 0).text()
            
            # Check if column should be included
            include_checkbox = self._mapping_table.cellWidget(row, 1)
            if not include_checkbox.isChecked():
                continue
            
            # Get column mappings for each file
            column_mappings = []
            for col in range(2, self._mapping_table.columnCount()):
                dropdown = self._mapping_table.cellWidget(row, col)
                if dropdown:
                    column_mappings.append(dropdown.currentData())
                else:
                    column_mappings.append(None)
            
            self._final_mapping[unified_name] = column_mappings
        
        # Validate that required columns are included
        required_columns = ['X', 'Y', 'Z']
        missing_required = [col for col in required_columns if col not in self._final_mapping]
        
        if missing_required:
            self._show_warning(f"The following required columns must be included: {', '.join(missing_required)}")
            return
        
        self.accept()
    
    def get_final_mapping(self) -> Dict[str, List[Optional[str]]]:
        """
        Get the final column mapping after user interaction.
        
        Returns:
            Dictionary mapping unified column names to lists of column names from each file
        """
        return self._final_mapping 

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, self.tr("Column Mapping Warning"), self.tr(message)) 