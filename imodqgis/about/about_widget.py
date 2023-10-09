# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import os

from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
)

path_text = os.path.abspath(os.path.join(os.path.dirname(__file__), "about.md"))

with open(path_text) as file:
    TEXT = file.read()


class ImodAboutDialog(QDialog):
    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("About the iMOD plugin")
        self.iface = iface

        # Set minimum width of Dialog
        self.setMinimumWidth(800)

        self.text = QLabel()

        # Set MarkdownText as TextFormat
        # https://doc.qt.io/qt-5/qt.html#TextFormat-enum
        self.text.setTextFormat(3)

        # Allow hyperlinks to open a browser tab
        self.text.setOpenExternalLinks(True)

        self.text.setText(TEXT)

        layout = QVBoxLayout()
        layout.addWidget(self.text)
        self.setLayout(layout)
