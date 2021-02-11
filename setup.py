import json
import os
import platform
import sys
from pathlib import Path

# Write all the environmental variables so the QGIS interpreter
# can (re)set them properly.
if platform.system() == "Windows":
    configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
else:
    configdir = Path(os.environ["HOME"]) / ".imod-qgis"
configdir.mkdir(exist_ok=True)

env_vars = {key: value for key, value in os.environ.items()}
with open(configdir / "environmental-variables.json", "w") as f:
    f.write(json.dumps(env_vars))

viewer_exe = r"c:\Users\engelen\projects_wdir\iMOD6\viewer\install\IMOD6.exe"

with open(configdir / "viewer_exe.txt", "w") as f:
    f.write(viewer_exe)

with open("activate.py", "r") as src:
    content = src.read()
with open(configdir / "activate.py", "w") as dst:
    dst.write(content)
