from PyQt5.QtWidgets import (
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
)

from qgis.gui import QgsExtentGroupBox, QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel, QgsMeshDatasetIndex

from .maptools import RectangleMapTool
from .imod.xml_tree import load_to_explorer_tree, write_xml, add_to_explorer_tree, create_file_tree, command_xml
from .server_handler import ServerHandler
from ..utils.layers import groupby_layer

import os
import subprocess

import uuid

# TODOs: 
#   - Implement current functionality & cleanup old stuff
#   - Add functionality for view iMOD button

class ImodViewerWidget(QWidget):
    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.crs = self.canvas.mapSettings().destinationCrs()
        self.server_handler = ServerHandler()

        #Layer selection
        self.layer_selection = QgsMapLayerComboBox()
        self.layer_selection.setFilters(QgsMapLayerProxyModel.MeshLayer)

        #Draw extent button      
        #TODO: Create seperate widget for extent_button, so that the right click button can be used to unset geometry
        self.extent_button = QPushButton("Draw extent")
        self.extent_button.clicked.connect(self.draw_extent)
        self.rectangle_tool = RectangleMapTool(self.canvas)
        self.rectangle_tool.rectangleCreated.connect(self.set_bbox)

        #Extent box
        self.extent_box = self._init_extent_box()
        self.bbox = None

        #Start viewer button
        self.viewer_button = QPushButton("start iMOD 3D viewer")
        self.viewer_button.clicked.connect(self.start_viewer)

        self.update_button = QPushButton("update 3D plot")
        self.update_button.clicked.connect(self.update_viewer)

        #Define layout
        first_column = QVBoxLayout()
        first_column.addWidget(self.layer_selection)
        first_column.addWidget(self.extent_button)

        third_column = QVBoxLayout()
        third_column.addWidget(self.viewer_button)
        third_column.addWidget(self.update_button)

        layout = QHBoxLayout() #Create horizontal layout, define stretch factors as 1 - 2 - 1
        layout.addLayout(first_column, 1)
        layout.addWidget(self.extent_box, 2)
        layout.addLayout(third_column, 1)

        self.setLayout(layout)

    def _init_extent_box(self):
        extent_box = QgsExtentGroupBox()

        extent_box.setOriginalExtent(
            self.canvas.extent(),
            self.canvas.mapSettings().destinationCrs()
        )
        extent_box.setCurrentExtent(
            self.canvas.extent(),
            self.crs #TODO: Set based on layer crs
        )
        extent_box.setOutputCrs(self.crs)

        return extent_box

    def set_bbox(self):
        self.bbox = self.rectangle_tool.rectangle()

        self.extent_box.setOutputExtentFromUser(self.bbox, self.crs)

    def draw_extent(self):
        print("Please draw extent")
        self.canvas.setMapTool(self.rectangle_tool)

    def initialize_xml(self, xml_path):
        """Write imod projectfile to immediately have data in the explorer.
        """
        self.xml_dict = {}

        current_layer = self.layer_selection.currentLayer()
        self.xml_dict["path"] = current_layer.dataProvider().dataSourceUri()
    
        idx = current_layer.datasetGroupsIndexes()
        self.xml_dict["group_names"] = [current_layer.datasetGroupMetadata(QgsMeshDatasetIndex(group=i)).name() for i in idx]

        style_group_index = idx[0]  #Same style used for all groups in QGIS 3.16
                                    #FUTURE: Check if this remains

        colorramp = current_layer.rendererSettings(
            ).scalarSettings(style_group_index
            ).colorRampShader(
            ).colorRampItemList()

        self.xml_dict["rgb_point_data"] = self.create_rgb_array(colorramp)

        self.xml_dict["bbox_rectangle"] = self.extent_box.outputExtent()

        n_layers = len(groupby_layer(self.xml_dict["group_names"]))

        self.xml_dict["guids_grids"] = [uuid.uuid4() for i in range(n_layers)]

        write_xml(xml_path, **self.xml_dict)

    def rgb_components_to_float(self, components):
        return [comp/256 for comp in components]

    def rgb_string(self, c):
        rgb = c.color.red(), c.color.green(), c.color.blue()
        return "{} {} {} {}".format(c.value, *self.rgb_components_to_float(rgb))

    def create_rgb_array(self, colorramp):
        return ' '.join(self.rgb_string(c) for c in colorramp)

    def start_viewer(self):
        configdir = self.server_handler.get_configdir()
        xml_path = configdir / 'qgis_viewer.imod'

        self.settings_to_xml(xml_path)

        self.server_handler.start_server()
    
    def update_viewer(self):
        #Load model
        for guid_grid in self.xml_dict["guids_grids"]:
            command = command_xml(load_to_explorer_tree, guid_grid=gruid_grid)
            self.server_handler.send(command)