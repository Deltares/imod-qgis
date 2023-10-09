# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox


class UserCommunication:
    """Class for communication with user"""

    def __init__(self, iface, context):
        self.iface = iface
        self.context = context

    def show_info(self, msg):
        QMessageBox.information(self.iface.mainWindow(), self.context, msg)

    def show_warn(self, msg):
        QMessageBox.warning(self.iface.mainWindow(), self.context, msg)

    def log_info(self, msg):
        QgsMessageLog.logMessage(msg, self.context, QgsMessageLog.INFO)

    def bar_error(self, msg):
        self.iface.messageBar().pushMessage(self.context, msg, level=Qgis.Critical)

    def bar_warn(self, msg, dur=5):
        self.iface.messageBar().pushMessage(
            self.context, msg, level=Qgis.Warning, duration=dur
        )

    def bar_info(self, msg, dur=5):
        self.iface.messageBar().pushMessage(self.context, msg, duration=dur)

    def clear_bar_messages(self):
        self.iface.messageBar().clearWidgets()
