"""Modified from https://github.com/lutraconsulting/qgis-crayfish-plugin/blob/master/crayfish/gui/plot_dataset_groups_widget.py
"""

from PyQt5.QtWidgets import QMenu, QToolButton
from PyQt5.QtCore import Qt, pyqtSignal

class DatasetVariableMenu(QMenu):

    dataset_variables_changed = pyqtSignal(list)  # emits empty list when "current" is selected

    def __init__(self, parent=None, datasetType=None):
        QMenu.__init__(self, parent)

        self.variable_options = None
        self.layer = None
        self.action_current = None
        self.datasetType = datasetType

    def populate_actions(self, variables):
        """
        Populate actions

        Parameters
        ----------
        variables : list
            List with variable names
        """

        self.clear()

        if self.layer is None or self.layer.dataProvider() is None:
            return

        self.action_current = self.addAction("[current]")
        self.action_current.setCheckable(True)
        self.action_current.setChecked(True)
        self.action_current.triggered.connect(self.triggered_action_current)
        self.addSeparator()

        for variable in variables:
            a = self.addAction(variable)
            a.variable_name = variable
            a.setCheckable(True)
            a.triggered.connect(self.triggered_action)

    def triggered_action(self):
        for a in self.actions():
          a.setChecked(a == self.sender())
        self.dataset_variables_changed.emit([self.sender().variable_name])

    def triggered_action_current(self):
        for a in self.actions():
            a.setChecked(a == self.action_current)
        self.dataset_variables_changed.emit([])

    def on_current_dataset_changed(self, index):
        if self.action_current.isChecked():
            self.dataset_variables_changed.emit([])  # re-emit changed signal

    def set_layer(self, layer, variables):

        if layer is self.layer:
            return

        if self.layer is not None:
            self.layer.activeScalarDatasetGroupChanged.disconnect(self.on_current_dataset_changed)
            self.layer.dataChanged.disconnect(self.populate_actions)

        self.layer = layer

        if self.layer is not None:
            self.layer.activeScalarDatasetGroupChanged.connect(self.on_current_dataset_changed)
            self.layer.dataChanged.connect(self.populate_actions)

        self.populate_actions(variables)


class VariablesWidget(QToolButton):

    dataset_variables_changed = pyqtSignal(list)

    def __init__(self, parent=None, datasetType=None):
        QToolButton.__init__(self, parent)

        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        #self.setIcon(QIcon(QPixmap(":/plugins/crayfish/images/icon_contours.png")))

        self.menu_datasets = DatasetVariableMenu(datasetType=datasetType)

        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.menu_datasets.dataset_variable_changed.connect(self.on_dataset_variables_changed)

        self.set_dataset_variables([])

    def on_dataset_variables_changed(self, lst):
        self.dataset_variables = lst
        if len(lst) == 0:
            self.setText("Variable: [current]")
        elif len(lst) == 1:
            self.setText("Variable: " + lst[0])
        self.dataset_variables_changed.emit(lst)

    def set_dataset_variables(self, lst):
        self.on_dataset_variables_changed(lst)

    def set_layer(self, layer, variables):
        self.menu_datasets.set_layer(layer, variables)
        self.set_dataset_variables([])