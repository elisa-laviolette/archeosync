# -*- coding: utf-8 -*-
"""
Tests for ArcheoSync settings functionality.

This module contains tests for the QGISSettingsManager class and related
settings management functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from qgis.PyQt.QtCore import QSettings

# Add the parent directory to the path to allow importing the plugin
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.settings_service import QGISSettingsManager


class TestArcheoSyncSettings(unittest.TestCase):
    """Test cases for QGISSettingsManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock QSettings to avoid affecting actual QGIS settings
        self.settings_patcher = patch('services.settings_service.QSettings')
        self.mock_qsettings_class = self.settings_patcher.start()
        self.mock_qsettings = Mock()
        self.mock_qsettings_class.return_value = self.mock_qsettings
        
        # Create settings manager instance
        self.settings_manager = QGISSettingsManager()

    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()

    def test_init(self):
        """Test settings manager initialization."""
        # Verify QSettings was created
        self.mock_qsettings_class.assert_called_once()
        
        # Verify plugin group is set correctly
        self.assertEqual(self.settings_manager.plugin_group, 'ArcheoSync')

    def test_set_value(self):
        """Test setting a value."""
        # Test data
        key = 'test_key'
        value = 'test_value'
        
        # Call method
        self.settings_manager.set_value(key, value)
        
        # Verify QSettings methods were called correctly
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.setValue.assert_called_with(key, value)
        self.mock_qsettings.endGroup.assert_called()

    def test_get_value_with_default(self):
        """Test getting a value with default."""
        # Test data
        key = 'test_key'
        default = 'default_value'
        
        # Mock QSettings.value to return the default
        self.mock_qsettings.value.return_value = default
        
        # Call method
        result = self.settings_manager.get_value(key, default)
        
        # Verify result
        self.assertEqual(result, default)
        
        # Verify QSettings methods were called correctly
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.value.assert_called_with(key, default)
        self.mock_qsettings.endGroup.assert_called()

    def test_get_value_existing(self):
        """Test getting an existing value."""
        # Test data
        key = 'test_key'
        stored_value = 'stored_value'
        default = 'default_value'
        
        # Mock QSettings.value to return the stored value
        self.mock_qsettings.value.return_value = stored_value
        
        # Call method
        result = self.settings_manager.get_value(key, default)
        
        # Verify result
        self.assertEqual(result, stored_value)
        
        # Verify QSettings methods were called correctly
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.value.assert_called_with(key, default)
        self.mock_qsettings.endGroup.assert_called()

    def test_remove_value(self):
        """Test removing a value."""
        # Test data
        key = 'test_key'
        
        # Call method
        self.settings_manager.remove_value(key)
        
        # Verify QSettings methods were called correctly
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.remove.assert_called_with(key)
        self.mock_qsettings.endGroup.assert_called()

    def test_clear_all(self):
        """Test clearing all settings."""
        # Call method
        self.settings_manager.clear_all()
        
        # Verify QSettings methods were called correctly
        self.mock_qsettings.beginGroup.assert_called_with('ArcheoSync')
        self.mock_qsettings.clear.assert_called()
        self.mock_qsettings.endGroup.assert_called()

    def test_multiple_operations(self):
        """Test multiple operations in sequence."""
        # Set multiple values
        self.settings_manager.set_value('key1', 'value1')
        self.settings_manager.set_value('key2', 'value2')
        
        # Mock get operations
        self.mock_qsettings.value.side_effect = ['value1', 'value2']
        
        # Get values
        result1 = self.settings_manager.get_value('key1', 'default1')
        result2 = self.settings_manager.get_value('key2', 'default2')
        
        # Verify results
        self.assertEqual(result1, 'value1')
        self.assertEqual(result2, 'value2')
        
        # Verify all operations used the correct group
        expected_calls = [
            (('ArcheoSync',),),
            (('key1', 'value1'),),
            (),
            (('ArcheoSync',),),
            (('key2', 'value2'),),
            (),
            (('ArcheoSync',),),
            (('key1', 'default1'),),
            (),
            (('ArcheoSync',),),
            (('key2', 'default2'),),
            ()
        ]
        
        # Verify beginGroup and endGroup calls
        begin_group_calls = [call for call in self.mock_qsettings.beginGroup.call_args_list]
        end_group_calls = [call for call in self.mock_qsettings.endGroup.call_args_list]
        
        self.assertEqual(len(begin_group_calls), 4)  # 2 sets + 2 gets
        self.assertEqual(len(end_group_calls), 4)

    def test_different_data_types(self):
        """Test setting and getting different data types."""
        test_cases = [
            ('string', 'test_string'),
            ('integer', 42),
            ('float', 3.14),
            ('boolean', True),
            ('list', [1, 2, 3]),
            ('dict', {'key': 'value'}),
        ]
        
        for data_type, value in test_cases:
            with self.subTest(data_type=data_type):
                # Set value
                self.settings_manager.set_value(f'{data_type}_key', value)
                
                # Mock get operation
                self.mock_qsettings.value.return_value = value
                
                # Get value
                result = self.settings_manager.get_value(f'{data_type}_key', None)
                
                # Verify result
                self.assertEqual(result, value)


class TestArcheoSyncSettingsIntegration(unittest.TestCase):
    """Integration tests for settings functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create settings manager with real QSettings
        self.settings_manager = QGISSettingsManager()

    def tearDown(self):
        """Clean up after tests."""
        # Clear any settings that were set during tests
        self.settings_manager.clear_all()

    def test_real_settings_persistence(self):
        """Test that settings actually persist using real QSettings."""
        # Set a value
        test_key = 'integration_test_key'
        test_value = 'integration_test_value'
        self.settings_manager.set_value(test_key, test_value)
        
        # Create a new settings manager instance
        new_settings_manager = QGISSettingsManager()
        
        # Retrieve the value
        retrieved_value = new_settings_manager.get_value(test_key, 'default')
        
        # Verify the value was persisted
        self.assertEqual(retrieved_value, test_value)

    def test_settings_isolation(self):
        """Test that settings are properly isolated by plugin group."""
        # Set a value in our plugin group
        test_key = 'isolation_test_key'
        test_value = 'isolation_test_value'
        self.settings_manager.set_value(test_key, test_value)
        
        # Create a settings manager with a different group
        other_settings_manager = QGISSettingsManager('OtherPlugin')
        
        # Try to retrieve the value from the other group
        retrieved_value = other_settings_manager.get_value(test_key, 'default')
        
        # Verify the value is not found in the other group
        self.assertEqual(retrieved_value, 'default')


if __name__ == '__main__':
    unittest.main() 