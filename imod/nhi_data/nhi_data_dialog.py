from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QTableView,
    QAbstractItemView,
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QSortFilterProxyModel, Qt

import urllib.request
from xml.etree import cElementTree as ElementTree


PROVIDERS = [
    ("https://data.nhi.nu/geoserver/ows", "wcs", "2.0.1"),
    ("https://data.nhi.nu/geoserver/ows", "wfs", "2.0.0"),
    ("https://data.nhi.nu/geoserver/ows", "wms", "1.3.0"),
    ("https://modeldata-nhi-data.deltares.nl/geoserver/ows", "wcs", "2.0.1"),
    ("https://modeldata-nhi-data.deltares.nl/geoserver/ows", "wfs", "2.0.0"),
    ("https://modeldata-nhi-data.deltares.nl/geoserver/ows", "wms", "1.3.0"),
]
NAMESPACES = {
    "wcs": "http://www.opengis.net/wcs/2.0",
    "ows": "http://www.opengis.net/ows/2.0",
    "wfs": "http://www.opengis.net/wfs/2.0",
    "wms": "http://www.opengis.net/wms",
}


def wcs_metadata(url, version):
    response = urllib.request.urlopen(
        f"{url}?service=WCS&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    # Read WCS capabilities
    # Whole boatload of CRS supported
    # Just defaulting to ESPG:28992 for now
    formats = [item.text for item in root.find('wcs:ServiceMetadata', NAMESPACES)]
    contents_xml = root.find('wcs:Contents', NAMESPACES)
    metadata = []
    for layer_xml in contents_xml:
        d = {
            "abstract": layer_xml.find('ows:Abstract', NAMESPACES).text,
            "crs": "EPSG:28992",
            "formats": formats,
            "identifier": layer_xml.find('wcs:CoverageId', NAMESPACES).text,
            "service": "wcs",
            "title": layer_xml.find('ows:Title', NAMESPACES).text,
            "url": url,
            "version": version,
        }
        metadata.append(d)
    return metadata


def wfs_metadata(url, version):
    response = urllib.request.urlopen(
        f"{url}?service=wfs&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    metadata = []
    for xml_layer in root.find('wfs:FeatureTypeList', NAMESPACES):
        d = {
                "abstract": xml_layer.find('ows:Abstract', NAMESPACES).text,
                "crs": xml_layer.find('wfs:DefaultCRS', NAMESPACES).text,
                "title": xml_layer.find('wfs:Title', NAMESPACES).text,
                "typename": xml_layer.find('wfs:Name', NAMESPACES).text,
                "service": "wfs",
                "url": url,
                "version": version,
        }
        metadata.append(d)
    return metadata


def wms_metadata(url, version):
    response = urllib.request.urlopen(
        f"{url}?service=wms&version={version}&request=GetCapabilities"
    ).read()
    root = ElementTree.XML(response)
    metadata = []
    xml_layers = root.find("wms:Capability", NAMESPACES).find("wms:Layer", NAMESPACES)
    default_crs = "EPSG:28992"
    for xml_layer in xml_layers.findall("wms:Layer", NAMESPACES):
        crs_options = [a.text for a in xml_layer.findall("wms:CRS", NAMESPACES)]
        imgformat = xml_layer.find("wms:Style", NAMESPACES).find("wms:LegendURL", NAMESPACES).find("wms:Format", NAMESPACES).text
        d = {
            "abstract": xml_layer.find("wms:Abstract", NAMESPACES).text,
            "crs": default_crs if default_crs in crs_options else crs_options[0],
            "format": imgformat,
            "layers": xml_layer.find("wms:Name", NAMESPACES).text,
            "service": "wms",
            "title": xml_layer.find("wms:Title", NAMESPACES).text,
            "url": url,
            "version": version,
        }
        metadata.append(d)
    return metadata


# WFS
"https://data.nhi.nu/geoserver/oppervlaktewater_1/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=oppervlaktewater_1:bijzonderhydraulischobject_v13&outputFormat=SHAPE-ZIP"
d = {"type":"wfs","title":"aardgas_buurt_bedrijven_2014","abstract":"Aardgas- en elektriciteitslevering t.b.v. de Nationale Energieatlas","url":"https://geodata.nationaalgeoregister.nl/cbsenergieleveringen/wfs","layers":"cbsenergieleveringen:aardgas_buurt_bedrijven_2014","servicetitle":"CBS Aardgas- en Elektriciteitslevering 2014"} 
version = " 2.0.0"
layers = d["layers"]
layers = a.id

uri = f"pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{typename}' url='{url}' version='{version}' "


def provider_metadata():
    metadata = []
    for url, service, version in PROVIDERS:
        my_service = OWSLIB_TYPES[service](url, version)
        contents.extend(my_service.contents.keys())

    return metadata


class ImodNhiDataDialog(QDialog):
    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Add NHI data")
        self.iface = iface
        
        self.search_edit = QLineEdit()
        self.data_model = QStandardItemModel()
        self.data_model.setHeaderData(0, Qt.Horizontal, "Layer name")
        self.data_model.setHeaderData(1, Qt.Horizontal, "Service")
        self.data_model.setHorizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.data_model.setHorizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.data_model)
        self.proxy_model.setFilterKeyColumn(3)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_view = QTableView()
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setColumnWidth(0, 300)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.add_button = QPushButton("Add layer")
        self.close_button = QPushButton("Close")
        
        # Connect to methods
        self.search_edit.onTextChanged.connect(self.filter_layers)
        self.add_button.clicked.connect(self.add_layer)
        self.close_button.clicked.connect(self.reject)
        
        # Set layout
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Search:"))
        first_row.addWidget(self.search_edit)

        third_row = QHBoxLayout()
        third_row.addStretch()
        third_row.addWidget(self.add_button)

        fourth_row = QHBoxLayout()
        fourth_row.addStretch()
        fourth_row.addWidget(self.close_button)

        column = QVBoxLayout()
        column.addLayout(first_row)
        column.addWidget(self.table_view)
        column.addLayout(third_row)
        column.addLayout(fourth_row)
        self.setLayout(column)
        self.load_services()

    def add_layer(self):
        if self.current_layer is None:
            return
        service = self.current_layer["service"]
        url = self.current_layer["url"]
        version = self.current_layer["version"]
        title = self.current_layer["title"]
        
        if service == "wms":
            imgformat = self.current_layer["imgformats"]
            style = self.current_layer.get("style", "")
            uri = f"crs={crs}&layers={layers}&styles={styles}&format={imgformat}&url={url}"
            self.iface.addRasterLayer(uri, title, service)
        elif service == "wcs":
            uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={imgformat}&identifier={layers}&url={url}"
            self.iface.addRasterLayer(uri, title, service)
        elif service == "wfs":
            typename = self.current_layer["typename"]
            uri = f"pagingEnabled='true' restrictToRequestBBOX='1' srsname='{crs}' typename='{layers}' url='{url}' version='{version}' "
            self.iface.addVectorLayer(uri, title, service)
        else:
            raise ValueError(
                f"Invalid service. Should be one of [wms, wcs, wfs]. Got instead: {service}"
            )


    def filter_layers(self):
        self.table_view.selectRow(0)
        string = self.search_edit.text()
        self.proxy_model.setFilterFixedString(string)
    
    def add_row(self, layer):
        service = layer["service"]
        layername = layer["title"]
        service = QStandardItem(service.upper())
        service.setData(layer, Qt.UserRole)
        layername = QStandardItem(layername)
        item_filter = QStandardItem(f"{service} {layername}")
        
        self.data_model.appendRow(
            [
                layername, service, item_filter
            ]
        )

    def load_services(self):
        for layer in provider_metadata():
            self.add_row(layer)
