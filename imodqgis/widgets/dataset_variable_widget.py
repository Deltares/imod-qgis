# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Modified from https://github.com/lutraconsulting/qgis-crayfish-plugin/blob/master/crayfish/gui/plot_dataset_groups_widget.py
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QMenu, QToolButton, QWidgetAction


class DatasetVariableMenu(QMenu):

    # emits empty list when "current" is selected
    dataset_variable_changed = pyqtSignal(str)

    def __init__(self, parent=None, datasetType=None):
        QMenu.__init__(self, parent)
        self.variable_options = None
        self.action_current = None
        self.datasetType = datasetType
        self.dataset_variable = None

    def populate_actions(self, variables):
        """
        Populate actions

        Parameters
        ----------
        variables : list
            List with variable names
        """
        self.clear()
        for variable in variables:
            a = self.addAction(variable)
            a.variable_name = variable
            a.setCheckable(True)
            a.triggered.connect(self.triggered_action)

    def triggered_action(self):
        for a in self.actions():
            a.setChecked(a == self.sender())
        self.dataset_variable_changed.emit(self.sender().variable_name)

    def triggered_action_current(self):
        for a in self.actions():
            a.setChecked(a == self.action_current)

    def on_current_dataset_changed(self):
        if self.action_current.isChecked():
            self.dataset_variable_changed.emit()  # re-emit changed signal

    def check_first(self):
        for a in self.actions():
            a.setChecked(True)
            self.dataset_variable_changed.emit(a.variable_name)
            return


class VariablesWidget(QToolButton):
    """
    Allows selection of a single variable.
    """

    dataset_variable_changed = pyqtSignal(str)

    def __init__(self, parent=None, datasetType=None):
        QToolButton.__init__(self, parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.menu_datasets = DatasetVariableMenu(datasetType=datasetType)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.menu_datasets.dataset_variable_changed.connect(
            self.on_dataset_variable_changed
        )
        self.set_dataset_variable(None)

    def on_dataset_variable_changed(self, name):
        self.dataset_variable = name
        if name is None:
            self.setText("Variable: ")
        else:
            self.setText("Variable: " + name)
        self.dataset_variable_changed.emit(name)

    def set_dataset_variable(self, name):
        self.on_dataset_variable_changed(name)

    def set_layer(self, variables):
        self.menu_datasets.populate_actions(variables)
        self.set_dataset_variable(variables[0])


class MultipleVariablesMenu(QMenu):
    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.setContentsMargins(10, 5, 5, 5)
        self.checkboxes = []
        self.variables = []

    def populate_actions(self, variables):
        self.checkboxes = []
        self.variables = []
        self.clear()
        self.check_all = QCheckBox("Select all")
        self.check_all.stateChanged.connect(self.on_check_all)
        self.add_checkbox(self.check_all)
        self.addSeparator()
        for variable in variables:
            checkbox = QCheckBox(variable)
            self.checkboxes.append(checkbox)
            self.add_checkbox(checkbox)
            self.variables.append(variable)

    def add_checkbox(self, checkbox):
        a = QWidgetAction(self)
        a.setDefaultWidget(checkbox)
        self.addAction(a)

    def on_check_all(self):
        state = self.check_all.isChecked()
        for b in self.checkboxes:
            b.setChecked(state)

    def checked_variables(self):
        return [v for v, b in zip(self.variables, self.checkboxes) if b.isChecked()]

    def check_first(self):
        for b in self.checkboxes:
            b.setChecked(True)
            return


class MultipleVariablesWidget(QToolButton):
    """
    Allows selection of multiple variables.
    """

    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.menu_datasets = MultipleVariablesMenu()
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.setText("Selection: ")

    def checked_variables(self):
        return self.menu_datasets.checked_variables()
