# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#

import itertools
import os
import platform
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMapLayerType,
    QgsMeshDatasetIndex,
    QgsProject,
)
from qgis.gui import (
    QgsExtentGroupBox,
    QgsFileWidget,
    QgsMapLayerComboBox,
    QgsMessageBar,
)

from imodqgis.ipf import IpfType
from imodqgis.utils.layers import groupby_variable
from imodqgis.utils.pathing import get_configdir
from imodqgis.viewer import xml_tree
from imodqgis.viewer.server import Server
from imodqgis.widgets import MultipleLineGeometryPickerWidget, RectangleMapTool

VIEWER_NOT_FOUND_ERROR = (
    "Cannot find the iMOD 3D viewer, please specify by clicking the 'Options' button."
)

VIEWER_NOT_FOUND_MESSAGE = "Cannot find the iMOD 3D viewer, make sure you have installed it and specify its path here."


def get_programdir():
    if platform.system() == "Windows":
        programdir = os.environ["PROGRAMFILES"]
    else:
        programdir = os.environ["HOME"]
    return programdir


@dataclass
class MeshViewerData:
    path: str = None
    group_names: List[str] = None
    variable_names: List[str] = None
    rgb_point_data: str = None
    bbox_rectangle: tuple = None
    guids_grids: List[str] = None
    legend_guid: str = None

    def open(self, server):
        c = xml_tree.command_xml(xml_tree.open_file_models_tree, **asdict(self))
        server.send(c)

    def load(self, server):
        c = xml_tree.command_xml(xml_tree.model_load_tree, **asdict(self))
        server.send(c)

    def unload(self, server):
        c = xml_tree.command_xml(xml_tree.model_unload_tree, **asdict(self))
        server.send(c)

    def set_legend(self, server):
        c = xml_tree.command_xml(xml_tree.set_legend_tree, **asdict(self))
        server.send(c)


@dataclass
class FenceViewerData:
    path: str = None
    group_names: List[str] = None
    variable_names: List[str] = None
    rgb_point_data: str = None
    bbox_rectangle: tuple = None
    guids_grids: List[str] = None
    legend_guid: str = None
    polylines: List[str] = None

    def open(self, server):
        c = xml_tree.command_xml(xml_tree.create_fence_diagram_tree, **asdict(self))
        server.send(c)

    def load(self, server):
        # Fence data does not need to be loaded with a command,
        # because the CreateFenceDiagram command automatically loads.
        pass

    def unload(self, server):
        c = xml_tree.command_xml(xml_tree.model_unload_tree, **asdict(self))
        server.send(c)

    def set_legend(self, server):
        c = xml_tree.command_xml(xml_tree.set_legend_tree, **asdict(self))
        server.send(c)


@dataclass
class BoreholeViewerData:
    path: str = None
    name: str = None
    guids_grids: List[str] = None
    column_mapping: dict = None

    def open(self, server):
        c = xml_tree.command_xml(xml_tree.add_borelogs_tree, **asdict(self))
        server.send(c)

    def load(self, server):
        c = xml_tree.command_xml(xml_tree.model_load_tree, **asdict(self))
        server.send(c)

    def unload(self, server):
        c = xml_tree.command_xml(xml_tree.model_unload_tree, **asdict(self))
        server.send(c)


class UpdatingQgsMapLayerComboBox(QgsMapLayerComboBox):
    def __init__(self, mapLayers):
        super(UpdatingQgsMapLayerComboBox, self).__init__()
        self.mapLayers = mapLayers

    def enterEvent(self, e):
        self.update_layers()
        super(UpdatingQgsMapLayerComboBox, self).enterEvent(e)

    def update_layers(self):
        # Allow:
        # * Point data with associated IPF borehole data
        # * Mesh layers
        excepted_layers = []
        for layer in self.mapLayers().values():
            if not (
                (layer.type() == QgsMapLayerType.MeshLayer)
                or (layer.customProperty("ipf_type") == IpfType.BOREHOLE.name)
            ):
                excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ImodViewerExeSelectionWidget(QDialog):
    def __init__(self, parent, initial_path=None, push_warning=False):
        QDialog.__init__(self, parent)

        # Set internal states
        self.viewer_exe = None
        self.push_warning = push_warning

        # Create message bar
        self.messagebar = QgsMessageBar()
        self.messagebar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        exe_selection_label = QLabel("3D viewer .exe")

        # Create QgsFileWidget
        self.exe_selection_widget = QgsFileWidget(
            parent=self,
            filter="*.exe",
        )
        defaultdir = self.get_defaultdir()
        self.exe_selection_widget.setDefaultRoot(defaultdir)
        self.exe_selection_widget.setDialogTitle("Select iMOD 3D viewer .exe")

        if initial_path is not None:
            self.exe_selection_widget.setFilePath(str(initial_path))

        # Create simple OK/Cancel button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Layout things
        layout = QVBoxLayout()

        ## Prepare row with .exe selection
        exe_selection_row = QHBoxLayout()
        exe_selection_row.addWidget(exe_selection_label)
        exe_selection_row.addWidget(self.exe_selection_widget)

        ## Fill in layout
        layout.addWidget(self.messagebar)
        layout.addLayout(exe_selection_row)
        layout.addWidget(button_box)
        self.setLayout(layout)
        self.setWindowTitle("Options")

        if self.push_warning:
            self.messagebar.pushMessage(
                "Warning", VIEWER_NOT_FOUND_MESSAGE, level=Qgis.Warning
            )

    def accept(self):
        path = self.exe_selection_widget.filePath()
        if path != "":
            self.viewer_exe = Path(path)
        return QDialog.accept(self)

    def get_defaultdir(self):
        return get_programdir()


class ImodViewerWidget(QWidget):
    def __init__(self, canvas, parent=None):
        QWidget.__init__(self, parent)

        self.canvas = canvas
        self.crs = self.canvas.mapSettings().destinationCrs()
        self.server = Server()
        self.project = QgsProject.instance()

        # Layer selection
        self.layer_selection = UpdatingQgsMapLayerComboBox(self.project.mapLayers)

        # Draw fence diagram button
        self.line_picker = MultipleLineGeometryPickerWidget(canvas)
        self.line_picker.draw_button.clicked.connect(self.unset_rectangle_tool)

        # Draw extent button
        # TODO: Create seperate widget for extent_button, so that the right click button can be used to unset geometry
        self.extent_button = QPushButton("Draw extent")
        self.extent_button.clicked.connect(self.draw_extent)
        self.rectangle_tool = RectangleMapTool(self.canvas)
        self.rectangle_tool.rectangleCreated.connect(self.set_bbox)

        # Extent box
        self.extent_box = self._init_extent_box()
        self.bbox = None

        # Start viewer button
        self.viewer_button = QPushButton("Start iMOD 3D viewer")
        self.viewer_button.clicked.connect(self.start_viewer)
        self.viewer_exe = self.find_viewer_exe()

        self.update_button = QPushButton("Load mesh data")
        self.update_button.clicked.connect(self.update_viewer)

        self.fence_button = QPushButton("Load fence diagram")
        self.fence_button.clicked.connect(self.load_fence_diagram)

        self.legend_button = QPushButton("Load legend")
        self.legend_button.clicked.connect(self.load_legend)

        self.options_button = QToolButton()
        self.options_button.setAutoRaise(True)
        self.options_button.setToolTip("Options")
        self.options_button.setIcon(QgsApplication.getThemeIcon("/mActionOptions.svg"))
        self.options_button.clicked.connect(self.on_options_clicked)

        # Define layout
        layout = QVBoxLayout()
        top_row = QHBoxLayout()
        top_row.addWidget(self.layer_selection)
        top_row.addWidget(self.options_button)

        layout.addLayout(top_row)
        layout.addWidget(self.extent_box)

        select_group = QGroupBox("Select")
        first_column = QVBoxLayout()
        self.line_picker.add_to_layout(first_column)
        first_column.addWidget(self.extent_button)
        # Dummy label, causes buttons to align nicely
        first_column.addWidget(QLabel())
        select_group.setLayout(first_column)

        view_group = QGroupBox("View")
        second_column = QVBoxLayout()
        second_column.addWidget(self.viewer_button)
        second_column.addWidget(self.update_button)
        second_column.addWidget(self.fence_button)
        second_column.addWidget(self.legend_button)
        view_group.setLayout(second_column)

        button_groups = QHBoxLayout()
        button_groups.addWidget(select_group)
        button_groups.addWidget(view_group)
        layout.addLayout(button_groups)
        layout.addStretch()

        self.setLayout(layout)

        # Initiate data for xml commands
        self.mesh_data = MeshViewerData()
        self.fence_data = FenceViewerData()
        self.borehole_data = BoreholeViewerData()

    def _init_extent_box(self):
        extent_box = QgsExtentGroupBox()

        extent_box.setOriginalExtent(
            self.canvas.extent(), self.canvas.mapSettings().destinationCrs()
        )
        extent_box.setCurrentExtent(
            self.canvas.extent(), self.crs  # TODO: Set based on layer crs
        )
        extent_box.setOutputCrs(self.crs)

        return extent_box

    def unset_rectangle_tool(self):
        self.canvas.unsetMapTool(self.rectangle_tool)

    def hideEvent(self, e):
        """Ensure rubberbands are removed and picking tools are unset when hiding widget."""
        self.rectangle_tool.reset()
        self.unset_rectangle_tool()

        self.line_picker.stop_picking()
        self.line_picker.clear_rubber_bands()

        QWidget.hideEvent(self, e)

    def find_viewer_exe(self):
        """
        Check if viewer executable can be found,
        First looks if a path was previously saved in viewer_exe.txt, in the Appdata folder
        If not an existing path here, use the default path provided by the installer.
        Else return None (and a warning will be thrown later)
        """
        configdir = get_configdir()
        viewer_textfile = configdir / "viewer_exe.txt"

        # FUTURE: Default viewer path now purely for Windows.
        # No iMOD 3D viewer can be compiled for Linux yet
        default_viewer_exe = (
            Path(get_programdir()) / "Deltares" / "iMOD Viewer" / "IMOD6.exe"
        )

        # Old viewer exe location, still left in here as some people might still have
        # this old version installed.
        # FUTURE: Remove for release 2022.02
        old_viewer_exe = Path(get_programdir()) / "Deltares" / "IMOD6 GUI" / "IMOD6.exe"

        if viewer_textfile.exists():
            with open(configdir / "viewer_exe.txt") as f:
                viewer_textfile_exe = Path(f.read().strip())
            viewer_textfile_exe_exists = viewer_textfile_exe.exists()
        else:
            viewer_textfile_exe_exists = False

        # First check whether some working viewer exe is saved in the textfile.
        if viewer_textfile_exe_exists:
            return viewer_textfile_exe
        # Second check whether the default Deltares path exists
        elif default_viewer_exe.exists():
            return default_viewer_exe
        elif old_viewer_exe.exists():
            return old_viewer_exe
        # Else return None
        else:
            return None

    def save_viewer_exe_path(self):
        """
        Save viewer exe path in textfile in the configdir,
        so that these settings are saved.
        """

        if self.viewer_exe is not None:
            configdir = get_configdir()
            with open(configdir / "viewer_exe.txt", "w") as f:
                f.write(str(self.viewer_exe))

    def set_viewer_exe(self, initial_path=None, push_warning=False):
        selection_widget = ImodViewerExeSelectionWidget(
            self, initial_path=initial_path, push_warning=push_warning
        )

        selection_widget.setMinimumSize(800, 200)
        selection_widget.exec()

        if selection_widget.viewer_exe is not None:
            self.viewer_exe = selection_widget.viewer_exe

        self.save_viewer_exe_path()

    def on_options_clicked(self):
        self.set_viewer_exe(initial_path=self.viewer_exe)

    def set_bbox(self):
        self.bbox = self.rectangle_tool.rectangle()

        self.extent_box.setOutputExtentFromUser(self.bbox, self.crs)

    def draw_extent(self):
        """TODO: check if native draw extent function is better option
        https://qgis.org/api/classQgsExtentGroupBox.html#ac213324b4796e579303693b375de41ca"""
        self.canvas.setMapTool(self.rectangle_tool)
        # Ensure line picker also internally knows it is not picking at the moment.
        self.line_picker.pick_mode = self.line_picker.PICK_NO

    def path_from_vector_uri(self, uri):
        """Extract path from vector uri

        The Vector URI has the following shape for .ipfs:
        'file:///C:/path.ipf?encoding=UTF-8&delimiter=,&type=csv&xField=field_1&yField=field_2&skipLines=9&useHeader=no&trimFields=yes&geomType=point'
        """
        return uri.split("?")[0].split("file:///")[-1]

    def update_borehole_data(self):
        """Update data for xml command to render boreholes"""
        current_layer = self.layer_selection.currentLayer()
        uri = current_layer.dataProvider().dataSourceUri()
        path = self.path_from_vector_uri(uri)
        self.borehole_data.path = path
        self.borehole_data.name = "boreholes_from_qgis"

        self.borehole_data.guids_grids = [uuid.uuid4()]

        columnmapping = {}
        columnmapping["X"] = current_layer.fields().toList()[0].alias()
        columnmapping["Y"] = current_layer.fields().toList()[1].alias()
        # Hardcoded commands to tell the viewer to use the first column
        # of the associated file to plot tops and bottoms.
        columnmapping["Z0"] = "tops 1dBoreholes"
        columnmapping["Z1"] = "bottoms 1dBoreholes"
        # Explicitly tell the viewer to ignore the labels
        columnmapping["Label"] = "*Not Set*"

        self.borehole_data.column_mapping = columnmapping

    def update_mesh_data(self):
        self.mesh_data = MeshViewerData(**self._collect_data_mesh())

    def _transform_linestrings(self, linestrings):
        """Reproject list of linestrings from project crs to layer crs"""
        layer_crs = self.layer_selection.currentLayer().crs()
        viewer_transform = QgsCoordinateTransform(
            self.project.crs(), layer_crs, self.project
        )

        # By providing the QgsGeometry constructor with a QgsGeometry object,
        # a deepcopy is performed on linestring
        # We do this, because QgsGeometry.transform performs an inplace transformation.
        # This is problematic, as transforms would repeatedly be performed each time
        # "Load fence diagram" is pressed
        linestrings_transformed = [
            QgsGeometry(linestring) for linestring in linestrings
        ]

        for linestring in linestrings_transformed:
            # Transform does nothing if no layer crs is set
            linestring.transform(viewer_transform)

        return linestrings_transformed

    def _transform_bbox(self, bbox):
        """Reproject bbox from project crs to layer crs"""
        layer_crs = self.layer_selection.currentLayer().crs()
        viewer_transform = QgsCoordinateTransform(
            self.project.crs(), layer_crs, self.project
        )
        # Returns original bbox if no layer crs is set
        return viewer_transform.transformBoundingBox(bbox)

    def update_fence_data(self):
        # Data nearly equal to mesh data (except different guids that will be assigned)
        d = self._collect_data_mesh()

        linestrings_transformed = self._transform_linestrings(
            self.line_picker.geometries
        )

        # Add polylines
        d["polylines"] = []
        for linestring in linestrings_transformed:
            xyz_points = [
                (int(p.x()), int(p.y()), 0) for p in linestring.asPolyline()
            ]  # TODO: Integer required??
            d["polylines"].append(itertools.chain(*xyz_points))

        self.fence_data = FenceViewerData(**d)

    def _collect_data_mesh(self):
        """Collect data for xml command to render meshes."""
        d = {}
        current_layer = self.layer_selection.currentLayer()
        d["path"] = current_layer.dataProvider().dataSourceUri()

        idx = current_layer.datasetGroupsIndexes()
        d["group_names"] = [
            current_layer.datasetGroupMetadata(QgsMeshDatasetIndex(group=i)).name()
            for i in idx
        ]

        d["variable_names"] = list(groupby_variable(d["group_names"], idx).keys())
        d["variable_names"].append(
            "Elevation (cell centre)"
        )  # computed by the viewer itsself from 'top' and 'bot'

        style_group_index = current_layer.rendererSettings().activeScalarDatasetGroup()

        colorramp = (
            current_layer.rendererSettings()
            .scalarSettings(style_group_index)
            .colorRampShader()
            .colorRampItemList()
        )

        d["rgb_point_data"] = self.create_rgb_array(colorramp)

        bbox_rectangle = self._transform_bbox(self.extent_box.outputExtent())
        xmin = str(bbox_rectangle.xMinimum())
        xmax = str(bbox_rectangle.xMaximum())
        ymin = str(bbox_rectangle.yMinimum())
        ymax = str(bbox_rectangle.yMaximum())
        d["bbox_rectangle"] = xmin, xmax, ymin, ymax

        n_vars = len(d["variable_names"])
        d["guids_grids"] = [uuid.uuid4() for i in range(n_vars + 1)]

        style_group_name = current_layer.datasetGroupMetadata(
            QgsMeshDatasetIndex(group=style_group_index)
        ).name()

        d["legend_guid"] = self._get_legend_guid(style_group_name, d)

        return d

    def _get_legend_guid(self, style_group_name, d):
        if "_layer_" in style_group_name:
            style_variable_name = style_group_name.split("_layer_")[0]
            idx_guid = (
                d["variable_names"].index(style_variable_name) + 1
            )  # Add one because first guid is the LayeredGrid itsself
            return d["guids_grids"][idx_guid]
        else:
            return None

    def rgb_components_to_float(self, components):
        return [comp / 256 for comp in components]

    def rgb_string(self, c):
        rgb = c.color.red(), c.color.green(), c.color.blue()
        return "{} {} {} {}".format(c.value, *self.rgb_components_to_float(rgb))

    def create_rgb_array(self, colorramp):
        return " ".join(self.rgb_string(c) for c in colorramp)

    def start_viewer(self):
        self.server.start_server()

        # First let user try to configure path to viewer exe
        if self.viewer_exe is None:
            self.set_viewer_exe(push_warning=True)

        # If this failed, raise error
        if (
            self.viewer_exe is None
            or not self.viewer_exe.exists()
            or (self.viewer_exe.suffix != ".exe")
        ):
            raise FileNotFoundError(VIEWER_NOT_FOUND_ERROR)

        self.server.start_viewer(self.viewer_exe)
        self.server.accept_client()

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
            if self.mesh_data.guids_grids is not None:
                self.mesh_data.unload(self.server)
            self.update_mesh_data()
            self.mesh_data.open(self.server)
            self.mesh_data.load(self.server)
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            if self.borehole_data.guids_grids is not None:
                self.borehole_data.unload(self.server)
            self.update_borehole_data()
            self.borehole_data.open(self.server)
            self.borehole_data.load(self.server)
        else:
            raise ValueError(
                "File could not be interpreted as borelog ipf or Qgs.MeshLayer"
            )

    def fence_diagram_is_active(self):
        return len(self.line_picker.geometries) > 0

    def load_fence_diagram(self):
        if self.fence_data.guids_grids is not None:
            self.fence_data.unload(self.server)

        if self.fence_diagram_is_active():
            self.update_fence_data()
            self.fence_data.open(self.server)

    def load_legend(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        layer_type = layer.type()

        if layer_type == QgsMapLayerType.MeshLayer:
            if self.mesh_data.legend_guid is not None:
                self.mesh_data.set_legend(self.server)

        if self.fence_diagram_is_active():
            if self.fence_data.legend_guid is not None:
                self.fence_data.set_legend(self.server)
