import sys

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtTest import QSignalSpy, QTest
from qgis.core import (
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsPoint,
    QgsPointXY,
    QgsProject,
)
from qgis.gui import (
    QgsLayerTreeMapCanvasBridge,
    QgsMapCanvas,
    QgsRubberBand,
    QgsVertexMarker,
)
from qgis.testing import unittest
from qgis.utils import plugins


class TestPickGeometryTool(unittest.TestCase):
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
        assert bridge is not None  # TODO

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

        points_clicked = [s[0][-1] for s in signals]
        # On first two clicks, click locations emitted
        self.assertEqual(points_clicked[0], QgsPointXY(200, -199))
        self.assertEqual(points_clicked[1], QgsPointXY(300, -299))
        # On right click, click location not emitted
        self.assertEqual(points_clicked[2], QgsPointXY(300, -299))

        endpoint_is_end = [s[-1] for s in signals]

        self.assertTrue(endpoint_is_end == [False, False, True])


class TestLineGeometryPickerWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets.maptools import LineGeometryPickerWidget, PickGeometryTool

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)
        assert bridge is not None  # TODO

        self.widget = LineGeometryPickerWidget(self.canvas)
        self.tooltype = PickGeometryTool
        self.signalspy = QSignalSpy(self.widget.geometries_changed)

        self.points = [QgsPointXY(200, -199), QgsPointXY(300, -299)]
        self.expected_geometry = QgsGeometry.fromPolylineXY(self.points)

    def tearDown(self):
        # Make sure MapTool is unset, otherwise QGIS dies during tests: "QGIS
        # died on signal 11"
        self.widget.stop_picking()

    def test_start_picking_map(self):
        # Test if properly initialized
        self.assertEqual(self.widget.pick_mode, 0)

        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)  # == self.widget.PICK_MAP
        # Test if mapTool set
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

    def test_stop_picking(self):
        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

    def test_start_and_stop_picking(self):
        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

    def test_picker_clicked(self):
        self.widget.picker_clicked()

        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

    def test_picker_clicked_was_active(self):
        self.widget.start_picking_map()
        self.widget.picker_clicked()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

    def test_on_picked_one_point(self):
        point = [QgsPointXY(200, -199)]

        self.assertEqual(len(self.signalspy), 0)

        self.widget.on_picked(point, False)

        self.assertEqual(self.widget.geometries, [])
        self.assertEqual(len(self.signalspy), 1)

    def test_on_picked_two_points(self):
        self.assertEqual(len(self.signalspy), 0)  # No signals emitted

        self.widget.on_picked(self.points, False)

        self.assertGeometriesEqual(self.widget.geometries[0], self.expected_geometry)
        self.assertEqual(len(self.signalspy), 1)  # Signal now emitted

    def test_on_picked_finished(self):
        self.assertEqual(len(self.signalspy), 0)

        self.widget.on_picked(self.points, True)

        self.assertGeometriesEqual(self.widget.geometries[0], self.expected_geometry)
        self.assertEqual(len(self.signalspy), 1)
        self.assertEqual(self.widget.pick_mode, 0)  # Picking should be stopped

    def test_clear_geometries(self):
        self.assertEqual(len(self.signalspy), 0)

        self.widget.on_picked(self.points, False)
        self.widget.clear_geometries()

        self.assertEqual(self.widget.geometries, [])
        self.assertEqual(len(self.signalspy), 2)


class TestMultipleLineGeometryPickerWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets.maptools import (
            MultipleLineGeometryPickerWidget,
            PickGeometryTool,
        )

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)
        assert bridge is not None  # TODO

        self.widget = MultipleLineGeometryPickerWidget(self.canvas)
        self.tooltype = PickGeometryTool

        self.points = [QgsPointXY(200, -199), QgsPointXY(300, -299)]
        self.expected_geometry = QgsGeometry.fromPolylineXY(self.points)

        self.points2 = [QgsPointXY(300, -199), QgsPointXY(200, -299)]
        self.expected_geometry2 = QgsGeometry.fromPolylineXY(self.points2)

    def tearDown(self):
        # Make sure MapTool is unset, otherwise QGIS dies during tests: "QGIS
        # died on signal 11"
        self.widget.stop_picking()

    def test_start_picking_map(self):
        # Test if properly initialized
        self.assertEqual(self.widget.pick_mode, 0)

        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)  # == self.widget.PICK_MAP
        # Test if mapTool set
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

    def test_stop_picking(self):
        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

    def test_start_and_stop_picking(self):
        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

    def test_on_picked_one_point(self):
        point = [QgsPointXY(200, -199)]

        self.widget.on_picked(point, False)

        self.assertEqual(self.widget.geometries, [])
        self.assertEqual(self.widget.last_geometry, None)

        self.assertEqual(self.widget.rubber_bands, None)
        self.assertEqual(self.widget.last_rubber_band, None)

    def test_on_picked_not_finished(self):
        self.widget.on_picked(self.points, False)

        self.assertEqual(self.widget.geometries, [])
        self.assertGeometriesEqual(self.widget.last_geometry, self.expected_geometry)

        self.assertEqual(self.widget.rubber_bands, None)
        self.assertEqual(type(self.widget.last_rubber_band), QgsRubberBand)

    def test_on_picked_finished(self):
        self.widget.on_picked(self.points, True)
        self.widget.on_picked(self.points2, True)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertGeometriesEqual(self.widget.geometries[0], self.expected_geometry)
        self.assertGeometriesEqual(self.widget.geometries[1], self.expected_geometry2)
        self.assertEqual(self.widget.last_geometry, None)

        self.assertEqual(type(self.widget.rubber_bands), QgsRubberBand)
        self.assertEqual(self.widget.last_rubber_band, None)

    def test_change_last_geometry(self):
        self.widget.last_geometry = self.expected_geometry
        self.widget.change_last_geometry()

        self.assertEqual(type(self.widget.last_rubber_band), QgsRubberBand)
        self.assertGeometriesEqual(
            self.widget.last_rubber_band.asGeometry(), self.expected_geometry
        )
        self.assertEqual(self.widget.last_rubber_band.width(), 2)
        self.assertEqual(self.widget.last_rubber_band.fillColor(), QColor(Qt.red))

    def test_draw_geometry_list(self):
        self.widget.geometries = [self.expected_geometry, self.expected_geometry2]
        self.widget.draw_geometry_list()

        mls = QgsMultiLineString()
        for linestring in self.widget.geometries:
            linestring = [QgsPoint(x=p.x(), y=p.y()) for p in linestring.asPolyline()]
            linestring = QgsLineString(linestring)
            mls.addGeometry(linestring)

        expected_geometry = QgsGeometry(mls)

        self.assertEqual(type(self.widget.rubber_bands), QgsRubberBand)
        self.assertGeometriesEqual(
            self.widget.rubber_bands.asGeometry(), expected_geometry
        )
        self.assertEqual(self.widget.rubber_bands.width(), 2)
        self.assertEqual(self.widget.rubber_bands.fillColor(), QColor(Qt.red))

    def test_clear_multilines(self):
        self.widget.geometries = [self.expected_geometry, self.expected_geometry2]
        self.widget.draw_geometry_list()
        self.widget.clear_multi_lines()

        self.assertEqual(self.widget.rubber_bands, None)
        self.assertEqual(self.widget.geometries, [])

    def test_clear_last_line(self):
        self.widget.last_geometry = self.expected_geometry
        self.widget.change_last_geometry()
        self.widget.clear_last_line()

        self.assertEqual(self.widget.last_rubber_band, None)
        self.assertEqual(self.widget.last_geometry, None)

    def test_clear_rubber_bands(self):
        self.widget.geometries = [self.expected_geometry, self.expected_geometry2]
        self.widget.draw_geometry_list()
        self.widget.last_geometry = self.expected_geometry
        self.widget.change_last_geometry()
        self.widget.clear_rubber_bands()

        self.assertEqual(self.widget.rubber_bands, None)
        self.assertEqual(self.widget.geometries, [])
        self.assertEqual(self.widget.last_rubber_band, None)
        self.assertEqual(self.widget.last_geometry, None)


class TestPickPointGeometryTool(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets.maptools import PickPointGeometryTool

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)
        assert bridge is not None  # TODO

        self.tool = PickPointGeometryTool(self.canvas)
        self.signalspy = QSignalSpy(self.tool.picked)

        self.canvas.setMapTool(self.tool)

    def test_canvasPressEvent(self):
        viewport = self.canvas.viewport()

        # Source of this solution:
        # https://gis.stackexchange.com/questions/250234/qtest-interactions-with-the-qgis-map-canvas
        QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(200, 200))
        QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(300, 300), delay=200)
        QTest.mouseClick(viewport, Qt.RightButton, pos=QPoint(400, 400), delay=400)

        signals = list(self.signalspy)

        # Three signals are emitted (2 left clicks + 1 right click)
        self.assertTrue(len(signals) == 3)
        # Length of geometry list emitted should be 1
        is_length_1 = [len(s[0]) == 1 for s in signals]
        self.assertTrue(all(is_length_1))

        # On first two clicks, click locations emitted
        points_clicked = [s[0][0] for s in signals]
        self.assertEqual(points_clicked[0], QgsPointXY(200, -199))
        self.assertEqual(points_clicked[1], QgsPointXY(300, -299))
        self.assertEqual(points_clicked[2], QgsPointXY(400, -399))

        endpoint_is_end = [s[-1] for s in signals]

        self.assertTrue(endpoint_is_end == [False, False, True])

    def test_canvasPressEvent_modified(self):
        """Add CTRL modifier"""
        viewport = self.canvas.viewport()

        # Source of this solution:
        # https://gis.stackexchange.com/questions/250234/qtest-interactions-with-the-qgis-map-canvas
        QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(200, 200))
        QTest.mouseClick(
            viewport,
            Qt.LeftButton,
            modifier=Qt.ControlModifier,
            pos=QPoint(300, 300),
            delay=200,
        )
        QTest.mouseClick(
            viewport,
            Qt.RightButton,
            modifier=Qt.ControlModifier,
            pos=QPoint(400, 400),
            delay=400,
        )

        signals = list(self.signalspy)

        # Three signals are emitted (2 left clicks + 1 right click)
        self.assertTrue(len(signals) == 3)
        # Length of geometry list emitted should be 1
        is_length_1 = [len(s[0]) == 1 for s in signals]
        self.assertTrue(all(is_length_1))

        # On first two clicks, click locations emitted
        points_clicked = [s[0][0] for s in signals]
        self.assertEqual(points_clicked[0], QgsPointXY(200, -199))
        self.assertEqual(points_clicked[1], QgsPointXY(300, -299))
        self.assertEqual(points_clicked[2], QgsPointXY(400, -399))

        endpoint_is_end = [s[-1] for s in signals]
        self.assertTrue(endpoint_is_end == [False, False, True])

        is_ctrl_clicked = [s[2] for s in signals]
        # Last element should be False, because CTRL modifier is ignored upon
        # right-click.
        self.assertTrue(is_ctrl_clicked == [False, True, False])


class TestPointGeometryPickerWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets.maptools import (
            PickPointGeometryTool,
            PointGeometryPickerWidget,
        )

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)
        assert bridge is not None  # TODO

        self.widget = PointGeometryPickerWidget(self.canvas)
        self.tooltype = PickPointGeometryTool

        self.signalspy = QSignalSpy(self.widget.geometries_changed)

        self.point1 = QgsPointXY(200, -199)
        self.point2 = QgsPointXY(300, -299)

    def test_start_picking_map(self):
        # Test if properly initialized
        self.assertEqual(self.widget.pick_mode, 0)

        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)  # == self.widget.PICK_MAP
        # Test if mapTool set
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.assertEqual(len(self.signalspy), 1)  # clear_geometries() called

    def test_stop_picking(self):
        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

        self.assertEqual(len(self.signalspy), 0)  # No signals should be sent

    def test_start_and_stop_picking(self):
        self.widget.start_picking_map()

        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.widget.stop_picking()

        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

        self.assertEqual(len(self.signalspy), 1)  # clear_geometries() called

    def test_on_picked_clicked(self):
        """No ctrl_click, not finished"""
        self.widget.start_picking_map()
        self.widget.on_picked([self.point1], True, False, False)
        self.widget.on_picked([self.point2], True, False, False)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertEqual(self.widget.geometries[0], self.point1)
        self.assertEqual(self.widget.geometries[1], self.point2)

        self.assertEqual(len(self.widget.markers), 2)
        self.assertEqual(type(self.widget.markers[0]), QgsVertexMarker)
        self.assertEqual(self.widget.temp_geometry_index, -1)

        # Assert picking stopped (no CTRL click)
        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

        self.assertEqual(len(self.signalspy), 3)

    def test_on_picked_ctrl_clicked(self):
        """ctrl_click, not finished"""
        self.widget.start_picking_map()
        self.widget.on_picked([self.point1], True, True, False)
        self.widget.on_picked([self.point2], True, True, False)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertEqual(self.widget.geometries[0], self.point1)
        self.assertEqual(self.widget.geometries[1], self.point2)

        self.assertEqual(len(self.widget.markers), 2)
        self.assertEqual(type(self.widget.markers[0]), QgsVertexMarker)
        self.assertEqual(self.widget.temp_geometry_index, -1)

        # Assert still picking
        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.assertEqual(len(self.signalspy), 3)

    def test_on_picked_ctrl_clicked_finished(self):
        """ctrl_click, finished"""
        self.widget.start_picking_map()
        self.widget.on_picked([self.point1], True, True, False)
        self.widget.on_picked([self.point2], True, True, True)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertEqual(self.widget.geometries[0], self.point1)
        self.assertEqual(self.widget.geometries[1], self.point2)

        self.assertEqual(len(self.widget.markers), 2)
        self.assertEqual(type(self.widget.markers[0]), QgsVertexMarker)
        self.assertEqual(self.widget.temp_geometry_index, -1)

        # Assert picking stopped
        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

        self.assertEqual(len(self.signalspy), 3)

    def test_on_picked_ctrl_clicked_then_clicked(self):
        """1st ctrl_click, 2nd not ctrl_click"""
        self.widget.start_picking_map()
        self.widget.on_picked([self.point1], True, True, False)
        self.widget.on_picked([self.point2], True, False, False)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertEqual(self.widget.geometries[0], self.point1)
        self.assertEqual(self.widget.geometries[1], self.point2)

        self.assertEqual(len(self.widget.markers), 2)
        self.assertEqual(type(self.widget.markers[0]), QgsVertexMarker)
        self.assertEqual(self.widget.temp_geometry_index, -1)

        # Assert picking stopped
        self.assertEqual(self.widget.pick_mode, 0)
        self.assertEqual(type(self.canvas.mapTool()), type(None))

        self.assertEqual(len(self.signalspy), 3)

    def test_on_picked_mouse_move(self):
        """1st ctrl_click, then just move mouse."""
        self.widget.start_picking_map()
        self.widget.on_picked([self.point1], True, True, False)
        self.widget.on_picked([self.point2], False, False, False)

        self.assertEqual(len(self.widget.geometries), 2)
        self.assertEqual(self.widget.geometries[0], self.point1)
        self.assertEqual(self.widget.geometries[1], self.point2)

        # No marker drawn for moving the mouse
        self.assertEqual(len(self.widget.markers), 1)
        self.assertEqual(type(self.widget.markers[0]), QgsVertexMarker)
        self.assertEqual(self.widget.temp_geometry_index, 1)

        # Assert still picking
        self.assertEqual(self.widget.pick_mode, 1)
        self.assertEqual(type(self.canvas.mapTool()), self.tooltype)

        self.assertEqual(len(self.signalspy), 3)

    def test_clear_geometries(self):
        self.widget.on_picked([self.point1], True, True, False)
        self.widget.on_picked([self.point2], False, False, False)
        self.widget.clear_geometries()

        self.assertEqual(self.widget.geometries, [])
        self.assertEqual(self.widget.markers, [])
        self.assertEqual(self.widget.temp_geometry_index, -1)

        self.assertEqual(len(self.signalspy), 3)


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestPickGeometryTool))
    suite.addTests(unittest.makeSuite(TestLineGeometryPickerWidget))
    suite.addTests(unittest.makeSuite(TestMultipleLineGeometryPickerWidget))
    suite.addTests(unittest.makeSuite(TestPickPointGeometryTool))
    suite.addTests(unittest.makeSuite(TestPointGeometryPickerWidget))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
