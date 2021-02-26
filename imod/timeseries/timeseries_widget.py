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
    QWidgetAction,
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
)
import pandas as pd
import pyqtgraph as pg
from ..ipf import read_associated_timeseries, IpfType
from ..widgets import ImodUniqueColorWidget
import pathlib

import numpy as np


# Set rendering backend and set pen widths
# DO NOT USE PEN WIDTHS > 1 WITHOUT OPENGL
pg.setConfigOptions(useOpenGL=True)
WIDTH = 2
SELECTED_WIDTH = 3
# pyqtgraph expects datetimes expressed as seconds from 1970-01-01
PYQT_REFERENCE_TIME = pd.Timestamp("1970-01-01")


class DatasetVariableMenu(QMenu):
    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.setContentsMargins(10, 5, 5, 5)

    def populate_actions(self, variables):
        self.clear()
        for variable in variables:
            a = QWidgetAction(self)
            a.variable_name = variable
            a.setDefaultWidget(QCheckBox(variable))
            self.addAction(a)


class VariablesWidget(QToolButton):
    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.menu_datasets = DatasetVariableMenu()
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.setText("Columns to plot: ")


class SymbologyDialog(QDialog):
    def __init__(self, color_widget, parent=None):
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


class ImodTimeSeriesWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.layer_selection = QgsMapLayerComboBox()
        self.layer_selection.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layer_selection.setMinimumWidth(200)

        self.variable_selection = VariablesWidget()

        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.load)

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

        self.color_button = QgsColorButton()
        self.apply_color_button = QPushButton("Apply")
        self.apply_color_button.clicked.connect(self.apply_color)
        self.marker_checkbox = QCheckBox()
        self.marker_checkbox.stateChanged.connect(self.show_or_hide_markers)

        self.plot_widget = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        self.legend = self.plot_widget.getPlotItem().legend

        self.colors_button = QPushButton("Colors")
        self.colors_button.clicked.connect(self.colors)
        self.color_widget = ImodUniqueColorWidget()

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.load_button)
        first_row.addWidget(self.variable_selection)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        third_row = QHBoxLayout()
        third_row.addWidget(QLabel("Line Color:"))
        third_row.addWidget(self.color_button)
        third_row.addWidget(self.apply_color_button)

        fourth_row = QHBoxLayout()
        fourth_row.addWidget(QLabel("Draw markers"))
        fourth_row.addWidget(self.marker_checkbox)

        second_column = QVBoxLayout()
        second_column.addLayout(third_row)
        second_column.addLayout(fourth_row)
        second_column.addWidget(self.colors_button)
        second_column.addStretch()
        second_row.addLayout(second_column)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

        # Data
        self.dataframes = {}
        self.variables = set()
        # Graphing
        self.names = []
        self.curves = []
        self.pens = []
        self.selected = (None, None, None)

    def hideEvent(self, e):
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.legend.clear()
        self.names = []
        self.curves = []
        self.pens = []
        self.selected = (None, None)

    def load(self):
        self.dataframes = {}
        self.variables = set()
        layer = self.layer_selection.layer(0)
        features = layer.selectedFeatures()

        if len(features) == 0:
            # warn user: no features selected in current layer
            return

        if layer.customProperty("ipf_type") == IpfType.TIMESERIES:
            index = layer.customProperty("ipf_indexcolumn")
            ext = layer.customProperty("ipf_assoc_ext")
            ipf_path = layer.customProperty("ipf_path")
            parent = pathlib.Path(ipf_path).parent
            names = sorted([str(f.attribute(index)) for f in features])
            for name in names:
                dataframe = read_associated_timeseries(f"{parent.joinpath(name)}.{ext}")
                self.dataframes[name] = dataframe
                self.variables.update(dataframe.columns[1:])

        self.variable_selection.menu_datasets.populate_actions(self.variables)
        self.variable_selection.showMenu()

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

    def draw_plot(self):
        columns_to_plot = [
            a.variable_name
            for a in self.variable_selection.menu_datasets.actions()
            if a.defaultWidget().isChecked()
        ]
        series_list = []
        for name, dataframe in self.dataframes.items():
            for column in columns_to_plot:
                if column in dataframe:
                    self.names.append(f"{name} {column}")
                    series_list.append(dataframe[column])

        self.color_widget.set_data(self.names)
        shader = self.color_widget.shader()
        for name, series in zip(self.names, series_list):
            color = shader.shade(name)
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
        curve = pg.PlotDataItem(x, y, pen=pen, clickable=True, symbol=symbol)
        curve.sigClicked.connect(self.select_item)
        curve.curve.setClickable(True)
        curve.curve.sigClicked.connect(self.select_curve)
        self.plot_widget.addItem(curve)
        self.curves.append(curve)
        self.pens.append(pen)

    def update_legend(self):
        self.legend.clear()
        labels = self.color_widget.labels()
        for curve, name in zip(self.curves, self.names):
            if name in labels:
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
                    if name in labels:
                        pen.setColor(shader.shade(name))
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
