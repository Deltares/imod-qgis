"""
Layer utilities, different layers are currently stored 
in datasets as individual variables ("group_names").

When MDAL supports layers for UGRID, these utilities become unnecessary
"""

from 

from collections import defaultdict
import re

def get_group_names(layer):
    idx = layer.datasetGroupsIndexes()
    #TODO: Include time index as dataset argument during QgsMeshDatasetIndex construction
    idx = [QgsMeshDatasetIndex(group=i, dataset=0) for i in idx]
    group_names = [layer.datasetGroupMetadata(i).name() for i in idx]

    return idx, group_names

def groupby_variable(group_names, dataset_indexes):
    """Groupby variable
    """

    gb = defaultdict(list)

    for group_name, dataset_idx in zip(group_names, dataset_indexes):

        if "_layer_" in group_name:
            parts = group_name.split("_layer_")
            name, lay_nr = parts
            gb[name].append((int(lay_nr), dataset_idx))
        
    return gb

def groupby_layer(group_names):
    """Groupby layer, provided by a list variable names ("group names", in MDAL terms).
    
    Parameters
    ----------
    group_names : list of str
        list with dataset group names
    

    Returns
    -------
    gb : dict
        A dictionary with "layer_{\d+}" as key and 
        a list with all full dataset names
        as value 
    """
    prog = re.compile("(.+)_(layer_\d+)")
    groups = [prog.match(group_name) for group_name in group_names]

    #Filter None from list, as to filter variables without "layer" in name, e.g. 'faces_x'
    groups = list(filter(None.__ne__, groups))
    #Convert to list of tuples: [('layer_1', 'bottom_layer_1'), ...]
    #the .group confusingly is a regex method here.
    groups = [(g.group(2), g.group(0)) for g in groups] 

    gb = defaultdict(list)
    for key, group in groups:
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