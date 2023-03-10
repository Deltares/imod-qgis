# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import abc
import pathlib
from typing import List, Tuple

import numpy as np
from ..dependencies import pyqtgraph_0_12_3 as pg
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from qgis import processing
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsMeshDatasetIndex,
    QgsProject,
    QgsRaster,
    QgsVectorLayer,
)

from ..ipf import IpfType, read_associated_borehole
from ..widgets import (
    PSEUDOCOLOR,
    UNIQUE_COLOR,
    ColorsDialog,
    ImodPseudoColorWidget,
    ImodUniqueColorWidget,
)
from .borehole_plot_item import BoreholePlotItem
from .pcolormesh import PColorMeshItem
from .plot_util import (
    cross_section_x_data,
    cross_section_y_data,
    project_points_to_section,
)

from ..utils.layers import NO_LAYERS

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

    def requires_loading(self, **kwargs):
        return self.x is None

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

    def requires_static_index(self, datetime_range):
        """
        Check if data requires static indexing, meaning temporal manager inactive
        (datetime_range is None) or layer has not time data.
        """
        
        # This works for Raster, Mesh and Vector data, as they all have this
        # method.
        is_temporal_layer = self.layer.temporalProperties().isActive()

        return (datetime_range is None) or (not is_temporal_layer)

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
        for variable, y in zip(self.variables, self.y):
            to_draw, r, g, b, alpha = colorshader.shade(variable)
            color = QColor(r, g, b, alpha)
            pen = pg.mkPen(color=color, width=WIDTH)
            curve = pg.PlotDataItem(x=self.x, y=y, pen=pen, stepMode="right")
            self.plot_item.append(curve)
            plot_widget.addItem(curve)

    def clear(self):
        self.x = None
        self.y = None
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
        self.y = None
        if layer_numbers == NO_LAYERS:
            self.variables = [f"{variable}"]
        else:
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

    def load(self, geometry, resolution, datetime_range, **_):

        if self.requires_static_index(datetime_range):  # Just take the first one in such a case
            plot_datetime_range = None # Fix datetime_range of cross_section_y_data to None
        else:
            plot_datetime_range = datetime_range

        n_lines = len(self.layer_numbers)
        x = cross_section_x_data(self.layer, geometry, resolution)
        y = np.empty((n_lines, x.size))
        for i, k in enumerate(self.layer_numbers):
            dataset_index = self.variables_indexes[self.variable][k]
            y[i, :] = cross_section_y_data(
                self.layer, geometry, dataset_index, x, plot_datetime_range
            )
        self.x = x
        self.y = y
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
        y = np.empty((x.size, n_lines))
        bands = [self.variables_indexes[v] for v in self.variables]
        for i, x_value in enumerate(x):
            pt = geometry.interpolate(x_value).asPoint()
            sampling = provider.identify(pt, QgsRaster.IdentifyFormatValue).results()
            for j, band in enumerate(bands):
                y[i, j] = sampling[band]
        # Might wanna test improved memory access versus cost of transpose
        self.x = x
        self.y = y.transpose().copy()
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
        self.styling_data = None
        self.plot_item = None


class MeshData(AbstractCrossSectionData):
    def __init__(self, layer, variables_indexes, variable, layer_numbers):
        self.layer = layer
        self.variables_indexes = variables_indexes
        self.variable = variable
        self.layer_numbers = layer_numbers
        self.x = None
        self.y_top = None
        self.y_bottom = None
        self.z = None
        self.variables = None
        self.pseudocolor_widget = ImodPseudoColorWidget()
        self.unique_color_widget = ImodUniqueColorWidget()
        self.render_style = PSEUDOCOLOR
        self.color_widget = self.pseudocolor_widget
        self.legend_items = []
        self.styling_data = None
        self.cache = {}
        self.sample_index = (None, None)
        self.dummy_widget = DummyWidget()

    def requires_loading(self, datetime_range):
        group_index = self.variables_indexes[self.variable][self.layer_numbers[0]]
        if self.requires_static_index(datetime_range):  # Just take the first one in such a case
            sample_index = (group_index, 0)
        else:
            index = self.layer.datasetIndexAtTime(datetime_range, group_index)
            sample_index = (index.group(), index.dataset())

        if sample_index == self.sample_index:
            return False
        else:
            return True

    def load(self, geometry, resolution, datetime_range, **_):
        group_index = self.variables_indexes[self.variable][self.layer_numbers[0]]

        if self.requires_static_index(datetime_range):  # Just take the first one in such a case
            sample_index = QgsMeshDatasetIndex(group=group_index, dataset=0)
            plot_datetime_range = None # Fix datetime_range of cross_section_y_data to None
        else:
            sample_index = self.layer.datasetIndexAtTime(datetime_range, group_index)
            plot_datetime_range = datetime_range
        index = (sample_index.dataset(), sample_index.group())

        # Get result from cache if available.
        result = self.cache.get(index, None)
        if result is not None:
            x, top, bottom, z = result
        else:
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
                bottom[i, :] = cross_section_y_data(
                    self.layer, geometry, bottom_index, x
                )

                x_mids = (x[1:] + x[:-1]) / 2
                z = np.full((n_layer, x_mids.size), np.nan)
                for i, k in enumerate(self.layer_numbers):
                    group_index = self.variables_indexes[self.variable][k]
                    z[i, :] = cross_section_y_data(
                        self.layer, geometry, group_index, x_mids, plot_datetime_range
                    )
            # Store in cache
            self.cache[index] = (x, top, bottom, z)
            self.sample_index = index

        self.x = x
        self.y_top = top
        self.y_bottom = bottom
        self.z = z
        self.styling_data = self.z.ravel()
        self.set_color_data()

    def plot(self, plot_widget):
        if self.x is None:
            return
        self.plot_item = [
            PColorMeshItem(
                self.x,
                self.y_top,
                self.y_bottom,
                self.z,
                colorshader=self.colorshader(),
            )
        ]
        plot_widget.addItem(self.plot_item[0])

    def clear(self):
        self.x = None
        self.y_top = None
        self.y_bottom = None
        self.z = None
        self.styling_data = None
        self.cache = {}
        self.plot_item = None
