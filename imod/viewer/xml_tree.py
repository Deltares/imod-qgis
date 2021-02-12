import os

import declxml as xml
from . import xml_utils as xmu

from ..utils.layers import groupby_layer, get_layer_idx

def create_legend(rgb_point_data):
    legend = xmu.Legend(Discrete = False,
                ColorScheme="Rainbow",
                RgbPointData=rgb_point_data)
    return legend

def create_grid_model_list(path, legend, groupby_dict):
    #Manually add "computed" DataSet
    ds_elevation = xmu.DataSet(Name = "Elevation (cell centre)",
                            Time = 0,
                            Origin = "computed",
                            legend = legend)

    fname = os.path.basename(path)

    gm_list = []

    for key in groupby_dict.keys():
        ds_ls = xmu.DataSetList(
            [xmu.DataSet(Name = i) for i in groupby_dict[key]]+[ds_elevation]
            )
        
        name = fname + key
        grid_idx = 0
        layer_idx = get_layer_idx(key)

        uri = r'Ugrid:"{}":mesh2d'.format(path)

        gm = xmu.GridModel(Name = name, Url = path, Uri = uri,
                    GridIndex = grid_idx, LayerIndex = layer_idx,
                    datasetlist=ds_ls)

        gm_list.append(gm)
    
    return gm_list
    

def create_imod_tree(path, group_names, rgb_point_data):
    groupby_dict = groupby_layer(group_names)
    legend = create_legend(rgb_point_data)
    
    gm_list = create_grid_model_list(path, legend, groupby_dict)

    viewer_3d = xmu.Viewer(type="3D", 
        explorermodellist=xmu.ExplorerModelList(gridmodel=gm_list))

    imod_tree = xmu.IMOD6(viewer=[xmu.Viewer(), viewer_3d])

    return imod_tree

def write_xml(path, xml_path, group_names, rgb_point_data):
    imod_tree = create_imod_tree(path, group_names, rgb_point_data)

    processor = xmu.make_processor(xmu.IMOD6)

    xml.serialize_to_file(processor, imod_tree, xml_path, indent='   ')