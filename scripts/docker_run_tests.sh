#!/usr/bin/env bash
# Runs inside a qgis/qgis docker container (see test_docker.sh): installs the
# plugin dependencies, enables the plugin in a QGIS profile, and runs every
# test module in tests/unittests inside QGIS.
set -euo pipefail

echo "Installing plugin dependencies"
apt-get update -qq
# expect provides unbuffer, which qgis_testrunner.sh needs but the image lacks
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-pandas python3-xarray python3-netcdf4 expect > /dev/null

echo "Setting up QGIS profile with the imodqgis plugin enabled"
qgis_setup.sh imodqgis

# qgis_setup.sh always writes the QGIS3 profile, but QGIS 4 reads
# ~/.local/share/QGIS/QGIS4/profiles/default/QGIS/QGIS4.ini.
QGIS_MAJOR=$(python3 -c "from qgis.core import Qgis; print(Qgis.versionInt() // 10000)")
if [ "${QGIS_MAJOR}" != "3" ]; then
    QGIS_DIR=/root/.local/share/QGIS
    mv "${QGIS_DIR}/QGIS3" "${QGIS_DIR}/QGIS${QGIS_MAJOR}"
    mv "${QGIS_DIR}/QGIS${QGIS_MAJOR}/profiles/default/QGIS/QGIS3.ini" \
        "${QGIS_DIR}/QGIS${QGIS_MAJOR}/profiles/default/QGIS/QGIS${QGIS_MAJOR}.ini"
fi

# qgis_testrunner.sh imports the test modules as unittests.<module>
export PYTHONPATH="/tests_directory/tests:${PYTHONPATH:-}"
cd /tests_directory/tests

failed=()
for test_file in unittests/test_*.py; do
    module="unittests.$(basename "${test_file}" .py)"
    if ! xvfb-run -a qgis_testrunner.sh "${module}"; then
        failed+=("${module}")
    fi
done

if [ ${#failed[@]} -ne 0 ]; then
    echo "Failed test modules: ${failed[*]}"
    exit 1
fi
echo "All test modules passed"
