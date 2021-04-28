import os

import declxml as xml
from . import xml_utils as xmu


def create_legend(rgb_point_data):
    legend = xmu.Legend(
        LegendType="Continuous", ColorScheme="Rainbow", RgbPointData=rgb_point_data
    )
    return legend


def create_boundingbox(bbox_rectangle):
    # TODO implement support for ZMin and ZMax as well
    xmin = str(bbox_rectangle.xMinimum())
    xmax = str(bbox_rectangle.xMaximum())
    ymin = str(bbox_rectangle.yMinimum())
    ymax = str(bbox_rectangle.yMaximum())
    return xmu.BoundingBox(XMin=xmin, XMax=xmax, YMin=ymin, YMax=ymax)


def create_object_list(guids_grids=None, variable_names=None, **xml_dict):
    if guids_grids is None:
        raise ValueError("guids_grids is not specified")

    objects = [xmu.Object(type="LayeredGrid", guid=guids_grids[0])]
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
    guids_grids = xml_dict["guids_grids"]
    return xmu.ImodCommand(
        type="LoadExplorerModel", targetmodel=[xmu.TargetModel(guid=guids_grids[0])]
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

    guids_grids = xml_dict["guids_grids"]
    target_model = [xmu.TargetModel(guid=guids_grids[0])]
    polylines = xmu.PolyLines(
        PolyLine=[_to_string(polyline) for polyline in xml_dict["polylines"]]
    )

    return xmu.ImodCommand(
        type="CreateFenceDiagram",
        targetmodel=target_model,
        polylines=polylines,
        Url=None,
    )


def open_file_models_tree(**xml_dict):
    objectguids = create_object_list(**xml_dict)

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
