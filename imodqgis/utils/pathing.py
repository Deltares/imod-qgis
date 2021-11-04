from pathlib import Path
import os
import platform


def get_configdir() -> Path:
    """
    Get the location of the imod-qgis plugin settings.

    The location differs per OS.

    Returns
    -------
    configdir: pathlib.Path
    """
    if platform.system() == "Windows":
        configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
    else:
        configdir = Path(os.environ["HOME"]) / ".imod-qgis"
    return configdir
