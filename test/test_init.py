# coding=utf-8
"""Tests QGIS plugin init."""

__author__ = 'Tim Sutton <tim@linfiniti.com>'
__revision__ = '$Format:%H$'
__date__ = '17/10/2010'
__license__ = "GPL"
__copyright__ = 'Copyright 2012, Australia Indonesia Facility for '
__copyright__ += 'Disaster Reduction'

import os
import pytest
import logging
import configparser

LOGGER = logging.getLogger('QGIS')


class TestInit:
    """Test that the plugin init is usable for QGIS.

    Based heavily on the validator class by Alessandro
    Passoti available here:

    http://github.com/qgis/qgis-django/blob/master/qgis-app/
             plugins/validator.py

    """

    def test_read_init(self):
        """Test that the plugin __init__ will validate on plugins.qgis.org."""

        # You should update this list according to the latest in
        # https://github.com/qgis/qgis-django/blob/master/qgis-app/
        #        plugins/validator.py

        required_metadata = [
            'name',
            'description',
            'version',
            'qgisMinimumVersion',
            'qgisMaximumVersion',
            'email',
            'author']

        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            'metadata.txt'))
        LOGGER.info(file_path)
        metadata = []
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(file_path)
        message = 'Cannot find a section named "general" in %s' % file_path
        assert parser.has_section('general'), message
        metadata.extend(parser.items('general'))

        for expectation in required_metadata:
            message = ('Cannot find metadata "%s" in metadata source (%s).' % (
                expectation, file_path))

            assert expectation in dict(metadata), message

    def test_qgis_version_range_supports_3_and_4(self):
        """Ensure declared compatibility covers both QGIS 3 and QGIS 4."""
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            'metadata.txt'))
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(file_path)
        assert parser.has_section('general')

        minimum_version = parser.get('general', 'qgisMinimumVersion')
        maximum_version = parser.get('general', 'qgisMaximumVersion')

        min_major = int(minimum_version.split('.')[0])
        max_major = int(maximum_version.split('.')[0])

        assert min_major <= 3, "qgisMinimumVersion must keep QGIS 3 compatibility."
        assert max_major >= 4, "qgisMaximumVersion must advertise QGIS 4 compatibility."

if __name__ == '__main__':
    pytest.main([__file__])
