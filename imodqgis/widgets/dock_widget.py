# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import Qt

FLAGS = (
    Qt.WindowType.CustomizeWindowHint
    | Qt.WindowType.Window
    | Qt.WindowType.WindowMinimizeButtonHint
    | Qt.WindowType.WindowMaximizeButtonHint
    | Qt.WindowType.WindowCloseButtonHint
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
