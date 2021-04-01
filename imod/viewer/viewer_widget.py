from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
)

from qgis.gui import QgsExtentGroupBox, QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel, QgsMeshDatasetIndex

from ..widgets import RectangleMapTool
from . import xml_tree
from .server import Server
from ..utils.layers import groupby_variable

import uuid

class ImodViewerWidget(QWidget):
    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.crs = self.canvas.mapSettings().destinationCrs()
        self.server = Server()

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

        #Initiate dictionary for xml commands
        self.xml_dict = {}

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

    def update_xml(self):
        """Update data for xml file.
        """

        current_layer = self.layer_selection.currentLayer()
        self.xml_dict["path"] = current_layer.dataProvider().dataSourceUri()
    
        idx = current_layer.datasetGroupsIndexes()
        self.xml_dict["group_names"] = [current_layer.datasetGroupMetadata(QgsMeshDatasetIndex(group=i)).name() for i in idx]

        self.xml_dict["variable_names"] = list(groupby_variable(self.xml_dict["group_names"], idx).keys())
        self.xml_dict["variable_names"].append("Elevation (cell centre)") #computed by the viewer itsself from 'top' and 'bot'

        style_group_index = idx[0]  #Same style used for all groups in QGIS 3.16
                                    #FUTURE: Check if this remains

        colorramp = current_layer.rendererSettings(
            ).scalarSettings(style_group_index
            ).colorRampShader(
            ).colorRampItemList()

        self.xml_dict["rgb_point_data"] = self.create_rgb_array(colorramp)

        self.xml_dict["bbox_rectangle"] = self.extent_box.outputExtent()

        n_vars = len(self.xml_dict["variable_names"])

        self.xml_dict["guids_grids"] = [uuid.uuid4() for i in range(n_vars+1)]

    def rgb_components_to_float(self, components):
        return [comp/256 for comp in components]

    def rgb_string(self, c):
        rgb = c.color.red(), c.color.green(), c.color.blue()
        return "{} {} {} {}".format(c.value, *self.rgb_components_to_float(rgb))

    def create_rgb_array(self, colorramp):
        return ' '.join(self.rgb_string(c) for c in colorramp)

    def start_viewer(self):
        self.server.start_server()
        self.server.start_imod()
        self.server.accept_client()

        self.update_viewer()

    def load_model(self):
        """Load model from explorer into the renderer
        """
        command = xml_tree.command_xml(
            xml_tree.model_load_tree,
            **self.xml_dict
        )
        self.server.send(command)

    def unload_model(self):
        """Unload model, removing it from the explorer as well
        """
        command = xml_tree.command_xml(
            xml_tree.model_unload_tree,
            **self.xml_dict
        )
        print(command)
        self.server.send(command)

    def open_file(self):
        """Open file into viewer explorer
        """
        command = xml_tree.command_xml(
            xml_tree.open_file_models_tree, 
            **self.xml_dict
            )
        print(command)
        self.server.send(command)

    def update_viewer(self):
        """Update viewer. 
        First, if created, unload previous model in viewer, also removing it from its explorer.
        Second, update data dictionary.
        Third, open file from a path into viewer explorer.
        Fourth, load model from explorer into renderer.
        """
        if "guids_grids" in self.xml_dict.keys():
            self.unload_model()
        self.update_xml()
        self.open_file()
        self.load_model()