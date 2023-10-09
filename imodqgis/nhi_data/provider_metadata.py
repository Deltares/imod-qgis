# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import json
import os
import platform
import urllib.request
from pathlib import Path
from typing import Dict, List
from xml.etree import cElementTree as ElementTree

PROVIDERS = [
    ("https://geoserver.data.nhi.nu/geoserver/ows", "wcs", "2.0.1"),
    ("https://geoserver.data.nhi.nu/geoserver/ows", "wfs", "2.0.0"),
    ("https://geoserver.data.nhi.nu/geoserver/ows", "wms", "1.3.0"),
    ("https://modeldata-nhi-data.deltares.nl/geoserver/ows", "wcs", "2.0.1"),
    ("https://modeldata-nhi-data.deltares.nl/geoserver/ows", "wms", "1.3.0"),
]
NAMESPACES = {
    "wcs": "http://www.opengis.net/wcs/2.0",
    "ows": "http://www.opengis.net/ows/2.0",
    "wfs": "http://www.opengis.net/wfs/2.0",
    "wms": "http://www.opengis.net/wms",
}


def wcs_metadata(url: str, version: str) -> List[Dict]:
    response = urllib.request.urlopen(
        f"{url}?service=WCS&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    # Read WCS capabilities
    # Whole boatload of CRS supported;
    # Just defaulting to ESPG:28992 for now
    # Also will default to format=GeoTIFF; to fetch formats:
    # formats = [item.text for item in root.find("wcs:ServiceMetadata", NAMESPACES)]
    contents_xml = root.find("wcs:Contents", NAMESPACES)
    metadata = []
    for layer_xml in contents_xml:
        d = {
            "abstract": layer_xml.findtext("ows:Abstract", "", NAMESPACES),
            "crs": "EPSG:28992",
            "format": "GeoTIFF",
            "identifier": layer_xml.findtext("wcs:CoverageId", "", NAMESPACES).replace(
                "__", ":"
            ),
            "service": "wcs",
            "title": layer_xml.findtext("ows:Title", "", NAMESPACES),
            "url": url,
            "version": version,
        }
        metadata.append(d)
    return metadata


def wfs_metadata(url: str, version: str) -> List[Dict]:
    response = urllib.request.urlopen(
        f"{url}?service=wfs&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    metadata = []
    for xml_layer in root.find("wfs:FeatureTypeList", NAMESPACES):
        crs = xml_layer.findtext("wfs:DefaultCRS", "", NAMESPACES).split("::")[1]
        d = {
            "abstract": xml_layer.findtext("wfs:Abstract", "", NAMESPACES),
            "crs": f"EPSG:{crs}",
            "title": xml_layer.findtext("wfs:Title", "", NAMESPACES),
            "typename": xml_layer.findtext("wfs:Name", "", NAMESPACES),
            "service": "wfs",
            "url": url,
            "version": version,
        }
        metadata.append(d)
    return metadata


def wms_metadata(url: str, version: str) -> List[Dict]:
    response = urllib.request.urlopen(
        f"{url}?service=wms&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    metadata = []
    xml_layers = root.find("wms:Capability", NAMESPACES).find("wms:Layer", NAMESPACES)
    for xml_layer in xml_layers.findall("wms:Layer", NAMESPACES):
        style = xml_layer.find("wms:Style", NAMESPACES)
        if style is not None:
            imgformat = (
                style.find("wms:LegendURL", NAMESPACES)
                .find("wms:Format", NAMESPACES)
                .text
            )
        else:
            # This is the default that QGIS chooses, seems to work alright
            imgformat = "image/png"
        d = {
            "abstract": xml_layer.findtext("wms:Abstract", "", NAMESPACES),
            "crs": "EPSG:28992",
            "format": imgformat,
            "layers": xml_layer.findtext("wms:Name", "", NAMESPACES),
            "service": "wms",
            "styles": "",
            "title": xml_layer.findtext("wms:Title", "", NAMESPACES),
            "url": url,
            "version": version,
        }
        metadata.append(d)
    return metadata


def fetch_metadata() -> None:
    functions = {
        "wcs": wcs_metadata,
        "wfs": wfs_metadata,
        "wms": wms_metadata,
    }
    metadata = []
    for url, service, version in PROVIDERS:
        metadata.extend(functions[service](url, version))

    if platform.system() == "Windows":
        configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
    else:
        configdir = Path(os.environ["HOME"]) / ".imod-qgis"

    with open(configdir / "nhi-data-providers.json", "w") as f:
        f.write(json.dumps(metadata))
