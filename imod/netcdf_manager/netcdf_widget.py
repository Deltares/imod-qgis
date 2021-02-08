from PyQt5.QtWidgets import (
    QWidget,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QComboBox,
    QLabel,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.utils import iface
from osgeo import gdal

from pathlib import Path
from .dimension_handler import DimensionHandler
import numpy as np
import xarray as xr
import uuid

GDT_FLOAT64 = 7


class ImodNetcdfManagerWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.dataset_line_edit = QLineEdit()
        self.dataset_line_edit.textChanged.connect(self.update_variables)

        self.open_button = QPushButton("...")
        self.open_button.clicked.connect(self.set_dataset)

        self.variables = QComboBox()
        self.variables.currentIndexChanged.connect(self.refresh_sliders)

        self.extract_button = QPushButton("Extract Raster")
        self.extract_button.clicked.connect(self.extract_raster)

        self.layer_selection = QgsMapLayerComboBox()
        self.layer_selection.setFilters(QgsMapLayerProxyModel.RasterLayer)

        self.subset_button = QPushButton("Subset Raster")
        self.subset_button.clicked.connect(self.subset_raster)
    
        first_row = QHBoxLayout()
        first_row.addWidget(self.dataset_line_edit)
        first_row.addWidget(self.open_button)

        second_row = QHBoxLayout()
        second_row.addWidget(QLabel("Variable:"))
        second_row.addWidget(self.variables)

        self.dimension_handler = DimensionHandler()

        third_row = QHBoxLayout()
        third_row.addWidget(self.layer_selection) 
        third_row.addWidget(self.subset_button)

        column = QVBoxLayout()
        column.addLayout(first_row)
        column.addLayout(second_row)
        column.addWidget(self.dimension_handler)
        column.addWidget(self.extract_button)
        column.addLayout(third_row)
        column.addStretch()

        self.setLayout(column)

    def set_dataset(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "*.nc")
        if path != "":  # Empty string in case of cancel button press
            self.dataset_line_edit.setText(path)

    def update_variables(self):
        path = self.dataset_line_edit.text()
        path = Path(self.dataset_line_edit.text())
        with xr.open_dataset(path) as ds:
            datavars = [var for var in ds.data_vars if len(ds[var]) > 2]
        self.variables.clear()
        self.variables.addItems(datavars)

    def refresh_sliders(self):
        path = Path(self.dataset_line_edit.text())
        var = self.variables.currentText()
        with xr.open_dataset(path) as ds:
            da = ds[var]
            dims = da.dims[:-2]  # Skip y, x
            values = [da[dim].values for dim in dims]
        self.dimension_handler.populate_sliders(dims, values)

    def extract_raster(self):
        indexer = {
            dim: slider.value()
            for dim, slider in zip(
                self.dimension_handler.dims, self.dimension_handler.sliders
            )
        }
        path = Path(self.dataset_line_edit.text())
        var = self.variables.currentText()
        with xr.open_dataset(path) as ds:
            da = ds[var].astype(np.float64)
            data = da.isel(indexer).values
            xdim = da.dims[-1]
            ncol = da.shape[-1]
            nrow = da.shape[-2]
            ydim = da.dims[-2]
            left = float(da[xdim][0])
            right = float(da[xdim][-1])
            top = float(da[ydim][0])
            bottom = float(da[ydim][-1])
            dx = (right - left) / (ncol - 1)
            dy = (bottom - top) / (nrow - 1)
        
        # Just dump it in the current working dir:
        dst_path = f"temporary-raster-{uuid.uuid4()}.tif"
        driver = gdal.GetDriverByName("GTiff")
        raster = driver.Create(dst_path, ncol, nrow, 1, GDT_FLOAT64)
        raster.SetGeoTransform([left, dx, 0, top, 0, dy])
        band = raster.GetRasterBand(1)
        band.SetNoDataValue(np.nan)
        band.WriteArray(data)
        raster.FlushCache()
        # Now load it into QGIS
        iface.addRasterLayer(dst_path, "temporary-raster", "gdal")

    def subset_raster(self):
        raster_layer = self.layer_selection.layer(0)
        path = raster_layer.dataProvider().dataSourceUri()
        raster = gdal.Open(path)
        data = raster.GetRasterBand(1).ReadAsArray()
        print(data)
