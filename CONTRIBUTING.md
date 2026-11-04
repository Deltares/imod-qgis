Useful links 
============

The PyQt5 and PyQgis documentation is quite scattered, and often we have to
resort to reading the C++ API or calling ``dir()``. Here is a list of useful
links which provide some information or examples on how to do things. Below are
some useful links that helped us develop the plugin and its' test bench.

PyQgis
------

* [PyQgis API](https://qgis.org/pyqgis/3.16/)
* [QGIS 3 Cheatsheet](https://github.com/All4Gis/QGIS-cheat-sheet/blob/master/QGIS3.md)

Testing PyQgis
--------------

* [QGIS plugin testing demo](https://github.com/opengisch/qgis_plugins_test_demo)
* [Python tests in QGIS repository](https://github.com/qgis/QGIS/tree/master/tests/src/python)
* [GUI testing PyQt5 with signalspy](https://sharplydescribed.wordpress.com/2020/09/17/gui-qt5-testing-with-python-qsignalspy-qtest/)
* [QTest in QGIS](https://gis.stackexchange.com/questions/250234/qtest-interactions-with-the-qgis-map-canvas)

Running the tests
=================

The plugin supports QGIS 3 (Qt5) and QGIS 4 (Qt6). Use the ``qgis.PyQt``
imports and fully scoped enums (e.g. ``Qt.AlignmentFlag.AlignLeft``) so the
code runs on both.

With [pixi](https://pixi.sh), the tests run against conda-forge QGIS:

```
pixi run test               # QGIS 4
pixi run -e qgis3 test      # QGIS 3
```

CI runs the tests inside the official QGIS docker images, which you can also
do locally (requires docker):

```
pixi run test-docker-qgis3
pixi run test-docker-qgis4
```

Packaging
=========

``pixi run package`` creates ``imodqgis.zip`` from the current ``imodqgis``
folder, which can be installed in QGIS via *Plugins > Manage and Install
Plugins > Install from ZIP*.
