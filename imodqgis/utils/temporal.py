# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from qgis.core import (
    QgsMeshDatasetIndex,
)


def get_group_is_temporal(layer):
    """Returns list of booleans of which meshdataset groups are temporal"""
    indexes = layer.datasetGroupsIndexes()
    qgs_indexes = [QgsMeshDatasetIndex(group=i, dataset=0) for i in indexes]
    return [layer.datasetGroupMetadata(i).isTemporal() for i in qgs_indexes]


def is_temporal_meshlayer(layer):
    """
    Return whether layer is temporal,

    There currently does not seem to exist a qgis mesh layer attribute that
    indicates whether there is a temporal dataset stored in a layer.
    If there is one, this function is obsolete.
    """

    return any(get_group_is_temporal(layer))
