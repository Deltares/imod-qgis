import csv
import pathlib
import shlex
from typing import List

from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)
from PyQt5.QtCore import QDateTime, QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsField,
    QgsVectorLayerTemporalProperties,
    qgsfunction,
    QgsExpression,
)
import numpy as np
import pandas as pd

from .reading import read_ipf_header, read_associated_header, IpfType


@qgsfunction(args="auto", group="Custom", usesGeometry=False)
def ipf_datetime_start(indexcol, ext, pathparent, feature, parent):
    filename = feature.attribute(indexcol)
    path = f"{pathparent}/{filename}.{ext}"
    with open(path) as f:
        f.readline()  # nrow
        line = f.readline()
        try:
            # csv.reader parse one line
            # this catches commas in quotes
            ncol, itype = map(int, map(str.strip, next(csv.reader([line]))))
        # itype can be implicit, in which case it's a timeseries
        except ValueError:
            ncol = int(line.strip())
            itype = 1
        if itype != 1:
            raise ValueError("Not a timeseries IPF")

        # Skip the column names, jump to the start of the data
        for _ in range(ncol):
            f.readline()
        line = f.readline()

    datetime = line.split(",")[0].strip()
    length = len(datetime)
    if length == 14:
        return QDateTime.fromString(datetime, "yyyyMMddhhmmss")
    elif length == 8:
        return QDateTime.fromString(datetime, "yyyyMMdd")
    else:
        raise ValueError(f"{path}: datetime format must be yyyymmddhhmmss or yyyymmdd")


@qgsfunction(args="auto", group="Custom", usesGeometry=False)
def ipf_datetime_end(indexcol, ext, pathparent, feature, parent):
    filename = feature.attribute(indexcol)
    path = f"{pathparent}/{filename}.{ext}"
    with open(path, "rb") as f:
        f.seek(-2, 2)
        while f.read(1) != b"\n":
            f.seek(-2, 1)
        line = f.read().decode("utf-8")
    datetime = line.split(",")[0].strip()
    length = len(datetime)
    if length == 14:
        return QDateTime.fromString(datetime, "yyyyMMddhhmmss")
    elif length == 8:
        return QDateTime.fromString(datetime, "yyyyMMdd")
    else:
        raise ValueError(f"{path}: datetime format must be yyyymmddhhmmss or yyyymmdd")


def set_timeseries_windows(
    layer: QgsVectorLayer,
    indexcol: int,
    ext: str,
    pathparent: str,
) -> None:
    QgsExpression.registerFunction(ipf_datetime_start)
    QgsExpression.registerFunction(ipf_datetime_end)
    # DO NOT USE DOUBLE QUOTES INSIDE THE EXPRESSION
    layer.addExpressionField(
        f"ipf_datetime_start({indexcol}, '{ext}', '{pathparent}')",
        (QgsField("datetime_start", QVariant.DateTime)),
    )
    layer.addExpressionField(
        f"ipf_datetime_end({indexcol}, '{ext}', '{pathparent}')",
        (QgsField("datetime_end", QVariant.DateTime)),
    )
    # Set the temporal properties
    temporal_properties = layer.temporalProperties()
    temporal_properties.setStartField("datetime_start")
    temporal_properties.setEndField("datetime_end")
    temporal_properties.setMode(
        QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields
    )
    temporal_properties.setIsActive(True)


def read_ipf(path: str) -> QgsVectorLayer:
    path = pathlib.Path(path)
    _, ncol, colnames, indexcol, ext = read_ipf_header(path)

    skip_lines = 2 + ncol + 1
    # See: https://qgis.org/pyqgis/master/core/QgsVectorLayer.html
    uri = "&".join(
        [
            f"file:///{str(path.as_posix())}?encoding=UTF-8",
            "delimiter=,",
            "type=csv",
            "xField=field_1",
            "yField=field_2",
            f"skipLines={skip_lines}",
            "useHeader=no",
            "trimFields=yes",
            "geomType=point",
        ]
    )
    layer = QgsVectorLayer(uri, path.stem, "delimitedtext")
    # Set column names
    for i, name in enumerate(colnames):
        layer.setFieldAlias(i, name)

    if indexcol >= 2:  # x:0, y:1
        assoc_columns = set()
        for feature in layer.getFeatures():
            filename = feature.attribute(indexcol)
            assoc_path = path.parent.joinpath(f"{filename}.{ext}")
            with open(assoc_path) as f:
                ipf_type, _, _, colnames, _ = read_associated_header(f)
            # Skip the first column, it's always depth or datetime
            assoc_columns.update(colnames[1:])

        if ipf_type == IpfType.TIMESERIES:
            set_timeseries_windows(layer, indexcol, ext, path.parent.as_posix())

        layer.setCustomProperty("ipf_type", ipf_type.name)
        layer.setCustomProperty("ipf_indexcolumn", indexcol)
        layer.setCustomProperty("ipf_assoc_ext", ext)
        layer.setCustomProperty("ipf_path", str(path))
        # use an ASCII record separator: ␞
        layer.setCustomProperty("ipf_assoc_columns", "␞".join(assoc_columns))

    return layer


class ImodIpfDialog(QDialog):
    def __init__(self, parent=None) -> None:
        QDialog.__init__(self, parent)
        self.setWindowTitle("Open IPF")
        self.label = QLabel("iMOD Point File(s)")
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
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", "", "*.ipf")
        # paths is empty list if cancel is clicked
        if len(paths) == 0:
            return
        else:
            # Surround the paths by double quotes and separate by a space
            self.line_edit.setText(" ".join(f'"{p}"' for p in paths))

    def add_ipfs(self):
        text = self.line_edit.text()
        paths = shlex.split(text, posix="/" in text)
        for path in paths:
            layer = read_ipf(path)
            QgsProject.instance().addMapLayer(layer)
