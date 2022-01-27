
Step 1: Enable WSL2
https://docs.microsoft.com/en-us/windows/wsl/install-win10#manual-installation-steps

Step 2: Install Docker
https://docs.docker.com/docker-for-windows/install/

Step 3: Install act
https://github.com/nektos/act

Step 4: Change the line under of code in tests.yml, for the step: "Install qgis
image" Change the absolute path if your working directory is not
c:/src/imod-qgis!

Step 5: Open up a prompt and run the command ``act``. This will fetch the QGIS
docker image, and run the tests on it. Note that you have to delete the running
qgis container in order to run the complete workflow again!

Step 6: If you want to run specific tests on a running docker container, in your
prompt, execute the following command: 
``docker exec -t qgis-testing-environment sh -c "cd /tests_directory/tests && qgis_testrunner.sh unittests.test_maptools"``