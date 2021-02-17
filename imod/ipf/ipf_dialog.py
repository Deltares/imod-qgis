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
    QgsPointXY,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsField,
    QgsVectorLayerTemporalProperties,
)
import pandas as pd

from .reading import read_ipf, sniff_timeseries_window


# There's only a few dtypes that pandas read_csv will return
QT_DATATYPES = {
    "object": QVariant.String,
    "int32": QVariant.Int,
    "int64": QVariant.Int,
    "float32": QVariant.Double,
    "float64": QVariant.Double,
}


def parse_date(s: str) -> QDateTime:
    if len(s) == 8:
        return QDateTime.fromString(s, "yyyyMMdd")
    elif len(s) == 14:
        return QDateTime.fromString(s, "yyyyMMddhhmmss")
    else:
        raise ValueError(f"Cannot convert date: {s}")
        # TODO: Warn user via UserCommunication class


def attribute_table_columns(dataframe: pd.DataFrame) -> List[QgsField]:
    columns = []
    for column, dtype in dataframe.dtypes.items():
        if column not in ("x", "y"):
            columns.append(QgsField(column, QT_DATATYPES[str(dtype)]))
    columns.append(QgsField("datetime_start", QVariant.DateTime))
    columns.append(QgsField("datetime_end", QVariant.DateTime))
    return columns


def point_features(
    dataframe: pd.DataFrame, parent: pathlib.Path, ext: str
) -> List[QgsFeature]:
    features = []
    for _, row in dataframe.iterrows():
        filename = row["timeseries_id"]
        path_assoc = parent.joinpath(f"{filename}.{ext}")
        datetime_start, datetime_end = sniff_timeseries_window(path_assoc)
        if datetime_start is None or datetime_end is None:
            continue

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row["x"], row["y"])))
        attributes = list(row.iloc[2:])
        attributes.append(parse_date(datetime_start))
        attributes.append(parse_date(datetime_end))
        feature.setAttributes(attributes)
        features.append(feature)

    return features


def add_layer(path: pathlib.Path, ext: str, columns: List[QgsField], features: List[QgsFeature]) -> None:
    point_layer = QgsVectorLayer("Point", path.stem, "memory")
    point_layer.startEditing()
    point_layer.dataProvider().addAttributes(columns)
    point_layer.dataProvider().addFeatures(features)
    point_layer.commitChanges()
    point_layer.setCustomProperty("ipf_type", "timeseries")
    point_layer.setCustomProperty("ipf_assoc_ext", ext)
    point_layer.setCustomProperty("ipf_path", str(path))
    temporal_properties = point_layer.temporalProperties()
    temporal_properties.setStartField("datetime_start")
    temporal_properties.setEndField("datetime_end")
    temporal_properties.setMode(
        QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields
    )
    temporal_properties.setIsActive(True)
    QgsProject.instance().addMapLayer(point_layer)


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
        self.add_button.clicked.connect(self.open_timeseries)
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
        # single file:
        # path, _ = QFileDialog.getOpenFileName(self, "Select file", "", "*.ipf")
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", "", "*.ipf")
        # paths is empty list if cancel is clicked
        if len(paths) == 0:
            return
        else:
            # Surround the paths by double quotes and separate by a space
            self.line_edit.setText(" ".join(f'"{p}"' for p in paths))

    def open_timeseries(self):
        paths = shlex.split(self.line_edit.text())
        for path in paths:
            path = pathlib.Path(path)
            dataframe, ext = read_ipf(path)
            columns = attribute_table_columns(dataframe)
            features = point_features(dataframe, path.parent, ext)
            add_layer(path, ext, columns, features)
