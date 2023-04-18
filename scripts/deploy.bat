set plugin_dir=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

rem Remove plugin folder before copying
rmdir %plugin_dir%\imodqgis /S /Q 
rem Copy
robocopy %~dp0\..\imodqgis %plugin_dir%\imodqgis /E
