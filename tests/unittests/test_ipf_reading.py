from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsMeshLayer, QgsProject
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
from pathlib import Path, PosixPath
import pandas as pd
import numpy as np
import sys


class TestCaseIpfBorehole(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        self.project = QgsProject.instance()
        self.canvas = QgsMapCanvas()
        # The bridge makes the link between QgsProject and QgsMapCanvas. So when
        # a layer is added in the project, it is displayed in the map canvas.
        # https://gis.stackexchange.com/a/340563
        bridge = QgsLayerTreeMapCanvasBridge(self.project.layerTreeRoot(), self.canvas)

        script_dir = Path(__file__).parent
        self.ipfdir = script_dir / ".." / "testdata" / "ipf-borehole"

        self.ipffile = (self.ipfdir / "boreholes.ipf").resolve()
        self.associated = [txt.resolve() for txt in self.ipfdir.glob("*.txt")]

    def test_read_ipf_header(self):
        from imodqgis.ipf.reading import read_ipf_header

        nrow, ncol, colnames, indexcol, ext = read_ipf_header(self.ipffile)

        self.assertEqual(nrow, 4)
        self.assertEqual(ncol, 3)
        self.assertEqual(colnames, ["x", "y", "id"])
        self.assertEqual(indexcol, 2)
        self.assertEqual(ext, "txt")

    def test_read_ipf(self):
        from imodqgis.ipf.reading import read_ipf

        df, ext = read_ipf(self.ipffile)

        expected_colnames = np.array(["x", "y", "indexcolumn"], dtype=object)

        self.assertEqual(type(df), pd.DataFrame)
        self.assertTrue(np.all(df.columns.values == expected_colnames))
        self.assertEqual(ext, "txt")

        expected_x = np.array([139354, 146343, 144914, 141419])
        expected_y = np.array([376437, 390891, 386603, 381043])
        expected_indexcolum = np.array(["id_0", "id_1", "id_2", "id_3"])

        self.assertTrue(np.all(df["x"].values == expected_x))
        self.assertTrue(np.all(df["y"].values == expected_y))
        self.assertTrue(np.all(df["indexcolumn"] == expected_indexcolum))

    def test_read_associated_header(self):
        from imodqgis.ipf.reading import read_associated_header

        with open(self.associated[0]) as f:
            itype, nrow, usecols, colnames, na_values = read_associated_header(f)

        expected_nan = {"top": [1e20, "-"], "lithology": [1e20, "-"]}

        self.assertEqual(itype, 2)
        self.assertEqual(nrow, 4)
        self.assertTrue(np.all(usecols == np.array([0, 1])))
        self.assertEqual(colnames, ["top", "lithology"])
        self.assertEqual(na_values, expected_nan)

    def test_read_associated_borehole(self):
        from imodqgis.ipf.reading import read_associated_borehole

        df = read_associated_borehole(self.associated[0])

        expected_top_values = np.array([0.0, -100.0, -200.0, -300.0])
        expected_lithology = np.array(["silt", "sandy loam", "clay", "silty clay"])

        self.assertEqual(list(df.columns), ["top", "lithology"])
        self.assertEqual(df.shape, (4, 2))
        self.assertTrue(np.all(df["top"].values == expected_top_values))
        self.assertTrue(np.all(df["lithology"].values == expected_lithology))

    def test_read_associated_timeseries(self):
        from imodqgis.ipf.reading import read_associated_timeseries

        with self.assertRaises(ValueError):
            read_associated_timeseries(self.associated[0])


class TestCaseIpfTimeseries(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

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

    def test_read_ipf_header(self):
        from imodqgis.ipf.reading import read_ipf_header

        nrow, ncol, colnames, indexcol, ext = read_ipf_header(self.ipffile)

        self.assertEqual(nrow, 3)
        self.assertEqual(ncol, 3)
        self.assertEqual(colnames, ["x", "y", "id"])
        self.assertEqual(indexcol, 2)
        self.assertEqual(ext, "txt")

    def test_read_ipf(self):
        from imodqgis.ipf.reading import read_ipf

        df, ext = read_ipf(self.ipffile)

        expected_colnames = np.array(["x", "y", "indexcolumn"], dtype=object)

        self.assertEqual(type(df), pd.DataFrame)
        self.assertTrue(np.all(df.columns.values == expected_colnames))
        self.assertEqual(ext, "txt")

        expected_x = np.array([92530, 93100, 92840])
        expected_y = np.array([463930, 464580, 463680])
        expected_indexcolum = np.array(["B30F0059001", "B30F0217001", "B30F0222001"])

        self.assertTrue(np.all(df["x"].values == expected_x))
        self.assertTrue(np.all(df["y"].values == expected_y))
        self.assertTrue(np.all(df["indexcolumn"] == expected_indexcolum))

    def test_read_associated_header(self):
        from imodqgis.ipf.reading import read_associated_header

        with open(self.associated[0]) as f:
            itype, nrow, usecols, colnames, na_values = read_associated_header(f)

        expected_nan = {"time": [1e20, "-"], "head": [1e20, "-"]}

        self.assertEqual(itype, 1)
        self.assertEqual(nrow, 95)
        self.assertTrue(np.all(usecols == np.array([0, 1])))
        self.assertEqual(colnames, ["time", "head"])
        self.assertEqual(na_values, expected_nan)

    def test_read_associated_timeseries(self):
        from imodqgis.ipf.reading import read_associated_timeseries

        df = read_associated_timeseries(self.associated[0])

        self.assertEqual(list(df.columns), ["time", "head"])
        self.assertEqual(df.shape, (95, 2))
        self.assertEqual(type(df.index), pd.DatetimeIndex)
        self.assertEqual(df.index.year[0], 1952)
        self.assertEqual(df.index.year[-1], 1977)

        # There is a column named "time", with time as strings, and the index is
        # called "time" as well.
        self.assertEqual(df["time"][0], "19520814000000")
        self.assertEqual(df["time"][-1], "19771214000000")

        self.assertEqual(df["head"][0], -2.1)
        self.assertEqual(df["head"][-1], -1.25)

    def test_read_associated_borehole(self):
        from imodqgis.ipf.reading import read_associated_borehole

        with self.assertRaises(ValueError):
            read_associated_borehole(self.associated[0])


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestCaseIpfBorehole))
    suite.addTests(unittest.makeSuite(TestCaseIpfTimeseries))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
