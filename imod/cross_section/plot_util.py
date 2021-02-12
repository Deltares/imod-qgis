import math
from qgis.core import QgsMeshDatasetIndex

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

def cross_section_plot_data(layer, ds_group_index, ds_index, geometry, resolution=1.):
    """ return array with tuples defining X,Y points for plot """
    x,y = [], []
    if not layer:
        return x, y

    dataset = QgsMeshDatasetIndex(ds_group_index, ds_index)
    offset = 0
    length = geometry.length()
    while offset < length:
        pt = geometry.interpolate(offset).asPoint()
        value = layer.datasetValue(dataset, pt).scalar()
        if not pyqtGraphAcceptNaN and math.isnan(value):
            value = 0
        x.append(offset)
        y.append(value)
        offset += resolution

    # let's make sure we include also the last point
    last_pt = geometry.asPolyline()[-1]
    last_value = layer.datasetValue(dataset, last_pt).scalar()

    if not pyqtGraphAcceptNaN and math.isnan(last_value):
        last_value = 0

    x.append(length)
    y.append(last_value)

    return x,y
