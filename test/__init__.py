# import qgis libs so that we set the correct sip api version
try:
    import qgis   # pylint: disable=W0611  # NOQA
except ImportError:
    # QGIS not available in current environment
    # This is expected when running tests outside of QGIS
    pass