set plugin_dir=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

robocopy %~dp0\..\imod %plugin_dir%\imod /E
