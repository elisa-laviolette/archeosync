"""
Import Data dialog for ArcheoSync plugin.

This module provides a dialog for importing data from CSV files and completed field projects.
The dialog displays two lists: one containing all CSV files found in the Total Station CSV Files
folder, and one containing all folders corresponding to completed recordings (containing a .qgs file)
in the Completed Field Projects folder.

Key Features:
- Dependency injection for all services
- Clean separation of UI and business logic
- Real-time scanning of folders
- User-friendly file and folder selection
- Responsive UI with refresh capabilities

Architecture Benefits:
- Single Responsibility: Only handles UI presentation
- Dependency Inversion: Depends on interfaces, not concretions
- Testability: All dependencies can be mocked
- Extensibility: New services can be injected easily

Usage:
    settings_manager = QGISSettingsManager()
    file_system_service = QGISFileSystemService()
    
    dialog = ImportDataDialog(
        settings_manager=settings_manager,
        file_system_service=file_system_service,
        parent=parent_widget
    )
    
    if dialog.exec_() == QDialog.Accepted:
        # Import data was selected
        selected_csv_files = dialog.get_selected_csv_files()
        selected_completed_projects = dialog.get_selected_completed_projects()
"""

from typing import Optional, List
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, QTimer

try:
    from ..core.interfaces import ISettingsManager, IFileSystemService
except ImportError:
    from core.interfaces import ISettingsManager, IFileSystemService


class ImportDataDialog(QtWidgets.QDialog):
    """
    Import Data dialog for ArcheoSync plugin.
    
    This dialog provides a clean interface for selecting CSV files and completed field projects
    for import, following the Single Responsibility Principle by focusing only on UI presentation
    and delegating business logic to injected services.
    """
    
    def __init__(self, 
                 settings_manager: ISettingsManager,
                 file_system_service: IFileSystemService,
                 parent=None):
        """
        Initialize the import data dialog.
        
        Args:
            settings_manager: Service for managing settings
            file_system_service: Service for file system operations
            parent: Parent widget for the dialog
        """
        super().__init__(parent)
        
        # Store injected dependencies
        self._settings_manager = settings_manager
        self._file_system_service = file_system_service
        
        # Store data
        self._csv_files: List[str] = []
        self._completed_projects: List[str] = []
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
        self._load_settings()
        self._scan_folders()
    
    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle("Import Data")
        self.setGeometry(0, 0, 800, 600)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Add title
        title_label = QtWidgets.QLabel("Import Data")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)
        
        # Add description
        description_label = QtWidgets.QLabel(
            "Select CSV files from Total Station data and/or completed field projects to import."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("margin: 5px; color: #666;")
        main_layout.addWidget(description_label)
        
        # Add content section
        self._create_content_section(main_layout)
        
        # Add button box
        self._create_button_box(main_layout)
    
    def _create_content_section(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the main content section with two lists."""
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        
        # CSV Files section
        csv_group = self._create_csv_files_section()
        content_layout.addWidget(csv_group)
        
        # Completed Projects section
        projects_group = self._create_completed_projects_section()
        content_layout.addWidget(projects_group)
        
        parent_layout.addWidget(content_widget)
    
    def _create_csv_files_section(self) -> QtWidgets.QGroupBox:
        """Create the CSV files selection section."""
        group = QtWidgets.QGroupBox("Total Station CSV Files")
        layout = QtWidgets.QVBoxLayout(group)
        
        # Header with refresh button
        header_layout = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Available CSV files:")
        self._csv_refresh_button = QtWidgets.QPushButton("Refresh")
        self._csv_refresh_button.setToolTip("Refresh the list of CSV files")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(self._csv_refresh_button)
        layout.addLayout(header_layout)
        
        # Select/Deselect all buttons
        select_buttons_layout = QtWidgets.QHBoxLayout()
        self._csv_select_all_button = QtWidgets.QPushButton("Select All")
        self._csv_select_all_button.setToolTip("Select all CSV files")
        self._csv_deselect_all_button = QtWidgets.QPushButton("Deselect All")
        self._csv_deselect_all_button.setToolTip("Deselect all CSV files")
        select_buttons_layout.addWidget(self._csv_select_all_button)
        select_buttons_layout.addWidget(self._csv_deselect_all_button)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)
        
        # CSV files list
        self._csv_list_widget = QtWidgets.QListWidget()
        self._csv_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self._csv_list_widget)
        
        # CSV files info
        self._csv_info_label = QtWidgets.QLabel("No CSV files found")
        self._csv_info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self._csv_info_label)
        
        return group
    
    def _create_completed_projects_section(self) -> QtWidgets.QGroupBox:
        """Create the completed projects selection section."""
        group = QtWidgets.QGroupBox("Completed Field Projects")
        layout = QtWidgets.QVBoxLayout(group)
        
        # Header with refresh button
        header_layout = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel("Available completed projects:")
        self._projects_refresh_button = QtWidgets.QPushButton("Refresh")
        self._projects_refresh_button.setToolTip("Refresh the list of completed projects")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(self._projects_refresh_button)
        layout.addLayout(header_layout)
        
        # Select/Deselect all buttons
        select_buttons_layout = QtWidgets.QHBoxLayout()
        self._projects_select_all_button = QtWidgets.QPushButton("Select All")
        self._projects_select_all_button.setToolTip("Select all completed projects")
        self._projects_deselect_all_button = QtWidgets.QPushButton("Deselect All")
        self._projects_deselect_all_button.setToolTip("Deselect all completed projects")
        select_buttons_layout.addWidget(self._projects_select_all_button)
        select_buttons_layout.addWidget(self._projects_deselect_all_button)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)
        
        # Completed projects list
        self._projects_list_widget = QtWidgets.QListWidget()
        self._projects_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self._projects_list_widget)
        
        # Projects info
        self._projects_info_label = QtWidgets.QLabel("No completed projects found")
        self._projects_info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self._projects_info_label)
        
        return group
    
    def _create_button_box(self, parent_layout: QtWidgets.QVBoxLayout) -> None:
        """Create the dialog button box."""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Create Import button
        self._import_button = QtWidgets.QPushButton("Import")
        self._import_button.setDefault(True)
        self._import_button.setEnabled(False)  # Initially disabled
        
        # Create Cancel button
        self._cancel_button = QtWidgets.QPushButton("Cancel")
        
        # Add buttons to layout
        button_layout.addStretch()
        button_layout.addWidget(self._cancel_button)
        button_layout.addWidget(self._import_button)
        
        parent_layout.addLayout(button_layout)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Button connections
        self._import_button.clicked.connect(self._accept)
        self._cancel_button.clicked.connect(self.reject)
        
        # List selection change connections
        self._csv_list_widget.itemSelectionChanged.connect(self._update_import_button_state)
        self._projects_list_widget.itemSelectionChanged.connect(self._update_import_button_state)
        
        # Refresh button connections
        self._csv_refresh_button.clicked.connect(self._refresh_csv_files)
        self._projects_refresh_button.clicked.connect(self._refresh_completed_projects)
        
        # Select/Deselect all button connections
        self._csv_select_all_button.clicked.connect(self._select_all_csv_files)
        self._csv_deselect_all_button.clicked.connect(self._deselect_all_csv_files)
        self._projects_select_all_button.clicked.connect(self._select_all_completed_projects)
        self._projects_deselect_all_button.clicked.connect(self._deselect_all_completed_projects)
    
    def _load_settings(self) -> None:
        """Load settings to get folder paths."""
        self._total_station_folder = self._settings_manager.get_value('total_station_folder', '')
        self._completed_projects_folder = self._settings_manager.get_value('completed_projects_folder', '')
    
    def _scan_folders(self) -> None:
        """Scan folders for CSV files and completed projects."""
        self._refresh_csv_files()
        self._refresh_completed_projects()
    
    def _refresh_csv_files(self) -> None:
        """Refresh the list of CSV files."""
        try:
            self._csv_list_widget.clear()
            self._csv_files = []
            
            if not self._total_station_folder or not self._file_system_service.path_exists(self._total_station_folder):
                self._csv_info_label.setText("Total Station folder not configured or does not exist")
                return
            
            # Get CSV files
            csv_files = self._file_system_service.list_files(self._total_station_folder, '.csv')
            
            # Sort files alphabetically by filename
            csv_files.sort(key=lambda x: x.split('/')[-1] if '/' in x else x.split('\\')[-1])
            self._csv_files = csv_files
            
            # Add files to list widget
            for csv_file in csv_files:
                # Get just the filename for display
                filename = csv_file.split('/')[-1] if '/' in csv_file else csv_file.split('\\')[-1]
                
                item = QtWidgets.QListWidgetItem(filename)
                item.setToolTip(csv_file)  # Show full path on hover
                self._csv_list_widget.addItem(item)
                # Select item by default
                item.setSelected(True)
            
            # Update info label
            if csv_files:
                self._csv_info_label.setText(f"Found {len(csv_files)} CSV file(s)")
            else:
                self._csv_info_label.setText("No CSV files found in the Total Station folder")
            
            # Update import button state
            self._update_import_button_state()
                
        except Exception as e:
            self._csv_info_label.setText(f"Error scanning CSV files: {str(e)}")
            self._update_import_button_state()
    
    def _refresh_completed_projects(self) -> None:
        """Refresh the list of completed projects."""
        try:
            self._projects_list_widget.clear()
            self._completed_projects = []
            
            if not self._completed_projects_folder or not self._file_system_service.path_exists(self._completed_projects_folder):
                self._projects_info_label.setText("Completed Projects folder not configured or does not exist")
                return
            
            # Get all directories
            directories = self._file_system_service.list_directories(self._completed_projects_folder)
            
            # Filter directories that contain .qgs files
            completed_projects = []
            for directory in directories:
                if self._file_system_service.contains_qgs_file(directory):
                    completed_projects.append(directory)
            
            # Sort projects alphabetically by directory name
            completed_projects.sort(key=lambda x: x.split('/')[-1] if '/' in x else x.split('\\')[-1])
            self._completed_projects = completed_projects
            
            # Add projects to list widget
            for project_dir in completed_projects:
                # Get just the directory name for display
                dirname = project_dir.split('/')[-1] if '/' in project_dir else project_dir.split('\\')[-1]
                
                item = QtWidgets.QListWidgetItem(dirname)
                item.setToolTip(project_dir)  # Show full path on hover
                self._projects_list_widget.addItem(item)
                # Select item by default
                item.setSelected(True)
            
            # Update info label
            if completed_projects:
                self._projects_info_label.setText(f"Found {len(completed_projects)} completed project(s)")
            else:
                self._projects_info_label.setText("No completed projects found in the Completed Projects folder")
            
            # Update import button state
            self._update_import_button_state()
                
        except Exception as e:
            self._projects_info_label.setText(f"Error scanning completed projects: {str(e)}")
            self._update_import_button_state()
    
    def _select_all_csv_files(self) -> None:
        """Select all CSV files in the list."""
        for i in range(self._csv_list_widget.count()):
            self._csv_list_widget.item(i).setSelected(True)
        self._update_import_button_state()
    
    def _deselect_all_csv_files(self) -> None:
        """Deselect all CSV files in the list."""
        for i in range(self._csv_list_widget.count()):
            self._csv_list_widget.item(i).setSelected(False)
        self._update_import_button_state()
    
    def _select_all_completed_projects(self) -> None:
        """Select all completed projects in the list."""
        for i in range(self._projects_list_widget.count()):
            self._projects_list_widget.item(i).setSelected(True)
        self._update_import_button_state()
    
    def _deselect_all_completed_projects(self) -> None:
        """Deselect all completed projects in the list."""
        for i in range(self._projects_list_widget.count()):
            self._projects_list_widget.item(i).setSelected(False)
        self._update_import_button_state()
    
    def _update_import_button_state(self) -> None:
        """Update the import button state based on selection."""
        csv_selected = len(self.get_selected_csv_files()) > 0
        projects_selected = len(self.get_selected_completed_projects()) > 0
        
        # Enable import button if at least one item is selected in either list
        self._import_button.setEnabled(csv_selected or projects_selected)
    
    def get_selected_csv_files(self) -> List[str]:
        """
        Get the list of selected CSV files.
        
        Returns:
            List of selected CSV file paths
        """
        selected_files = []
        for i in range(self._csv_list_widget.count()):
            item = self._csv_list_widget.item(i)
            if item.isSelected():
                # Get the full path from the tooltip
                full_path = item.toolTip()
                if full_path in self._csv_files:
                    selected_files.append(full_path)
        return selected_files
    
    def get_selected_completed_projects(self) -> List[str]:
        """
        Get the list of selected completed projects.
        
        Returns:
            List of selected completed project directory paths
        """
        selected_projects = []
        for i in range(self._projects_list_widget.count()):
            item = self._projects_list_widget.item(i)
            if item.isSelected():
                # Get the full path from the tooltip
                full_path = item.toolTip()
                if full_path in self._completed_projects:
                    selected_projects.append(full_path)
        return selected_projects
    
    def _accept(self) -> None:
        """Handle dialog acceptance."""
        # The import button is only enabled when there are valid selections,
        # so we can directly accept the dialog
        self.accept() 