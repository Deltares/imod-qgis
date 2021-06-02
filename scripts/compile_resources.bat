rem Set the OSGeo4W environmental variables
rem See if OSGeo4W batch file exist in an OSGeo4W dir 
rem If that doesn't work, try to find the QGIS dir (version numbers may differ)
if exist c:\OSGeo4W64\OSGeo4W.bat (
    call c:\OSGeo4W64\bin\o4w_env.bat
    call c:\OSGeo4W64\bin\qt5_env.bat
    call c:\OSGeo4W64\bin\py3_env.bat
) else (
    rem You have to use a for loop to set the output as a variable ...
    for /f "tokens=*" %%f in ('dir /b "c:\Program Files" ^| find "QGIS 3.1"') do (
        set qgis=%%f
    )
    call "c:\Program Files\%%qgis%%\bin\o4w_env.bat"
    call "c:\Program Files\%%qgis%%\bin\qt5_env.bat"
    call "c:\Program Files\%%qgis%%\bin\py3_env.bat"
)

cd ..\imod
call pyrcc5 resources.qrc -o resources.py
pause