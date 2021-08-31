*******************
Manual installation
*******************
Currently, no stable installer has been created, so instead the 
plugin can be installed following the following steps:

^^^^^^^^^^^^^^^^^^
1. Installing QGIS
^^^^^^^^^^^^^^^^^^
You can download the standalone QGIS setup 
`on the QGIS website <https://qgis.org/en/site/forusers/download.html>`_
currently we have developed with QGIS 3.16. 
But tested it on versions 3.18 and 3.20 as well.
Older versions are not tested, 
but any version prior to QGIS 3.14 will probably fail 
due to recent changes in the Mesh backend.

After downloading the QGIS setup, run it.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
1. Installing python dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The iMOD plugin has a couple of dependencies that are currently not
distributed with the plugin. To install them, follow these steps:

Open the OSGeo4W Shell that is provided with QGIS and type
the following two commands:

.. code:: console

    > py3_env
    > pip install declxml pandas pyqtgraph==0.11.1

``py3_env`` will temporarily set the QGIS python installation in your PATH within this shell.
``pip install <...>`` will install all necessary packages in your QGIS python installation.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
3. Download and copy the iMOD QGIS plugin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Download the iMOD QGIS plugin code from the `Github page <https://github.com/Deltares/imod-qgis>`_ 

Unpack the zip files, and copy the ``imod`` folder to your QGIS plugin directory. 
This is probably located in your Appdata folder.
In windows it is something such as:
``c:\Users\%USER%\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins``

If you cannot find the folder, follow `these instructions <https://gis.stackexchange.com/a/274312>`_.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
4. Optional: Connect to the iMOD 3D viewer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To be able to use the iMOD 3D viewer from the iMOD QGIS plugin, 
you still need to :

1. Download the viewer `at Deltares' Team City <https://dpcbuild.deltares.nl/project/iMOD6_IModGui?mode=builds>`_.
It currently is only available to Deltares employees. 

2. Let the plugin know where the viewer is located. 
If you ran the iMOD GUI installer, the viewer is probably installed here: 
``c:\Progam Files\Deltares\IMOD6 GUI``. 
To configure the QGIS pulgin, ``cd`` to the its' folder and run: 

``python configure_plugin.py /path/to/viewer/location/imod.exe``
