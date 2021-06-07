# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
)
from PyQt5.QtGui import QColor

from qgis.core import (
    QgsPointXY,
    QgsPoint,
    QgsLineString,
    QgsMultiLineString,
    QgsRectangle,
    QgsWkbTypes,
    QgsGeometry,
    QgsMesh,
)
from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsRubberBand, QgsVertexMarker

RUBBER_BAND_COLOR = QColor(Qt.red)


class RectangleMapTool(QgsMapToolEmitPoint):
    rectangleCreated = pyqtSignal()
    deactivated = pyqtSignal()

    def __init__(self, canvas):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)

        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))
        self.rubberBand.setWidth(2)

        self.reset()

        self.bbox = None

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.startPoint = self.toMapCoordinates(e.pos())
            self.endPoint = self.startPoint
            self.isEmittingPoint = True
            self.showRect(self.startPoint, self.endPoint)

        if e.button() == Qt.RightButton:
            self.reset()
            self.deactivate()

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        if self.rectangle() is not None:
            self.rectangleCreated.emit()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        # True to update canvas
        self.rubberBand.addPoint(point4, True)
        self.rubberBand.show()

    def rectangle(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (
            self.startPoint.x() == self.endPoint.x()
            or self.startPoint.y() == self.endPoint.y()
        ):
            return None

        return QgsRectangle(self.startPoint, self.endPoint)

    def setRectangle(self, rect):
        if rect == self.rectangle():
            return False

        if rect is None:
            self.reset()
        else:
            self.startPoint = QgsPointXY(rect.xMaximum(), rect.yMaximum())
            self.endPoint = QgsPointXY(rect.xMinimum(), rect.yMinimum())
            self.showRect(self.startPoint, self.endPoint)
        return True

    def deactivate(self):
        QgsMapTool.deactivate(self)
        self.deactivated.emit()


class PickGeometryTool(QgsMapTool):
    picked = pyqtSignal(
        list, bool
    )  # list of pointsXY, whether finished or still drawing

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.points = []
        self.capturing = False

    def canvasMoveEvent(self, e):
        if not self.capturing:
            return
        self.picked.emit(self.points + [e.mapPoint()], False)

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.capturing = True
            self.points.append(e.mapPoint())
            self.picked.emit(self.points, False)
        if e.button() == Qt.RightButton:
            self.picked.emit(self.points, True)
            self.capturing = False
            self.points = []

    def canvasReleaseEvent(self, e):
        pass


class LineGeometryPickerWidget(QWidget):
    geometries_changed = pyqtSignal()
    PICK_NO, PICK_MAP, PICK_LAYER = range(3)

    def __init__(self, iface, parent=None):
        QWidget.__init__(self, parent)

        self.iface = iface
        self.pick_mode = self.PICK_NO
        self.pick_layer = None
        self.geometries = []

        self.button = QPushButton("From map")
        self.button.clicked.connect(self.picker_clicked)
        self.button.clicked.connect(self.clear_geometries)

        self.tool = PickGeometryTool(self.iface.mapCanvas())
        self.tool.picked.connect(self.on_picked)
        self.tool.setButton(self.button)

        layout = QHBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

    def clear_geometries(self):
        self.geometries = []
        self.geometries_changed.emit()

    def picker_clicked(self):
        was_active = self.pick_mode == self.PICK_MAP
        self.stop_picking()
        if not was_active:
            self.start_picking_map()

    def start_picking_map(self):
        self.pick_mode = self.PICK_MAP
        self.iface.mapCanvas().setMapTool(self.tool)

    def stop_picking(self):
        if self.pick_mode == self.PICK_MAP:
            self.iface.mapCanvas().unsetMapTool(self.tool)
        elif self.pick_mode == self.PICK_LAYER:
            self.pick_layer.selectionChanged.disconnect(self.on_pick_selection_changed)
            self.pick_layer = None
        self.pick_mode = self.PICK_NO

    def on_picked(self, points, finished):
        if len(points) >= 2:
            self.geometries = [QgsGeometry.fromPolylineXY(points)]
        else:
            self.geometries = []
        self.geometries_changed.emit()
        if finished:  # no more updates
            self.stop_picking()


class MultipleLineGeometryPickerWidget(QWidget):
    PICK_NO, PICK_MAP, PICK_LAYER = range(3)

    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.pick_mode = self.PICK_NO
        self.pick_layer = None
        self.geometries = []
        self.last_geometry = None

        self.draw_button = QPushButton("Draw fence diagram")
        self.draw_button.clicked.connect(self.picker_clicked)
        self.draw_button.clicked.connect(self.clear_multi_lines)
        self.draw_button.clicked.connect(self.clear_last_line)

        self.clear_button = QPushButton("Clear fence diagram")
        self.clear_button.clicked.connect(self.clear_rubber_bands)
        self.clear_button.clicked.connect(self.stop_picking)

        self.tool = PickGeometryTool(canvas)
        self.tool.picked.connect(self.on_picked)
        self.tool.setButton(self.draw_button)

        self.last_rubber_band = None
        self.rubber_bands = None

    def create_layout(self):
        """
        Create new layout for widget, as a vertical column.
        Adding this layout to another layout creates a nested
        layout.
        """
        layout = QVBoxLayout()

        layout.addWidget(self.draw_button)
        layout.addWidget(self.clear_button)
        self.setLayout(layout)

    def add_to_layout(self, layout):
        """Add widget to existing layout"""
        layout.addWidget(self.draw_button)
        layout.addWidget(self.clear_button)

    def clear_multi_lines(self):
        self.geometries = []
        self.canvas.scene().removeItem(self.rubber_bands)
        self.rubber_bands = None

    def clear_last_line(self):
        self.last_geometry = None
        self.canvas.scene().removeItem(self.last_rubber_band)
        self.last_rubber_band = None

    def picker_clicked(self):
        was_active = self.pick_mode == self.PICK_MAP
        if not was_active:
            self.start_picking_map()

    def start_picking_map(self):
        self.pick_mode = self.PICK_MAP
        self.canvas.setMapTool(self.tool)

    def on_picked(self, points, finished):
        if len(points) >= 2:
            self.last_geometry = QgsGeometry.fromPolylineXY(points)

        if finished:
            self.clear_last_line()
            if len(points) >= 2:
                self.geometries.append(QgsGeometry.fromPolylineXY(points))
                self.draw_geometry_list()
        else:
            self.change_last_geometry()

    def clear_rubber_bands(self):
        self.clear_multi_lines()
        self.clear_last_line()

    def stop_picking(self):
        self.canvas.unsetMapTool(self.tool)
        self.pick_mode = self.PICK_NO

    def draw_geometry_list(self):
        if len(self.geometries) == 0:
            return

        # Remove previous items
        self.canvas.scene().removeItem(self.rubber_bands)

        self.rubber_bands = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubber_bands.setColor(RUBBER_BAND_COLOR)
        self.rubber_bands.setWidth(2)
        # Create multilinestring
        mls = QgsMultiLineString()
        for linestring in self.geometries:
            linestring = [QgsPoint(x=p.x(), y=p.y()) for p in linestring.asPolyline()]
            linestring = QgsLineString(linestring)
            mls.addGeometry(linestring)
        # Draw
        self.rubber_bands.setToGeometry(QgsGeometry(mls), None)

    def change_last_geometry(self):
        if self.last_geometry is None:
            return

        self.canvas.scene().removeItem(self.last_rubber_band)
        self.last_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.last_rubber_band.setColor(RUBBER_BAND_COLOR)
        self.last_rubber_band.setWidth(2)
        self.last_rubber_band.setToGeometry(self.last_geometry, None)


class PickPointGeometryTool(QgsMapTool):
    picked = pyqtSignal(
        QgsPointXY, bool, bool
    )  # point, whether clicked or just moving, whether clicked with Ctrl

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)

    def canvasMoveEvent(self, e):
        self.picked.emit(e.mapPoint(), False, False)

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.picked.emit(e.mapPoint(), True, e.modifiers() & Qt.ControlModifier)

    def canvasReleaseEvent(self, e):
        pass


class PointGeometryPickerWidget(QWidget):
    geometries_changed = pyqtSignal()
    PICK_NO = 0
    PICK_MAP = 1

    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)
        self.canvas = canvas
        self.pick_mode = self.PICK_NO
        self.geometries = []
        self.markers = []
        self.temp_geometry_index = -1
        self.tool = PickPointGeometryTool(self.canvas)
        self.tool.picked.connect(self.on_picked)
        self.updating = True

    def clear_geometries(self):
        self.geometries = []
        for marker in self.markers:
            self.canvas.scene().removeItem(marker)
        self.markers = []
        self.temp_geometry_index = -1
        self.geometries_changed.emit()

    def picker_clicked(self):
        was_active = self.pick_mode == self.PICK_MAP
        self.stop_picking()
        if not was_active:
            self.start_picking_map()

    def start_picking_map(self):
        self.pick_mode = self.PICK_MAP
        self.canvas.setMapTool(self.tool)
        self.clear_geometries()

    def stop_picking(self):
        if self.pick_mode == self.PICK_MAP:
            self.canvas.unsetMapTool(self.tool)
        self.pick_mode = self.PICK_NO

    def on_picked(self, geom, clicked, with_ctrl):
        if clicked:
            if self.temp_geometry_index == -1:
                self.geometries.append(geom)
            else:
                self.geometries[self.temp_geometry_index] = geom
                self.temp_geometry_index = -1
            marker = QgsVertexMarker(self.canvas)
            marker.setPenWidth(2)
            marker.setCenter(geom)
            self.markers.append(marker)
        else:  # just doing mouse move
            if self.temp_geometry_index == -1:
                self.temp_geometry_index = len(self.geometries)
                self.geometries.append(geom)
            else:
                self.geometries[self.temp_geometry_index] = geom

        self.geometries_changed.emit()
        if clicked and (self.updating and not with_ctrl):  # no more updates
            self.stop_picking()
