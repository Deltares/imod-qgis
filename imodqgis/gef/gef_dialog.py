# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import pathlib
import shlex
from typing import List
from tempfile import TemporaryFile

from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
)
import numpy as np
import pandas as pd

from .reading import CptGefFile


def read_gef(paths) -> QgsVectorLayer:
    paths = [pathlib.Path(path) for path in paths]
    x = []
    y = []
    filenames = []
    label = []
    gefdata = []
    for path in paths:
        gef = CptGefFile(path)
        x.append(gef.x)
        y.append(gef.y)
        filenames.append(path.stem)
        label.append(gef.nr)
        gefdata.append(gef)

    header_dataframe = pd.DataFrame({"x": x, "y": y, "label": label, "filenames": filenames})
    temp_file = TemporaryFile("gefheader.csv", "w")
    with open(temp_file) as f:
        header_dataframe.to_csv(f)
        
    uri = "&".join(
        (
            f"file:///{temp_file.path.as_posix()}?encoding=UTF-8",
            "delimiter=,",
            "type=csv",
            "xField=field_1",
            "yField=field_2",
            "useHeader=yes",
            "trimFields=yes",
            "geomType=point",
        )
    )
    layer = QgsVectorLayer(uri, "GEF-CPT", "delimitedtext")
    layer.setCustomProperty("gef_type", "cpt")
    layer.setCustomProperty("gef_paths", "␞".join(paths))


class ImodGefDialog(QDialog):
    def __init__(self, parent=None) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle("Open IPF")
        self.label = QLabel("GEF File(s)")
        self.line_edit = QLineEdit()
        self.line_edit.setMinimumWidth(250)
        self.dialog_button = QPushButton("...")
        self.dialog_button.clicked.connect(self.file_dialog)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_ipfs)
        self.add_button.clicked.connect(self.accept)
        self.line_edit.textChanged.connect(
            lambda: self.add_button.setEnabled(self.line_edit != "")
        )
        self.add_button.setEnabled(False)
        first_row = QHBoxLayout()
        first_row.addWidget(self.label)
        first_row.addWidget(self.line_edit)
        first_row.addWidget(self.dialog_button)
        second_row = QHBoxLayout()
        second_row.addStretch()
        second_row.addWidget(self.close_button)
        second_row.addWidget(self.add_button)
        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

    def file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", "", "*.gef")
        # paths is empty list if cancel is clicked
        if len(paths) == 0:
            return
        else:
            # Surround the paths by double quotes and separate by a space
            self.line_edit.setText(" ".join(f'"{p}"' for p in paths))

    def add_gefs(self):
        text = self.line_edit.text()
        paths = shlex.split(text, posix="/" in text)
        layer = read_gef(paths)
        QgsProject.instance().addMapLayer(layer)
