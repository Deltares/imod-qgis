# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import shlex
from pathlib import Path

import numpy as np
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    Qgis,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsRasterLayer,
)
from qgis.gui import QgsCrsSelectionWidget, QgsMapLayerComboBox

from imodqgis.idf.conversion import convert_gdal_to_idf, convert_idf_to_gdal
from imodqgis.idf.layer_styling import pseudocolor_renderer


class OpenWidget(QWidget):
    def __init__(self, iface, parent) -> None:
        super().__init__()
        self.parent = parent
        self.label = QLabel("iMOD IDF File(s)")
        self.line_edit = QLineEdit()
        self.line_edit.setMinimumWidth(250)
        self.dialog_button = QPushButton("...")
        self.dialog_button.clicked.connect(self.file_dialog)
        self.close_button = QPushButton("Close")
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_idfs)
        self.line_edit.textChanged.connect(
            lambda: self.add_button.setEnabled(self.line_edit != "")
        )
        self.add_button.setEnabled(False)
        self.crs_widget = QgsCrsSelectionWidget(self)
        self.crs_widget.setCrs(iface.mapCanvas().mapSettings().destinationCrs())
        first_row = QHBoxLayout()
        first_row.addWidget(self.label)
        first_row.addWidget(self.line_edit)
        first_row.addWidget(self.dialog_button)
        second_row = QHBoxLayout()
        second_row.addWidget(self.crs_widget)
        third_row = QHBoxLayout()
        third_row.addStretch()
        third_row.addWidget(self.close_button)
        third_row.addWidget(self.add_button)
        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        layout.addLayout(third_row)
        self.setLayout(layout)

    def file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", "", "*.idf *.IDF")
        # paths is empty list if cancel is clicked
        if len(paths) == 0:
            return
        else:
            # Surround the paths by double quotes and separate by a space
            self.line_edit.setText(" ".join(f'"{p}"' for p in paths))
        return

    def add_idfs(self) -> None:
        text = self.line_edit.text()
        paths = list(reversed(shlex.split(text, posix="/" in text)))

        if not self.crs_widget.hasValidSelection():
            return
        crs_wkt = self.crs_widget.crs().toWkt()

        for path in paths:
            tiff_path = convert_idf_to_gdal(path, crs_wkt)
            layer = QgsRasterLayer(str(tiff_path), tiff_path.stem)
            renderer = pseudocolor_renderer(layer, band=1, colormap="Turbo", nclass=10)
            layer.setRenderer(renderer)
            QgsProject.instance().addMapLayer(layer)

        return


class ExportWidget(QWidget):
    def __init__(self, parent) -> None:
        super().__init__()
        self.parent = parent
        self.raster_layer = QgsMapLayerComboBox()
        self.raster_layer.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.raster_layer.layerChanged.connect(self.on_layer_changed)
        self.label = QLabel("Export to IDF file")
        self.line_edit = QLineEdit()
        self.line_edit.setMinimumWidth(250)
        self.dialog_button = QPushButton("...")
        self.dialog_button.clicked.connect(self.file_dialog)
        self.double_precision_checkbox = QCheckBox("Double Precision")
        self.close_button = QPushButton("Close")
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_layer)

        self.line_edit.textChanged.connect(
            lambda: self.export_button.setEnabled(self.line_edit != "")
        )
        self.export_button.setEnabled(False)

        first_row = QHBoxLayout()
        first_row.addWidget(self.raster_layer)
        second_row = QHBoxLayout()
        second_row.addWidget(self.double_precision_checkbox)
        third_row = QHBoxLayout()
        third_row.addWidget(self.label)
        third_row.addWidget(self.line_edit)
        third_row.addWidget(self.dialog_button)
        fourth_row = QHBoxLayout()
        fourth_row.addStretch()
        fourth_row.addWidget(self.close_button)
        fourth_row.addWidget(self.export_button)
        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        layout.addLayout(third_row)
        layout.addStretch()
        layout.addLayout(fourth_row)
        self.setLayout(layout)
        # Trigger manually at initialization:
        self.on_layer_changed()

    def file_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select files", "", "*.idf *.IDF")
        # paths is empty list if cancel is clicked
        if len(path) != 0:
            # Surround the paths by double quotes and separate by a space
            self.line_edit.setText(path)
        return

    def on_layer_changed(self) -> None:
        layer = self.raster_layer.currentLayer()
        if layer is None:  # If no raster layers in project
            return
        path = Path(layer.dataProvider().dataSourceUri())
        idf_path = (path.parent / (path.name)).with_suffix(".idf")
        self.line_edit.setText(str(idf_path))
        return

    def export_layer(self) -> None:
        layer = self.raster_layer.currentLayer()
        if self.double_precision_checkbox.isChecked():
            dtype = np.float64
        else:
            dtype = np.float32
        idf_path = self.line_edit.text()
        gdal_path = layer.dataProvider().dataSourceUri()
        convert_gdal_to_idf(gdal_path, idf_path, dtype)

        self.parent.message_bar.pushMessage(
            title="Info",
            text=f"Exported {layer.name()} to {idf_path}",
            level=Qgis.Info,
        )
        return


class ImodIdfDialog(QDialog):
    def __init__(self, iface, parent=None) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle("Open and export IDF")
        self.message_bar = iface.messageBar()

        self.openwidget = OpenWidget(iface, self)
        self.openwidget.close_button.clicked.connect(self.reject)
        self.openwidget.add_button.clicked.connect(self.accept)

        self.exportwidget = ExportWidget(self)
        self.exportwidget.close_button.clicked.connect(self.reject)
        self.exportwidget.export_button.clicked.connect(self.accept)

        self.tabwidget = QTabWidget()
        self.tabwidget.addTab(self.openwidget, "Open")
        self.tabwidget.addTab(self.exportwidget, "Export")

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tabwidget)
        self.setLayout(self.layout)
