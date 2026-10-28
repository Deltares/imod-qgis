"""
Zip the plugin folder so it can be installed with QGIS' "Plugins > Manage and
Install Plugins > Install from ZIP". Run with `pixi run package`.

The zip contains the current working tree (including uncommitted changes) of
imodqgis/, without Python caches, under a top-level imodqgis/ folder.
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / "imodqgis"
OUTPUT = ROOT / "imodqgis.zip"


def main():
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            zf.write(path, path.relative_to(ROOT).as_posix())
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
