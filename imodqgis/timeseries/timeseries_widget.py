# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""
Widget for displaying timeseries data.

In general: plotting with pyqtgraph is fast, collecting data is relatively
slow.
"""
from pathlib import Path
import tempfile
from itertools import compress

import numpy as np
import pandas as pd
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtTest import QSignalSpy
from qgis.core import (
    QgsCoordinateTransformContext,
    QgsMapLayerType,
    QgsMeshDatasetIndex,
    QgsProject,
    QgsVectorFileWriter,
    QgsWkbTypes,
)
from qgis.gui import QgsColorButton, QgsMapLayerComboBox

from imodqgis.arrow import read_arrow
from imodqgis.dependencies import pyqtgraph_0_12_3 as pg
from imodqgis.dependencies.pyqtgraph_0_12_3.GraphicsScene.exportDialog import (
    ExportDialog,
)
from imodqgis.ipf import IpfType, read_associated_timeseries
from imodqgis.utils.layers import get_group_names, groupby_variable
from imodqgis.utils.temporal import get_group_is_temporal, is_temporal_meshlayer
from imodqgis.widgets import (
    ImodUniqueColorWidget,
    MultipleVariablesWidget,
    PointGeometryPickerWidget,
    VariablesWidget,
)

PYQT_DELETED_ERROR = "wrapped C/C++ object of type QgsVectorLayer has been deleted"


def timeseries_x_data(layer, group_index):
    # sample_index = QgsMeshDatasetIndex(group=group_index, dataset=0)
    # n_times = layer.dataProvider().datasetCount(group_index)
    sample_index = QgsMeshDatasetIndex(group=group_index, dataset=0)
    n_times = layer.dataProvider().datasetCount(sample_index)
    # Collect x data once
    # metadata.time() returns a floating point value:
    # hours since the reference time.
    times_float = np.empty(n_times)
    for j in range(n_times):
        metadata = layer.dataProvider().datasetMetadata(
            QgsMeshDatasetIndex(group_index, j)
        )
        times_float[j] = metadata.time()
    ref_time = layer.temporalProperties().referenceTime().toPyDateTime()
    x = ref_time + pd.to_timedelta(times_float, unit="h")
    return x


def timeseries_y_data(layer, geometry, group_index, n_times):
    y = np.zeros(n_times)
    for i in range(n_times):
        dataset_index = QgsMeshDatasetIndex(group=group_index, dataset=i)
        value = layer.datasetValue(dataset_index, geometry).scalar()
        y[i] = value
    return y


# Set rendering backend and set pen widths
# NOTE: DO NOT USE PEN WIDTHS > 1 WITHOUT OPENGL, THIS IS EXTREMELY SLOW
# This is due to an upstream issue with the Qt raster painting system:
# https://www.qcustomplot.com/index.php/support/forum/1008
# Setting useOpenGL will presumably use OpenGL's raster painting instead, which
# has good performance, but does not seem to support anti-aliasing.
pg.setConfigOptions(useOpenGL=True)
WIDTH = 2
SELECTED_WIDTH = 3
# pyqtgraph expects datetimes expressed as seconds from 1970-01-01
PYQT_REFERENCE_TIME = pd.Timestamp("1970-01-01")


def write_csv(layer, path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "csv"
    QgsVectorFileWriter.writeAsVectorFormatV2(
        layer,
        path.as_posix(),
        QgsCoordinateTransformContext(),
        options,
    )


class SymbologyDialog(QDialog):
    def __init__(self, color_widget, parent):
        QDialog.__init__(self, parent)
        self.color_widget = color_widget
        row = QHBoxLayout()
        apply_button = QPushButton("Apply")
        cancel_button = QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        row.addWidget(apply_button)
        row.addWidget(cancel_button)
        layout = QVBoxLayout()
        layout.addWidget(self.color_widget)
        layout.addLayout(row)
        self.setLayout(layout)

    def detach(self):
        self.color_widget.setParent(self.parent())

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


class UpdatingQgsMapLayerComboBox(QgsMapLayerComboBox):
    def enterEvent(self, e):
        self.update_layers()
        super(UpdatingQgsMapLayerComboBox, self).enterEvent(e)

    def update_layers(self):
        # Allow:
        # * point data with associated IPF timeseries
        # * point data with a temporal column
        excepted_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayerType.MeshLayer:
                if not is_temporal_meshlayer(layer):
                    excepted_layers.append(layer)
            # Also allow edges...
            elif (layer.type() != QgsMapLayerType.VectorLayer) or (
                layer.geometryType()
                not in (QgsWkbTypes.PointGeometry, QgsWkbTypes.LineGeometry)
            ):
                excepted_layers.append(layer)
            else:
                is_ipf_series = (
                    layer.customProperty("ipf_type") == IpfType.TIMESERIES.name
                )
                is_arrow = layer.customProperty("arrow_type") == "timeseries"
                is_temporal = layer.temporalProperties().startField() != ""
                if not (is_ipf_series or is_temporal or is_arrow):
                    excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ImodTimeSeriesWidget(QWidget):
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface

        self.layer_selection = UpdatingQgsMapLayerComboBox()
        self.layer_selection.layerChanged.connect(self.on_layer_changed)
        self.layer_selection.setMinimumWidth(200)

        self.id_label = QLabel("ID column:")
        self.id_selection_box = QComboBox()
        self.id_selection_box.setMinimumWidth(200)
        self.variable_selection = VariablesWidget()
        self.variable_selection.dataset_variable_changed.connect(
            self.set_variable_layernumbers
        )
        self.multi_variable_selection = MultipleVariablesWidget()

        self.point_picker = PointGeometryPickerWidget(iface.mapCanvas())
        self.point_picker.geometries_changed.connect(self.on_select)

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)

        self.selection_button = QPushButton("Select")
        self.selection_button.clicked.connect(self.start_selection)

        self.update_on_select = QCheckBox("Update on selection")
        self.update_on_select.stateChanged.connect(self.toggle_update)

        self.color_button = QgsColorButton()
        self.color_button.colorChanged.connect(self.apply_color)
        self.marker_checkbox = QCheckBox()
        self.marker_checkbox.stateChanged.connect(self.show_or_hide_markers)

        self.plot_widget = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        self.legend = self.plot_widget.getPlotItem().legend

        plot_box = QGroupBox()
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.plot_widget)
        plot_box.setLayout(plot_layout)

        self.colors_button = QPushButton("Colors")
        self.colors_button.clicked.connect(self.colors)
        self.color_widget = ImodUniqueColorWidget()

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export)
        self.export_dialog = ExportDialog(self.plot_widget.plotItem.scene())

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.id_label)
        first_row.addWidget(self.id_selection_box)
        first_row.addWidget(self.variable_selection)
        first_row.addWidget(self.multi_variable_selection)
        first_row.addWidget(self.selection_button)
        first_row.addWidget(self.update_on_select)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(plot_box)

        third_row = QHBoxLayout()
        third_row.addWidget(QLabel("Line Color:"))
        third_row.addWidget(self.color_button)

        fourth_row = QHBoxLayout()
        fourth_row.addWidget(QLabel("Draw markers"))
        fourth_row.addWidget(self.marker_checkbox)

        second_column = QVBoxLayout()
        second_column.addLayout(third_row)
        second_column.addLayout(fourth_row)
        second_column.addWidget(self.colors_button)
        second_column.addWidget(self.export_button)
        second_column.addStretch()
        second_row.addLayout(second_column)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

        # Data
        self.feature_ids = None
        self.dataframes = {}
        self.stored_dataframes = {}
        # Graphing
        self.names = []
        self.curves = []
        self.pens = []
        self.selected = (None, None, None)
        self.variables_indexes = None

        # Initialize stored layer
        self.previous_layer = None

        # Run a single time initialize the combo boxes
        self.layer_selection.update_layers()
        # Set default state of checkbox
        self.update_on_select.setChecked(True)
        self.on_layer_changed()

    def hideEvent(self, e):
        self.point_picker.stop_picking()

        # WORKAROUND ALERT
        # It seems impossible to "untrigger"
        # a self.actionRectangleSelect() trigger, except by
        # triggering another QAction method of self.iface.
        # The safest fallback option then is actionPan.
        # There also seems no attribute that gives us info
        # whether we are currently selecting or not.
        # TODO: Create a seperate object in maptools, which
        # stores whether we triggered self.iface.actionRectangleSelect
        # And has methods to "stop_picking" etc.
        # We could use the triggered() signal to store whether
        # we are currently selecting on the iface.
        self.iface.actionPan().trigger()

        self.clear()

        # Explicitly disconnect signal
        layer = self.layer_selection.currentLayer()
        if (layer is not None) and (layer.type() == QgsMapLayerType.VectorLayer):
            n_receivers = layer.receivers(layer.selectionChanged)
            # Methods can be connected multiple times to a signal, therefore
            # loop over n_receivers to ensure the signal is fully disconnected.
            # If we require more fine-grained control on finding signals:
            # https://stackoverflow.com/questions/8166571/how-to-find-if-a-signal-is-connected-to-anything/68621792#68621792
            for _ in range(n_receivers):
                # Try except to deal with the case where other method than
                # on_select is connected to selectionChanged.
                try:
                    layer.selectionChanged.disconnect(self.on_select)
                except TypeError:
                    pass
        QWidget.hideEvent(self, e)

    def showEvent(self, e):
        layer = self.layer_selection.currentLayer()
        if (layer is not None) and (layer.type() == QgsMapLayerType.VectorLayer):
            layer.selectionChanged.connect(self.on_select)
        QWidget.showEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.legend.clear()
        self.names = []
        self.curves = []
        self.pens = []
        self.selected = (None, None, None)

    def clear(self):
        self.feature_ids = None
        self.dataframes = {}
        self.stored_dataframes = {}
        self.point_picker.clear_geometries()
        # NOTE: self.point_picker.clear_geometries emits
        # a signal to self.point_picker.geometries_changed
        # which is connected to self.on_select,
        # which also calls self.clear_plot
        layer = self.layer_selection.currentLayer()
        if layer is not None and layer.type() != QgsMapLayerType.MeshLayer:
            layer.removeSelection()

        self.clear_plot()
        return

    def start_selection(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        if layer.type() == QgsMapLayerType.MeshLayer:
            self.point_picker.picker_clicked()
        else:
            self.iface.actionSelectRectangle().trigger()
        return

    def toggle_update(self):
        """
        Whether or not the plot automatically updates.

        For point layers (tables, IPF), this means the plot is updated every
        time a new selection is made. In this case, the old plot will be cleaned.

        For mesh layers, this means hovering on the map will cause the plot to update.
        In this case, the plot will NOT be cleaned.
        """
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        updating = self.update_on_select.isChecked()
        self.plot_button.setEnabled(not updating)
        self.point_picker.updating = updating

    def set_variable_layernumbers(self):
        layer = self.layer_selection.currentLayer()
        if layer.type() != QgsMapLayerType.MeshLayer:
            return
        variable = self.variable_selection.dataset_variable
        layers = [str(a) for a in self.variables_indexes[variable].keys()]
        self.multi_variable_selection.menu_datasets.populate_actions(layers)

        # If no layers present, but time is present, disable button.
        if layers == ["-1"]:
            self.multi_variable_selection.setDisabled(True)
        else:
            # Else statement to re-enable after being disabled
            # first (switching between two datasets)
            self.multi_variable_selection.setEnabled(True)

    def on_layer_changed(self):
        # Explicitly disconnect signal to formerly connected vector layers
        if self.previous_layer is not None:  # Do nothing the first time after init
            try:
                if self.previous_layer.type() == QgsMapLayerType.VectorLayer:
                    try:
                        self.previous_layer.selectionChanged.disconnect(self.on_select)
                    # Edge case where IPF points are selected with SHIFT+click.
                    # TODO: Investigate why this function is called when SHIFT clicking
                    except TypeError:
                        pass
            except RuntimeError as e:
                # The layer has been deleted from qgis
                print(e.args[0])
                if e.args[0] == PYQT_DELETED_ERROR:
                    pass
                else:
                    raise e

        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        # Reset state
        self.id_label.setVisible(True)
        self.id_selection_box.setVisible(True)
        self.variables_indexes = None
        self.variable_selection.setVisible(False)
        self.id_selection_box.clear()
        if layer.type() == QgsMapLayerType.MeshLayer:
            indexes, names = get_group_names(layer)
            is_temporal = get_group_is_temporal(layer)

            # Filter non-temporal dataset groups
            indexes = list(compress(indexes, is_temporal))
            names = list(compress(names, is_temporal))

            self.variables_indexes = groupby_variable(names, indexes)

            # Add groups without layer, but with time
            # (so which are in names after filtering, and not in variables_indexes)
            # to variables_index, with a sentinel layer index of -1
            for name, index in zip(names, indexes):
                if (name not in self.variables_indexes.keys()) and (
                    "_layer_" not in name
                ):
                    self.variables_indexes[name]["-1"] = index

            self.id_label.setVisible(False)
            self.id_selection_box.setVisible(False)
            self.variable_selection.setVisible(True)
            self.variable_selection.menu_datasets.populate_actions(
                self.variables_indexes.keys()
            )
            self.variable_selection.menu_datasets.check_first()
            self.set_variable_layernumbers()
            self.multi_variable_selection.menu_datasets.check_first()
            self.multi_variable_selection.setText("Layers: ")
        elif layer.type() == QgsMapLayerType.VectorLayer:
            # Connect to QGIS signal that selection changed
            layer.selectionChanged.connect(self.on_select)
            # Set active layer so the Selection Toolbar will work as expected
            # (since it works on the currently active layer)
            self.iface.setActiveLayer(layer)
            if layer.customProperty("ipf_type") == IpfType.TIMESERIES.name:
                index = int(layer.customProperty("ipf_indexcolumn"))
                self.id_selection_box.insertItem(0, layer.attributeAlias(index))
                self.id_selection_box.setEnabled(False)
                variables = layer.customProperty("ipf_assoc_columns").split("␞")
            elif layer.customProperty("arrow_type") == "timeseries":
                self.load_arrow_data(layer)
                if self.stored_dataframes:
                    sample_df = next(iter(self.stored_dataframes.values()))
                else:
                    sample_df = pd.DataFrame()
                variables = list(sample_df.columns)
                self.id_selection_box.insertItem(0, "fid")
                self.id_selection_box.setEnabled(False)
            else:
                datetime_column = layer.temporalProperties().startField()
                variables = [f.name() for f in layer.fields()]
                try:
                    variables.remove(datetime_column)
                except ValueError:
                    pass
                self.id_selection_box.insertItems(0, variables)
                self.id_selection_box.setEnabled(True)
            self.multi_variable_selection.menu_datasets.populate_actions(variables)
            self.multi_variable_selection.menu_datasets.check_first()
            self.multi_variable_selection.setText("Variable: ")

        # Set "previous" layer for next call of this method
        self.previous_layer = layer

    def load_mesh_data(self, layer):
        """Load timeseries data from a Mesh dataset"""
        if len(self.point_picker.geometries) == 0:
            return
        name = layer.name()
        n_geom = len(self.point_picker.geometries)
        if not self.update_on_select.isChecked():
            n_geom -= 1

        for i in range(n_geom):
            geometry = self.point_picker.geometries[i]
            variable = self.variable_selection.dataset_variable
            sample_index = next(iter(self.variables_indexes[variable].values()))
            times = timeseries_x_data(layer, sample_index)
            n_times = times.size
            layer_numbers = self.multi_variable_selection.checked_variables()
            columns = {"time": times}
            for number in layer_numbers:
                group_index = self.variables_indexes[variable][number]
                columns[number] = timeseries_y_data(
                    layer, geometry, group_index, n_times
                )
            self.dataframes[
                f"{name} point {i + 1} {variable}"
            ] = pd.DataFrame.from_dict(columns).set_index("time")

    def sync_ipf_data(self, layer):
        """Synchronize (load & unload) timeseries data from an IPF dataset"""
        feature_ids = layer.selectedFeatureIds()  # Returns a new list
        # Do not read the data if the selection is the same
        if self.feature_ids == feature_ids:
            return
        if len(feature_ids) == 0:
            # warn user: no features selected in current layer
            return

        index = int(layer.customProperty("ipf_indexcolumn"))
        ext = layer.customProperty("ipf_assoc_ext")
        ipf_path = layer.customProperty("ipf_path")
        parent = Path(ipf_path).parent
        names = sorted(
            [str(layer.getFeature(fid).attribute(index)) for fid in feature_ids]
        )

        # Filter names to add and to remove, to prevent loading duplicates
        names_to_add = set(names).difference(self.dataframes.keys())
        names_to_pop = set(self.dataframes.keys()).difference(names)

        for name in names_to_add:
            dataframe = read_associated_timeseries(f"{parent.joinpath(name)}.{ext}")
            self.dataframes[name] = dataframe

        for name in names_to_pop:
            self.dataframes.pop(name)

        # Store feature_ids for future comparison
        self.feature_ids = feature_ids
        return

    def load_arrow_data(self, layer):
        """Synchronize timeseries data from an Arrow dataset"""
        arrow_path = layer.customProperty("arrow_path")
        column = layer.customProperty("arrow_fid_column")
        if Path(arrow_path).is_file():
            df = read_arrow(arrow_path)
            if not df.empty:
                for key, groupdf in df.groupby(column):
                    self.stored_dataframes[key] = groupdf.set_index("time")
        return

    def sync_arrow_data(self, layer):
        feature_ids = layer.selectedFeatureIds()  # Returns a new list
        # Do not read the data if the selection is the same
        if self.feature_ids == feature_ids:
            return
        if len(feature_ids) == 0:
            # warn user: no features selected in current layer
            return

        feature_ids = set(feature_ids).intersection(self.stored_dataframes.keys())

        # Filter names to add and to remove, to prevent loading duplicates
        names_to_add = set(feature_ids).difference(self.dataframes.keys())
        names_to_pop = set(self.dataframes.keys()).difference(feature_ids)

        for name in names_to_add:
            self.dataframes[name] = self.stored_dataframes[name]

        for name in names_to_pop:
            self.dataframes.pop(name)

        # Store feature_ids for future comparison
        self.feature_ids = feature_ids
        return

    def sync_table_data(self, layer):
        """Synchronize timeseries data from a QGIS attribute table."""
        feature_ids = layer.selectedFeatureIds()  # Returns a new list
        # Do not read the data if the selection is the same
        if self.feature_ids == feature_ids:
            return
        if len(feature_ids) == 0:
            # warn user: no features selected in current layer
            return

        datetime_column = layer.temporalProperties().startField()
        id_column = self.id_selection_box.currentText()
        if datetime_column == "":  # Not a temporal layer
            # TODO: user communication?
            return

        with tempfile.TemporaryDirectory() as parent:
            path = Path(parent) / "temp-table.csv"
            write_csv(layer, path)
            df = pd.read_csv(
                path,
                parse_dates=[datetime_column],
                infer_datetime_format=True,
                index_col=id_column,
            )

        selection = {
            layer.getFeature(fid).attribute(id_column) for fid in feature_ids
        }

        # Filter names to add and to remove, to prevent loading duplicates
        names_to_add = set(selection).difference(self.dataframes.keys())
        names_to_pop = set(self.dataframes.keys()).difference(selection)

        for name in names_to_add:
            self.dataframes[name] = df.loc[[name]].set_index(datetime_column)

        for name in names_to_pop:
            self.dataframes.pop(name)

        # Store feature_ids for future comparison
        self.feature_ids = feature_ids

    def load(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        if layer.type() == QgsMapLayerType.MeshLayer:
            self.load_mesh_data(layer)
        elif layer.customProperty("ipf_type") == IpfType.TIMESERIES.name:
            self.sync_ipf_data(layer)
        elif layer.customProperty("arrow_type") == "timeseries":
            self.sync_arrow_data(layer)
        else:
            self.sync_table_data(layer)

    def select_curve(self, curve):
        for c, pen, name in zip(self.curves, self.pens, self.names):
            if c.curve is curve:
                self.selected = (c, pen, name)
                self.color_button.setColor(pen.color())
                pen.setWidth(SELECTED_WIDTH)
            else:
                pen.setWidth(WIDTH)
            c.curve.setPen(pen)

    def select_item(self, item):
        for c, pen, name in zip(self.curves, self.pens, self.names):
            if c is item:
                self.selected = (c, pen, name)
                self.color_button.setColor(pen.color())
                pen.setWidth(SELECTED_WIDTH)
            else:
                pen.setWidth(WIDTH)
            c.curve.setPen(pen)

    def on_select(self):
        # NOTE: Use self.sender() to know whether method is called by PointGeometryPickerWidget
        # or qgis._core.QgsVectorLayer (that is: connected to layer for IPFs and Vector data)
        if not self.update_on_select.isChecked():
            return
        self.draw_plot()

    def draw_plot(self):
        # Always clear plot before drawing
        self.clear_plot()

        self.load()
        columns_to_plot = self.multi_variable_selection.checked_variables()
        series_list = []
        for name, dataframe in self.dataframes.items():
            for column in columns_to_plot:
                if column in dataframe:
                    self.names.append(f"{name} {column}")
                    series_list.append(dataframe[column])

        self.color_widget.set_data(self.names)
        shader = self.color_widget.shader()
        for name, series in zip(self.names, series_list):
            to_draw, r, g, b, alpha = shader.shade(name)
            if to_draw:
                color = QColor(r, g, b, alpha)
                self.draw_timeseries(series, color)
        self.update_legend()

    def draw_timeseries(self, series, color):
        x = (series.index - PYQT_REFERENCE_TIME).total_seconds().to_numpy()
        y = series.to_numpy()
        pen = pg.mkPen(
            color=color,
            width=WIDTH,
        )
        symbol = "+" if self.marker_checkbox.checkState() else None
        curve = pg.PlotDataItem(
            x, y, pen=pen, clickable=True, symbol=symbol, symbolPen=pen
        )
        curve.sigClicked.connect(self.select_item)
        curve.curve.setClickable(True)
        curve.curve.sigClicked.connect(self.select_curve)
        self.plot_widget.addItem(curve)
        self.curves.append(curve)
        self.pens.append(pen)

    def update_legend(self):
        labels = self.color_widget.labels()
        for curve, name in zip(self.curves, self.names):
            if name in labels:
                self.legend.removeItem(curve)
                self.legend.addItem(curve, labels[name])

    def apply_color(self):
        curve, pen, name = self.selected
        if curve is not None and pen is not None:
            color = self.color_button.color()
            pen.setColor(color)
            pen.setWidth(WIDTH)
            curve.setPen(pen)
            curve.setSymbolPen(pen)
            self.color_widget.set_color(name, color)

    def colors(self):
        if self.color_widget is not None:
            dialog = SymbologyDialog(self.color_widget, self)
            dialog.show()
            ok = dialog.exec_()
            if ok and len(self.names) > 0:
                shader = self.color_widget.shader()
                labels = self.color_widget.labels()
                for curve, pen, name in zip(self.curves, self.pens, self.names):
                    to_draw, r, g, b, alpha = shader.shade(name)
                    if name in labels and to_draw:
                        color = QColor(r, g, b, alpha)
                        pen.setColor(color)
                        curve.setPen(pen)
                        curve.setSymbolPen(pen)
                    else:  # It has been removed from the colors menu
                        self.plot_widget.getPlotItem().removeItem(curve)
                        self.curves.remove(curve)
                        self.pens.remove(pen)
                        self.names.remove(name)
                self.update_legend()

    def show_or_hide_markers(self):
        symbol = "+" if self.marker_checkbox.checkState() else None
        for curve, pen in zip(self.curves, self.pens):
            curve.setSymbolPen(pen)
            curve.setSymbol(symbol)

    def export(self):
        plot_item = self.plot_widget.plotItem
        self.export_dialog.show(plot_item)
