from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QAbstractItemView,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from qgis.gui import (
    QgsColorRampButton,
    QgsColorWidget,
    QgsColorSwatchDelegate,
    QgsTreeWidgetItemObject,
)
from qgis.core import (
    QgsColorBrewerColorRamp,
    QgsGradientColorRamp,
    QgsColorRampShader,
)
from PyQt5.QtWidgets import QTreeWidget, QWidget

import numpy as np
import pandas as pd
from typing import Dict


class ImodUniqueColorShader:
    def __init__(self, values, colors):
        self.color_lookup = {v: c for v, c in zip(values, colors)}
    
    def shade(self, value):
        try:
            return self.color_lookup[value]
        except KeyError:  # e.g. NaN
            return QColor("transparent")


class ImodUniqueColorWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.data = None 

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
        self.classify()

    def classify(self) -> None:
        self.table.clear()
        uniques = pd.Series(self.data).dropna().unique()
        n_class = uniques.size
        ramp = self.color_ramp_button.colorRamp()
        colors = [ramp.color(f) for f in np.linspace(0.0, 1.0, n_class)]
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
            new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)

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

    def set_color(self, value, color):
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            if value == item.data(0, Qt.ItemDataRole.DisplayRole):
                item.setData(1, Qt.ItemDataRole.EditRole, color)

    def remove_selection(self) -> None:
        for item in self.table.selectedItems():
            self.table.takeTopLevelItem(self.table.indexOfTopLevelItem(item))

    def load_classes(self) -> None:
        pass

    def save_classes(self) -> None:
        pass

    def shader(self) -> ImodUniqueColorShader:
        values = []
        colors = []
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            values.append(item.data(0, Qt.ItemDataRole.DisplayRole))
            colors.append(item.data(1, Qt.ItemDataRole.EditRole))
        return ImodUniqueColorShader(values, colors)
