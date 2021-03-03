# Modified from https://github.com/lutraconsulting/qgis-crayfish-plugin/blob/54fa4691eab5adbe0ba419d907544760000fc9a5/crayfish/plot.py#L101

import math
from typing import List
from qgis.core import QgsMeshDatasetIndex, QgsGeometry, QgsPoint

import numpy as np

from PyQt5.Qt import PYQT_VERSION_STR


def check_if_PyQt_version_is_before(M, m, r):
    strVersion = PYQT_VERSION_STR
    num = strVersion.split(".")
    numM = int(num[0])
    numm = int(num[1])
    numr = int(num[2])
    return numM < M or (numM == M and numm < m) or (numM == M and numm < m and numr < r)


# see https://github.com/pyqtgraph/pyqtgraph/issues/1057
pyqtGraphAcceptNaN = check_if_PyQt_version_is_before(5, 13, 1)


def cross_section_x_data(layer, geometry, resolution=1.0):
    """return list defining X points for plot """
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


def cross_section_y_data(layer, geometry, dataset_index, x):
    """ return array defining Y points for plot """
    y = np.zeros(x.shape)
    if not layer:
        return y

    # TODO: This seems quite brute force. Is there a faster way to do this? Some raytracing algorithm?
    for i, x_value in enumerate(x):
        pt = geometry.interpolate(x_value).asPoint()
        y[i] = layer.datasetValue(dataset_index, pt).scalar()
        if not pyqtGraphAcceptNaN and math.isnan(y[i]):
            continue

    return y


def project_points_to_section(points: List[QgsPoint], geometry: QgsGeometry) -> np.ndarray:
    # vectors are denoted by upper case: U, V
    # scalar variables are lower case: a, p, s, x
    # arrays of scalars are repeated lower case: pp, aa, bb, tt
    #
    #   q              r
    #     \           /
    #      a---------c
    #     /|
    #    / |
    #   /  |
    #  p - x
    #      |
    #      b
    #
    # a, b, c are vertices of a line segment in geometry
    # p, q are points to project on to this geometry
    # vector U = a -> p
    # vector V = a -> b
    # x is the projection of p on V
    # s is length of vector V
    # t is length along V
    #
    # Note that when q is projected, its t will be outside of [0.0 - s]
    # In this case, it will be projected at the location of a (t=0.0).
    # Similarly, r will have its t > 1.0, and will be projected at c (t=s)
    vertices = np.array([(v.x(), v.y()) for v in geometry.vertices()])
    pp = np.array([(point.x(), point.y()) for point in points])
    aa = vertices[:-1]
    bb = vertices[1:]
    nsegment = len(aa)
    npoint = len(pp)
  
    # This array holds the distance from p to x
    distances = np.empty((nsegment, npoint), dtype=np.float)
    # x is the accumulating distance along the geometry
    xx = np.empty((nsegment, npoint), dtype=np.float)
    x = 0.0
    for i, (a, b) in enumerate(zip(aa, bb)):
        U = pp - a
        V = b - a
        s = np.linalg.norm(V)
        tt = np.dot(U, V) / s
        tt[tt < 0.0] = 0.0
        tt[tt > s] = s 
        xx[i] = x + tt
        distances[i] = np.sqrt(s ** 2 - tt ** 2)
        x += s
    # Find the intersection point with the minimum distance
    closest = np.argmin(distances, axis=0)
    return xx[closest, np.arange(npoint)]
