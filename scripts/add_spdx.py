import sys
from glob import glob
from pathlib import Path

SPDX = """\
# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""

wdir = (Path(sys.path[0]) / ".." / "imodqgis").resolve()

files = glob(str(wdir / "**" / "*.py"), recursive=True)
files = [Path(file) for file in files]

# Filter default scripts that were added by the QGIS plugin builder
files = [file for file in files if not file.match("imodqgis/plugin_upload.py")]
files = [file for file in files if not file.match("imodqgis/resources.py")]

# Filter dependencies, we are not copyrighting those
files = [file for file in files if "dependencies" not in list(file.parts)]

for file in files:
    with open(file, "r+", encoding="utf-8") as fd:
        contents = fd.readlines()
        if contents[0:3] != SPDX.splitlines(True):  # Only add SPDX if not yet in file
            contents.insert(0, SPDX)  # new_string should end in a newline
            fd.seek(0)  # readlines consumes the iterator, so we need to start over
            fd.writelines(contents)  # No need to truncate as we are increasing filesize
