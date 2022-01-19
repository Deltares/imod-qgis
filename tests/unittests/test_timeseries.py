from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsMeshLayer, QgsProject, QgsPointXY

import numpy as np

from pathlib import Path


import pandas as pd

import sys


class MockPointPicker:
    def __init__(self, points):
        self.set_geometries(points)

    def clear_geometries(self):
        self.geometries = []

    def set_geometries(self, points):
        self.geometries = points


class TestTimeseriesMesh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # setUpClass is used because this method has to be called once when setting up the instance.
        # If we were to use setUp(), all this code would be called for each test.
        # https://stackoverflow.com/questions/23667610/what-is-the-difference-between-setup-and-setupclass-in-python-unittest

        # Toggle timeseries
        # The toggle_timeseries() method also imports the timeseries
        # module, and thus is a requirement to test the timeseries module.
        imodplugin = plugins["imodqgis"]
        imodplugin.toggle_timeseries()

        cls.widget = imodplugin.timeseries_widget.widget()

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

        cls.point = QgsPointXY(43.67054079696396229, 49.67836812144211933)
        cls.group_nr = 5
        cls.n_timesteps = 5

        cls.expected_datetime_index = pd.DatetimeIndex(
            ["2018-01-01", "2018-01-02", "2018-01-03", "2018-01-04", "2018-01-05"],
            dtype="datetime64[ns]",
            freq=None,
            name="time",
        )
        cls.expected_data = np.array(
            [0.45458985, 1.41937719, 1.77983244, 1.95104218, 2.86607693]
        )

        cls.expected_key = "tri-time-test.nc point 1 data"

    def test_timeseries_x_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_x_data

        times = timeseries_x_data(self.mesh, self.group_nr)

        self.assertTrue(len(times) == 5)
        self.assertTrue(times.equals(self.expected_datetime_index))

    def test_timeseries_y_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_y_data

        data = timeseries_y_data(self.mesh, self.point, self.group_nr, self.n_timesteps)

        self.assertTrue(len(data) == self.n_timesteps)
        self.assertTrue(np.all(np.isclose(data, self.expected_data)))

    def test_timeseries_load_mesh_data_empty(self):
        self.widget.clear()  # Clear plot
        self.widget.load_mesh_data(self.mesh)

        self.assertTrue(len(self.widget.dataframes) == 0)
        self.assertTrue(self.widget.dataframes == {})

    def test_timeseries_load_mesh_data(self):
        # Mocked point picker, contains the required "geometries" attribute
        self.widget.point_picker = MockPointPicker([self.point])

        self.widget.load_mesh_data(self.mesh)

        expected_dataframe = pd.DataFrame(
            index=self.expected_datetime_index, data=self.expected_data, columns=["1"]
        )

        keys = list(self.widget.dataframes.keys())

        self.assertTrue(len(keys) == 1)
        self.assertTrue(keys == [self.expected_key])

        dataframe = self.widget.dataframes[self.expected_key]
        # Because data is float, we have to compensate for floating point errors
        data_match = np.all(np.isclose(expected_dataframe["1"], dataframe["1"]))

        self.assertTrue(dataframe.columns == ["1"])
        self.assertTrue(data_match)

    def test_on_layer_changed(self):
        self.widget.layer_selection.setLayer(self.mesh)

        expected_variables_indexes = {"1": 5, "2": 6, "3": 7, "4": 8, "5": 9}
        self.assertTrue(
            self.widget.variables_indexes["data"] == expected_variables_indexes
        )

    def test_visibility_widgets(self):
        # set layer to ensure on_layer_changed() is called
        self.widget.layer_selection.setLayer(self.mesh)

        self.assertFalse(self.widget.id_label.isVisible())
        self.assertFalse(self.widget.id_selection_box.isVisible())
        self.assertTrue(self.widget.variable_selection.isVisible())
        self.assertTrue(self.widget.multi_variable_selection.isEnabled())
        self.assertTrue(self.widget.multi_variable_selection.text() == "Layers: ")


def run_all():
    """Default function that is called by the runner if nothing else is specified"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestTimeseriesMesh))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
