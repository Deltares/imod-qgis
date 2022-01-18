from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsMeshLayer, QgsProject, QgsPointXY

import numpy as np

from pathlib import Path


import pandas as pd

import sys


class TestTimeseries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Toggle timeseries
        # The toggle_timeseries() method also imports the timeseries
        # module, and thus is a requirement to test the timeseries module.
        imodplugin = plugins["imodqgis"]
        imodplugin.toggle_timeseries()

        cls.widget = imodplugin.timeseries_widget

        script_dir = Path(__file__).parent
        meshfile = (script_dir / ".." / "testdata" / "tri-time-test.nc").resolve()

        cls.mesh = QgsMeshLayer(
            str(meshfile),
            "tri-time-test.nc",
            "mdal",
        )
        QgsProject.instance().addMapLayer(cls.mesh)

        # datasetValue() requires cached mesh,
        # so we have to call this method to cache the mesh
        cls.mesh.updateTriangularMesh()

    def test_timeseries_x_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_x_data

        group_nr = 5  # variable named "data_layer_1" is fifth group in dataset

        times = timeseries_x_data(self.mesh, group_nr)

        to_match = pd.DatetimeIndex(
            ["2018-01-01", "2018-01-02", "2018-01-03", "2018-01-04", "2018-01-05"],
            dtype="datetime64[ns]",
            freq=None,
        )

        self.assertTrue(len(times) == 5)
        self.assertTrue(times.equals(to_match))

    def test_timeseries_y_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_y_data

        geom = QgsPointXY(43.67054079696396229, 49.67836812144211933)
        group_nr = 5  # variable named "data_layer_1" is fifth group in dataset
        n_timesteps = 5

        data = timeseries_y_data(self.mesh, geom, group_nr, n_timesteps)
        print(data)

        to_match = np.array(
            [0.45458985, 1.41937719, 1.77983244, 1.95104218, 2.86607693]
        )

        matches = np.all(np.isclose(data, to_match))

        self.assertTrue(len(data) == n_timesteps)
        self.assertTrue(matches)


def run_all():
    """Default function that is called by the runner if nothing else is specified"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestTimeseries, "test_timeseries_x_data"))
    suite.addTests(unittest.makeSuite(TestTimeseries, "test_timeseries_y_data"))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
