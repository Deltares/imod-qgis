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
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPointF
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsVertexMarker,
    QgsRubberBand,
    QgsMapTool,
)
from qgis.core import (
    QgsGeometry,
    QgsWkbTypes,
    QgsPointXY,
    QgsMeshDatasetIndex,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsMapLayerType,
    QgsRaster,
)
from qgis import processing

import pathlib
from typing import List, Tuple

import numpy as np
import pyqtgraph as pg
from pyqtgraph.GraphicsScene.exportDialog import ExportDialog

from .pcolormesh import PColorMeshItem
from .borehole_plot_item import BoreholePlotItem
from .plot_util import (
    cross_section_x_data,
    cross_section_y_data,
    cross_section_hue_data,
    project_points_to_section,
)
from ..widgets import MultipleVariablesWidget, VariablesWidget, ImodPseudoColorWidget, ImodUniqueColorWidget
from ..utils.layers import groupby_variable, get_group_names
from ..ipf import IpfType, read_associated_borehole


def select_boreholes(
    layer: QgsVectorLayer, buffer_distance: float, geometry: QgsGeometry
) -> Tuple[np.ndarray, List[str], List[pathlib.Path]]:
    # Create a tempory layer to contain the buffer geometry
    buffered = geometry.buffer(buffer_distance, 4)
    tmp_layer = QgsVectorLayer("Polygon", "temp", "memory")
    tmp_layer.setCrs(QgsProject.instance().crs())
    tmp_feature = QgsFeature()
    tmp_feature.setGeometry(buffered)
    tmp_layer.dataProvider().addFeature(tmp_feature)

    # Collect the boreholes per layer
    boreholes_id = []
    paths = []
    points = []
    # Due to the selection, another column is added at the left
    indexcol = int(layer.customProperty("ipf_indexcolumn"))
    ext = layer.customProperty("ipf_assoc_ext")
    parent = pathlib.Path(layer.customProperty("ipf_path")).parent
    output = processing.run(
        "native:extractbylocation",
        {
            "INPUT": layer,
            "PREDICATE": 6,  # are within
            "INTERSECT": tmp_layer,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    for feature in output.getFeatures():
        filename = feature.attribute(indexcol)
        boreholes_id.append(filename)
        paths.append(parent.joinpath(f"{filename}.{ext}"))
        points.append(feature.geometry().asPoint())

    if len(points) > 0:
        x = project_points_to_section(points, geometry)
    else:
        x = []
    return x, boreholes_id, paths


def color_by_variable(layer, n_lay, geometry, x, variables_indexes, var_name):
    x_mids = (x[1:] + x[:-1]) / 2
    z = np.full((n_lay, x_mids.size), np.nan)
    for k in range(n_lay):
        _, dataset = variables_indexes[var_name][k]
        z[k, :] = cross_section_hue_data(layer, geometry, dataset, x_mids)
    return z


def extract_cross_section_data(layer, variable, variables_indexes, geometry, resolution):
    # Get arbitrary key
    first_key = next(iter(variables_indexes.keys()))

    # Get layer numbers: first element contains layer number
    layer_nrs = next(zip(*variables_indexes[first_key]))
    layer_nrs = sorted(list(layer_nrs))
    n_layer = len(layer_nrs)

    x = cross_section_x_data(layer, geometry, resolution)
    n_x = x.size
    # Get y values of points
    # Amount of layers * 2 because we have tops and bottoms we independently add
    top = np.empty((n_layer, n_x))
    bottom = np.empty((n_layer, n_x))

    # FUTURE: When MDAL supports UGRID layer, looping over layers not necessary.
    for k in range(n_layer):
        _, top_index = variables_indexes["top"][k]
        _, bottom_index = variables_indexes["bottom"][k]
        top[k, :] = cross_section_y_data(layer, geometry, top_index, x)
        bottom[k, :] = cross_section_y_data(layer, geometry, bottom_index, x)

    if len(variable) == 0:
        raise ValueError("No variable set")
    elif variable == "layer number":
        z = np.repeat(layer_nrs, n_x - 1).reshape(n_layer, n_x - 1)
    else:
        z = color_by_variable(layer, n_layer, geometry, x, variables_indexes, variable)

    return x, top, bottom, z


def extract_cross_section_lines(layer, variables, variables_indexes, geometry, resolution):
    n_lines = len(variables)
    x = cross_section_x_data(layer, geometry, resolution)
    top = np.empty((n_lines, x.size))
    for i, variable in enumerate(variables):
        dataset_index = variables_indexes[variable]
        top[i, :] = cross_section_y_data(layer, geometry, dataset_index, x)
    return x, top


def extract_raster_cross_section_lines(layer, variables, variables_indexes, geometry, resolution):
    provider = layer.dataProvider()
    n_lines = len(variables)
    x = cross_section_x_data(layer, geometry, resolution)
    top = np.empty((x.size, n_lines))
    bands = [variables_indexes[v] for v in variables]
    for i, x_value in enumerate(x):
        pt = geometry.interpolate(x_value).asPoint()
        sampling = provider.identify(pt, QgsRaster.IdentifyFormatValue).results()
        for j, band in enumerate(bands):
            top[i, j] = sampling[band]
    # Might wanna test improved memory access versus cost of transpose
    return x, top.transpose().copy()


PSEUDOCOLOR = 0
UNIQUE_COLOR = 1
WIDTH = 2


class ColorsDialog(QDialog):
    def __init__(self, pseudocolor_widget, unique_color_widget, default_to, data, parent):
        QDialog.__init__(self, parent)
        self.pseudocolor_widget = pseudocolor_widget
        self.unique_color_widget = unique_color_widget
        self.data = data

        self.render_type_box = QComboBox()
        self.render_type_box.insertItems(0, ["Pseudocolor", "Unique values"])
        self.render_type_box.setCurrentIndex(default_to)
        self.render_type_box.currentIndexChanged.connect(self.on_render_type_changed)

        # Check if data is a number dtype, if not: only unique coloring works properly
        if not np.issubdtype(data.dtype, np.number):
            self.render_type_box.setCurrentIndex(UNIQUE_COLOR)
            self.render_type_box.setEnabled(False)
        else:
            self.render_type_box.setEnabled(True)

        apply_button = QPushButton("Apply")
        cancel_button = QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Render type:"))
        first_row.addWidget(self.render_type_box)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(apply_button)
        second_row.addWidget(cancel_button)
        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addWidget(self.pseudocolor_widget)
        layout.addWidget(self.unique_color_widget)
        layout.addLayout(second_row)
        self.setLayout(layout)
        self.on_render_type_changed()
    
    def on_render_type_changed(self):
        if self.render_type_box.currentIndex() == PSEUDOCOLOR:
            self.pseudocolor_widget.setVisible(True)
            self.unique_color_widget.setVisible(False)
            self.pseudocolor_widget.set_data(self.data)
        else:
            self.pseudocolor_widget.setVisible(False)
            self.unique_color_widget.setVisible(True)
            self.unique_color_widget.set_data(self.data)

    def detach(self):
        self.pseudocolor_widget.setParent(self.parent())
        self.unique_color_widget.setParent(self.parent())

    # NOTA BENE: detach() and these overloaded methods are required, otherwise
    # the color_widget is garbage collected when the dialog closes.
    def closeEvent(self, e):
        self.detach()
        QDialog.closeEvent(self, e)

    def reject(self):
        self.detach()
        QDialog.reject(self)

    def accept(self):
        self.detach()
        QDialog.accept(self)


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


class UpdatingQgsMapLayerComboBox(QgsMapLayerComboBox):
    def enterEvent(self, e):
        self.update_layers()
        super(UpdatingQgsMapLayerComboBox, self).enterEvent(e)
    
    def update_layers(self):
        # Allow:
        # * Point data with associated IPF borehole data
        # * Mesh layers
        # * Raster layers
        excepted_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if not (
                (layer.type() == QgsMapLayerType.MeshLayer) or
                (layer.type() == QgsMapLayerType.RasterLayer) or
                (layer.customProperty("ipf_type") == IpfType.BOREHOLE.name)
            ):
                excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ImodCrossSectionWidget(QWidget):
    # TODO: Calculate proper default resolution
    # TODO: Include time selection box
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface

        self.layer_selection = UpdatingQgsMapLayerComboBox()
        self.layer_selection.layerChanged.connect(self.on_layer_changed)
        self.layer_selection.setMinimumWidth(200)

        self.variable_selection = VariablesWidget()
        self.variable_selection.dataset_variable_changed.connect(self.set_variable_layernumbers)
        self.multi_variable_selection = MultipleVariablesWidget()

        self.line_picker = LineGeometryPickerWidget(iface)
        self.line_picker.geometries_changed.connect(self.on_geometries_changed)

        self.as_line_checkbox = QCheckBox("Draw as line(s)")
        self.as_line_checkbox.stateChanged.connect(self.on_as_line_changed)

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True)

        self.dynamic_resolution_box = QCheckBox("Dynamic resolution")
        self.dynamic_resolution_box.setChecked(True)

        self.resolution_spinbox = QDoubleSpinBox()
        self.resolution_spinbox.setRange(0.01, 10000.)
        self.resolution_spinbox.setValue(50.0)

        self.buffer_label = QLabel("Search buffer")
        self.buffer_spinbox = QDoubleSpinBox()
        self.buffer_spinbox.setRange(0., 10000.)
        self.buffer_spinbox.setValue(250.0)

        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()

        self.color_button = QPushButton("Colors")
        self.color_button.clicked.connect(self.colors)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export)
        self.export_dialog = ExportDialog(self.plot_widget.plotItem.scene())

        # Selection geometry
        self.rubber_band = None

        # Data
        self.x = None
        self.top = None
        self.bottom = None
        self.z = None

        self.borehole_data = None
        self.relative_width = 0.01

        # for redrawing
        self.redraw = None
        self.render_style = PSEUDOCOLOR
        self.styling_data = None

        # Setup layout
        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.as_line_checkbox)
        first_row.addWidget(self.variable_selection)
        first_row.addWidget(self.multi_variable_selection)
        first_row.addWidget(self.line_picker)
        first_row.addWidget(self.dynamic_resolution_box)
        first_row.addWidget(self.resolution_spinbox)
        first_row.addWidget(self.buffer_label)
        first_row.addWidget(self.buffer_spinbox)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        second_column = QVBoxLayout()
        second_column.addWidget(self.color_button)
        second_column.addWidget(self.export_button)
        second_column.addStretch()
        second_row.addLayout(second_column)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)
        
        # Run a single time initialize the combo boxes
        self.layer_selection.update_layers()
        self.on_layer_changed()
        self.on_as_line_changed()

    def hideEvent(self, e):
        self.line_picker.clear_geometries()
        self.clear_plot()
        self.redraw = None
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.x = None
        self.top = None
        self.bottom = None
        self.z = None
        self.styling_data = None
        self.borehole_data = None
        self.redraw = None
    

    def on_as_line_changed(self):
        # Will only be called when a mesh layer is currentLayer
        as_line = self.as_line_checkbox.isChecked()
        self.multi_variable_selection.setVisible(as_line)
        self.set_variable_names()

    def load_borehole_data(self):
        self.x, self.z, paths = select_boreholes(
            self.layer_selection.currentLayer(),
            self.buffer_spinbox.value(),
            self.line_picker.geometries[0],
        )
        self.top = self.bottom = None
        self.borehole_data = [read_associated_borehole(p) for p in paths]
        variable_names = set()
        styling_entries = []
        for df in self.borehole_data:
            variable_names.update(df.columns)
            styling_entries.append(df["value"].values)
        self.styling_data = np.concatenate(styling_entries)

    def load_raster_data(self):
        variables_to_plot = self.multi_variable_selection.checked_variables()
        self.x, self.top = extract_raster_cross_section_lines(
            self.layer_selection.currentLayer(),
            variables=variables_to_plot,
            variables_indexes=self.variables_indexes,
            geometry=self.line_picker.geometries[0],
            resolution=self.resolution_spinbox.value(),
        )
        self.bottom = None
        self.z = self.styling_data = np.array(variables_to_plot)

    def load_mesh_data(self):
        if self.as_line_checkbox.isChecked():
            variables_to_plot = self.multi_variable_selection.checked_variables()
            self.x, self.top = extract_cross_section_lines(
                self.layer_selection.currentLayer(),
                variables=variables_to_plot,
                variables_indexes=self.variables_indexes,
                geometry=self.line_picker.geometries[0],
                resolution=self.resolution_spinbox.value(),
            )
            self.bottom = None
            self.z = self.styling_data = np.array(variables_to_plot)
        else:
            self.x, self.top, self.bottom, self.z = extract_cross_section_data(
                self.layer_selection.currentLayer(),
                variable = self.variable_selection.dataset_variable,
                variables_indexes=self.variables_indexes,
                geometry=self.line_picker.geometries[0],
                resolution=self.resolution_spinbox.value(),
            )
            self.styling_data = self.z.ravel()

    def colorshader(self):
        if self.render_style == PSEUDOCOLOR:
            return self.pseudocolor_widget.shader()
        elif self.render_style == UNIQUE_COLOR:
            return self.unique_color_widget.shader()

    def draw_cross_section(self):
        self.plot_item = [PColorMeshItem(self.x, self.top, self.bottom, self.z, colorshader=self.colorshader())]
        self.plot_widget.addItem(self.plot_item[0])
        self.redraw = self.draw_cross_section

    def draw_cross_section_lines(self):
        self.render_style = UNIQUE_COLOR
        colorshader = self.colorshader()
        self.plot_item = []
        for variable, y in zip(self.z, self.top):
            to_draw, r, g, b, alpha = colorshader.shade(variable)
            color = QColor(r, g, b, alpha)
            pen = pg.mkPen(color=color, width=WIDTH)
            curve = pg.PlotDataItem(x=self.x, y=y, pen=pen)
            self.plot_item.append(curve)
            self.plot_widget.addItem(curve)
        self.redraw = self.draw_cross_section_lines

    def draw_boreholes(self):
        column_to_plot = self.multi_variable_selection.checked_variables()
        self.plot_item = [BoreholePlotItem(
            self.x,
            [df["top"].values for df in self.borehole_data],
            [df["value"].values for df in self.borehole_data],  # TODO
            self.relative_width * (self.x.max() - self.x.min()),
            colorshader=self.colorshader(),
        )]
        self.plot_widget.addItem(self.plot_item[0])
        self.redraw = self.draw_boreholes

    def draw(self):
        """
        Update plot (e.g. after change in colorramp)
        """
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        if len(self.line_picker.geometries) == 0:
            return
        layer_type = layer.type()
        
        if layer_type == QgsMapLayerType.MeshLayer:
            self.load_mesh_data()
            if self.as_line_checkbox.isChecked():
                self.render_style = UNIQUE_COLOR
                self.unique_color_widget.set_data(self.styling_data)
                self.draw_cross_section_lines()
            else:
                self.render_style = PSEUDOCOLOR
                self.pseudocolor_widget.set_data(self.styling_data)
                self.draw_cross_section()
        elif layer_type == QgsMapLayerType.RasterLayer:
            self.load_raster_data()
            self.render_style = UNIQUE_COLOR
            self.unique_color_widget.set_data(self.styling_data)
            self.draw_cross_section_lines()
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            self.load_borehole_data()
            self.render_style = UNIQUE_COLOR
            self.unique_color_widget.set_data(self.styling_data)
            self.draw_boreholes()

    def set_variable_names(self):
        layer = self.layer_selection.currentLayer()
        if layer.type() == QgsMapLayerType.MeshLayer:
            indexes, names = get_group_names(layer)
            self.variables_indexes = groupby_variable(names, indexes)
            self.variable_selection.set_layer(layer, self.variables_indexes.keys())
            self.set_variable_layernumbers()
        elif layer.type() == QgsMapLayerType.RasterLayer:
            variables = [] 
            self.variables_indexes = {}
            for i in range(1, layer.bandCount() + 1):
                name = layer.bandName(i)
                variables.append(name)
                self.variables_indexes[name] = i
            self.multi_variable_selection.menu_datasets.populate_actions(variables)
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            variables = layer.customProperty("ipf_assoc_columns").split("␞")
            self.multi_variable_selection.menu_datasets.populate_actions(variables)

    def set_variable_layernumbers(self):
        if self.as_line_checkbox.isChecked():
            variable = self.variable_selection.dataset_variable
            layers = [str(a[0]) for a in self.variables_indexes[variable]]
            #self.variables_indexes = {n: i for i, n in zip(indexes, names)}
            #self.multi_variable_selection.menu_datasets.populate_actions(names)
            self.multi_variable_selection.menu_datasets.populate_actions(layers)

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

        if self.dynamic_resolution_box.isChecked():
            geometry = self.line_picker.geometries[0]
            resolution = geometry.length() / 300.0
            self.resolution_spinbox.setValue(resolution)

    def on_layer_changed(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        layer_type = layer.type()
        if layer_type == QgsMapLayerType.MeshLayer:
            self.as_line_checkbox.setVisible(True)
            self.as_line_checkbox.setChecked(False)
            self.as_line_checkbox.setEnabled(True)
            self.dynamic_resolution_box.setVisible(True)
            self.resolution_spinbox.setVisible(True)
            self.buffer_label.setVisible(False)
            self.buffer_spinbox.setVisible(False)
            self.variable_selection.setVisible(True)
        elif layer_type == QgsMapLayerType.RasterLayer:
            self.as_line_checkbox.setVisible(True)
            self.as_line_checkbox.setChecked(True)
            self.as_line_checkbox.setEnabled(False)
            self.dynamic_resolution_box.setVisible(True)
            self.resolution_spinbox.setVisible(True)
            self.buffer_label.setVisible(False)
            self.buffer_spinbox.setVisible(False)
            self.variable_selection.setVisible(False)
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            self.as_line_checkbox.setVisible(False)
            self.as_line_checkbox.setChecked(True)
            self.as_line_checkbox.setEnabled(False)
            self.dynamic_resolution_box.setVisible(False)
            self.resolution_spinbox.setVisible(False)
            self.buffer_label.setVisible(True)
            self.buffer_spinbox.setVisible(True)
            self.variable_selection.setVisible(False)
        self.set_variable_names()

    def colors(self):
        dialog = ColorsDialog(self.pseudocolor_widget, self.unique_color_widget, self.render_style, self.styling_data, self)
        dialog.show()
        ok = dialog.exec_()
        if ok and self.redraw is not None:
            self.render_style = dialog.render_type_box.currentIndex()
            for item in self.plot_item:
                self.plot_widget.removeItem(item)
            self.redraw()

    def export(self):
        plot_item = self.plot_widget.plotItem
        self.export_dialog.show(plot_item)
