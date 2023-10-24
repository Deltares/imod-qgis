from PyQt5.QtGui import QColor

from qgis.core import (
    QgsGradientStop,
    QgsGradientColorRamp
)
import numpy as np

from typing import List


def create_colorramp(
        boundaries: List[float],
        colors: List[QColor],
        discrete: bool = False,
    ):
    """
    Manually construct colorramp from boundaries and colors. The stops
    determined by the createColorRamp method appear to be broken.
    """

    # For some reason discrete colormaps require the last color also added as
    # stop
    if discrete:
        indices_stops = slice(1, None)
    else:
        indices_stops = slice(1, -1)

    bound_arr = np.array(boundaries)
    boundaries_norm = (bound_arr-bound_arr[0])/(bound_arr[-1]-bound_arr[0])
    stops = [
        QgsGradientStop(stop, color) for stop, color in zip(
            boundaries_norm[indices_stops], colors[indices_stops]
        )
    ]
    return QgsGradientColorRamp(colors[0], colors[-1], discrete, stops)
