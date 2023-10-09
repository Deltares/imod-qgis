# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import os
import platform
from pathlib import Path


def get_configdir() -> Path:
    """
    Get the location of the imod-qgis plugin settings.

    The location differs per OS. Configdir is created if not exists.

    Returns
    -------
    configdir: pathlib.Path
    """
    if platform.system() == "Windows":
        configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
    else:
        configdir = Path(os.environ["HOME"]) / ".imod-qgis"

    # If not present, make directory
    configdir.mkdir(exist_ok=True, mode=766)

    return configdir
