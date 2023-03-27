# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import pathlib
import shlex
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import List

import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import QgsProject, QgsVectorLayer

from ..utils.pathing import get_configdir
from .reading import CptGefFile


def read_gef(paths) -> QgsVectorLayer:
    filenames = [pathlib.Path(path).stem for path in paths]
    x = []
    y = []
    label = []
    gefdata = []
    for path in paths:
        try:
            gef = CptGefFile(path)
        except Exception as e:
            raise type(e)(f"Error reading file: {path}: {e}")
        x.append(gef.x)
        y.append(gef.y)
        label.append(gef.nr)
        gefdata.append(gef)

    header_dataframe = pd.DataFrame(
        {"x": x, "y": y, "label": label, "filenames": filenames}
    )

    fp = get_configdir() / "gef_header.csv"

    # with NamedTemporaryFile(delete=False) as fp:
    header_dataframe.to_csv(fp)
    temppath = pathlib.Path(fp)

    uri = "&".join(
        (
            f"file:///{temppath.as_posix()}?encoding=UTF-8",
            "delimiter=,",
            "type=csv",
            "xField=x",
            "yField=y",
            "useHeader=yes",
            "trimFields=yes",
            "geomType=point",
        )
    )

    layer = QgsVectorLayer(uri, "GEF-CPT", "delimitedtext")
    layer.setCustomProperty("gef_type", "cpt")
    layer.setCustomProperty("gef_path", paths[0])

    # TODO: See if storing all gef paths is necessary?
    # NOTE: Present approach goes wrong in select_geometry method in cross_section_data
    # layer.setCustomProperty("gef_paths", "␞".join(paths))

    # Gef index column can be hardcoded as we always take the same info from
    # the header into the attribute table
    layer.setCustomProperty("gef_indexcolumn", 4)
    # Gef file does not have associated file, instead vertical information
    # stored in geffile itsself.
    layer.setCustomProperty("gef_assoc_ext", "gef")

    return layer


class ImodGefDialog(QDialog):
    def __init__(self, parent=None) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle("Open GEF")
        self.label = QLabel("GEF File(s)")
        self.line_edit = QLineEdit()
        self.line_edit.setMinimumWidth(250)
        self.dialog_button = QPushButton("...")
        self.dialog_button.clicked.connect(self.file_dialog)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_gefs)
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
