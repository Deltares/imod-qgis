import os, sys
from pathlib import Path
from glob import glob

SPDX = """\
# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""

wdir = (Path(sys.path[0]) / ".." / "imod").resolve()

files = glob(str(wdir / "**" / "*.py"), recursive=True)

with open(files[0], "r") as fd:
    contents = fd.readlines()

for file in files:
    with open(file, "r+", encoding="utf-8") as fd:
        contents = fd.readlines()
        if contents[0:3] != SPDX.splitlines(True):  # Only add SPDX if not yet in file
            contents.insert(0, SPDX)  # new_string should end in a newline
            fd.seek(0)  # readlines consumes the iterator, so we need to start over
            fd.writelines(contents)  # No need to truncate as we are increasing filesize
