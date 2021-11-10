# iMOD-QGIS plugin

## Functionality
The iMOD QGIS plugin provides ways to visualize 4D unstructured subsurface data [time, layer, y, x].

Primary components are:

* An IPF reader to read .IPF files into Qgis, which is a Deltares point format that supports assocciated depth or time data.
* Connecting to the iMOD 3D viewer
* Timeseries visualization
* Cross-section visualization
* Connecting to the NHI data portal, which provides subsurface data for the Netherlands

## Data Requirements
3D data needs to be provided as an unstructured file readable by MDAL, 
preferably an 
[UGRID file](https://ugrid-conventions.github.io/ugrid-conventions/). 

Currently MDAL does not support the reading of 3D layered unstructured UGRID files.

Therefore, for each vertical layer, 
we require a mesh dataset with the following variables:

* `{var}_layer_{nr}` 
* `top_layer_{nr}`
* `bottom_layer_{nr}` 

Here is an example script how to do this with 
[iMOD-python](https://gitlab.com/deltares/imod/imod-python/-/snippets/2111702).

Point data with timeseries or borelogs need to be provided as 
[IPF](https://content.oss.deltares.nl/imod/iMOD_Manual_actual/imod-um-IPF-files.html#autosec-591) file.
The IPF file is a Deltares point format that supports assocciated depth or 
time data.

## Dependencies 
To do 3D viewing, the iMOD 3D Viewer is required,
[for which downloading and installing instructions can be found here](https://deltares.github.io/iMOD-Documentation/viewer_install.html).

This plugin uses:

* [PyQtGraph 12.2](https://www.pyqtgraph.org/) for graph visualization
* [declxml](https://declxml.readthedocs.io/en/latest/) to create xml files
* [pandas](https://pandas.pydata.org/) to read and process csv files

PyQtGraph and declxml are pure python packages distributed with the plugin,
pandas comes with the QGIS installation 

NOTE: If you installed QGIS with OSGeo4W, make sure pandas is installed as an extra dependency.
See the [installation instructions](https://deltares.github.io/iMOD-Documentation/qgis_install.html).

This package was inspired by the [Crayfish plugin](https://github.com/lutraconsulting/qgis-crayfish-plugin/tree/master/crayfish).

## Documentation

* [General iMOD documentation](https://deltares.github.io/iMOD-Documentation/index.html)
* [Plugin Installation Instructions](https://deltares.github.io/iMOD-Documentation/qgis_install.html)
* [Plugin User Manual](https://deltares.github.io/iMOD-Documentation/qgis_index.html)

## License
The iMOD plugin is a product of Deltares, and published under the GPLv2 license.
