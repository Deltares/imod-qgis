"""
NOTA BENE: without OpenGL, setting pen width > 1 kills performance:
https://github.com/pyqtgraph/pyqtgraph/issues/533#

This enables OpenGL:
pg.setConfigOptions(useOpenGL=True)
But might not work on every system...
"""
from PyQt5.QtWidgets import (
    QCheckBox,
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
    QDialog,
    QToolButton,
    QMenu,
    QComboBox,
    QGroupBox,
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor
from qgis.gui import QgsMapLayerComboBox, QgsColorButton
from qgis.core import (
    QgsMapLayerProxyModel,
    QgsColorBrewerColorRamp,
    QgsVectorLayer,
    QgsPointXY,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsMapLayerType,
)
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.GraphicsScene.exportDialog import ExportDialog
from ..ipf import read_associated_timeseries, IpfType
from ..widgets import ImodUniqueColorWidget, MultipleVariablesWidget
import pathlib
import tempfile

import numpy as np


# Set rendering backend and set pen widths
# DO NOT USE PEN WIDTHS > 1 WITHOUT OPENGL
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
            if (layer.type() != QgsMapLayerType.VectorLayer) or (layer.geometryType() != QgsWkbTypes.PointGeometry):
                excepted_layers.append(layer)
            else:
                is_ipf_series = layer.customProperty("ipf_type") == IpfType.TIMESERIES.name
                is_temporal = layer.temporalProperties().startField() != ""
                if not (is_ipf_series or is_temporal):
                    excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ImodTimeSeriesWidget(QWidget):
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface

        self.layer_selection = UpdatingQgsMapLayerComboBox()
        self.layer_selection.layerChanged.connect(self.on_layer_changed)
        self.layer_selection.setMinimumWidth(200)

        self.id_selection_box = QComboBox()
        self.id_selection_box.setMinimumWidth(200)
        self.variable_selection = MultipleVariablesWidget()
    
        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

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
        first_row.addWidget(QLabel("ID column:"))
        first_row.addWidget(self.id_selection_box)
        first_row.addWidget(self.variable_selection)
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
        self.dataframes = {}
        # Graphing
        self.names = []
        self.curves = []
        self.pens = []
        self.selected = (None, None, None)

        # Run a single time initialize the combo boxes
        self.feature_ids = None
        self.layer_selection.update_layers()
        # Set default state of checkbox
        self.update_on_select.setChecked(True)

    def hideEvent(self, e):
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.legend.clear()
        self.names = []
        self.curves = []
        self.pens = []

    def toggle_update(self):
        updating = self.update_on_select.isChecked()
        self.plot_button.setEnabled(not updating)
        self.clear_button.setEnabled(not updating)
        layer = self.layer_selection.currentLayer()
        if updating:
            layer.selectionChanged.connect(self.on_select)
        else:
            layer.selectionChanged.disconnect(self.on_select)
    
    def on_layer_changed(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return

        self.id_selection_box.clear()
        if layer.customProperty("ipf_type") == IpfType.TIMESERIES.name:
            index = int(layer.customProperty("ipf_indexcolumn"))
            self.id_selection_box.insertItem(0, layer.attributeAlias(index))
            self.id_selection_box.setEnabled(False)
            variables = layer.customProperty("ipf_assoc_columns").split("␞")
        else:
            datetime_column = layer.temporalProperties().startField()
            variables = [f.name() for f in layer.fields()]
            try:
                variables.remove(datetime_column)
            except ValueError:
                pass
            self.id_selection_box.insertItems(0, variables)
            self.id_selection_box.setEnabled(True)

        self.iface.setActiveLayer(layer)
        self.variable_selection.menu_datasets.populate_actions(variables)

    def load(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        feature_ids = layer.selectedFeatureIds()  # Returns a new list
        # Do not read the data if the selection is the same
        if self.feature_ids == feature_ids:
            return

        if len(feature_ids) == 0:
            # warn user: no features selected in current layer
            return

        self.dataframes = {}
        if layer.customProperty("ipf_type") == IpfType.TIMESERIES.name:
            index = int(layer.customProperty("ipf_indexcolumn"))
            ext = layer.customProperty("ipf_assoc_ext")
            ipf_path = layer.customProperty("ipf_path")
            parent = pathlib.Path(ipf_path).parent
            names = sorted([str(layer.getFeature(fid).attribute(index)) for fid in feature_ids])

            for name in names:
                dataframe = read_associated_timeseries(f"{parent.joinpath(name)}.{ext}")
                self.dataframes[name] = dataframe

        else:
            datetime_column = layer.temporalProperties().startField()
            id_column = self.id_selection_box.currentText()
            if datetime_column == "":  # Not a temporal layer
                # TODO: user communication?
                return

            with tempfile.TemporaryDirectory() as parent:
                path = pathlib.Path(parent) / "temp-table.csv"
                write_csv(layer, path)
                df = pd.read_csv(path, parse_dates=[datetime_column], infer_datetime_format=True, index_col=id_column)

            selection = set(layer.getFeature(fid).attribute(id_column) for fid in feature_ids)
            for name in selection:
                self.dataframes[name] = df.loc[name].set_index(datetime_column)
        # Store feature_ids for future comparison 
        self.feature_ids = feature_ids

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
        self.clear_plot()
        self.draw_plot()

    def draw_plot(self):
        self.load()
        columns_to_plot = self.variable_selection.checked_variables()
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
        x = (series.index - PYQT_REFERENCE_TIME).total_seconds().values
        y = series.values
        pen = pg.mkPen(
            color=color,
            width=WIDTH,
        )
        symbol = "+" if self.marker_checkbox.checkState() else None
        curve = pg.PlotDataItem(x, y, pen=pen, clickable=True, symbol=symbol, symbolPen=pen)
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
