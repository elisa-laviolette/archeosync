"""
Tests for the new file system service methods.

This module tests the list_directories and contains_qgs_file methods
that were added to support the Import Data dialog functionality.
"""

import unittest
import tempfile
import os
from pathlib import Path

try:
    from ..services.file_system_service import QGISFileSystemService
except ImportError:
    from services.file_system_service import QGISFileSystemService


class TestFileSystemNewMethods(unittest.TestCase):
    """Test cases for the new file system service methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.file_system_service = QGISFileSystemService()
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create some test files and directories
        self.test_dir1 = os.path.join(self.temp_dir, "test_dir1")
        self.test_dir2 = os.path.join(self.temp_dir, "test_dir2")
        self.test_dir3 = os.path.join(self.temp_dir, "test_dir3")
        
        os.makedirs(self.test_dir1)
        os.makedirs(self.test_dir2)
        os.makedirs(self.test_dir3)
        
        # Create some test files
        with open(os.path.join(self.temp_dir, "test.txt"), "w") as f:
            f.write("test")
        
        with open(os.path.join(self.test_dir1, "test.csv"), "w") as f:
            f.write("test")
        
        with open(os.path.join(self.test_dir2, "project.qgs"), "w") as f:
            f.write("test")
        
        with open(os.path.join(self.test_dir3, "other.txt"), "w") as f:
            f.write("test")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_list_directories(self):
        """Test that list_directories returns all directories."""
        directories = self.file_system_service.list_directories(self.temp_dir)
        
        # Should find 3 directories
        self.assertEqual(len(directories), 3)
        
        # Check that all expected directories are found
        expected_dirs = {self.test_dir1, self.test_dir2, self.test_dir3}
        found_dirs = set(directories)
        self.assertEqual(found_dirs, expected_dirs)
    
    def test_list_directories_nonexistent(self):
        """Test that list_directories returns empty list for nonexistent directory."""
        directories = self.file_system_service.list_directories("/nonexistent/directory")
        self.assertEqual(directories, [])
    
    def test_list_directories_file(self):
        """Test that list_directories returns empty list when given a file path."""
        file_path = os.path.join(self.temp_dir, "test.txt")
        directories = self.file_system_service.list_directories(file_path)
        self.assertEqual(directories, [])
    
    def test_contains_qgs_file_true(self):
        """Test that contains_qgs_file returns True when directory contains .qgs file."""
        result = self.file_system_service.contains_qgs_file(self.test_dir2)
        self.assertTrue(result)
    
    def test_contains_qgs_file_false(self):
        """Test that contains_qgs_file returns False when directory doesn't contain .qgs file."""
        result = self.file_system_service.contains_qgs_file(self.test_dir1)
        self.assertFalse(result)
        
        result = self.file_system_service.contains_qgs_file(self.test_dir3)
        self.assertFalse(result)
    
    def test_contains_qgs_file_nonexistent(self):
        """Test that contains_qgs_file returns False for nonexistent directory."""
        result = self.file_system_service.contains_qgs_file("/nonexistent/directory")
        self.assertFalse(result)
    
    def test_contains_qgs_file_file(self):
        """Test that contains_qgs_file returns False when given a file path."""
        file_path = os.path.join(self.temp_dir, "test.txt")
        result = self.file_system_service.contains_qgs_file(file_path)
        self.assertFalse(result)
    
    def test_contains_qgs_file_case_insensitive(self):
        """Test that contains_qgs_file is case insensitive."""
        # Create a file with uppercase extension
        qgs_file_upper = os.path.join(self.test_dir1, "project.QGS")
        with open(qgs_file_upper, "w") as f:
            f.write("test")
        
        result = self.file_system_service.contains_qgs_file(self.test_dir1)
        self.assertTrue(result)
    
    def test_integration_with_import_data_scenario(self):
        """Test integration scenario similar to Import Data dialog usage."""
        # Simulate a completed projects folder structure
        completed_projects_dir = os.path.join(self.temp_dir, "completed_projects")
        os.makedirs(completed_projects_dir)
        
        # Create some project directories
        project1_dir = os.path.join(completed_projects_dir, "project1")
        project2_dir = os.path.join(completed_projects_dir, "project2")
        project3_dir = os.path.join(completed_projects_dir, "project3")
        
        os.makedirs(project1_dir)
        os.makedirs(project2_dir)
        os.makedirs(project3_dir)
        
        # Add .qgs files to some projects
        with open(os.path.join(project1_dir, "project.qgs"), "w") as f:
            f.write("test")
        
        with open(os.path.join(project2_dir, "project.QGS"), "w") as f:
            f.write("test")
        
        # project3 has no .qgs file
        
        # Get all directories
        all_directories = self.file_system_service.list_directories(completed_projects_dir)
        self.assertEqual(len(all_directories), 3)
        
        # Filter directories that contain .qgs files
        completed_projects = []
        for directory in all_directories:
            if self.file_system_service.contains_qgs_file(directory):
                completed_projects.append(directory)
        
        # Should find 2 completed projects
        self.assertEqual(len(completed_projects), 2)
        
        # Check that the correct projects are found
        expected_projects = {project1_dir, project2_dir}
        found_projects = set(completed_projects)
        self.assertEqual(found_projects, expected_projects)


if __name__ == '__main__':
    unittest.main() 