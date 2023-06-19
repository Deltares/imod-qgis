# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from typing import List

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class DimensionSlider(QWidget):
    def __init__(self, dim, values, parent=None):
        QWidget.__init__(self, parent)
        self.values = values  # noqa

        self.first = QPushButton("|<")
        self.first.clicked.connect(self._first)
        self.previous = QPushButton("<")
        self.previous.clicked.connect(self._previous)
        self.next = QPushButton(">")
        self.next.clicked.connect(self._next)
        self.last = QPushButton(">|")
        self.last.clicked.connect(self._last)

        self.dim = dim
        self.maximum = values.size - 1
        self.label = QLineEdit()
        self.label.textEdited.connect(self.validate)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.maximum)

        first_row = QHBoxLayout()
        first_row.addWidget(QLabel(f"{dim}:"))
        first_row.addWidget(self.label)
        first_row.addStretch()

        second_row = QHBoxLayout()
        second_row.addWidget(self.first)
        second_row.addWidget(self.previous)
        second_row.addWidget(self.next)
        second_row.addWidget(self.last)
        second_row.addWidget(self.slider)

        column = QVBoxLayout()
        column.addLayout(first_row)
        column.addLayout(second_row)

        self.setLayout(column)
        self.slider.valueChanged.connect(self.set_value)
        self.slider.setValue(0)

    def validate(self):
        value = int(self.label.text())
        if not np.isin(value, self.values):
            raise ValueError(f"Value {value} does not occur in dimension {self.dim}")

    def set_value(self, i: int):
        self.label.setText(str(self.values[i]))  # noqa

    def _first(self):
        self.slider.setValue(0)

    def _next(self):
        self.slider.setValue(self.slider.value() + 1)

    def _previous(self):
        self.slider.setValue(self.slider.value() - 1)

    def _last(self):
        self.slider.setValue(self.maximum)

    def value(self):
        return self.slider.value()


class DimensionHandler(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.column = QVBoxLayout()
        self.dims = []
        self.sliders = []
        self.setLayout(self.column)

    def populate_sliders(self, dims: List[str], values: List[np.ndarray]):
        # Remove from layout:
        for slider in self.sliders:
            slider.setParent(None)
        self.dims = []
        self.sliders = []
        for dim, dim_values in zip(dims, values):
            self.dims.append(dim)
            slider = DimensionSlider(dim, dim_values)
            self.sliders.append(slider)
            self.column.addWidget(slider)
