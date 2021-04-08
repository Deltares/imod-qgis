from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
)


from qgis.gui import QgsExtentGroupBox, QgsMapLayerComboBox
from qgis.core import (
    QgsProject,
    QgsMapLayerProxyModel, 
    QgsMeshDatasetIndex, 
    QgsMapLayerType,
)

from ..widgets import RectangleMapTool, MultipleLineGeometryPickerWidget
from . import xml_tree
from .server import Server
from ..utils.layers import groupby_variable
import itertools

from ..ipf import IpfType

import uuid

class UpdatingQgsMapLayerComboBox(QgsMapLayerComboBox):
    def enterEvent(self, e):
        self.update_layers()
        super(UpdatingQgsMapLayerComboBox, self).enterEvent(e)
    
    def update_layers(self):
        # Allow:
        # * Point data with associated IPF borehole data
        # * Mesh layers
        excepted_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if not (
                (layer.type() == QgsMapLayerType.MeshLayer) or
                (layer.customProperty("ipf_type") == IpfType.BOREHOLE.name)
            ):
                excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ImodViewerWidget(QWidget):
    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.crs = self.canvas.mapSettings().destinationCrs()
        self.server = Server()

        #Layer selection
        self.layer_selection = UpdatingQgsMapLayerComboBox()

        #Draw fence diagram button
        self.line_picker = MultipleLineGeometryPickerWidget(canvas)

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
        self.viewer_button = QPushButton("Start iMOD 3D viewer")
        self.viewer_button.clicked.connect(self.start_viewer)

        self.update_button = QPushButton("Update 3D plot")
        self.update_button.clicked.connect(self.update_viewer)

        self.fence_buttion = QPushButton("Load fence diagram")
        self.fence_buttion.clicked.connect(self.load_fence_diagram)

        #Define layout
        first_column = QVBoxLayout()
        first_column.addWidget(self.layer_selection)
        first_column.addWidget(self.line_picker)
        first_column.addWidget(self.extent_button)

        third_column = QVBoxLayout()
        third_column.addWidget(self.viewer_button)
        third_column.addWidget(self.update_button)
        third_column.addWidget(self.fence_buttion)

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

    def on_close(self):
        """Ensure rubberbands are removed and picking tools are unset when hiding widget.
        """

        self.rectangle_tool.reset()
        self.canvas.unsetMapTool(self.rectangle_tool)

        self.line_picker.stop_picking()
        self.line_picker.clear_rubber_bands()

    def set_bbox(self):
        self.bbox = self.rectangle_tool.rectangle()

        self.extent_box.setOutputExtentFromUser(self.bbox, self.crs)

    def draw_extent(self):
        """TODO: check if native draw extent function is better option
        https://qgis.org/api/classQgsExtentGroupBox.html#ac213324b4796e579303693b375de41ca"""
        print("Please draw extent")
        self.canvas.setMapTool(self.rectangle_tool)

    def path_from_vector_uri(self, uri):
        """Extract path from vector uri

        The Vector URI has the following shape for .ipfs:
        'file:///C:/path.ipf?encoding=UTF-8&delimiter=,&type=csv&xField=field_1&yField=field_2&skipLines=9&useHeader=no&trimFields=yes&geomType=point'
        """
        return uri.split("?")[0].split("file:///")[-1]

    def update_data_borehole(self):
        """Update data for xml command to render boreholes
        """
        self.xml_dict = {}

        current_layer = self.layer_selection.currentLayer()
        uri = current_layer.dataProvider().dataSourceUri()
        path = self.path_from_vector_uri(uri)
        self.xml_dict["path"] = path
        self.xml_dict["name"] = "test"

        self.xml_dict["guids_grids"] = [uuid.uuid4()]

        columnmapping = {}
        columnmapping["X"] = current_layer.fields().toList()[0].alias()
        columnmapping["Y"] = current_layer.fields().toList()[1].alias()

        self.xml_dict["column_mapping"] = columnmapping

    def update_data_mesh(self):
        """Update data for xml command to render meshes.
        """
        self.xml_dict = {}

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
        self.server.send(command)

    def open_mesh_file(self):
        """Open file into viewer explorer
        """
        command = xml_tree.command_xml(
            xml_tree.open_file_models_tree, 
            **self.xml_dict
            )
        self.server.send(command)

    def open_borelogs(self):
        command = xml_tree.command_xml(
            xml_tree.add_borelogs_tree,
            **self.xml_dict
        )
        self.server.send(command)

    def update_viewer(self):
        """Update viewer. 
        First, if created, unload previous model in viewer, also removing it from its explorer.
        Second, update data dictionary.
        Third, open file from a path into viewer explorer.
        Fourth, load model from explorer into renderer.
        """

        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        layer_type = layer.type()
        
        if layer_type == QgsMapLayerType.MeshLayer:
            if "guids_grids" in self.xml_dict.keys():
                self.unload_model()
            self.update_data_mesh()
            self.open_mesh_file()
            self.load_model()
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            self.update_data_borehole()
            self.open_borelogs()
        else:
            raise ValueError("File could not be interpreted as borelog ipf or Qgs.MeshLayer")

    def fence_diagram_is_active(self):
        return len(self.line_picker.geometries) > 0

    def prepare_fence_diagram(self):
        self.xml_dict["polylines"] = []
        for linestring in self.line_picker.geometries:
            xyz_points = [(int(p.x()), int(p.y()), 0) for p in linestring.asPolyline()] #TODO: Integer required??
            self.xml_dict["polylines"].append(itertools.chain(*xyz_points))

    def create_fence_diagram(self):
        """Open file into viewer explorer
        """
        command = xml_tree.command_xml(
            xml_tree.create_fence_diagram_tree, 
            **self.xml_dict
            )
        self.server.send(command)

    def load_fence_diagram(self):
        if self.fence_diagram_is_active():
            self.prepare_fence_diagram()
            self.create_fence_diagram()