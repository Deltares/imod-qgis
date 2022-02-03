from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsVectorLayerTemporalProperties,
    QgsExpression,
    QgsLayerTreeUtils,
)
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
from pathlib import Path, PosixPath
import pandas as pd
import numpy as np
import sys
import os


class TestCaseIpfTimeseries(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.ipf.ipf_dialog import ImodIpfDialog

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        self.bridge = QgsLayerTreeMapCanvasBridge(
            self.project.layerTreeRoot(), self.canvas
        )

        script_dir = Path(__file__).parent
        self.ipfdir = script_dir / ".." / "testdata" / "ipf-timeseries"

        self.ipffile = (self.ipfdir / "timeseries.ipf").resolve()

        self.dialog = ImodIpfDialog()

    def tearDown(self):
        # For some reason canvas is not cleaned up after tearDown,
        # so we have to do it manually.
        layers = self.canvas.layers()
        if len(layers) > 0:
            for layer in layers:
                self.project.removeMapLayer(layer.id())

    def test_add_ipfs(self):
        self.dialog.line_edit.setText(str(self.ipffile))
        self.dialog.add_ipfs()

        # Force update of MapCanvas
        self.bridge.setCanvasLayers()

        layer = self.canvas.layers()[0]

        # Test if added to canvas
        self.assertEqual(len(self.canvas.layers()), 1)
        self.assertEqual(type(layer), QgsVectorLayer)
        self.assertEqual(layer.name(), "timeseries")

        # Test if custom properties properly set
        custom_properties = layer.customProperties()
        expected_keys = [
            "ipf_assoc_columns",
            "ipf_assoc_ext",
            "ipf_indexcolumn",
            "ipf_path",
            "ipf_type",
        ]

        self.assertEqual(custom_properties.keys(), expected_keys)
        self.assertEqual(custom_properties.value("ipf_assoc_columns"), "head")
        self.assertEqual(custom_properties.value("ipf_assoc_ext"), "txt")
        self.assertEqual(custom_properties.value("ipf_type"), "TIMESERIES")
        path = custom_properties.value("ipf_path")
        self.assertTrue(os.path.exists(path))

        # Test temporal properties
        temporal_properties = layer.temporalProperties()
        self.assertTrue(temporal_properties.isActive())
        self.assertEqual(temporal_properties.endField(), "datetime_end")
        self.assertEqual(temporal_properties.startField(), "datetime_start")
        self.assertEqual(
            temporal_properties.mode(),
            QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields,
        )

        # Test fields
        fields = layer.fields().toList()
        display_names = [f.displayName() for f in fields]
        self.assertEqual(
            display_names, ["x", "y", "id", "datetime_start", "datetime_end"]
        )
        self.assertFalse(fields[0].isDateOrTime())
        self.assertFalse(fields[1].isDateOrTime())
        self.assertFalse(fields[2].isDateOrTime())
        self.assertTrue(fields[3].isDateOrTime())
        self.assertTrue(fields[4].isDateOrTime())

        # TODO Find out how to iterate over features, to test them and call the two qgsexpressions on them.

    def test_read_ipfs(self):
        from imodqgis.ipf.ipf_dialog import read_ipf

        layer = read_ipf(self.ipffile)

        self.assertEqual(type(layer), QgsVectorLayer)
        self.assertEqual(layer.name(), "timeseries")

        # Test if custom properties properly set
        custom_properties = layer.customProperties()
        expected_keys = [
            "ipf_assoc_columns",
            "ipf_assoc_ext",
            "ipf_indexcolumn",
            "ipf_path",
            "ipf_type",
        ]

        self.assertEqual(custom_properties.keys(), expected_keys)
        self.assertEqual(custom_properties.value("ipf_assoc_columns"), "head")
        self.assertEqual(custom_properties.value("ipf_assoc_ext"), "txt")
        self.assertEqual(custom_properties.value("ipf_type"), "TIMESERIES")
        path = custom_properties.value("ipf_path")
        self.assertTrue(os.path.exists(path))

        # Test temporal properties
        temporal_properties = layer.temporalProperties()
        self.assertTrue(temporal_properties.isActive())
        self.assertEqual(temporal_properties.endField(), "datetime_end")
        self.assertEqual(temporal_properties.startField(), "datetime_start")
        self.assertEqual(
            temporal_properties.mode(),
            QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields,
        )

    def test_set_timeseries_windows(self):
        from imodqgis.ipf.ipf_dialog import set_timeseries_windows

        skip_lines = 6

        uri = "&".join(
            [
                f"file:///{str(self.ipffile.as_posix())}?encoding=UTF-8",
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
        layer = QgsVectorLayer(uri, self.ipffile.stem, "delimitedtext")

        # Functions are registered during the call of this function
        set_timeseries_windows(layer, 2, "txt", self.ipffile.parent.as_posix())

        # Test if functions properly registered
        QgsExpression().isFunctionName("ipf_datetime_start")
        QgsExpression().isFunctionName("ipf_datetime_end")

        # Test temporal properties
        temporal_properties = layer.temporalProperties()
        self.assertTrue(temporal_properties.isActive())
        self.assertEqual(temporal_properties.endField(), "datetime_end")
        self.assertEqual(temporal_properties.startField(), "datetime_start")
        self.assertEqual(
            temporal_properties.mode(),
            QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields,
        )


class TestCaseIpfBorehole(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.ipf.ipf_dialog import ImodIpfDialog

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        self.bridge = QgsLayerTreeMapCanvasBridge(
            self.project.layerTreeRoot(), self.canvas
        )
        self.bridge.setCanvasLayers()

        script_dir = Path(__file__).parent
        self.ipfdir = script_dir / ".." / "testdata" / "ipf-borehole"

        self.ipffile = (self.ipfdir / "boreholes.ipf").resolve()

        self.dialog = ImodIpfDialog()

    def tearDown(self):
        # For some reason canvas is not cleaned up after tearDown,
        # so we have to do it manually.
        layers = self.canvas.layers()
        if len(layers) > 0:
            for layer in layers:
                self.project.removeMapLayer(layer.id())

    def test_add_ipfs(self):
        self.dialog.line_edit.setText(str(self.ipffile))
        self.dialog.add_ipfs()

        # Force update of MapCanvas
        self.bridge.setCanvasLayers()

        layer = self.canvas.layers()[0]

        # Test if added to canvas
        self.assertEqual(len(self.canvas.layers()), 1)
        self.assertEqual(type(layer), QgsVectorLayer)
        self.assertEqual(layer.name(), "boreholes")

        # Test if custom properties properly set
        custom_properties = layer.customProperties()
        expected_keys = [
            "ipf_assoc_columns",
            "ipf_assoc_ext",
            "ipf_indexcolumn",
            "ipf_path",
            "ipf_type",
        ]

        self.assertEqual(custom_properties.keys(), expected_keys)
        self.assertEqual(custom_properties.value("ipf_assoc_columns"), "lithology")
        self.assertEqual(custom_properties.value("ipf_assoc_ext"), "txt")
        self.assertEqual(custom_properties.value("ipf_type"), "BOREHOLE")
        path = custom_properties.value("ipf_path")
        self.assertTrue(os.path.exists(path))

        # Test temporal properties
        temporal_properties = layer.temporalProperties()
        self.assertFalse(temporal_properties.isActive())

        # Test fields
        fields = layer.fields().toList()
        display_names = [f.displayName() for f in fields]
        self.assertEqual(display_names, ["x", "y", "id"])
        self.assertFalse(fields[0].isDateOrTime())
        self.assertFalse(fields[1].isDateOrTime())
        self.assertFalse(fields[2].isDateOrTime())

        # TODO Find out how to iterate over features, to test them

    def test_read_ipfs(self):
        from imodqgis.ipf.ipf_dialog import read_ipf

        layer = read_ipf(self.ipffile)

        self.assertEqual(type(layer), QgsVectorLayer)
        self.assertEqual(layer.name(), "boreholes")

        # Test if custom properties properly set
        custom_properties = layer.customProperties()
        expected_keys = [
            "ipf_assoc_columns",
            "ipf_assoc_ext",
            "ipf_indexcolumn",
            "ipf_path",
            "ipf_type",
        ]

        self.assertEqual(custom_properties.keys(), expected_keys)
        self.assertEqual(custom_properties.value("ipf_assoc_columns"), "lithology")
        self.assertEqual(custom_properties.value("ipf_assoc_ext"), "txt")
        self.assertEqual(custom_properties.value("ipf_type"), "BOREHOLE")
        path = custom_properties.value("ipf_path")
        self.assertTrue(os.path.exists(path))

        # Test temporal properties
        temporal_properties = layer.temporalProperties()
        self.assertFalse(temporal_properties.isActive())


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestCaseIpfBorehole))
    suite.addTests(unittest.makeSuite(TestCaseIpfTimeseries))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
