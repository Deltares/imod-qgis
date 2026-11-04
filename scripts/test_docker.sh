#!/usr/bin/env bash
# Run the unit tests inside an official QGIS docker image, e.g.:
#
#   bash scripts/test_docker.sh qgis/qgis:3.44
#   bash scripts/test_docker.sh qgis/qgis:4.2
#
# The repository is mounted at /tests_directory, where qgis_setup.sh expects
# the plugin folder (imodqgis) to be.
set -euo pipefail

IMAGE=${1:?usage: test_docker.sh <qgis docker image>}
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

docker run --rm \
    --platform linux/amd64 \
    --volume "${REPO_DIR}:/tests_directory" \
    "${IMAGE}" \
    bash /tests_directory/scripts/docker_run_tests.sh
