
Running workflow on Windows
==========================
This document describes how to run the github workflow on your windows machine.
This makes writing tests doable.

1: Enable WSL2
-------------------
[Follow the instructions
here.](https://docs.microsoft.com/en-us/windows/wsl/install-win10#manual-installation-steps)

2: Install Docker
---------------------
[Follow the instructions here.](
https://docs.docker.com/docker-for-windows/install/)

3: Install ``act``
--------------------
[Follow the instructions here.](https://github.com/nektos/act)

4: Manually modify 1 line in tests.yml
---------------------------------------
Change the line under of code in tests.yml, for the step: "Install qgis image"
Change the absolute path if your working directory is not ``c:/src/imod-qgis``!

5: Run ``act`` 
-------------------
Open up a prompt and run the command ``act``. This will fetch the QGIS docker
image, and run the tests on it. **Note that you have to delete the running qgis
container in order to run the complete workflow again!**

6: Re-run specific tests
---------------------------
If you want to run specific tests on a running docker container, in your
prompt, execute the following command: 
``docker exec -t qgis-testing-environment sh -c "cd /tests_directory/tests && qgis_testrunner.sh unittests.test_maptools"``