from PyQt5.QtWidgets import QCheckBox

from qgis.utils import plugins
from qgis.testing import unittest
import sys


class TestVariablesWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets import VariablesWidget

        self.widget = VariablesWidget()
        self.names = ["var1", "var2", "var3"]

    def test_set_dataset_variable(self):
        self.widget.set_dataset_variable(self.names[0])
        text = self.widget.text()
        expected_text = "Variable: var1"

        self.assertTrue(text == expected_text)

    def test_set_dataset_variable_empty(self):
        self.widget.set_dataset_variable(None)
        text = self.widget.text()
        expected_text = "Variable: "

        self.assertTrue(text == expected_text)

    def test_menu_populate_actions(self):
        self.widget.menu_datasets.populate_actions(self.names)
        actions = self.widget.menu_datasets.actions()
        names = [a.text() for a in actions]

        self.assertTrue(len(names) == 3)
        self.assertTrue(names == self.names)

    def test_menu_check_first(self):
        self.widget.menu_datasets.populate_actions(self.names)
        self.widget.menu_datasets.check_first()

        actions = self.widget.menu_datasets.actions()
        checkboxes_checked = [action.isChecked() for action in actions]

        expected_checkboxes_checked = [True, False, False]

        self.assertTrue(len(actions) == 3)
        self.assertTrue(checkboxes_checked == expected_checkboxes_checked)

    def test_menu_trigger_action(self):
        self.widget.menu_datasets.populate_actions(self.names)

        # Trigger second action
        self.widget.menu_datasets.actions()[1].trigger()

        actions = self.widget.menu_datasets.actions()

        self.assertTrue(actions[1].isChecked())

        checkboxes_checked = [action.isChecked() for action in actions]
        expected_checkboxes_checked = [False, True, False]

        self.assertTrue(len(actions) == 3)
        self.assertTrue(checkboxes_checked == expected_checkboxes_checked)

    def test_menu_checkbox_exlusivity(self):
        # test if only one checkbox is checked after changing
        self.widget.menu_datasets.populate_actions(self.names)

        # Trigger first action, then trigger second action
        self.widget.menu_datasets.check_first()
        self.widget.menu_datasets.actions()[1].trigger()

        actions = self.widget.menu_datasets.actions()

        checkboxes_checked = [action.isChecked() for action in actions]
        expected_checkboxes_checked = [False, True, False]

        self.assertTrue(len(actions) == 3)
        self.assertTrue(checkboxes_checked == expected_checkboxes_checked)
        self.assertTrue(checkboxes_checked != [True, True, False])


class TestMultipleVariablesWidget(unittest.TestCase):
    def setUp(self):
        imodplugin = plugins["imodqgis"]
        # Required call in order to import widgets
        imodplugin._import_all_submodules()

        from imodqgis.widgets import MultipleVariablesWidget

        self.widget = MultipleVariablesWidget()
        self.names = ["var1", "var2", "var3"]

    def test_menu_populate_actions(self):
        self.widget.menu_datasets.populate_actions(self.names)

        variables = self.widget.menu_datasets.variables
        expected_variables = self.names
        checkboxes = self.widget.menu_datasets.checkboxes

        self.assertTrue(len(variables) == 3)
        self.assertTrue(variables == expected_variables)
        self.assertTrue(len(checkboxes) == 3)

    def test_menu_add_checkbox(self):
        checkbox_name = "Test checkbox"

        checkbox = QCheckBox(checkbox_name)
        self.widget.menu_datasets.add_checkbox(checkbox)
        actions = self.widget.menu_datasets.actions()

        self.assertTrue(len(actions) == 1)

    def test_menu_on_check_all(self):
        self.widget.menu_datasets.populate_actions(self.names)
        # This calls on_layer_changed
        self.widget.menu_datasets.check_all.setChecked(True)

        checkboxes_checked = [
            checkbox.isChecked() for checkbox in self.widget.menu_datasets.checkboxes
        ]

        self.assertTrue(all(checkboxes_checked))

    def test_checked_variables(self):
        self.widget.menu_datasets.populate_actions(self.names)
        self.widget.menu_datasets.check_first()
        checked_variables = self.widget.checked_variables()

        self.assertTrue(len(checked_variables) == 1)
        self.assertTrue(checked_variables[0] == "var1")

    def test_menu_check_first(self):
        self.widget.menu_datasets.populate_actions(self.names)
        self.widget.menu_datasets.check_first()

        checkboxes_checked = [
            checkbox.isChecked() for checkbox in self.widget.menu_datasets.checkboxes
        ]

        # First item is "Check all" box
        expected = [True, False, False]

        self.assertTrue(checkboxes_checked == expected)

    def test_change_text(self):
        # Test for completeness' sake, because text is changed in Timeseries
        # plot.
        text = "Test text"
        self.widget.setText(text)
        self.assertTrue(self.widget.text() == text)


def run_all():
    """
    Default function that is called by the runner if nothing else is specified
    """
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(TestVariablesWidget))
    suite.addTests(unittest.makeSuite(TestMultipleVariablesWidget))
    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(suite)
