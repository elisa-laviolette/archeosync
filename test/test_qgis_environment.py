# coding=utf-8
"""Tests for QGIS functionality.


.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
__author__ = 'tim@linfiniti.com'
__date__ = '20/01/2011'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')

import os
import pytest
from .utilities import get_qgis_app

# Try to import QGIS modules, skip tests if not available
try:
    from qgis.core import (
        QgsProviderRegistry,
        QgsCoordinateReferenceSystem,
        QgsRasterLayer)
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

QGIS_APP = get_qgis_app()


@pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")
class TestQGIS:
    """Test the QGIS Environment"""

    def test_qgis_environment(self):
        """QGIS environment has the expected providers"""

        r = QgsProviderRegistry.instance()
        providers = r.providerList()
        
        # Check for core providers that should be available
        assert 'gdal' in providers, f"GDAL provider not found. Available: {providers}"
        assert 'ogr' in providers, f"OGR provider not found. Available: {providers}"
        
        # PostgreSQL provider is optional, so we'll just log if it's missing
        if 'postgres' not in providers:
            print(f"Warning: PostgreSQL provider not available. Available providers: {providers}")

    def test_projection(self):
        """Test that QGIS properly parses a wkt string.
        """
        crs = QgsCoordinateReferenceSystem()
        wkt = (
            'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
            'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",'
            '0.0174532925199433]]')
        crs.createFromWkt(wkt)
        auth_id = crs.authid()
        
        # Both EPSG:4326 and OGC:CRS84 are valid identifiers for WGS84
        expected_auth_ids = ['EPSG:4326', 'OGC:CRS84']
        assert auth_id in expected_auth_ids, f"Expected one of {expected_auth_ids}, got {auth_id}"

        # now test for a loaded layer
        path = os.path.join(os.path.dirname(__file__), 'tenbytenraster.asc')
        title = 'TestRaster'
        layer = QgsRasterLayer(path, title)
        layer_auth_id = layer.crs().authid()
        assert layer_auth_id in expected_auth_ids, f"Expected one of {expected_auth_ids}, got {layer_auth_id}"

if __name__ == '__main__':
    pytest.main([__file__])
