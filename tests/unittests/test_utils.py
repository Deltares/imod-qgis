import sys
from pathlib import Path, PosixPath

from qgis.core import QgsMeshLayer, QgsProject
from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas
from qgis.testing import unittest
from qgis.utils import plugins


class TestCaseMesh(unittest.TestCase):
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
        assert bridge is not None  # TODO

        script_dir = Path(__file__).parent
        meshfile = (script_dir / ".." / "testdata" / "tri-time-test.nc").resolve()

        self.mesh = QgsMeshLayer(
            str(meshfile),
            "tri-time-test.nc",
            "mdal",
        )
        QgsProject.instance().addMapLayer(self.mesh)


class TestUtilsLayer(TestCaseMesh):
    def setUp(self):
        super().setUp()

        self.expected_indexes = list(range(22))
        self.expected_group_names = [
            "bottom_layer_1",
            "bottom_layer_2",
            "bottom_layer_3",
            "bottom_layer_4",
            "bottom_layer_5",
            "data_layer_1",
            "data_layer_2",
            "data_layer_3",
            "data_layer_4",
            "data_layer_5",
            "face_x",
            "face_y",
            "thickness_layer_1",
            "thickness_layer_2",
            "thickness_layer_3",
            "thickness_layer_4",
            "thickness_layer_5",
            "top_layer_1",
            "top_layer_2",
            "top_layer_3",
            "top_layer_4",
            "top_layer_5",
        ]

        self.expected_variables = ["bottom", "data", "thickness", "top"]
        self.expected_layers = ["layer_1", "layer_2", "layer_3", "layer_4", "layer_5"]

    def test_get_group_names(self):
        from imodqgis.utils.layers import get_group_names

        indexes, group_names = get_group_names(self.mesh)

        self.assertEqual(indexes, self.expected_indexes)
        self.assertEqual(group_names, self.expected_group_names)

    def test_groupby_variable(self):
        from imodqgis.utils.layers import groupby_variable

        gb_var = groupby_variable(self.expected_group_names, self.expected_indexes)

        self.assertEqual(list(gb_var.keys()), self.expected_variables)

        expected_layers = [str(i + 1) for i in range(5)]
        for d in gb_var.values():
            self.assertEqual(list(d.keys()), expected_layers)

    def test_groupby_layers(self):
        from imodqgis.utils.layers import groupby_layer

        gb_lay = groupby_layer(self.expected_group_names)

        self.assertEqual(list(gb_lay.keys()), self.expected_layers)

        for key in self.expected_layers:
            expected_values = [f"{var}_{key}" for var in self.expected_variables]
            self.assertEqual(gb_lay[key], expected_values)

    def test_get_layer_idx(self):
        from imodqgis.utils.layers import get_layer_idx

        layer_indexes = [
            get_layer_idx(layer_name) for layer_name in self.expected_layers
        ]

        expected_layer_indexes = [i + 1 for i in range(5)]

        self.assertEqual(layer_indexes, expected_layer_indexes)


class TestUtilsTemporal(TestCaseMesh):
    def setUp(self):
        super().setUp()

        # (4 variables * 5 layers) + face_x and face_y = 22
        self.expected_is_temporal = ([False] * 5) + ([True] * 5) + ([False] * 12)

    def test_get_group_is_temporal(self):
        from imodqgis.utils.temporal import get_group_is_temporal

        self.assertEqual(get_group_is_temporal(self.mesh), self.expected_is_temporal)

    def test_is_temporal_meshlayer(self):
        from imodqgis.utils.temporal import is_temporal_meshlayer

        self.assertTrue(is_temporal_meshlayer(self.mesh))


class TestUtilsConfigDir(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

    def test_get_configdir(self):
        from imodqgis.utils.pathing import get_configdir

        configdir = get_configdir()

        # We are testing on Linux
        self.assertEquals(type(configdir), PosixPath)
        self.assertEquals(configdir.stem, ".imod-qgis")


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestUtilsLayer))
    suite.addTests(unittest.makeSuite(TestUtilsTemporal))
    suite.addTests(unittest.makeSuite(TestUtilsConfigDir))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
