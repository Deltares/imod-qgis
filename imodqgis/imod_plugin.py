# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Import the code for the DockWidget
from pathlib import Path

from .dependencies import pyqtgraph_0_12_3 as pg

from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .ipf import ImodIpfDialog
from .widgets import ImodDockWidget

# Set plot background color
pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")
pg.setConfigOption("antialias", True)


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
        self.netcdf_manager = None
        self.plugin_dir = Path(__file__).parent
        self.pluginIsActive = False
        self.toolbar = iface.addToolBar(u"iMOD")
        self.toolbar.setObjectName(u"iMOD")

    def add_action(self, icon_name, text="", callback=None, add_to_toolbar=False):
        icon = QIcon(str(self.plugin_dir / "icons" / icon_name))
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        return action

    def initGui(self):
        self.action_about_dialog = self.add_action(
            "iMOD.svg", "About", self.about_dialog, True
        )

        self.action_ipf_dialog = self.add_action(
            "ipf-reader.svg", "Open IPF", self.ipf_dialog, True
        )
        self.action_viewer = self.add_action(
            "3d-viewer.svg", "3D Viewer", self.toggle_viewer, True
        )
        self.action_timeseries = self.add_action(
            "time-series.svg", "Time Series", self.toggle_timeseries, True
        )
        self.action_cross_section = self.add_action(
            "cross-section.svg", "Cross section", self.toggle_cross_section, True
        )
        # self.action_netcdf_manager = self.add_action(
        #    "iMOD.svg", "NetCDF Manager", self.toggle_netcdf_manager, False
        # )
        self.action_nhi_data = self.add_action(
            "NHI-portal.svg", "Add NHI Data", self.nhi_data_dialog, True
        )

    def about_dialog(self):
        from .about import ImodAboutDialog

        dialog = ImodAboutDialog(self.iface)
        dialog.show()
        dialog.exec_()

    def ipf_dialog(self):
        dialog = ImodIpfDialog()
        dialog.show()
        dialog.exec_()

    def nhi_data_dialog(self):
        from .nhi_data import ImodNhiDataDialog

        dialog = ImodNhiDataDialog(self.iface)
        dialog.show()
        dialog.exec_()

    # Note, normally one would be able to simply hide a widget, and make it
    # visible again. However, due to a Qt Bug:
    # https://bugreports.qt.io/browse/QTBUG-69922
    # This will break the docking behavior. To avoid this, currently toggling
    # simply fully reinitializes the widget.

    def toggle_viewer(self):
        from .viewer import ImodViewerWidget

        canvas = self.iface.mapCanvas()
        self.viewer_widget = QgsDockWidget("iMOD 3D Viewer")
        self.viewer_widget.setObjectName("ImodViewerDock")
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.viewer_widget)
        widget = ImodViewerWidget(canvas, parent=self.viewer_widget)
        self.viewer_widget.setWidget(widget)

    def toggle_timeseries(self):
        from .timeseries import ImodTimeSeriesWidget

        self.timeseries_widget = ImodDockWidget("iMOD Time Series Plot")
        self.timeseries_widget.setObjectName("ImodTimeSeriesDock")
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.timeseries_widget)
        widget = ImodTimeSeriesWidget(self.timeseries_widget, self.iface)
        self.timeseries_widget.setWidget(widget)

    def toggle_cross_section(self):
        from .cross_section import ImodCrossSectionWidget

        self.cross_section_widget = ImodDockWidget("iMOD Cross Section Plot")
        self.cross_section_widget.setObjectName("ImodCrossSectionDock")
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.cross_section_widget)
        widget = ImodCrossSectionWidget(self.cross_section_widget, self.iface)
        self.cross_section_widget.setWidget(widget)

    def toggle_netcdf_manager(self):
        from .netcdf_manager import ImodNetcdfManagerWidget

        self.netcdf_manager = QgsDockWidget("iMOD NetCDF Manager")
        self.netcdf_manager.setObjectName("ImodNetcdfDock")
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.netcdf_manager)
        widget = ImodNetcdfManagerWidget(self.netcdf_manager)
        self.netcdf_manager.setWidget(widget)

    def unload(self):
        del self.toolbar
        # self.toolbar.deleteLater()
