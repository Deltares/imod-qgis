"""
pytest setup for running the tests outside of QGIS, e.g. with `pixi run test`.

pytest-qgis starts a QgsApplication and provides a mocked QgisInterface. The
tests expect the plugin to be loaded in ``qgis.utils.plugins``, as QGIS does
when it starts, so we do the same here.
"""

import pytest
import qgis.utils


@pytest.fixture(autouse=True, scope="session")
def imodqgis_plugin(qgis_iface):
    import imodqgis

    # The mocked addDockWidget does nothing, so docks would never become
    # visible. Add them to the (shown) main window like QGIS does.
    main_window = qgis_iface.mainWindow()
    qgis_iface.addDockWidget = main_window.addDockWidget
    qgis_iface.removeDockWidget = main_window.removeDockWidget
    main_window.show()

    plugin = imodqgis.classFactory(qgis_iface)
    plugin.initGui()
    qgis.utils.plugins["imodqgis"] = plugin
    yield plugin
    del qgis.utils.plugins["imodqgis"]
