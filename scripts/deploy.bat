set plugin_dir=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

robocopy %~dp0\..\imodqgis %plugin_dir%\imodqgis /E
