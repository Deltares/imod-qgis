# iMOD-QGIS plugin
This plugin aids exploring 4D geospatial data and links to the iMOD 3D viewer.
It is part of a larger software suite, named [iMOD Suite](https://deltares.github.io/iMOD-Documentation/index.html). 

Primary components are:

* Timeseries visualization
* Cross-section visualization 
* Connecting to the iMOD 3D viewer
* Reading .IPF files
* Connecting to the NHI Data portal

Mesh data can be used to store data with a time, z, y, 
and x dimension. 
Currently the z-dimension is only scarcely supported by MDAL. 
Therefore, for each vertical layer, 
we require a mesh dataset with the following variables:

* `{var}_layer_{nr}` 
* `top_layer_{nr}`
* `bottom_layer_{nr}` 

To prepare your datasets for the iMOD QGIS plugin, [we advice using this utility
function in iMOD
Python](https://deltares.github.io/imod-python/api/generated/util/imod.util.mdal_compliant_ugrid2d.html#imod.util.mdal_compliant_ugrid2d).
If you'd like to prepare data yourself for the plugin, [follow this
example.](https://deltares.github.io/iMOD-Documentation/tutorial_wq.html#convert-output-data).
We expect to make this less specific in the future.

## Further reading

* [Installation instructions](https://deltares.github.io/iMOD-Documentation/qgis_install.html)

* [User manual](https://deltares.github.io/iMOD-Documentation/qgis_user_manual.html)

* [Known issues](https://deltares.github.io/iMOD-Documentation/qgis_known_issues.html)
