# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from imodqgis import xml_utils as xmu
from imodqgis.dependencies import declxml as xml


def create_legend(rgb_point_data):
    legend = xmu.Legend(
        LegendType="Continuous", ColorScheme="Rainbow", RgbPointData=rgb_point_data
    )
    return legend


def create_boundingbox(bbox_rectangle):
    # TODO implement support for ZMin and ZMax as well
    xmin, xmax, ymin, ymax = bbox_rectangle
    return xmu.BoundingBox(XMin=xmin, XMax=xmax, YMin=ymin, YMax=ymax)


def create_object_list(
    type_object_list, guids_grids=None, variable_names=None, **xml_dict
):
    """
    Create list of object guids for layered grids and fence diagrams

    Parameters
    ----------
    type_object_list : str
        Should be either "LayeredGrid" or "FenceDiagram"

    """
    if guids_grids is None:
        raise ValueError("guids_grids is not specified")

    objects = [xmu.Object(type=type_object_list, guid=guids_grids[0])]
    for i, name in enumerate(variable_names):
        objects.append(
            xmu.Object(name=name, type="LayeredDataSet", guid=guids_grids[i + 1])
        )

    return xmu.ObjectGuids(object=objects)


def model_unload_tree(**xml_dict):
    guids_grids = xml_dict["guids_grids"]
    return xmu.ImodCommand(
        type="UnloadModel",
        targetmodel=[xmu.TargetModel(guid=guid) for guid in guids_grids],
    )


def model_load_tree(**xml_dict):
    target_guid = xml_dict["guids_grids"][0]

    return xmu.ImodCommand(
        type="LoadExplorerModel", targetmodel=[xmu.TargetModel(guid=target_guid)]
    )


def set_legend_tree(legend_guid=None, **xml_dict):
    rgb_point_data = xml_dict["rgb_point_data"]

    legend = create_legend(rgb_point_data)
    return xmu.ImodCommand(
        type="SetLegendCommand",
        legend=legend,
        targetmodel=[xmu.TargetModel(guid=legend_guid)],
    )


def add_borelogs_tree(**xml_dict):
    guids_grids = xml_dict["guids_grids"]
    name = path = xml_dict["name"]
    path = xml_dict["path"]
    column_mapping = xmu.ColumnMapping(
        map=[
            xmu.Map(Purpose=key, Name=value)
            for key, value in xml_dict["column_mapping"].items()
        ]
    )
    borehole = xmu.TableGeometryModel(
        guid=guids_grids[0], Name=name, Url=path, columnmapping=column_mapping
    )
    viewer = [
        xmu.Viewer(
            explorermodellist=xmu.ExplorerModelList(tablegeometrymodel=[borehole])
        )
    ]

    return xmu.ImodCommand(type="AddToExplorer", viewer=viewer)


def create_fence_diagram_tree(**xml_dict):
    def _to_string(iterable):
        return " ".join(str(p) for p in iterable)

    objectguids = create_object_list(type_object_list="FenceDiagram", **xml_dict)

    path = xml_dict["path"]
    boundingbox = create_boundingbox(xml_dict["bbox_rectangle"])

    polylines = xmu.PolyLines(
        PolyLine=[_to_string(polyline) for polyline in xml_dict["polylines"]]
    )

    return xmu.ImodCommand(
        type="CreateFenceDiagram",
        objectguids=objectguids,
        polylines=polylines,
        Url=path,
        boundingbox=boundingbox,
    )


def open_file_models_tree(**xml_dict):
    objectguids = create_object_list(type_object_list="LayeredGrid", **xml_dict)

    viewer = [xmu.Viewer(type="3D")]
    path = xml_dict["path"]
    boundingbox = create_boundingbox(xml_dict["bbox_rectangle"])

    return xmu.ImodCommand(
        type="AddLayeredGridToExplorer",
        objectguids=objectguids,
        viewer=viewer,
        Url=path,
        boundingbox=boundingbox,
    )


def command_xml(func, **xml_dict):
    """Serialize command, func should indicate which command should be called.

    func : types.FunctionTypes
        Functions should be either: add_to_explorer_tree, load_to_explorer_tree

    xml_dict : dict

    """

    if not callable(func):
        raise TypeError("func should be callable")

    command_tree = func(**xml_dict)

    processor = xmu.make_processor(xmu.ImodCommand)

    return xml.serialize_to_string(processor, command_tree, indent="   ")
