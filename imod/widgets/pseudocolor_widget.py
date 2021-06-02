# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QGridLayout,
    QTableView,
    QHeaderView,
    QComboBox,
    QPushButton,
    QCheckBox,
    QAbstractItemView,
)
from PyQt5.QtGui import QDoubleValidator, QColor
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

from typing import Dict, Union

import numpy as np

Number = Union[int, float]


SHADER_TYPES = {
    "Discrete": QgsColorRampShader.Discrete,
    "Linear": QgsColorRampShader.Interpolated,
    "Exact": QgsColorRampShader.Exact,
}
CLASSIFICATION_MODE = {
    "Equal interval": QgsColorRampShader.EqualInterval,
    "Continuous": QgsColorRampShader.Continuous,
    "Quantile": QgsColorRampShader.Quantile,
}


def format_number(number, precision):
    return f"{round(number, precision):.{precision}f}"


class ImodPseudoColorWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.data = None 

        # Create widgets
        self.min_edit = QLineEdit()
        self.max_edit = QLineEdit()
        self.min_edit.setValidator(QDoubleValidator())
        self.max_edit.setValidator(QDoubleValidator())
        # Connect widgets
        self.min_edit.textChanged.connect(self.classify)
        self.max_edit.textChanged.connect(self.classify)
        # Add widgets to layout
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Min"))
        first_row.addWidget(self.min_edit)
        first_row.addWidget(QLabel("Max"))
        first_row.addWidget(self.max_edit)

        # Create widgets
        self.interpolation_box = QComboBox()
        self.interpolation_box.addItems(list(SHADER_TYPES.keys()))
        self.color_ramp_button = QgsColorRampButton()
        self.color_ramp_button.setColorRampFromName("Viridis")
        self.color_ramp_button.setMinimumWidth(400)
        self.suffix_edit = QLineEdit()
        self.precision_box = QSpinBox()
        self.precision_box.setValue(2)
        # Connect widgets
        self.interpolation_box.currentTextChanged.connect(self.classify)
        self.color_ramp_button.colorRampChanged.connect(self.classify)
        self.suffix_edit.textChanged.connect(self.format_labels)
        self.precision_box.valueChanged.connect(self.format_labels)
        # Add widgets to layout
        grid = QGridLayout()
        grid.addWidget(QLabel("Interpolation"), 0, 0)
        grid.addWidget(self.interpolation_box, 0, 1)
        grid.addWidget(QLabel("Color ramp"), 1, 0)
        grid.addWidget(self.color_ramp_button, 1, 1, Qt.AlignRight)
        grid.addWidget(QLabel("Label unit suffix"), 2, 0)
        grid.addWidget(self.suffix_edit, 2, 1)
        grid.addWidget(QLabel("Label precision"), 3, 0)
        grid.addWidget(self.precision_box, 3, 1)

        self.table = QTreeWidget()
        self.table.setColumnCount(3)
        self.table.setHeaderLabels(["Value", "Color", "Label"])
        self.table.setItemDelegateForColumn(1, QgsColorSwatchDelegate())
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Create widgets
        self.classification_box = QComboBox()
        self.classification_box.addItems(list(CLASSIFICATION_MODE.keys()))
        self.n_classes_box = QSpinBox()
        self.n_classes_box.setValue(5)
        self.n_classes_box.setValue(5)
        # Connect widgets
        self.classification_box.currentTextChanged.connect(self.classify)
        self.n_classes_box.valueChanged.connect(self.classify)
        # Add widgets to layout
        second_row = QHBoxLayout()
        second_row.addWidget(QLabel("Mode"))
        second_row.addWidget(self.classification_box)
        second_row.addStretch()
        second_row.addWidget(QLabel("Classes"))
        second_row.addWidget(self.n_classes_box)

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
        third_row = QHBoxLayout()
        third_row.addWidget(self.classify_button)
        third_row.addWidget(self.add_class_button)
        third_row.addWidget(self.remove_selection_button)
        third_row.addWidget(self.load_classes_button)
        third_row.addWidget(self.save_classes_button)
        third_row.addStretch()

        fourth_row = QHBoxLayout()
        self.clip_checkbox = QCheckBox()
        fourth_row.addWidget(self.clip_checkbox)
        fourth_row.addWidget(QLabel("Clip out of range values"))
        fourth_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(grid)
        layout.addWidget(self.table)
        layout.addLayout(second_row)
        layout.addLayout(third_row)
        layout.addLayout(fourth_row)
        self.setLayout(layout)

    def set_data(self, data: np.ndarray):
        self.data = data
        self.min_edit.setText(str(np.nanmin(data)))
        self.max_edit.setText(str(np.nanmax(data)))
        self.classify()

    def minimum(self):
        min_text = self.min_edit.text()
        if min_text not in ("", "-"):
            return float(min_text)
        else:
            return np.nanmin(self.data)

    def maximum(self):
        max_text = self.max_edit.text()
        if max_text not in ("", "-"):
            return float(max_text)
        else:
            return np.nanmax(self.data)

    def classify(self) -> None:
        self.table.clear()
        shader_mode = CLASSIFICATION_MODE[self.classification_box.currentText()]
        shader_type = SHADER_TYPES[self.interpolation_box.currentText()]

        ramp = self.color_ramp_button.colorRamp()
        n_class = self.n_classes_box.value()
        if shader_mode == QgsColorRampShader.Quantile:
            if shader_type == QgsColorRampShader.Discrete:
                percentile_values = np.linspace(0, 100, n_class + 1)[1:]
            else:
                percentile_values = np.linspace(0, 100, n_class)
            boundaries = np.nanpercentile(self.data, percentile_values)
        else:
            if shader_mode == QgsColorRampShader.Continuous:
                n_class = ramp.count()
            if shader_type == QgsColorRampShader.Discrete:
                boundaries = np.linspace(self.minimum(), self.maximum(), n_class + 1)[1:]
            else:
                boundaries = np.linspace(self.minimum(), self.maximum(), n_class)

        colors = [ramp.color(f) for f in np.linspace(0.0, 1.0, n_class)]
        for boundary, color in zip(boundaries, colors):
            new_item = QgsTreeWidgetItemObject(self.table)
            new_item.setData(0, Qt.ItemDataRole.DisplayRole, float(boundary))
            new_item.setData(1, Qt.ItemDataRole.EditRole, color)
            new_item.setText(2, "")
            new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
            new_item.itemEdited.connect(self.item_edited)
        self.format_labels()

    def format_labels(self):
        shader_type = SHADER_TYPES[self.interpolation_box.currentText()]
        precision = self.precision_box.value()
        suffix = self.suffix_edit.text()

        nrow = self.table.topLevelItemCount()
        if shader_type == QgsColorRampShader.Discrete:
            item = self.table.topLevelItem(0)
            start = format_number(item.data(0, Qt.ItemDataRole.DisplayRole), precision)
            item.setText(2, f"<= {start}{suffix}")
            for i in range(1, nrow - 1):
                item = self.table.topLevelItem(i)
                end = format_number(item.data(0, Qt.ItemDataRole.DisplayRole), precision)
                item.setText(2, f"{start} - {end}{suffix}")
                start = end
            item = self.table.topLevelItem(nrow - 1)
            item.setText(2, f"> {start}{suffix}")
        else:
            for i in range(nrow):
                item = self.table.topLevelItem(i)
                value = format_number(item.data(0, Qt.ItemDataRole.DisplayRole), precision)
                item.setText(2, f"{value}{suffix}")

    def item_edited(self, item, column):
        if column == 0:
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
            self.format_labels()

    def add_class(self):
        new_item = QgsTreeWidgetItemObject(self.table)
        new_item.setData(0, Qt.ItemDataRole.DisplayRole, 0.0)
        new_item.setData(1, Qt.ItemDataRole.EditRole, QColor(Qt.magenta))
        new_item.setText(2, "")
        new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        new_item.itemEdited.connect(self.item_edited)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def remove_selection(self):
        for item in self.table.selectedItems():
            self.table.takeTopLevelItem(self.table.indexOfTopLevelItem(item))

    def load_classes(self):
        pass

    def save_classes(self):
        pass

    def labels(self) -> Dict[str, str]:
        label_dict = {}
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            value = item.data(0, Qt.ItemDataRole.DisplayRole)
            label = item.text(2)
            label_dict[value] = label
        return label_dict

    def colors(self) -> Dict[Number, QColor]:
        color_dict = {}
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            value = item.data(0, Qt.ItemDataRole.DisplayRole)
            color = item.data(1, Qt.ItemDataRole.EditRole)
            color_dict[value] = color
        return color_dict

    def shader(self) -> QgsColorRampShader:
        shader_type = SHADER_TYPES[self.interpolation_box.currentText()]
        shader_mode = CLASSIFICATION_MODE[self.classification_box.currentText()]
        color_ramp_items = []
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            value = float(item.data(0, Qt.ItemDataRole.DisplayRole))
            color = item.data(1, Qt.ItemDataRole.EditRole)
            color_ramp_items.append(QgsColorRampShader.ColorRampItem(value, color))
        shader = QgsColorRampShader(0.0, 255.0, None, shader_type, shader_mode)
        shader.setColorRampItemList(color_ramp_items)
        shader.setClip(self.clip_checkbox.checkState())
        return shader
