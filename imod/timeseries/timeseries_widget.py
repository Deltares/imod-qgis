from PyQt5.QtWidgets import (
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
    QDialog,
)
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
from ..utils import ImodUniqueColorWidget
import pathlib

import numpy as np

# pyqtgraph expects datetimes expressed as seconds from 1970-01-01
PYQT_REFERENCE_TIME = pd.Timestamp("1970-01-01")


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

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

        self.color_button = QgsColorButton()
        self.apply_color_button = QPushButton("Apply")
        self.apply_color_button.clicked.connect(self.apply_color)

        self.plot_widget = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()

        self.symbology_button = QPushButton("Symbology")
        self.symbology_button.clicked.connect(self.symbology)
        self.color_widget = ImodUniqueColorWidget(self) 
        self.names = None

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        third_row = QHBoxLayout()
        third_row.addWidget(QLabel("Line Color:"))
        third_row.addWidget(self.color_button)
        third_row.addWidget(self.apply_color_button)

        second_column = QVBoxLayout() 
        second_column.addLayout(third_row)
        second_column.addWidget(self.symbology_button)
        second_column.addStretch()
        second_row.addLayout(second_column)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

        self.curves = []
        self.pens = []
        self.selected = (None, None)

    def hideEvent(self, e):
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.clear_legend()
        self.current_color = 0

    def clear_legend(self):
        pass

    def select_curve(self, curve):
        for c, pen in zip(self.curves, self.pens):
            pen.setWidth(4)
            if c is curve:
                pen.setWidth(4)
                self.selected = (c, pen)
                self.color_button.setColor(pen.color())
            else:
                pen.setWidth(2)
            c.setPen(pen)

    def draw_plot(self):
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
            self.names = sorted([f.attribute(index) for f in features])
            self.color_widget.set_data(self.names)
            for name in self.names:
                dataframe = read_associated_timeseries(f"{parent.joinpath(name)}.{ext}")
                self.draw_timeseries(dataframe, name)
        else:
            # Collect the features into a dataframe, set fid as index
            # TODO: assume Qt DateTime column format for datetime column
            pass
            # dataframe = pd.DataFrame(
            #    data=[feature.attributes() for feature in features],
            #    columns=[field.name() for field in layer.fields()],
            # ).set_index("fid")
            ## Make sure the date column is a date time object
            # dataframe["date"] = pd.to_datetime(dataframe["date"], dayfirst=True)
            # self._plot(dataframe)

    def draw_timeseries(self, dataframe, name):
        shader = self.color_widget.shader()
        x = (dataframe["datetime"] - PYQT_REFERENCE_TIME).dt.total_seconds().values
        y = dataframe["level"].values
        curve = pg.PlotCurveItem(x, y, clickable=True)
        pen = pg.mkPen(
            color=shader.shade(name),
            width=2,
            cosmetic=True,
        )
        curve.setPen(pen)
        curve.sigClicked.connect(self.select_curve)
        self.plot_widget.addItem(curve)
        self.curves.append(curve)
        self.pens.append(pen)

    def apply_color(self):
        curve, pen = self.selected
        if curve is not None and pen is not None:
            pen.setColor(self.color_button.color())
            pen.setWidth(2)
            curve.setPen(pen)

    def symbology(self):
        if self.color_widget is not None:
            dialog = SymbologyDialog(self.color_widget, self)
            dialog.show()
            ok = dialog.exec_() 
            if ok and len(self.names) > 0:
                shader = self.color_widget.shader()
                for curve, pen, name in zip(self.curves, self.pens, self.names):
                    pen.setColor(shader.shade(name))
                    curve.setPen(pen)
