from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsProject, QgsPointXY
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
import sys

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest, QSignalSpy


class TestPickGeometryWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets.maptools import PickGeometryTool

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)

        self.tool = PickGeometryTool(self.canvas)

    def test_canvasPressEvent(self):
        viewport = self.canvas.viewport()

        signalspy = QSignalSpy(self.tool.picked)
        self.canvas.setMapTool(self.tool)

        # Source of this solution:
        # https://gis.stackexchange.com/questions/250234/qtest-interactions-with-the-qgis-map-canvas
        QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(200, 200))
        capturing_first_click = self.tool.capturing
        QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(300, 300), delay=200)
        QTest.mouseClick(viewport, Qt.RightButton, pos=QPoint(400, 400), delay=400)
        capturing_last_click = self.tool.capturing

        self.assertTrue(capturing_first_click)
        self.assertFalse(capturing_last_click)

        signals = list(signalspy)

        # Three signals are emitted (2 left clicks + 1 right click)
        self.assertTrue(len(signals) == 3)

        # On first two clicks, click locations emitted
        self.assertEqual(signals[0][0][-1], QgsPointXY(200, -199))
        self.assertEqual(signals[1][0][-1], QgsPointXY(300, -299))
        # On right click, click location not emitted
        self.assertEqual(signals[2][0][-1], QgsPointXY(300, -299))

        endpoint_is_end = [s[-1] for s in signals]

        self.assertTrue(endpoint_is_end == [False, False, True])


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestPickGeometryWidget))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
