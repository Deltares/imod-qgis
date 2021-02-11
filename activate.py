import json
import os
import subprocess
import sys

env_vars_json = sys.argv[1]
viewer_exe = sys.argv[2]
xml_path = sys.argv[3]

with open(env_vars_json, "r") as f:
    env_vars = json.loads(f.read())

for key in os.environ:
    os.environ.pop(key)

for key, value in env_vars.items():
    os.environ[key] = value

xml_path = r"c:/Users/engelen/AppData/Roaming/imod-qgis/qgis_viewer.imod"

subprocess.run([viewer_exe, xml_path])