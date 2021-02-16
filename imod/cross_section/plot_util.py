#Modified from https://github.com/lutraconsulting/qgis-crayfish-plugin/blob/54fa4691eab5adbe0ba419d907544760000fc9a5/crayfish/plot.py#L101

import math
from qgis.core import QgsMeshDatasetIndex

import numpy as np

from PyQt5.Qt import PYQT_VERSION_STR

def check_if_PyQt_version_is_before(M,m,r):
    strVersion=PYQT_VERSION_STR
    num=strVersion.split('.')
    numM=int(num[0])
    numm = int(num[1])
    numr = int(num[2])
    return  numM < M or (numM == M and numm < m) or (numM == M and numm < m and numr < r)


# see https://github.com/pyqtgraph/pyqtgraph/issues/1057
pyqtGraphAcceptNaN = check_if_PyQt_version_is_before(5, 13, 1)

def cross_section_x_data(layer, geometry, resolution=1.):
    """ return list defining X points for plot """
    x = []
    if not layer:
        return x

    offset = 0
    length = geometry.length()

    while offset < length:
        x.append(offset)
        offset += resolution

    # let's make sure we include also the last point
    x.append(length)
    
    return np.array(x)

def cross_section_y_data(layer, geometry, dataset, x):
    """ return array defining Y points for plot """
    y = np.zeros(x.shape)
    if not layer:
        return y

    #TODO: This seems quite brute force. Is there a faster way to do this? Some raytracing algorithm?
    for i, x_value in enumerate(x):
        pt = geometry.interpolate(x_value).asPoint()
        y[i] = layer.datasetValue(dataset, pt).scalar()
        if not pyqtGraphAcceptNaN and math.isnan(y[i]):
            continue

    return y

def cross_section_hue_data(layer, geometry, dataset, x):
    return cross_section_y_data(layer, geometry, dataset, x)