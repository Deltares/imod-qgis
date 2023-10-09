# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import json
import os
import platform
import textwrap
from pathlib import Path

from PyQt5.QtCore import QSortFilterProxyModel, Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
)

from imodqgis.nhi_data.provider_metadata import fetch_metadata


class ImodNhiDataDialog(QDialog):
    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Add NHI data")
        self.iface = iface
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("service type, (part of) name")
        # QStandard Item Model
        self.data_model = QStandardItemModel()
        # Proxy model
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.data_model)
        self.proxy_model.setFilterKeyColumn(2)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # Table view
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionMode(self.table_view.SingleSelection)
        self.table_view.setSelectionBehavior(self.table_view.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setColumnWidth(0, 300)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.setAutoScroll(False)
        self.table_view.setSortingEnabled(True)
        # Abstract text box
        self.abstract_text = QTextEdit()
        self.abstract_text.setMaximumHeight(150)
        # Buttons
        self.add_button = QPushButton("Add layer")
        self.close_button = QPushButton("Close")

        # Connect to methods
        self.search_edit.textChanged.connect(self.filter_layers)
        self.add_button.clicked.connect(self.add_layer)
        self.close_button.clicked.connect(self.reject)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection)

        # Set layout
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Search:"))
        first_row.addWidget(self.search_edit)

        third_row = QHBoxLayout()
        third_row.addStretch()
        third_row.addWidget(self.add_button)

        fourth_row = QHBoxLayout()
        fourth_row.addStretch()
        fourth_row.addWidget(self.close_button)

        column = QVBoxLayout()
        column.addLayout(first_row)
        column.addWidget(self.table_view)
        column.addWidget(self.abstract_text)
        column.addLayout(third_row)
        column.addLayout(fourth_row)
        self.load_services()
        # Gotta set titles and hide after adding the data, not before it:
        self.data_model.setHeaderData(0, Qt.Horizontal, "Service")
        self.data_model.setHeaderData(1, Qt.Horizontal, "Layer name")
        self.data_model.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.data_model.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.table_view.hideColumn(2)
        self.setLayout(column)
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)
        self.add_button.setEnabled(False)

    def add_layer(self):
        layer = self.table_view.selectedIndexes()[0].data(Qt.UserRole)
        if layer is None:
            return

        service = layer["service"]
        title = layer["title"]
        if service == "wms":
            uri = "crs={crs}&layers={layers}&styles={styles}&format={format}&url={url}".format(
                **layer
            )
            self.iface.addRasterLayer(uri, title, service)
        elif service == "wcs":
            # https://docs.qgis.org/3.16/en/docs/pyqgis_developer_cookbook/loadlayer.html#raster-layers
            # cache options: AlwaysCache, PreferCache, PreferNetwork, AlwaysNetwork
            # AlwaysCache seems to result in an error?
            uri = "cache=PreferCache&crs={crs}&format={format}&identifier={identifier}&url={url}".format(
                **layer
            )
            self.iface.addRasterLayer(uri, title, service)
        elif service == "wfs":
            uri = "pagingEnabled='true' restrictToRequestBBOX='1' srsname='{crs}' typename='{typename}' url='{url}' version='{version}' ".format(
                **layer
            )
            self.iface.addVectorLayer(uri, title, service)
        else:
            raise ValueError(
                f"Invalid service. Should be one of [wms, wcs, wfs]. Got instead: {service}"
            )

    def filter_layers(self):
        self.table_view.selectRow(0)
        string = self.search_edit.text()
        self.proxy_model.setFilterFixedString(string)

    def add_row(self, layer):
        service = layer["service"]
        layername = layer["title"]
        item_filter = QStandardItem(f"{service} {layername}")
        service = QStandardItem(service.upper())
        service.setData(layer, Qt.UserRole)
        layername = QStandardItem(layername)
        self.data_model.appendRow([service, layername, item_filter])

    def load_services(self):
        if platform.system() == "Windows":
            configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
        else:
            configdir = Path(os.environ["HOME"]) / ".imod-qgis"
        path = configdir / "nhi-data-providers.json"
        if not path.exists():
            configdir.mkdir(parents=True, exist_ok=True)
            fetch_metadata()

        with open(path, "r") as f:
            metadata = json.loads(f.read())

        for layer in metadata:
            self.add_row(layer)

    def on_selection(self):
        self.add_button.setEnabled(True)
        layer = self.table_view.selectedIndexes()[0].data(Qt.UserRole)
        if layer is None:
            return
        self.abstract_text.setText(
            textwrap.dedent(
                f"""
                {layer["title"]}
                
                Service type: {layer["service"]}
                
                Abstract:
                {layer["abstract"]}
                
                URL:
                {layer["url"]}
                """
            )
        )
