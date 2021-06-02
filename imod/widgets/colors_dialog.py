# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from PyQt5.QtWidgets import (
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QDialog,
)
import numpy as np


PSEUDOCOLOR = 0
UNIQUE_COLOR = 1


class ColorsDialog(QDialog):
    def __init__(
        self, pseudocolor_widget, unique_color_widget, default_to, data, parent
    ):
        QDialog.__init__(self, parent)
        self.pseudocolor_widget = pseudocolor_widget
        self.unique_color_widget = unique_color_widget
        self.data = data

        self.render_type_box = QComboBox()
        self.render_type_box.insertItems(0, ["Pseudocolor", "Unique values"])
        self.render_type_box.setCurrentIndex(default_to)
        self.render_type_box.currentIndexChanged.connect(self.on_render_type_changed)

        # Check if data is a number dtype, if not: only unique coloring works properly
        if not np.issubdtype(data.dtype, np.number):
            self.render_type_box.setCurrentIndex(UNIQUE_COLOR)
            self.render_type_box.setEnabled(False)
        else:
            self.render_type_box.setEnabled(True)

        apply_button = QPushButton("Apply")
        cancel_button = QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Render type:"))
        first_row.addWidget(self.render_type_box)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(apply_button)
        second_row.addWidget(cancel_button)
        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addWidget(self.pseudocolor_widget)
        layout.addWidget(self.unique_color_widget)
        layout.addLayout(second_row)
        self.setLayout(layout)
        self.on_render_type_changed()

    def on_render_type_changed(self):
        if self.render_type_box.currentIndex() == PSEUDOCOLOR:
            self.pseudocolor_widget.setVisible(True)
            self.unique_color_widget.setVisible(False)
            self.pseudocolor_widget.set_data(self.data)
        else:
            self.pseudocolor_widget.setVisible(False)
            self.unique_color_widget.setVisible(True)
            self.unique_color_widget.set_data(self.data)

    def detach(self):
        self.pseudocolor_widget.setParent(self.parent())
        self.unique_color_widget.setParent(self.parent())

    # NOTA BENE: detach() and these overloaded methods are required, otherwise
    # the color_widget is garbage collected when the dialog closes.
    def closeEvent(self, e):
        self.detach()
        QDialog.closeEvent(self, e)

    def reject(self):
        self.detach()
        QDialog.reject(self)

    def accept(self):
        self.detach()
        QDialog.accept(self)
