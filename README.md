# iMOD-QGIS plugin

The iMOD plugin extends QGIS functionalities to assist with groundwater modeling.

Primary components are:

* Connecting to the iMOD 3D viewer
* netCDF manager to deal with non-XY dimensions
* Timeseries visualization
* Cross-section visualization 

## Installation instructions
We currently have not spent time yet on creating an installer, 
so a couple of steps are required to get a working iMOD plugin in QGIS.

### 1. Installing QGIS
You can download the standalone QGIS setup 
[here](https://qgis.org/en/site/forusers/download.html#),
currently we have developed with QGIS 3.16. 
We have not tested with newer versions yet. 
Same holds for older versions, 
but any version prior to QGIS 3.14 will probably fail 
due to recent changes in the Mesh backend.
Run the QGIS setup.

### 2. Installing python dependencies
The iMOD plugin has a couple of dependencies that are currently not
distributed with the plugin.
To install them, follow these steps: 
1. Open the OSGeo4W Shell that is provided with QGIS.
2. Run the command `py3_env`, this will temporarily set the QGIS python installation in your PATH within this shell.
3. Run `pip install pyqtgraph declxml pandas` to install all necessary packages in your QGIS python installation.

[comment]: # (Is this a complete list of all the packages required???)

### 3. Download and copy the iMOD QGIS plugin
Download the iMOD QGIS plugin code from the [Github page](https://github.com/Deltares/imod-qgis) 
(You are probably reading these instructions on this page already).

Unpack the zip files, and copy the `imod` folder to your QGIS plugin directory. 
This is probably located in your Appdata folder.
In windows it is something such as:
`c:\Users\%USER%\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

If you cannot find the folder, follow [these instructions](https://gis.stackexchange.com/a/274312). 

### 4. Optional: Connect to the iMOD 3D viewer
To be able to use the iMOD 3D viewer from the iMOD QGIS plugin, 
you still need to :

1. Download the viewer [here](https://dpcbuild.deltares.nl/project/iMOD6_IModGui?mode=builds). 
It currently is only available to Deltares employees. 

2. Let the plugin know where the viewer is located. 
If you ran the iMOD GUI installer, the viewer is probably installed here: 
`c:\Progam Files\Deltares\IMOD6 GUI`. 
To configure the QGIS pulgin, `cd` to the its' folder and run: 

```python configure_plugin.py /path/to/viewer/location/imod.exe```