import abc
import pathlib
from typing import List, Tuple

import numpy as np
import pyqtgraph as pg

from PyQt5.QtGui import QColor
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget

from qgis.core import (
    QgsRaster,
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
    QgsProject,
)
from qgis import processing

from .pcolormesh import PColorMeshItem
from .borehole_plot_item import BoreholePlotItem
from .plot_util import (
    cross_section_x_data,
    cross_section_y_data,
    project_points_to_section,
)
from ..widgets import (
    ColorsDialog,
    PSEUDOCOLOR,
    UNIQUE_COLOR,
    ImodPseudoColorWidget,
    ImodUniqueColorWidget,
)
from ..ipf import IpfType, read_associated_borehole


WIDTH = 2


class DummyWidget(QWidget):
    """
    This widget has two purposes:

    * Hold the pyqtSignal for changing colors
    * Provide a parent to the color widgets so Qt doesn't garbage collect them

    This is necessary because:

    * Only Qt Widgets can contain pyqtSignals
    * Closing a dialog (in this case the symbology Dialog) results in the
      deletion of children widgets (in this case a color widget).

    But it's never displayed.
    """

    colors_changed = pyqtSignal()


class AbstractCrossSectionData(abc.ABC):
    @abc.abstractmethod
    def load(self, geometry, **kwargs):
        pass

    @abc.abstractmethod
    def plot(self, plot_widget):
        pass

    @abc.abstractmethod
    def clear(self):
        pass

    def add_to_legend(self, legend):
        for color, name in zip(self.colors().values(), self.labels().values()):
            item = pg.BarGraphItem(x=0, y=0, brush=color)
            legend.addItem(item, name.replace("<", "&lt;").replace(">", "&gt;"))

    def set_color_data(self):
        if self.color_widget.data is None and self.styling_data is not None:
            self.color_widget.set_data(self.styling_data)

    def colorshader(self):
        return self.color_widget.shader()

    def labels(self):
        return self.color_widget.labels()

    def colors(self):
        return self.color_widget.colors()

    def color_ramp(self):
        return self.color_widget.color_ramp_button.colorRamp()

    @property
    def colors_changed(self):
        return self.dummy_widget.colors_changed

    def edit_colors(self):
        dialog = ColorsDialog(
            self.pseudocolor_widget,
            self.unique_color_widget,
            self.render_style,
            self.styling_data,
            self.dummy_widget,
        )
        dialog.show()
        ok = dialog.exec_()
        if ok:
            self.render_style = dialog.render_type_box.currentIndex()
            if self.render_style == UNIQUE_COLOR:
                self.color_widget = self.unique_color_widget
            elif self.render_style == PSEUDOCOLOR:
                self.color_widget = self.pseudocolor_widget
            else:
                raise ValueError("Invalid render style")
            self.colors_changed.emit()


class AbstractLineData(AbstractCrossSectionData):
    def plot(self, plot_widget):
        if self.x is None:
            return
        colorshader = self.colorshader()
        self.plot_item = []
        for variable, y in zip(self.variables, self.top):
            to_draw, r, g, b, alpha = colorshader.shade(variable)
            color = QColor(r, g, b, alpha)
            pen = pg.mkPen(color=color, width=WIDTH)
            curve = pg.PlotDataItem(x=self.x, y=y, pen=pen, stepMode="right")
            self.plot_item.append(curve)
            plot_widget.addItem(curve)

    def clear(self):
        self.x = None
        self.top = None
        self.plot_item = None

    def add_to_legend(self, legend):
        for item, name in zip(self.plot_item, self.labels()):
            legend.addItem(item, name)


class MeshLineData(AbstractLineData):
    def __init__(self, layer, variables_indexes, variable, layer_numbers):
        self.layer = layer
        self.variables_indexes = variables_indexes
        self.variable = variable
        self.layer_numbers = layer_numbers
        self.x = None
        self.top = None
        self.variables = np.array(
            [f"{variable} layer {layer}" for layer in layer_numbers]
        )
        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()
        self.render_style = UNIQUE_COLOR
        self.color_widget = self.unique_color_widget
        self.legend_items = []
        self.styling_data = np.array(self.variables)
        self.dummy_widget = DummyWidget()

    def load(self, geometry, resolution, **_):
        n_lines = len(self.layer_numbers)
        x = cross_section_x_data(self.layer, geometry, resolution)
        top = np.empty((n_lines, x.size))
        for i, k in enumerate(self.layer_numbers):
            dataset_index = self.variables_indexes[self.variable][k]
            top[i, :] = cross_section_y_data(self.layer, geometry, dataset_index, x)
        self.x = x
        self.top = top
        self.set_color_data()


class RasterLineData(AbstractLineData):
    def __init__(self, layer, variables, variables_indexes):
        self.layer = layer
        self.variables = variables
        self.variables_indexes = variables_indexes
        self.x = None
        self.z = None
        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()
        self.render_style = UNIQUE_COLOR
        self.color_widget = self.unique_color_widget
        self.legend_items = []
        self.styling_data = np.array(variables)
        self.dummy_widget = DummyWidget()

    def load(self, geometry, resolution, **_):
        provider = self.layer.dataProvider()
        n_lines = len(self.variables)
        x = cross_section_x_data(self.layer, geometry, resolution)
        top = np.empty((x.size, n_lines))
        bands = [self.variables_indexes[v] for v in self.variables]
        for i, x_value in enumerate(x):
            pt = geometry.interpolate(x_value).asPoint()
            sampling = provider.identify(pt, QgsRaster.IdentifyFormatValue).results()
            for j, band in enumerate(bands):
                top[i, j] = sampling[band]
        # Might wanna test improved memory access versus cost of transpose
        self.x = x
        self.top = top.transpose().copy()
        self.set_color_data()


class BoreholeData(AbstractCrossSectionData):
    def __init__(self, layer, variable):
        self.layer = layer
        self.variable = variable
        self.x = None
        self.boreholes_id = None
        self.boreholes_data = None
        self.relative_width = 0.01
        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()
        self.render_style = UNIQUE_COLOR
        self.color_widget = self.unique_color_widget
        self.legend_items = []
        self.styling_data = None
        self.dummy_widget = DummyWidget()

    def load(
        self, geometry: QgsGeometry, buffer_distance: float, **_
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
        indexcol = int(self.layer.customProperty("ipf_indexcolumn"))
        ext = self.layer.customProperty("ipf_assoc_ext")
        parent = pathlib.Path(self.layer.customProperty("ipf_path")).parent
        output = processing.run(
            "native:extractbylocation",
            {
                "INPUT": self.layer,
                "PREDICATE": 6,  # are within
                "INTERSECT": tmp_layer,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        
        # Check if nothing is selected.
        if output.featureCount() == 0:
            return

        for feature in output.getFeatures():
            filename = feature.attribute(indexcol)
            boreholes_id.append(filename)
            paths.append(parent.joinpath(f"{filename}.{ext}"))
            points.append(feature.geometry().asPoint())

        if len(points) > 0:
            x = project_points_to_section(points, geometry)
        else:
            x = []

        self.x = x
        self.boreholes_id = boreholes_id
        self.boreholes_data = [read_associated_borehole(p) for p in paths]

        variable_names = set()
        styling_entries = []
        for df in self.boreholes_data:
            variable_names.update(df.columns)
            styling_entries.append(df[self.variable].values)
        self.styling_data = np.concatenate(styling_entries)
        self.set_color_data()

    def plot(self, plot_widget):
        if self.x is None:
            return

        # First column in IPF associated file indicates vertical coordinates
        y_plot = [df.iloc[:, 0].values for df in self.boreholes_data]

        # Collect values in column to plot
        z_plot = [df[self.variable].values for df in self.boreholes_data]

        self.plot_item = [
            BoreholePlotItem(
                self.x,
                y_plot,
                z_plot,
                self.relative_width * (self.x.max() - self.x.min()),
                colorshader=self.colorshader(),
            )
        ]
        plot_widget.addItem(self.plot_item[0])

    def clear(self):
        self.x = None
        self.boreholes_id = None
        self.boreholes_data = None
        self.plot_item = None


class MeshData(AbstractCrossSectionData):
    def __init__(self, layer, variables_indexes, variable, layer_numbers):
        self.layer = layer
        self.variables_indexes = variables_indexes
        self.variable = variable
        self.layer_numbers = layer_numbers
        self.x = None
        self.top = None
        self.bottom = None
        self.z = None
        self.variables = None
        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()
        self.render_style = PSEUDOCOLOR
        self.color_widget = self.pseudocolor_widget
        self.legend_items = []
        self.styling_data = None
        self.dummy_widget = DummyWidget()

    def load(self, geometry, resolution, **_):
        n_layer = len(self.layer_numbers)
        x = cross_section_x_data(self.layer, geometry, resolution)
        n_x = x.size
        top = np.empty((n_layer, n_x))
        bottom = np.empty((n_layer, n_x))

        # FUTURE: When MDAL supports UGRID layer, looping over layers not necessary.
        for i, k in enumerate(self.layer_numbers):
            top_index = self.variables_indexes["top"][k]
            bottom_index = self.variables_indexes["bottom"][k]
            top[i, :] = cross_section_y_data(self.layer, geometry, top_index, x)
            bottom[i, :] = cross_section_y_data(self.layer, geometry, bottom_index, x)

        if self.variable == "layer number":
            z = np.repeat(self.layer_numbers, n_x - 1).reshape(n_layer, n_x - 1)
        else:
            x_mids = (x[1:] + x[:-1]) / 2
            z = np.full((n_layer, x_mids.size), np.nan)
            for i, k in enumerate(self.layer_numbers):
                dataset_index = self.variables_indexes[self.variable][k]
                z[i, :] = cross_section_y_data(
                    self.layer, geometry, dataset_index, x_mids
                )

        self.x = x
        self.top = top
        self.bottom = bottom
        self.z = z
        self.styling_data = self.z.ravel()
        self.set_color_data()

    def plot(self, plot_widget):
        if self.x is None:
            return
        self.plot_item = [
            PColorMeshItem(
                self.x, self.top, self.bottom, self.z, colorshader=self.colorshader()
            )
        ]
        plot_widget.addItem(self.plot_item[0])

    def clear(self):
        self.x = None
        self.top = None
        self.bottom = None
        self.z = None
        self.styling_data = None
        self.plot_item = None
