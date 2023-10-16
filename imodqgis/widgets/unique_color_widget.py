# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from typing import Dict, List

import numpy as np
import pandas as pd
import json
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QPushButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsColorBrewerColorRamp,
)
from qgis.gui import (
    QgsColorRampButton,
    QgsColorSwatchDelegate,
    QgsTreeWidgetItemObject,
)


class ImodUniqueColorShader:
    def __init__(self, values, colors):
        self.color_lookup = {v: c.getRgb() for v, c in zip(values, colors)}

    def shade(self, value):
        try:
            return (True, *self.color_lookup[value])
        except KeyError:  # e.g. NaN
            return False, 0, 0, 0, 0


class ImodUniqueColorWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.data = None
        self.loaded_colors = []

        self.color_ramp_button = QgsColorRampButton()
        self.color_ramp_button.setColorRamp(QgsColorBrewerColorRamp("Set1", colors=9))
        self.color_ramp_button.colorRampChanged.connect(self.classify)
        self.color_ramp_button.setMinimumWidth(400)
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Color ramp"))
        first_row.addWidget(self.color_ramp_button, Qt.AlignRight)

        self.table = QTreeWidget()
        self.table.setColumnCount(3)
        self.table.setHeaderLabels(["Value", "Color", "Label"])
        self.table.setItemDelegateForColumn(1, QgsColorSwatchDelegate())
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Create widgets
        self.classify_button = QPushButton("Classify")
        self.add_class_button = QPushButton("+")
        self.remove_selection_button = QPushButton("-")
        self.load_classes_button = QPushButton("Load")
        self.save_classes_button = QPushButton("Save")
        # Connect widgets
        self.classify_button.clicked.connect(self.classify)
        self.add_class_button.clicked.connect(self.add_class)
        self.remove_selection_button.clicked.connect(self.remove_selection)
        self.load_classes_button.clicked.connect(self.load_classes)
        self.save_classes_button.clicked.connect(self.save_classes)
        # Add widgets to layout
        second_row = QHBoxLayout()
        second_row.addWidget(self.classify_button)
        second_row.addWidget(self.add_class_button)
        second_row.addWidget(self.remove_selection_button)
        second_row.addWidget(self.load_classes_button)
        second_row.addWidget(self.save_classes_button)
        second_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addWidget(self.table)
        layout.addLayout(second_row)
        self.setLayout(layout)

    def set_data(self, data: np.ndarray):
        self.data = data
        # Extend list of colors with colors from colorramp button if more data
        # points available than in loaded file.
        ramp_colors = self.get_colors_from_ramp_button()
        n_loaded_colors = len(self.loaded_colors)
        if n_loaded_colors < len(ramp_colors):
            colors = self.loaded_colors + ramp_colors[n_loaded_colors:]
        else:
            colors = self.loaded_colors
        self.set_legend(colors)

    def set_legend(self, colors) -> None:
        uniques = pd.Series(self.data).dropna().unique()
        self.table.clear()
        for value, color in zip(uniques, colors):
            new_item = QgsTreeWidgetItemObject(self.table)
            # Make sure to convert from numpy type to Python type with .item()
            try:
                python_value = value.item()
            except AttributeError:
                python_value = value
            new_item.setData(0, Qt.ItemDataRole.DisplayRole, python_value)
            new_item.setData(1, Qt.ItemDataRole.EditRole, color)
            new_item.setText(2, str(value))
            new_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable
            )

    def _get_tiled_normalized_midpoints(self, n_elements, tilesize):
        """
        Create array with length n_class of rolling normalized midpoint values
        which can be used to to fetch values on unique colors colormap.

        Example
        -------
        >>> self._get_tiled_normalized_midpoints(n_elements=6, tilesize=4)
        array([0.125, 0.375, 0.625, 0.875, 0.125, 0.375)]
        """
        return ((np.arange(n_elements) % tilesize) + 0.5) / tilesize

    def get_colors_from_ramp_button(self) -> List[QColor]:
        uniques = pd.Series(self.data).dropna().unique()
        n_class = uniques.size
        ramp = self.color_ramp_button.colorRamp()
        n_colors = ramp.count()

        values_colors = self._get_tiled_normalized_midpoints(n_class, n_colors)
        return [ramp.color(f) for f in values_colors]

    def classify(self) -> None:
        self.table.clear()
        colors = self.get_colors_from_ramp_button()
        self.set_legend(colors)
        self.loaded_colors = []

    def add_class(self) -> None:
        new_item = QgsTreeWidgetItemObject(self.table)
        new_item.setData(0, Qt.ItemDataRole.DisplayRole, 0)
        new_item.setData(1, Qt.ItemDataRole.EditRole, QColor(Qt.magenta))
        new_item.setText(2, "")
        new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)

    def labels(self) -> Dict[str, str]:
        label_dict = {}
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            value = item.data(0, Qt.ItemDataRole.DisplayRole)
            label = item.text(2)
            label_dict[value] = label
        return label_dict

    def colors(self) -> Dict[str, QColor]:
        color_dict = {}
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            value = item.data(0, Qt.ItemDataRole.DisplayRole)
            color = item.data(1, Qt.ItemDataRole.EditRole)
            color_dict[value] = color
        return color_dict

    def set_color(self, value, color):
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            if value == item.data(0, Qt.ItemDataRole.DisplayRole):
                item.setData(1, Qt.ItemDataRole.EditRole, color)

    def remove_selection(self) -> None:
        for item in self.table.selectedItems():
            self.table.takeTopLevelItem(self.table.indexOfTopLevelItem(item))

    def load_classes(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load colors", "", "*.txt")
        with open(path, "r") as file:
            rgb_values = json.load(file)
        self.loaded_colors = [QColor(*rgb) for rgb in rgb_values]
        table_iter = range(self.table.topLevelItemCount())

        for i, color in zip(table_iter, self.loaded_colors):
            item = self.table.topLevelItem(i)
            item.setData(1, Qt.ItemDataRole.EditRole, color)

    def save_classes(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save colors", "", "*.txt")
        colors = self.colors().values()
        rgb_values = [c.getRgb() for c in colors]

        with open(path, "w") as file:
            file.write(json.dumps(rgb_values))

    def shader(self) -> ImodUniqueColorShader:
        values = []
        colors = []
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            values.append(item.data(0, Qt.ItemDataRole.DisplayRole))
            colors.append(item.data(1, Qt.ItemDataRole.EditRole))
        return ImodUniqueColorShader(values, colors)
