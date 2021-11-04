# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsDockWidget


FLAGS = (
    Qt.CustomizeWindowHint
    | Qt.Window
    | Qt.WindowMinimizeButtonHint
    | Qt.WindowMaximizeButtonHint
    | Qt.WindowCloseButtonHint
)


class ImodDockWidget(QgsDockWidget):
    """
    This gives a minimize and maximize button to a DockWidget when detached.
    """

    def __init__(self, parent=None):
        QgsDockWidget.__init__(self, parent)
        self.topLevelChanged.connect(self.onTopLevelChanged)

    def onTopLevelChanged(self):
        sender = self.sender()
        if sender.isFloating():
            sender.setWindowFlags(FLAGS)
            sender.show()
