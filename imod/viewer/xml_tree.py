import os

import declxml as xml
from . import xml_utils as xmu

from ..utils.layers import groupby_layer, get_layer_idx

def create_legend(rgb_point_data):
    legend = xmu.Legend(LegendType = "Continuous",
                ColorScheme="Rainbow",
                RgbPointData=rgb_point_data)
    return legend

def create_boundingbox(bbox_rectangle):
    #TODO implement support for ZMin and ZMax as well
    xmin = str(bbox_rectangle.xMinimum())
    xmax = str(bbox_rectangle.xMaximum())
    ymin = str(bbox_rectangle.yMinimum())
    ymax = str(bbox_rectangle.yMaximum())
    return xmu.BoundingBox(XMin = xmin, XMax = xmax, YMin = ymin, YMax = ymax)

def create_grid_model_list(**xml_dict):
    "path=None, legend=None, groupby_dict=None, bbox_rectangle=None"
    #Manually add "computed" DataSet
    guids_grids = xml_dict['guids_grids']
    path = xml_dict['path']
    legend = xml_dict['legend']
    groupby_dict = xml_dict['groupby_dict']
    bbox_rectangle = xml_dict['bbox_rectangle']

    ds_elevation = xmu.DataSet(Name = "Elevation (cell centre)",
                            Time = 0,
                            Origin = "computed",
                            legend = legend)

    fname = os.path.basename(path)

    boundingbox = create_boundingbox(bbox_rectangle)

    gm_list = []

    for key, guid_grid in zip(groupby_dict.keys(), guids_grids):
        ds_ls = xmu.DataSetList(
            [xmu.DataSet(Name = i) for i in groupby_dict[key]]+[ds_elevation]
            )
        
        name = fname + key
        grid_idx = 0
        layer_idx = get_layer_idx(key)

        uri = r'Ugrid:"{}":mesh2d'.format(path)

        gm = xmu.GridModel(guid = guid_grid, Name=name, 
                    Url=path, Uri=uri,
                    GridIndex=grid_idx, LayerIndex=layer_idx,
                    datasetlist=ds_ls, boundingbox=boundingbox)

        gm_list.append(gm)
    
    return gm_list
    

def create_viewer_tree(**xml_dict):
    group_names = xml_dict.pop("group_names")
    rgb_point_data = xml_dict.pop("rgb_point_data")

    xml_dict["groupby_dict"] = groupby_layer(group_names)
    xml_dict["legend"] = create_legend(rgb_point_data)
    
    gm_list = create_grid_model_list(**xml_dict)

    viewer_3d = xmu.Viewer(type="3D", 
        explorermodellist=xmu.ExplorerModelList(gridmodel=gm_list))

    return viewer_3d

def create_file_tree(**xml_dict):
    viewer_3d = create_viewer_tree(**xml_dict)

    return xmu.IMOD6(viewer=[xmu.Viewer(), viewer_3d])

def write_xml(xml_path, **xml_dict):
    """Write xml command

    xml_path : string
        path to xml file
    
    xml_dict : dict
        dictionary, should contain keys "path", "group_names", "rgb_point_data", "bbox_rectangle"

    """
    file_tree = create_file_tree(**xml_dict)

    processor = xmu.make_processor(xmu.IMOD6)

    xml.serialize_to_file(processor, file_tree, xml_path, indent='   ')

def add_to_explorer_tree(**xml_dict):
    viewer_3d = create_viewer_tree(**xml_dict)

    return xmu.ImodCommand(viewer=[xmu.Viewer(), viewer_3d], type="AddToExplorer")

def load_to_explorer_tree(**xml_dict):
    guid_grid = xml_dict["guid_grid"]
    
    modeltoload = xmu.ModelToLoad(guid=guid_grid)

    return xmu.ImodCommand(modeltoload=modeltoload, type="LoadExplorerModel")


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

    return xml.serialize_to_string(processor, command_tree, indent='   ')