# iMOD-QGIS plugin

## Functionality
The iMOD QGIS plugin provides ways to visualize 4D unstructured subsurface data [time, layer, y, x].

Primary components are:

* An IPF reader to read .IPF files into Qgis, which is a Deltares point format that supports assocciated depth or time data.
* Connecting to the iMOD 3D viewer
* Timeseries visualization
* Cross-section visualization
* Connecting to the NHI data portal, which provides subsurface data for the Netherlands

3D data needs to be provided as an unstructured file readable by MDAL, preferably an UGRID file. 
Currently MDAL does not support the reading of 3D layered unstructured UGRID files.
Therefore, each layer needs to be provided as a seperate variable as "*{varname}*-layer-1".
Here is an example script how to do this with [iMOD-python](https://gitlab.com/deltares/imod/imod-python/-/snippets/2111702).

## Dependencies 
This plugin uses:

* [PyQtGraph 12.2](https://www.pyqtgraph.org/) for graph visualization
* [declxml](https://declxml.readthedocs.io/en/latest/) to create xml files
* [pandas](https://pandas.pydata.org/) to read and process csv files
* OPTIONAL: [iMOD 3D Viewer --insert-link--]() to view unstructured grids in 3D

PyQtGraph and declxml are pure python packages distributed with the plugin,
pandas comes with the QGIS installation 

NOTE: If you installed QGIS with OSGeo4W, make sure pandas is installed as an extra dependency.
See the [installation instructions --insert-link--]()

This package was inspired by the [Crayfish plugin](https://github.com/lutraconsulting/qgis-crayfish-plugin/tree/master/crayfish)

## Documentation
The iMOD documentation can be found [here --insert-link--]()

## License
The iMOD plugin is a product of Deltares, and published under the GPLv2 license.
