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

# TODOs: 
#   - Implement current functionality & cleanup old stuff
#   - Add functionality for view iMOD button

class ImodViewerWidget(QWidget):
    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.crs = self.canvas.mapSettings().destinationCrs()

        #Layer selection
        self.layer_selection = QgsMapLayerComboBox()
        self.layer_selection.setFilters(QgsMapLayerProxyModel.MeshLayer)

        #Draw extent button        
        self.extent_button = QPushButton("Draw extent")
        self.extent_button.clicked.connect(self.draw_extent)

        #Extent box
        self.extent_box = self._init_extent_box()
        self.bbox = None #TODO: Get viewextent, use qgis-tim as example
        self.rectangle_tool = RectangleMapTool(self.canvas)
        self.rectangle_tool.rectangleCreated.connect(self.set_bbox)

        #Start viewer button
        self.viewer_button = QPushButton("Plot in iMOD 3D viewer")
        self.viewer_button.clicked.connect(self.start_viewer)

        #Define layout
        first_column = QVBoxLayout()
        first_column.addWidget(self.layer_selection)
        first_column.addWidget(self.extent_button)

        layout = QHBoxLayout() #Create horizontal layout, define stretch factors as 1 - 2 - 1
        layout.addLayout(first_column, 1)
        layout.addWidget(self.extent_box, 2)
        layout.addWidget(self.viewer_button, 1)

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
        print(self.bbox)

    def draw_extent(self):
        print("Please draw extent")
        self.canvas.setMapTool(self.rectangle_tool)

    def write_xml(self, data_path):
        #TODO: Recreate this example:
        #c:\Users\engelen\projects_wdir\iMOD6\test_data\3d_dommel.imod
        pass

    def rgb_components_to_float(self, components):
        return [comp/256 for comp in components]

    def rgb_string(self, c):
        rgb = c.color.red(), c.color.green(), c.color.blue()
        return "{} {} {} {}".format(c.value, *self.rgb_components_to_float(rgb))

    def create_rgb_array(self, colorramp):
        return ' '.join(self.rgb_string(c) for c in colorramp)

    def start_viewer(self):
        current_layer = self.layer_selection.currentLayer()
        path = current_layer.dataProvider().dataSourceUri()

        idx = current_layer.datasetGroupsIndexes()
        group_names = [current_layer.datasetGroupMetadata(QgsMeshDatasetIndex(group=i)).name() for i in idx]

        style_group_index = idx[0]  #Same style used for all groups in QGIS 3.16
                                    #FUTURE: Check if this remains

        colorramp = current_layer.rendererSettings(
            ).scalarSettings(style_group_index
            ).colorRampShader(
            ).colorRampItemList()

        #For debugging
        self.rgb_array = self.create_rgb_array(colorramp)
        self.idx = idx
        self.group_names = group_names

        self.write_xml(path)

        #subprocess.call(imod_exe etc.)