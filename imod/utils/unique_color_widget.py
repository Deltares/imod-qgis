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
    QgsGradientColorRamp,
    QgsColorRampShader,
)
from PyQt5.QtWidgets import QTreeWidget, QWidget

import numpy as np


class ImodUniqueColorShader:
    def __init__(self, values, colors):
        self.color_lookup = {v: c for v, c in zip(values, colors)}
    
    def shade(self, value):
        try:
            return self.color_lookup[value]
        except KeyError:  # e.g. NaN
            return QColor("transparent")


class ImodUniqueColorWidget(QWidget):
    def __init__(self, data: np.ndarray, parent=None):
        QWidget.__init__(self, parent)
        self.data = data

        self.color_ramp_button = QgsColorRampButton()
        self.color_ramp_button.setColorRampFromName("Viridis")
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
        # Finally, fill the table
        self.classify()

    def classify(self) -> None:
        self.table.clear()
        uniques = np.unique(self.data[~np.isnan(self.data)])
        n_class = uniques.size
        ramp = self.color_ramp_button.colorRamp()
        colors = [ramp.color(f) for f in np.linspace(0.0, 1.0, n_class)]
        for value, color in zip(uniques, colors):
            new_item = QgsTreeWidgetItemObject(self.table)
            # Make sure to convert from numpy type to Python type with .item()
            new_item.setData(0, Qt.ItemDataRole.DisplayRole, value.item())
            new_item.setData(1, Qt.ItemDataRole.EditRole, color)
            new_item.setText(2, str(value))
            new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)

    def add_class(self) -> None:
        new_item = QgsTreeWidgetItemObject(self.table)
        new_item.setData(0, Qt.ItemDataRole.DisplayRole, 0)
        new_item.setData(1, Qt.ItemDataRole.EditRole, QColor(Qt.magenta))
        new_item.setText(2, "")
        new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)

    def remove_selection(self) -> None:
        for item in self.table.selectedItems():
            self.table.takeTopLevelItem(self.table.indexOfTopLevelItem(item))

    def load_classes(self) -> None:
        pass

    def save_classes(self) -> None:
        pass

    def shader(self) -> ImodPalettedShader:
        values = []
        colors = []
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            values.append(item.data(0, Qt.ItemDataRole.DisplayRole))
            colors.append(item.data(1, Qt.ItemDataRole.EditRole))
        return ImodPalettedShader(values, colors)
