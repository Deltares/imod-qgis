from qgis.utils import plugins
from qgis.testing import unittest
from qgis.core import QgsMeshLayer, QgsProject, QgsPointXY
from PyQt5.QtGui import QColor, QPicture, QPainter

import numpy as np

from pathlib import Path
import pandas as pd

import sys

# TODO: Create TestTimeseriesIpf


def get_axis_ticklabels(axis_item):
    """
    Helper function to safely get axis ticklabels, as pyqtgraph does not provide
    one (only on to set one).
    https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/AxisItem.html
    """

    picture = QPicture()
    painter = QPainter(picture)
    specs = axis_item.generateDrawSpecs(painter)

    dateaxis_ticklabels = [spec[2] for spec in specs[2]]
    painter.end()
    return dateaxis_ticklabels


class MockPointPicker:
    def __init__(self, points):
        self.set_geometries(points)

    def clear_geometries(self):
        self.geometries = []

    def set_geometries(self, points):
        self.geometries = points


class TestTimeseriesMesh(unittest.TestCase):
    def setUp(self):
        # setUp is used instead of setUpClas because this setUp is called before
        # each test. This to ensure the tests are isolated.
        # https://stackoverflow.com/questions/23667610/what-is-the-difference-between-setup-and-setupclass-in-python-unittest

        # Toggle timeseries The toggle_timeseries() method also imports the
        # timeseries module, and thus is a requirement to test the timeseries
        # module.
        imodplugin = plugins["imodqgis"]
        imodplugin.toggle_timeseries()

        self.widget = imodplugin.timeseries_widget.widget()

        script_dir = Path(__file__).parent
        meshfile = (script_dir / ".." / "testdata" / "tri-time-test.nc").resolve()

        self.mesh = QgsMeshLayer(
            str(meshfile),
            "tri-time-test.nc",
            "mdal",
        )
        QgsProject.instance().addMapLayer(self.mesh)

        # datasetValue() requires cached mesh, so we have to call this method to
        # cache the mesh
        self.mesh.updateTriangularMesh()

        self.point = QgsPointXY(43.67054079696396229, 49.67836812144211933)
        self.group_nr = 5
        self.n_timesteps = 5

        # Mocked point picker, contains the required "geometries" attribute
        self.widget.point_picker = MockPointPicker([self.point])
        self.widget.load_mesh_data(self.mesh)

        self.expected_datetime_index = pd.DatetimeIndex(
            ["2018-01-01", "2018-01-02", "2018-01-03", "2018-01-04", "2018-01-05"],
            dtype="datetime64[ns]",
            freq=None,
            name="time",
        )
        self.expected_key = "tri-time-test.nc point 1 data"

        self.expected_x_data = np.array(
            [1.5147648e9, 1.5148512e9, 1.5149376e9, 1.5150240e9, 1.5151104e9]
        )
        self.expected_y_data = np.array(
            [0.45458985, 1.41937719, 1.77983244, 1.95104218, 2.86607693]
        )

        self.expected_x_ticklabels_large = [
            "Mon 01",
            "Tue 02",
            "Wed 03",
            "Thu 04",
            "Fri 05",
        ]  # ticklabels on large window
        self.expected_x_ticklabels_small = [
            "Jan",
            "02",
            "03",
            "04",
            "05",
        ]  # ticklabels on small window

    def test_timeseries_x_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_x_data

        times = timeseries_x_data(self.mesh, self.group_nr)

        self.assertTrue(len(times) == 5)
        self.assertTrue(times.equals(self.expected_datetime_index))

    def test_timeseries_y_data(self):
        from imodqgis.timeseries.timeseries_widget import timeseries_y_data

        data = timeseries_y_data(self.mesh, self.point, self.group_nr, self.n_timesteps)

        self.assertTrue(len(data) == self.n_timesteps)
        self.assertTrue(np.all(np.isclose(data, self.expected_y_data)))

    def test_timeseries_load_mesh_data_empty(self):
        self.widget.clear()  # Clear plot
        self.widget.load_mesh_data(self.mesh)

        self.assertTrue(len(self.widget.dataframes) == 0)
        self.assertTrue(self.widget.dataframes == {})

    def test_timeseries_load_mesh_data(self):

        # Clear and add point geometry again to test load_mesh_data in isolation
        self.widget.clear()
        self.widget.point_picker = MockPointPicker([self.point])

        self.widget.load_mesh_data(self.mesh)

        expected_dataframe = pd.DataFrame(
            index=self.expected_datetime_index, data=self.expected_y_data, columns=["1"]
        )

        keys = list(self.widget.dataframes.keys())

        self.assertTrue(len(keys) == 1)
        self.assertTrue(keys == [self.expected_key])

        dataframe = self.widget.dataframes[self.expected_key]

        self.assertTrue(dataframe.columns == ["1"])

        # Because data is float, we have to compensate for floating point errors
        data_match = np.all(np.isclose(expected_dataframe["1"], dataframe["1"]))

        self.assertTrue(data_match)

    def test_on_layer_changed(self):
        self.widget.layer_selection.setLayer(self.mesh)

        checkboxes = self.widget.multi_variable_selection.menu_datasets.checkboxes
        checkboxes_checked = [checkbox.isChecked() for checkbox in checkboxes]
        # By default first checkbox should be checked
        expected_checkboxes_checked = [True, False, False, False, False]

        expected_variables_indexes = {"1": 5, "2": 6, "3": 7, "4": 8, "5": 9}

        self.assertTrue(len(checkboxes) == 5)
        self.assertTrue(checkboxes_checked == expected_checkboxes_checked)
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

    def test_set_variable_layernumbers(self):
        self.widget.set_variable_layernumbers()

        layers = self.widget.multi_variable_selection.menu_datasets.variables
        expected_layers = ["1", "2", "3", "4", "5"]

        self.assertTrue(len(layers) == 5)
        self.assertTrue(layers == expected_layers)

    def test_draw_timeseries(self):
        # Ensure plot is cleared
        self.widget.clear_plot()

        dataframe = pd.DataFrame(
            index=self.expected_datetime_index, data=self.expected_y_data, columns=["1"]
        )

        series = dataframe["1"]
        color = QColor(0, 0, 0, 255)

        self.widget.draw_timeseries(series, color)

        x_data_matches = np.all(
            np.isclose(self.expected_x_data, self.widget.curves[0].xData)
        )
        y_data_matches = np.all(
            np.isclose(self.expected_y_data, self.widget.curves[0].yData)
        )

        axis_item = self.widget.plot_widget.getAxis("bottom")
        ticklabels = get_axis_ticklabels(axis_item)

        correct_ticklabels = (ticklabels == self.expected_x_ticklabels_large) | (
            ticklabels == self.expected_x_ticklabels_small
        )

        self.assertTrue(len(self.widget.curves) == 1)
        self.assertTrue(x_data_matches)
        self.assertTrue(y_data_matches)
        self.assertTrue(correct_ticklabels)

    def test_draw_plot(self):
        self.widget.draw_plot()

        x_data_matches = np.all(
            np.isclose(self.expected_x_data, self.widget.curves[0].xData)
        )
        y_data_matches = np.all(
            np.isclose(self.expected_y_data, self.widget.curves[0].yData)
        )

        axis_item = self.widget.plot_widget.getAxis("bottom")
        ticklabels = get_axis_ticklabels(axis_item)

        correct_ticklabels = (ticklabels == self.expected_x_ticklabels_large) | (
            ticklabels == self.expected_x_ticklabels_small
        )

        self.assertTrue(len(self.widget.curves) == 1)
        self.assertTrue(x_data_matches)
        self.assertTrue(y_data_matches)
        self.assertTrue(correct_ticklabels)


def run_all():
    """Default function that is called by the runner if nothing else is specified"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestTimeseriesMesh))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
