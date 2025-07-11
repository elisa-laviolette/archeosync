"""
File system service implementation for ArcheoSync plugin.

This module provides a concrete implementation of the IFileSystemService interface
for handling file system operations in a platform-agnostic way. This service
encapsulates all file system interactions, making the plugin more testable and
platform-independent.

Key Features:
- Platform-agnostic file operations
- QGIS/Qt dialog integration for file selection
- Comprehensive file and directory utilities
- Error handling for file system operations

Usage:
    file_service = QGISFileSystemService(parent_widget)
    folder_path = file_service.select_directory("Select Folder")
    if file_service.path_exists(folder_path):
        files = file_service.list_files(folder_path, '.csv')

The service provides:
- Directory selection dialogs
- File existence and type checking
- Directory creation and management
- File listing with filtering
- Extension-based file operations

This abstraction allows for:
- Easy testing with mock implementations
- Platform-specific optimizations
- Consistent error handling
- Future extensions (e.g., cloud storage)
"""

import os
from typing import Optional
from pathlib import Path
from qgis.PyQt.QtWidgets import QFileDialog

try:
    from ..core.interfaces import IFileSystemService
except ImportError:
    from core.interfaces import IFileSystemService


class QGISFileSystemService(IFileSystemService):
    """
    QGIS-specific implementation of file system operations.
    
    This class provides file system operations using QGIS/Qt dialogs
    and standard Python file system operations.
    """
    
    def __init__(self, parent_widget=None):
        """
        Initialize the file system service.
        
        Args:
            parent_widget: Parent widget for dialogs
        """
        self._parent_widget = parent_widget
    
    def select_directory(self, title: str, initial_path: Optional[str] = None) -> Optional[str]:
        """
        Open directory selection dialog.
        
        Args:
            title: Dialog title
            initial_path: Initial directory path to show
            
        Returns:
            Selected directory path or None if cancelled
        """
        folder_path = QFileDialog.getExistingDirectory(
            self._parent_widget,
            title,
            initial_path or ""
        )
        
        return folder_path if folder_path else None
    
    def path_exists(self, path: str) -> bool:
        """
        Check if a path exists.
        
        Args:
            path: Path to check
            
        Returns:
            True if path exists, False otherwise
        """
        return os.path.exists(path)
    
    def create_directory(self, path: str) -> bool:
        """
        Create a directory if it doesn't exist.
        
        Args:
            path: Directory path to create
            
        Returns:
            True if directory was created or already exists, False on error
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False
    
    def is_directory(self, path: str) -> bool:
        """
        Check if a path is a directory.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is a directory, False otherwise
        """
        return os.path.isdir(path)
    
    def is_file(self, path: str) -> bool:
        """
        Check if a path is a file.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is a file, False otherwise
        """
        return os.path.isfile(path)
    
    def get_file_extension(self, path: str) -> str:
        """
        Get the file extension from a path.
        
        Args:
            path: File path
            
        Returns:
            File extension (including the dot)
        """
        return Path(path).suffix
    
    def list_files(self, directory: str, extension: Optional[str] = None) -> list:
        """
        List files in a directory.
        
        Args:
            directory: Directory to list files from
            extension: Optional file extension filter
            
        Returns:
            List of file paths
        """
        if not self.path_exists(directory) or not self.is_directory(directory):
            return []
        
        files = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if self.is_file(item_path):
                if extension is None or self.get_file_extension(item_path).lower() == extension.lower():
                    files.append(item_path)
        
        return files
    
    def list_directories(self, directory: str) -> list:
        """
        List directories in a directory.
        
        Args:
            directory: Directory to list subdirectories from
            
        Returns:
            List of directory paths
        """
        if not self.path_exists(directory) or not self.is_directory(directory):
            return []
        
        directories = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if self.is_directory(item_path):
                directories.append(item_path)
        
        return directories
    
    def is_writable(self, path: str) -> bool:
        """
        Check if a path is writable.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is writable, False otherwise
        """
        try:
            test_file = Path(path) / ".test_write"
            test_file.touch()
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False
    
    def is_readable(self, path: str) -> bool:
        """
        Check if a path is readable.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is readable, False otherwise
        """
        try:
            list(Path(path).iterdir())
            return True
        except (OSError, PermissionError):
            return False
    
    def contains_qgs_file(self, directory: str) -> bool:
        """
        Check if a directory contains a .qgs file.
        
        Args:
            directory: Directory to check
            
        Returns:
            True if directory contains a .qgs file, False otherwise
        """
        if not self.path_exists(directory) or not self.is_directory(directory):
            return False
        
        for item in os.listdir(directory):
            if self.is_file(os.path.join(directory, item)) and self.get_file_extension(item).lower() == '.qgs':
                return True
        
        return False
    
    def move_file(self, source_path: str, destination_path: str) -> bool:
        """
        Move a file from source to destination.
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            True if file was moved successfully, False otherwise
        """
        try:
            if not self.path_exists(source_path):
                return False
            
            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(destination_path)
            if not self.path_exists(dest_dir):
                if not self.create_directory(dest_dir):
                    return False
            
            # Handle case where destination file already exists
            final_destination = destination_path
            if self.path_exists(final_destination):
                # Generate unique filename
                base_name = os.path.splitext(os.path.basename(destination_path))[0]
                extension = os.path.splitext(destination_path)[1]
                counter = 1
                while self.path_exists(final_destination):
                    new_name = f"{base_name}_{counter}{extension}"
                    final_destination = os.path.join(dest_dir, new_name)
                    counter += 1
            
            # Move the file
            import shutil
            shutil.move(source_path, final_destination)
            return True
            
        except (OSError, PermissionError, shutil.Error):
            return False
    
    def move_directory(self, source_path: str, destination_path: str) -> bool:
        """
        Move a directory from source to destination.
        
        Args:
            source_path: Source directory path
            destination_path: Destination directory path
            
        Returns:
            True if directory was moved successfully, False otherwise
        """
        try:
            if not self.path_exists(source_path) or not self.is_directory(source_path):
                return False
            
            # Create destination parent directory if it doesn't exist
            dest_parent = os.path.dirname(destination_path)
            if not self.path_exists(dest_parent):
                if not self.create_directory(dest_parent):
                    return False
            
            # Handle case where destination directory already exists
            final_destination = destination_path
            if self.path_exists(final_destination):
                # Generate unique directory name
                base_name = os.path.basename(destination_path)
                counter = 1
                while self.path_exists(final_destination):
                    new_name = f"{base_name}_{counter}"
                    final_destination = os.path.join(dest_parent, new_name)
                    counter += 1
            
            # Move the directory
            import shutil
            shutil.move(source_path, final_destination)
            return True
            
        except (OSError, PermissionError, shutil.Error):
            return False 