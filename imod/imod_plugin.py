from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.gui import QgsDockWidget
# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .imod_plugin_dockwidget import ImodDockWidget
from pathlib import Path


class ImodPlugin:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.viewer_widget = None
        self.timeseries_widget = None
        self.cross_section_widget = None
        self.action_timeseries = None
        self.action_viewer = None
        self.action_cross_section = None
        self.plugin_dir = Path(__file__).parent
        self.pluginIsActive = False
        self.menu = u"iMOD"
        self.actions = []

    def add_action(self, icon_name, text="", callback=None, add_to_menu=False):
        icon = QIcon(str(self.plugin_dir / icon_name))
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_name = "icon.png"
        self.action_viewer = self.add_action(icon_name, "3D Viewer", self.toggle_viewer, True)
        self.action_timeseries = self.add_action(icon_name, "Time Series", self.toggle_timeseries, True)
        self.action_cross_section = self.add_action(icon_name, "Cross section", self.toggle_cross_section, True)

    def toggle_viewer(self):
        if self.viewer_widget is None:
            from .viewer import ImodViewerWidget
            self.viewer_widget = QgsDockWidget("iMOD 3D Viewer")
            self.viewer_widget.setObjectName("ImodViewerDock")
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.viewer_widget)
            widget = ImodViewerWidget(self.viewer_widget)
            self.viewer_widget.setWidget(widget)
            self.viewer_widget.hide()
        self.viewer_widget.setVisible(not self.viewer_widget.isVisible())

    def toggle_timeseries(self):
        if self.timeseries_widget is None:
            from .timeseries import ImodTimeSeriesWidget
            self.timeseries_widget = QgsDockWidget("iMOD Time Series Plot")
            self.timeseries_widget.setObjectName("ImodTimeSeriesDock")
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.timeseries_widget)
            widget = ImodTimeSeriesWidget(self.timeseries_widget)
            self.timeseries_widget.setWidget(widget)
            self.timeseries_widget.hide()
        self.timeseries_widget.setVisible(not self.timeseries_widget.isVisible())

    def toggle_cross_section(self):
        if self.cross_section_widget is None:
            from .cross_section import ImodCrossSectionWidget
            self.cross_section_widget = QgsDockWidget("iMOD Cross Section Plot")
            self.cross_section_widget.setObjectName("ImodCrossSectionDock")
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.cross_section_widget)
            widget = ImodCrossSectionWidget(self.cross_section_widget)
            self.cross_section_widget.setWidget(widget)
            self.cross_section_widget.hide()
        self.cross_section_widget.setVisible(not self.cross_section_widget.isVisible())
    
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu('iMOD', action) 
