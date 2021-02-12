import os
import re

import declxml as xml
from . import xml_utils as xmu

def groupby_layer(group_names):
    """Groupby layer
    
    Parameters
    ----------
    group_names : list of str
        list with dataset group names
    

    Returns
    -------
    gb : dict
        A dictionary with "_layer_{\d+}" as key and 
        a list with all full dataset names
        as value 
    """
    prog = re.compile("(.+)_(layer_\d+)")
    groups = [prog.match(group_name) for group_name in group_names]
    #Filter None from list, so variables without "layer" in name, e.g. 'faces_x'
    groups = list(filter(None.__ne__, groups))
    #Convert to list of tuples: [('layer_1', 'bottom_layer_1'), ...]
    #the .group confusingly is a regex method here.
    groups = [(g.group(2), g.group(0)) for g in groups] 

    gb = {}
    for key, group in groups:
        if key not in gb.keys():
            gb[key] = [group]
        else:
            gb[key].append(group)
    return gb

def get_layer_idx(layer_key):
    """Extract layer number from a key such as 'layer_1'

    Parameters
    ----------
    key : str
        layer key like 'layer_1'

    Returns
    -------
    int
    """

    return int(re.match("layer_(\d+)", layer_key).group(1))

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