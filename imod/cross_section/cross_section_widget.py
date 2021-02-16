from PyQt5.QtWidgets import (
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
    QToolButton,
    QMenu,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsColorButton,
    QgsColorRampButton,
    QgsVertexMarker,
    QgsRubberBand,
    QgsMapTool,
)
from qgis.core import (
    QgsColorBrewerColorRamp,
    QgsGeometry,
    QgsWkbTypes,
    QgsPointXY,
    QgsMeshDatasetIndex
)

import numpy as np
import pyqtgraph as pg

from .pcolormesh import PColorMeshItem
from .plot_util import cross_section_x_data, cross_section_y_data
from ..utils.layers import groupby_variable

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
        self.clear_geometries()

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


class ImodCrossSectionWidget(QWidget):
    #TODO: Use QGIS colormaps instead of pyqt ones
    #TODO: Fix bug, so that "holes" in data by line are not connected in crosssection
    #TODO: Filter Raster data
    #TODO: Include select variable box to be plotted
    #TODO: Include resolution setting in box
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface
        self.layer_selection = QgsMapLayerComboBox()
        # TODO: Filter for mesh and raster layers
        self.line_picker = LineGeometryPickerWidget(iface)
        self.line_picker.geometries_changed.connect(
            self.on_geometries_changed
            )

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True)

        self.rubber_band = None

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.line_picker)

        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

    def hideEvent(self, e):
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.line_picker.clear_geometries()
        self.clear_legend()

    def clear_legend(self):
        pass

    def get_group_names(self):
        current_layer = self.layer_selection.currentLayer()
        idx = current_layer.datasetGroupsIndexes()
        #TODO: Include time index as dataset argument during QgsMeshDatasetIndex construction
        idx = [QgsMeshDatasetIndex(group=i, dataset=0) for i in idx]
        group_names = [current_layer.datasetGroupMetadata(i).name() for i in idx]

        return idx, group_names

    def _repeat_to_2d(self, arr, n, axis=0):
        """Repeat array n times along new axis
        
        Parameters
        ----------
        arr : np.array[m]
        
        n : int
        

        Returns
        -------
        np.array[n x m]

        """
        return np.repeat(np.expand_dims(arr, axis=axis), n, axis=axis)

    def extract_cross_section_data(self):
        current_layer = self.layer_selection.currentLayer()
        idx, group_names = self.get_group_names()
        gb_var = groupby_variable(group_names, idx)

        #Get arbitrary key
        first_key = next(iter(gb_var.keys()))

        #Get layer numbers: first element contains layer number
        layer_nrs = next(zip(*gb_var[first_key]))
        layer_nrs = list(layer_nrs)
        layer_nrs.sort()
        n_lay = len(layer_nrs)

        #TODO: Are there ever more geometries than one Linestring?
        geometry = self.line_picker.geometries[0] 

        #Get x values of points
        x = cross_section_x_data(current_layer, geometry, resolution=50.)
        n_x = x.size
        y = np.zeros((n_lay * 2, n_x))

        #FUTURE: When MDAL supports UGRID layer, looping over layers not necessary.
        for k in range(n_lay):
            layer_nr, dataset_bottom = gb_var["bottom"][k]
            layer_nr, dataset_top    = gb_var["top"][k]

            i = layer_nr * 2 - 1
            y[i-1, :] = cross_section_y_data(current_layer, geometry, dataset_top, x)
            y[i, :] = cross_section_y_data(current_layer, geometry, dataset_bottom, x)

        #Filter values line outside mesh
        #Assume: NaNs in first layer are NaNs in every layer
        is_nan = np.isnan(y[0, :]) 
        y = y[:, ~is_nan]
        x = x[~is_nan]
        n_x = x.size

        #Repeat x along new dimension to get np.meshgrid like thing
        x = self._repeat_to_2d(x, n_lay * 2)

        #Color by layer
        z = np.empty((n_lay * 2 - 1, n_x - 1))
        z[:] = np.nan
        z[::2, :] = np.expand_dims(layer_nrs, axis=1)
        
        return x, y, z

    def draw_plot(self):
        x, y, z = self.extract_cross_section_data()

        #debug
        self.x_values = x
        self.y_values = y

        pcmi = PColorMeshItem(x, y, z, cmap="inferno")
        self.plot_widget.addItem(pcmi)

        # Might be smart to draw ConvexPolygons instead of pColorMeshItem,
        # (see code in pColorMeshItem)
        # https://github.com/pyqtgraph/pyqtgraph/blob/5eb671217c295178de255b1fece56379cdef8235/pyqtgraph/graphicsItems/PColorMeshItem.py#L140
        # So we can draw rectangular polygons if necessary.

    def on_geometries_changed(self):
        self.iface.mapCanvas().scene().removeItem(self.rubber_band)
        if len(self.line_picker.geometries) == 0:
            return
        self.rubber_band = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.rubber_band.setColor(QColor(Qt.red))
        self.rubber_band.setWidth(2)
        self.rubber_band.setToGeometry(self.line_picker.geometries[0], None)