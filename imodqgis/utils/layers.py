# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""
Layer utilities, different layers are currently stored 
in datasets as individual variables ("group_names").

When MDAL supports layers for UGRID, these utilities become unnecessary
"""

import re
from collections import defaultdict

from qgis.core import (
    QgsMeshDatasetIndex,
)

NO_LAYERS = ["0"]

def natural_sort_key(pair, _nsre=re.compile("([0-9]+)")):
    # From: https://stackoverflow.com/questions/4836710/is-there-a-built-in-function-for-string-natural-sort
    s = pair[0]
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def get_group_names(layer):
    indexes = layer.datasetGroupsIndexes()
    qgs_indexes = [QgsMeshDatasetIndex(group=i, dataset=0) for i in indexes]
    group_names = [layer.datasetGroupMetadata(i).name() for i in qgs_indexes]
    # Sort the entries by name
    sorted_pairs = sorted(zip(group_names, indexes), key=natural_sort_key)
    group_names, indexes = [list(tup) for tup in zip(*sorted_pairs)]
    return indexes, group_names


def groupby_variable(group_names, dataset_indexes):
    EXCEPTED_VARIABLE_NAMES = ["face_x", "face_y"] # Might be further expanded with other UGRID groups.
    grouped = defaultdict(dict)
    for group_name, dataset_idx in zip(group_names, dataset_indexes):
        if "_layer_" in group_name:
            parts = group_name.split("_layer_")
            name, layer_number = parts
            grouped[name][layer_number] = dataset_idx
        elif group_name not in EXCEPTED_VARIABLE_NAMES:
            layer_number = NO_LAYERS[0]
            name = group_name
            grouped[name][layer_number] = dataset_idx

    return grouped


def groupby_layer(group_names):
    """
    Groupby layer, provided by a list variable names ("group names", in MDAL terms).

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
    # Filter None from list, as to filter variables without "layer" in name, e.g. 'faces_x'
    groups = list(filter(None.__ne__, groups))
    # Convert to list of tuples: [('layer_1', 'bottom_layer_1'), ...]
    # the .group confusingly is a regex method here.
    groups = [(g.group(2), g.group(0)) for g in groups]
    gb = defaultdict(list)
    for key, group in groups:
        gb[key].append(group)
    return gb


def get_layer_idx(layer_key):
    """
    Extract layer number from a key such as 'layer_1'

    Parameters
    ----------
    key : str
        layer key like 'layer_1'

    Returns
    -------
    int
    """
    return int(re.match("layer_(\d+)", layer_key).group(1))
