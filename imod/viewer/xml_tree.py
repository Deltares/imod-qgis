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

def create_grid_model_list(path, legend, groupby_dict, bbox_rectangle):
    #Manually add "computed" DataSet
    ds_elevation = xmu.DataSet(Name = "Elevation (cell centre)",
                            Time = 0,
                            Origin = "computed",
                            legend = legend)

    fname = os.path.basename(path)

    boundingbox = create_boundingbox(bbox_rectangle)

    gm_list = []

    for key in groupby_dict.keys():
        ds_ls = xmu.DataSetList(
            [xmu.DataSet(Name = i) for i in groupby_dict[key]]+[ds_elevation]
            )
        
        name = fname + key
        grid_idx = 0
        layer_idx = get_layer_idx(key)

        uri = r'Ugrid:"{}":mesh2d'.format(path)

        gm = xmu.GridModel(Name=name, Url=path, Uri=uri,
                    GridIndex=grid_idx, LayerIndex=layer_idx,
                    datasetlist=ds_ls, boundingbox=boundingbox)

        gm_list.append(gm)
    
    return gm_list
    

def create_viewer_tree(path, group_names, rgb_point_data, bbox_rectangle):
    groupby_dict = groupby_layer(group_names)
    legend = create_legend(rgb_point_data)
    
    gm_list = create_grid_model_list(path, legend, groupby_dict, bbox_rectangle)

    viewer_3d = xmu.Viewer(type="3D", 
        explorermodellist=xmu.ExplorerModelList(gridmodel=gm_list))

    return viewer_3d

def create_file_tree(path, group_names, rgb_point_data, bbox_rectangle):
    viewer_3d = create_viewer_tree(path, group_names, rgb_point_data, bbox_rectangle)

    file_tree = xmu.IMOD6(viewer=[xmu.Viewer(), viewer_3d])
    return(file_tree)

def create_command_tree(path, group_names, rgb_point_data, bbox_rectangle):
    viewer_3d = create_viewer_tree(path, group_names, rgb_point_data, bbox_rectangle)

    command_tree = xmu.ImodCommand(viewer=[xmu.Viewer(), viewer_3d])

    return command_tree

def write_xml(path, xml_path, group_names, rgb_point_data, bbox_rectangle):
    file_tree = create_file_tree(path, group_names, rgb_point_data, bbox_rectangle)

    processor = xmu.make_processor(xmu.IMOD6)

    xml.serialize_to_file(processor, file_tree, xml_path, indent='   ')

def serialize_xml(path, group_names, rgb_point_data, bbox_rectangle):
    command_tree = create_command_tree(path, group_names, rgb_point_data, bbox_rectangle)

    processor = xmu.make_processor(xmu.ImodCommand)

    return xml.serialize_to_string(processor, command_tree, indent='   ')