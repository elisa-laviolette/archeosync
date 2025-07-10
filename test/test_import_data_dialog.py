"""
Tests for the Import Data dialog.

This module tests the ImportDataDialog class to ensure it correctly displays
CSV files and completed field projects, and handles user selections properly.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import Qt

try:
    from ..ui.import_data_dialog import ImportDataDialog
    from ..services.settings_service import QGISSettingsManager
    from ..services.file_system_service import QGISFileSystemService
except ImportError:
    from ui.import_data_dialog import ImportDataDialog
    from services.settings_service import QGISSettingsManager
    from services.file_system_service import QGISFileSystemService


class TestImportDataDialog(unittest.TestCase):
    """Test cases for the ImportDataDialog class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock QApplication if one doesn't exist
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # Create mock services
        self.mock_settings_manager = Mock(spec=QGISSettingsManager)
        self.mock_file_system_service = Mock(spec=QGISFileSystemService)
        
        # Set up default mock responses
        self.mock_settings_manager.get_value.side_effect = lambda key, default='': {
            'total_station_folder': '/path/to/total_station',
            'completed_projects_folder': '/path/to/completed_projects'
        }.get(key, default)
        
        self.mock_file_system_service.path_exists.return_value = True
        self.mock_file_system_service.list_files.return_value = []
        self.mock_file_system_service.list_directories.return_value = []
        self.mock_file_system_service.contains_qgs_file.return_value = False
    
    def test_dialog_initialization(self):
        """Test that the dialog initializes correctly."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that the dialog was created
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.windowTitle(), "Import Data")
        
        # Check that services were called to load settings
        self.mock_settings_manager.get_value.assert_any_call('total_station_folder', '')
        self.mock_settings_manager.get_value.assert_any_call('completed_projects_folder', '')
    
    def test_csv_files_display(self):
        """Test that CSV files are displayed correctly."""
        # Set up mock CSV files
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that CSV files are in the list
        self.assertEqual(dialog._csv_list_widget.count(), 2)
        
        # Check that the info label is updated
        self.assertIn("2 CSV file(s)", dialog._csv_info_label.text())
    
    def test_completed_projects_display(self):
        """Test that completed projects are displayed correctly."""
        # Set up mock directories with .qgs files
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that completed projects are in the list
        self.assertEqual(dialog._projects_list_widget.count(), 2)
        
        # Check that the info label is updated
        self.assertIn("2 completed project(s)", dialog._projects_info_label.text())
    
    def test_no_csv_files_message(self):
        """Test that appropriate message is shown when no CSV files are found."""
        self.mock_file_system_service.list_files.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that the info label shows no files found
        self.assertIn("No CSV files found", dialog._csv_info_label.text())
    
    def test_no_completed_projects_message(self):
        """Test that appropriate message is shown when no completed projects are found."""
        self.mock_file_system_service.list_directories.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that the info label shows no projects found
        self.assertIn("No completed projects found", dialog._projects_info_label.text())
    
    def test_folder_not_configured_message(self):
        """Test that appropriate message is shown when folders are not configured."""
        self.mock_settings_manager.get_value.side_effect = lambda key, default='': ''
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that the info labels show folder not configured
        self.assertIn("not configured", dialog._csv_info_label.text())
        self.assertIn("not configured", dialog._projects_info_label.text())
    
    def test_get_selected_csv_files(self):
        """Test that selected CSV files are returned correctly."""
        # Set up mock CSV files
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all items first (since they are selected by default)
        for i in range(dialog._csv_list_widget.count()):
            dialog._csv_list_widget.item(i).setSelected(False)
        
        # Select the first item
        dialog._csv_list_widget.item(0).setSelected(True)
        
        # Get selected files
        selected_files = dialog.get_selected_csv_files()
        
        # Check that the correct file is returned
        self.assertEqual(len(selected_files), 1)
        self.assertEqual(selected_files[0], '/path/to/total_station/file1.csv')
    
    def test_get_selected_completed_projects(self):
        """Test that selected completed projects are returned correctly."""
        # Set up mock directories with .qgs files
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all items first (since they are selected by default)
        for i in range(dialog._projects_list_widget.count()):
            dialog._projects_list_widget.item(i).setSelected(False)
        
        # Select the second item
        dialog._projects_list_widget.item(1).setSelected(True)
        
        # Get selected projects
        selected_projects = dialog.get_selected_completed_projects()
        
        # Check that the correct project is returned
        self.assertEqual(len(selected_projects), 1)
        self.assertEqual(selected_projects[0], '/path/to/completed_projects/project2')
    
    def test_refresh_csv_files(self):
        """Test that CSV files list is refreshed correctly."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Initially no files
        self.assertEqual(dialog._csv_list_widget.count(), 0)
        
        # Set up mock CSV files for refresh
        csv_files = ['/path/to/total_station/new_file.csv']
        self.mock_file_system_service.list_files.return_value = csv_files
        
        # Trigger refresh
        dialog._refresh_csv_files()
        
        # Check that the list is updated
        self.assertEqual(dialog._csv_list_widget.count(), 1)
        self.assertIn("1 CSV file(s)", dialog._csv_info_label.text())
    
    def test_refresh_completed_projects(self):
        """Test that completed projects list is refreshed correctly."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Initially no projects
        self.assertEqual(dialog._projects_list_widget.count(), 0)
        
        # Set up mock directories with .qgs files for refresh
        directories = ['/path/to/completed_projects/new_project']
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        # Trigger refresh
        dialog._refresh_completed_projects()
        
        # Check that the list is updated
        self.assertEqual(dialog._projects_list_widget.count(), 1)
        self.assertIn("1 completed project(s)", dialog._projects_info_label.text())
    
    def test_error_handling_in_csv_scan(self):
        """Test that errors during CSV scanning are handled gracefully."""
        self.mock_file_system_service.list_files.side_effect = Exception("Test error")
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that error message is displayed
        self.assertIn("Error scanning CSV files", dialog._csv_info_label.text())
    
    def test_error_handling_in_projects_scan(self):
        """Test that errors during projects scanning are handled gracefully."""
        self.mock_file_system_service.list_directories.side_effect = Exception("Test error")
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that error message is displayed
        self.assertIn("Error scanning completed projects", dialog._projects_info_label.text())
    
    def test_csv_files_sorted_by_name(self):
        """Test that CSV files are displayed in alphabetical order."""
        # Set up mock CSV files in non-alphabetical order
        csv_files = [
            '/path/to/total_station/zebra.csv',
            '/path/to/total_station/alpha.csv',
            '/path/to/total_station/beta.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that files are displayed in alphabetical order
        self.assertEqual(dialog._csv_list_widget.item(0).text(), 'alpha.csv')
        self.assertEqual(dialog._csv_list_widget.item(1).text(), 'beta.csv')
        self.assertEqual(dialog._csv_list_widget.item(2).text(), 'zebra.csv')
    
    def test_completed_projects_sorted_by_name(self):
        """Test that completed projects are displayed in alphabetical order."""
        # Set up mock directories in non-alphabetical order
        directories = [
            '/path/to/completed_projects/zebra_project',
            '/path/to/completed_projects/alpha_project',
            '/path/to/completed_projects/beta_project'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that projects are displayed in alphabetical order
        self.assertEqual(dialog._projects_list_widget.item(0).text(), 'alpha_project')
        self.assertEqual(dialog._projects_list_widget.item(1).text(), 'beta_project')
        self.assertEqual(dialog._projects_list_widget.item(2).text(), 'zebra_project')
    
    def test_csv_files_selected_by_default(self):
        """Test that all CSV files are selected by default."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv',
            '/path/to/total_station/file3.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that all items are selected by default
        for i in range(dialog._csv_list_widget.count()):
            self.assertTrue(dialog._csv_list_widget.item(i).isSelected())
    
    def test_completed_projects_selected_by_default(self):
        """Test that all completed projects are selected by default."""
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2',
            '/path/to/completed_projects/project3'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that all items are selected by default
        for i in range(dialog._projects_list_widget.count()):
            self.assertTrue(dialog._projects_list_widget.item(i).isSelected())
    
    def test_csv_select_all_button(self):
        """Test that CSV select all button selects all items."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all items first
        for i in range(dialog._csv_list_widget.count()):
            dialog._csv_list_widget.item(i).setSelected(False)
        
        # Click select all button
        dialog._csv_select_all_button.click()
        
        # Check that all items are selected
        for i in range(dialog._csv_list_widget.count()):
            self.assertTrue(dialog._csv_list_widget.item(i).isSelected())
    
    def test_csv_deselect_all_button(self):
        """Test that CSV deselect all button deselects all items."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Click deselect all button
        dialog._csv_deselect_all_button.click()
        
        # Check that all items are deselected
        for i in range(dialog._csv_list_widget.count()):
            self.assertFalse(dialog._csv_list_widget.item(i).isSelected())
    
    def test_projects_select_all_button(self):
        """Test that projects select all button selects all items."""
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all items first
        for i in range(dialog._projects_list_widget.count()):
            dialog._projects_list_widget.item(i).setSelected(False)
        
        # Click select all button
        dialog._projects_select_all_button.click()
        
        # Check that all items are selected
        for i in range(dialog._projects_list_widget.count()):
            self.assertTrue(dialog._projects_list_widget.item(i).isSelected())
    
    def test_projects_deselect_all_button(self):
        """Test that projects deselect all button deselects all items."""
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Click deselect all button
        dialog._projects_deselect_all_button.click()
        
        # Check that all items are deselected
        for i in range(dialog._projects_list_widget.count()):
            self.assertFalse(dialog._projects_list_widget.item(i).isSelected())
    
    def test_select_all_buttons_exist(self):
        """Test that select all and deselect all buttons are created."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that buttons exist
        self.assertIsNotNone(dialog._csv_select_all_button)
        self.assertIsNotNone(dialog._csv_deselect_all_button)
        self.assertIsNotNone(dialog._projects_select_all_button)
        self.assertIsNotNone(dialog._projects_deselect_all_button)
        
        # Check button text
        self.assertEqual(dialog._csv_select_all_button.text(), "Select All")
        self.assertEqual(dialog._csv_deselect_all_button.text(), "Deselect All")
        self.assertEqual(dialog._projects_select_all_button.text(), "Select All")
        self.assertEqual(dialog._projects_deselect_all_button.text(), "Deselect All")
    
    def test_import_button_exists(self):
        """Test that the Import button is created."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that Import button exists
        self.assertIsNotNone(dialog._import_button)
        self.assertEqual(dialog._import_button.text(), "Import")
    
    def test_import_button_initially_disabled(self):
        """Test that the Import button is initially disabled when no items are loaded."""
        self.mock_file_system_service.list_files.return_value = []
        self.mock_file_system_service.list_directories.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that Import button is disabled
        self.assertFalse(dialog._import_button.isEnabled())
    
    def test_import_button_enabled_with_csv_selection(self):
        """Test that the Import button is enabled when CSV files are selected."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        self.mock_file_system_service.list_directories.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # CSV files are selected by default, so Import button should be enabled
        self.assertTrue(dialog._import_button.isEnabled())
    
    def test_import_button_enabled_with_project_selection(self):
        """Test that the Import button is enabled when projects are selected."""
        self.mock_file_system_service.list_files.return_value = []
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Projects are selected by default, so Import button should be enabled
        self.assertTrue(dialog._import_button.isEnabled())
    
    def test_import_button_disabled_when_all_deselected(self):
        """Test that the Import button is disabled when all items are deselected."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        self.mock_file_system_service.list_directories.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Initially enabled because items are selected by default
        self.assertTrue(dialog._import_button.isEnabled())
        
        # Deselect all CSV files
        dialog._csv_deselect_all_button.click()
        
        # Import button should now be disabled
        self.assertFalse(dialog._import_button.isEnabled())
    
    def test_import_button_enabled_when_csv_selected(self):
        """Test that the Import button is enabled when CSV files are selected."""
        csv_files = [
            '/path/to/total_station/file1.csv',
            '/path/to/total_station/file2.csv'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        self.mock_file_system_service.list_directories.return_value = []
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all first
        dialog._csv_deselect_all_button.click()
        self.assertFalse(dialog._import_button.isEnabled())
        
        # Select one CSV file
        dialog._csv_list_widget.item(0).setSelected(True)
        
        # Import button should now be enabled
        self.assertTrue(dialog._import_button.isEnabled())
    
    def test_import_button_enabled_when_project_selected(self):
        """Test that the Import button is enabled when projects are selected."""
        self.mock_file_system_service.list_files.return_value = []
        directories = [
            '/path/to/completed_projects/project1',
            '/path/to/completed_projects/project2'
        ]
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Deselect all first
        dialog._projects_deselect_all_button.click()
        self.assertFalse(dialog._import_button.isEnabled())
        
        # Select one project
        dialog._projects_list_widget.item(0).setSelected(True)
        
        # Import button should now be enabled
        self.assertTrue(dialog._import_button.isEnabled())
    
    def test_import_button_remains_enabled_with_mixed_selection(self):
        """Test that the Import button remains enabled when items are selected in both lists."""
        csv_files = [
            '/path/to/total_station/file1.csv'
        ]
        directories = [
            '/path/to/completed_projects/project1'
        ]
        self.mock_file_system_service.list_files.return_value = csv_files
        self.mock_file_system_service.list_directories.return_value = directories
        self.mock_file_system_service.contains_qgs_file.side_effect = lambda path: True
        
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Should be enabled with both CSV and project selected
        self.assertTrue(dialog._import_button.isEnabled())
        
        # Deselect CSV files
        dialog._csv_deselect_all_button.click()
        
        # Should still be enabled because projects are selected
        self.assertTrue(dialog._import_button.isEnabled())
        
        # Deselect projects
        dialog._projects_deselect_all_button.click()
        
        # Should now be disabled
        self.assertFalse(dialog._import_button.isEnabled())
    
    def test_cancel_button_exists(self):
        """Test that the Cancel button is created."""
        dialog = ImportDataDialog(
            settings_manager=self.mock_settings_manager,
            file_system_service=self.mock_file_system_service
        )
        
        # Check that Cancel button exists
        self.assertIsNotNone(dialog._cancel_button)
        self.assertEqual(dialog._cancel_button.text(), "Cancel")


if __name__ == '__main__':
    unittest.main() 