from PyQt5.QtWidgets import (
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
)
from PyQt5.QtGui import QColor
from qgis.gui import QgsMapLayerComboBox, QgsColorButton, QgsColorRampButton
from qgis.core import QgsMapLayerProxyModel, QgsColorBrewerColorRamp
import pyqtgraph as pg


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

        self.color_ramp_button = QgsColorRampButton()
        self.color_ramp_button.setColorRamp(QgsColorBrewerColorRamp("Set1", colors=9))

        self.plot_widget = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        second_column = QGridLayout()
        second_column.addWidget(QLabel("Line Color:"), 0, 0)
        second_column.addWidget(self.color_button, 0, 1)
        second_column.addWidget(self.apply_color_button, 1, 1)
        second_column.addWidget(QLabel("Color ramp:"), 2, 0)
        second_column.addWidget(self.color_ramp_button, 2, 1)
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
        import pandas as pd
        dataframe = pd.read_csv(
            r"C:\src\imod-qgis\imod\timeseries\test-timeseries.csv",
            parse_dates=["date"],
            dayfirst=True,
        )
        dataframe = dataframe.set_index("fid")
        features_ids = [1, 2]
        timeseries = dataframe.loc[features_ids]
        reference_time = pd.Timestamp("1970-01-01")

        color_ramp = self.color_ramp_button.colorRamp()
        ncolor = color_ramp.colors()

        for i, (feature_id, point_series) in enumerate(timeseries.groupby(timeseries.index)):
            x = (point_series["date"] - reference_time).dt.total_seconds().values
            y = point_series["level"].values
            curve = pg.PlotCurveItem(x, y, clickable=True)
            pen = pg.mkPen(color=color_ramp.color(i % ncolor), width=2, cosmetic=True)
            curve.setPen(pen)
            curve.sigClicked.connect(self.select_curve)
            self.plot_widget.addItem(curve)
            self.curves.append(curve)
            self.pens.append(pen)

    def apply_color(self):
        curve, pen = self.selected
        if curve is not None and pen is not None:
            pen.setColor(self.color_button.color())
            curve.setPen(pen)
