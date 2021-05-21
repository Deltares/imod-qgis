import pathlib
from typing import List, Tuple

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QDropEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.GraphicsScene.exportDialog import ExportDialog
from qgis import processing
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsMapLayerType,
    QgsProject,
    QgsRaster,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import (
    QgsColorRampButton,
    QgsMapLayerComboBox,
    QgsRubberBand,
    QgsVertexMarker,
)

from ..ipf import IpfType, read_associated_borehole
from ..utils.layers import get_group_names, groupby_variable
from ..widgets import LineGeometryPickerWidget, MultipleVariablesWidget, VariablesWidget
from .cross_section_data import BoreholeData, MeshData, MeshLineData, RasterLineData

RUBBER_BAND_COLOR = QColor(Qt.black)
BUFFER_RUBBER_BAND_COLOR = QColor(Qt.yellow)
BUFFER_RUBBER_BAND_COLOR.setAlphaF(0.2)


class UpdatingQgsMapLayerComboBox(QgsMapLayerComboBox):
    def enterEvent(self, e):
        self.update_layers()
        super(UpdatingQgsMapLayerComboBox, self).enterEvent(e)

    def update_layers(self):
        # Allow:
        # * Point data with associated IPF borehole data
        # * Mesh layers
        # * Raster layers
        excepted_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if not (
                (layer.type() == QgsMapLayerType.MeshLayer)
                or (layer.type() == QgsMapLayerType.RasterLayer)
                or (layer.customProperty("ipf_type") == IpfType.BOREHOLE.name)
            ):
                excepted_layers.append(layer)
        self.setExceptedLayerList(excepted_layers)


class ColorRampView(QgsColorRampButton):
    """
    By overloading & disabling the mousePressEvent, the ColorRampButton becomes
    a ColorRampView instead.

    A new clicked signal is introduced instead, which is used to open a dialog.
    """

    clicked = pyqtSignal()

    def mousePressEvent(self, _):
        self.clicked.emit()


class StyleTree(QTreeWidget):
    """
    By default, a QTreeWidget does not deal very gracefully with dragging and
    dropping of items to reorder them by hand. QTreeWidget.takeTopLevelItem()
    deletes the widgets (checkboxes, the ColorRampView) when called.

    This class overloads the DropEvent, ensuring the removed item is copied in
    full, including widgets.

    See also:
    https://www.qtcentre.org/threads/40500-QTreeWidget-setItemWidget()-item-disappears-after-moving-item

    This class also automatically configures the desired drag and drop behavior,
    so items can be ordered (only) at the top level.
    """

    def __init__(self, parent=None):
        super(StyleTree, self).__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)

    def dropEvent(self, event):
        # Get the currently selected item and copy it
        item = self.selectedItems()[0]
        new = StyleTreeItem.copy(item)
        destination = self.indexOfTopLevelItem(self.itemAt(event.pos()))
        # Remove the item
        self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        if destination == -1:
            self.addTopLevelItem(new)
        else:
            self.insertTopLevelItem(destination, new)
        new.set_widgets()

    def remove(self):
        item = self.currentItem()
        if item is not None:
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))


class StyleTreeItem(QTreeWidgetItem):
    """
    This holds the items of the styling tree:

    * A checkbox whether the item is displayed
    * Its name
    * Its type: mesh, raster, borehole; and whether drawn as lines
    * A legend checkbox whether its legend is displayed
    * A view on the ColorRamp
    """

    def __init__(self, name, layer_type, section_data):
        super(StyleTreeItem, self).__init__()
        self.show_checkbox = QCheckBox()
        self.legend_checkbox = QCheckBox()
        self.colors_view = ColorRampView()
        self.setText(1, name)
        self.setText(2, layer_type)
        self.show_checkbox.setChecked(True)
        self.legend_checkbox.setChecked(True)
        self.colors_view.setEnabled(False)
        # Do not allow inserting items into these child items
        self.setFlags(self.flags() ^ Qt.ItemIsDropEnabled)
        self.section_data = section_data
        self.update_ramp()
        self.section_data.colors_changed.connect(self.update_ramp)
        self.colors_view.clicked.connect(self.section_data.edit_colors)

    def set_widgets(self):
        """
        A QTreeWidget maintains ownership of the widgets, rather than the item
        itself.
        """
        self.treeWidget().setItemWidget(self, 0, self.show_checkbox)
        self.treeWidget().setItemWidget(self, 3, self.legend_checkbox)
        self.treeWidget().setItemWidget(self, 4, self.colors_view)

    def update_ramp(self):
        self.colors_view.setColorRamp(self.section_data.color_ramp())

    @staticmethod
    def copy(item):
        """
        Because QTreeWidget.takeTopLevelItem() deletes widgets when called (see
        docstring of StyleTree), a copy method is required to ensure all contents
        are copied when moving an item.
        """
        new = StyleTreeItem(
            item.text(1),
            item.text(2),
            item.section_data,
        )
        new.show_checkbox.setChecked(item.show_checkbox.isChecked())
        new.legend_checkbox.setChecked(item.legend_checkbox.isChecked())
        new.colors_view.setEnabled(item.colors_view.isEnabled())
        return new


class ImodCrossSectionWidget(QWidget):
    # TODO: Include time selection box
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface
        self.temporal_controller = self.iface.mapCanvas().temporalController()
        self.temporal_controller.updateTemporalRange.connect(self.plot)
        self.temporal_frame = None

        self.layer_selection = UpdatingQgsMapLayerComboBox()
        self.layer_selection.layerChanged.connect(self.on_layer_changed)
        self.layer_selection.setMinimumWidth(200)

        self.variable_selection = VariablesWidget()
        self.variable_selection.dataset_variable_changed.connect(
            self.set_variable_layernumbers
        )
        self.multi_variable_selection = MultipleVariablesWidget()

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add)
        self.add_button.setMaximumWidth(70)

        self.line_picker = LineGeometryPickerWidget(iface)
        self.line_picker.geometries_changed.connect(self.on_geometries_changed)
        self.line_picker.button.clicked.connect(self.hide_vertex)

        self.as_line_checkbox = QCheckBox("As line(s)")
        self.as_line_checkbox.setMaximumWidth(90)

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.plot)

        self.plot_widget = pg.PlotWidget()
        self.mouse_proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved, rateLimit=25, slot=self.track_mouse
        )
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        self.legend = self.plot_widget.getPlotItem().legend
        self.legend_items = []

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export)
        self.export_dialog = ExportDialog(self.plot_widget.plotItem.scene())

        self.dynamic_resolution_box = QCheckBox("Dynamic resolution")
        self.dynamic_resolution_box.setChecked(True)

        self.resolution_spinbox = QDoubleSpinBox()
        self.resolution_spinbox.setRange(0.01, 10000.0)
        self.resolution_spinbox.setValue(50.0)

        self.buffer_label = QLabel("Search buffer")
        self.buffer_spinbox = QDoubleSpinBox()
        self.buffer_spinbox.setRange(0.0, 10000.0)
        self.buffer_spinbox.setValue(250.0)
        self.buffer_spinbox.valueChanged.connect(self.refresh_buffer)

        self.style_tree = StyleTree()
        self.style_tree.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.style_tree.setColumnCount(5)
        self.style_tree.setHeaderLabels(["", "name", "type", "legend", "symbology"])

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove)

        self.style_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.style_tree.setDragEnabled(True)

        # Selection geometry
        self.rubber_band = None
        self.show_buffer = True
        self.buffer_rubber_band = None
        self.point_rubber_band = QgsVertexMarker(self.iface.mapCanvas())
        self.point_rubber_band.setColor(RUBBER_BAND_COLOR)
        self.point_rubber_band.setIconSize(10)
        self.point_rubber_band.setPenWidth(3)

        # Setup layout
        first_row = QHBoxLayout()
        first_row.addWidget(self.line_picker)
        first_row.addWidget(self.dynamic_resolution_box)
        first_row.addWidget(self.resolution_spinbox)
        first_row.addWidget(self.buffer_label)
        first_row.addWidget(self.buffer_spinbox)
        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.export_button)
        first_row.addStretch()

        layer_selection_row = QHBoxLayout()
        layer_selection_row.addWidget(self.layer_selection)
        layer_selection_row.addWidget(self.variable_selection)
        layer_selection_row.addWidget(self.multi_variable_selection)
        layer_selection_row.addWidget(self.as_line_checkbox)
        layer_selection_row.addWidget(self.add_button)
        layer_column_box = QGroupBox()
        layer_column = QVBoxLayout(layer_column_box)
        layer_column.addLayout(layer_selection_row)
        layer_column.addWidget(self.style_tree)
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.remove_button)
        bottom_row.addStretch()
        layer_column.addLayout(bottom_row)

        plot_column = QHBoxLayout()
        plot_column.addWidget(self.plot_widget)
        plot_box = QGroupBox()
        plot_box.setLayout(plot_column)

        second_row = QSplitter()
        second_row.addWidget(layer_column_box)
        second_row.addWidget(plot_box)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addWidget(second_row)
        self.setLayout(layout)

        # Run a single time initialize the combo boxes
        self.layer_selection.update_layers()
        self.on_layer_changed()

    def hideEvent(self, e):
        self.line_picker.clear_geometries()
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.legend.clear()

    def refresh_buffer(self):
        self.iface.mapCanvas().scene().removeItem(self.buffer_rubber_band)
        if self.show_buffer and len(self.line_picker.geometries) > 0:
            self.buffer_rubber_band = QgsRubberBand(
                self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry
            )
            self.buffer_rubber_band.setColor(BUFFER_RUBBER_BAND_COLOR)
            buffer_distance = self.buffer_spinbox.value()
            self.buffer_rubber_band.setToGeometry(
                self.line_picker.geometries[0].buffer(buffer_distance, 4), None
            )

    def add(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        layer_type = layer.type()
        name = layer.name()

        if layer_type == QgsMapLayerType.MeshLayer:
            variable = self.variable_selection.dataset_variable
            layers = self.multi_variable_selection.checked_variables()
            if self.as_line_checkbox.isChecked():
                data = MeshLineData(layer, self.variables_indexes, variable, layers)
                layer_item = StyleTreeItem(f"{name}: {variable}", "mesh: lines", data)
            else:
                data = MeshData(layer, self.variables_indexes, variable, layers)
                layer_item = StyleTreeItem(f"{name}: {variable}", "mesh", data)
            self.resolution_spinbox.valueChanged.connect(data.clear)
        elif layer_type == QgsMapLayerType.RasterLayer:
            variables = self.multi_variable_selection.checked_variables()
            data = RasterLineData(layer, variables, self.variables_indexes)
            layer_item = StyleTreeItem(f"{name}", "raster: lines", data)
            self.resolution_spinbox.valueChanged.connect(data.clear)
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            variable = self.variable_selection.dataset_variable
            data = BoreholeData(layer, variable)
            layer_item = StyleTreeItem(f"{name}: {variable}", "IPF", data)
            self.buffer_spinbox.valueChanged.connect(data.clear)
        else:
            raise ValueError(
                "Inappropriate layer type: only meshes, rasters, and IPFs are allowed"
            )
        self.style_tree.addTopLevelItem(layer_item)
        layer_item.set_widgets()
        layer_item.show_checkbox.stateChanged.connect(self.plot)
        data.colors_changed.connect(self.plot)
        layer_item.legend_checkbox.stateChanged.connect(self.update_legend)

    def remove(self):
        self.style_tree.remove()

    def plot(self):
        if len(self.line_picker.geometries) == 0:
            return
        self.clear_plot()
        nrow = self.style_tree.topLevelItemCount()

        # Only take temporal data into account of the Temporal Controller is active.
        if self.temporal_controller.navigationMode() != 0:
            frame = self.temporal_controller.currentFrameNumber()
            datetime_range = self.temporal_controller.dateTimeRangeForFrameNumber(frame)
        else:
            datetime_range = None

        load_kwargs = {
            "geometry": self.line_picker.geometries[0],
            "resolution": self.resolution_spinbox.value(),
            "buffer_distance": self.buffer_spinbox.value(),
            "datetime_range": datetime_range,
        }
        for i in range(nrow):
            item = self.style_tree.topLevelItem(i)
            if item.show_checkbox.isChecked():
                data = item.section_data
                if data.requires_loading(datetime_range=datetime_range):
                    data.load(**load_kwargs)
                    if data.x is not None:
                        item.colors_view.setEnabled(True)
                data.plot(self.plot_widget)
        self.update_legend()

    def update_legend(self):
        self.legend.clear()
        nrow = self.style_tree.topLevelItemCount()
        for i in range(nrow):
            item = self.style_tree.topLevelItem(i)
            if item.legend_checkbox.isChecked():
                data = item.section_data
                data.add_to_legend(self.legend)

    def set_variable_names(self):
        layer = self.layer_selection.currentLayer()
        if layer.type() == QgsMapLayerType.MeshLayer:
            indexes, names = get_group_names(layer)
            self.variables_indexes = groupby_variable(names, indexes)
            self.variable_selection.menu_datasets.populate_actions(
                self.variables_indexes.keys()
            )
            self.variable_selection.menu_datasets.check_first()
            self.set_variable_layernumbers()
        elif layer.type() == QgsMapLayerType.RasterLayer:
            variables = []
            self.variables_indexes = {}
            for i in range(1, layer.bandCount() + 1):
                name = layer.bandName(i)
                variables.append(name)
                self.variables_indexes[name] = i
            self.multi_variable_selection.menu_datasets.populate_actions(variables)
            self.multi_variable_selection.menu_datasets.check_first()
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            variables = layer.customProperty("ipf_assoc_columns").split("␞")
            self.variable_selection.set_layer(variables)
            self.variable_selection.menu_datasets.check_first()

    def set_variable_layernumbers(self):
        layer = self.layer_selection.currentLayer()
        if layer.type() != QgsMapLayerType.MeshLayer:
            return
        variable = self.variable_selection.dataset_variable
        layers = [str(a) for a in self.variables_indexes[variable].keys()]
        self.multi_variable_selection.menu_datasets.populate_actions(layers)
        self.multi_variable_selection.menu_datasets.check_all.setChecked(True)

    def on_geometries_changed(self):
        self.iface.mapCanvas().scene().removeItem(self.rubber_band)
        self.iface.mapCanvas().scene().removeItem(self.buffer_rubber_band)
        if len(self.line_picker.geometries) == 0:
            return
        self.rubber_band = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.rubber_band.setColor(RUBBER_BAND_COLOR)
        self.rubber_band.setWidth(2)
        self.rubber_band.setToGeometry(self.line_picker.geometries[0], None)

        if self.show_buffer:
            self.refresh_buffer()

        if self.dynamic_resolution_box.isChecked():
            geometry = self.line_picker.geometries[0]
            resolution = geometry.length() / 300.0
            self.resolution_spinbox.setValue(resolution)

        nrow = self.style_tree.topLevelItemCount()
        for i in range(nrow):
            item = self.style_tree.topLevelItem(i)
            item.section_data.clear()

    def on_layer_changed(self):
        layer = self.layer_selection.currentLayer()
        if layer is None:
            return
        layer_type = layer.type()
        if layer_type == QgsMapLayerType.MeshLayer:
            self.as_line_checkbox.setVisible(True)
            self.as_line_checkbox.setChecked(False)
            self.as_line_checkbox.setEnabled(True)
            self.variable_selection.setVisible(True)
            self.multi_variable_selection.setVisible(True)
        elif layer_type == QgsMapLayerType.RasterLayer:
            self.as_line_checkbox.setVisible(True)
            self.as_line_checkbox.setChecked(True)
            self.as_line_checkbox.setEnabled(False)
            self.variable_selection.setVisible(False)
            self.multi_variable_selection.setVisible(True)
        elif layer.customProperty("ipf_type") == IpfType.BOREHOLE.name:
            self.as_line_checkbox.setVisible(False)
            self.variable_selection.setVisible(True)
            self.multi_variable_selection.setVisible(False)
        self.set_variable_names()
        self.refresh_buffer()

    def track_mouse(self, event):
        if len(self.line_picker.geometries) == 0:
            self.hide_vertex()
            return
        geometry = self.line_picker.geometries[0]
        point_geometry = geometry.interpolate(
            self.plot_widget.plotItem.vb.mapSceneToView(event[0]).x()
        )
        if point_geometry:  # could also be null geometry
            self.point_rubber_band.setCenter(point_geometry.asPoint())
            self.point_rubber_band.show()

    def export(self):
        plot_item = self.plot_widget.plotItem
        self.export_dialog.show(plot_item)

    def hide_vertex(self):
        self.point_rubber_band.hide()

    def on_close(self):
        scene = self.iface.mapCanvas().scene()
        scene.removeItem(self.buffer_rubber_band)
        scene.removeItem(self.point_rubber_band)
        scene.removeItem(self.buffer_rubber_band)
