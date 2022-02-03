from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsVectorLayer, QgsProject, QgsVectorLayerTemporalProperties
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
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)

        script_dir = Path(__file__).parent
        self.ipfdir = script_dir / ".." / "testdata" / "ipf-timeseries"

        self.ipffile = (self.ipfdir / "timeseries.ipf").resolve()
        self.associated = [txt.resolve() for txt in self.ipfdir.glob("*.txt")]

        self.dialog = ImodIpfDialog()

    def test_add_ipfs(self):
        self.dialog.line_edit.setText(self.ipffile)

        self.dialog.add_ipfs()

        layers = self.canvas.layers

        # Test if added to canvas
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0], QgsVectorLayer)
        self.assertEqual(layers[0], "timeseries")

        # Test if custom properties properly set
        custom_properties = layers[0].customProperties()
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
        path = custom_properties.customProperties().value("ipf_path")
        self.assertTrue(os.path.exists(path))

        # Test temporal properties
        temporal_properties = layers[0].temporalProperties()
        self.assertTrue(temporal_properties.isActive())
        self.assertEqual(temporal_properties.endField(), "datetime_end")
        self.assertEqual(temporal_properties.startField(), "datetime_start")
        self.assertEqual(
            temporal_properties.mode(),
            QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields,
        )

        # Test fields
        fields = layers[0].fields().toList()
        display_names = [f.displayName() for f in fields]
        self.assertEqual(
            display_names, ["x", "y", "id", "datetime_start", "datetime_end"]
        )
        self.assertFalse(fields[0].isDateOrTime())
        self.assertFalse(fields[1].isDateOrTime())
        self.assertFalse(fields[2].isDateOrTime())
        self.assertTrue(fields[3].isDateOrTime())
        self.assertTrue(fields[4].isDateOrTime())


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    # suite.addTests(unittest.makeSuite(TestCaseIpfBorehole))
    suite.addTests(unittest.makeSuite(TestCaseIpfTimeseries))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
