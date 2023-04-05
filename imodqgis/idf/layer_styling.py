# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
from typing import List

from qgis.core import (
    QgsColorRampShader,
    QgsRasterBandStats,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
)


def color_ramp_items(
    colormap: str, minimum: float, maximum: float, nclass: int
) -> List[QgsColorRampShader.ColorRampItem]:
    """
    Parameters
    ----------
    colormap: str
        Name of QGIS colormap
    minimum: float
    maximum: float
    nclass: int
        Number of colormap classes to create

    Returns
    -------
    color_ramp: QgsGradientColorRamp
    color_ramp_items: List[QgsColorRampShader.ColorRampItem]
        Can be used directly by the QgsColorRampShader
    """
    delta = maximum - minimum
    fractional_steps = [i / nclass for i in range(nclass + 1)]
    ramp = QgsStyle().defaultStyle().colorRamp(colormap)
    colors = [ramp.color(f) for f in fractional_steps]
    steps = [minimum + f * delta for f in fractional_steps]
    return ramp, [
        QgsColorRampShader.ColorRampItem(step, color, str(step))
        for step, color in zip(steps, colors)
    ]


def pseudocolor_renderer(
    layer, band: int, colormap: str, nclass: int
) -> QgsSingleBandPseudoColorRenderer:
    """
    Parameters
    ----------
    layer: QGIS map layer
    band: int
        band number of the raster to create a renderer for
    colormap: str
        Name of QGIS colormap
    nclass: int
        Number of colormap classes to create

    Returns
    -------
    renderer: QgsSingleBandPseudoColorRenderer
    """
    stats = layer.dataProvider().bandStatistics(band, QgsRasterBandStats.All)
    minimum = stats.minimumValue
    maximum = stats.maximumValue

    ramp, ramp_items = color_ramp_items(colormap, minimum, maximum, nclass)
    shader_function = QgsColorRampShader()
    shader_function.setMinimumValue(minimum)
    shader_function.setMaximumValue(maximum)
    shader_function.setSourceColorRamp(ramp)
    shader_function.setColorRampType(QgsColorRampShader.Interpolated)
    shader_function.setClassificationMode(QgsColorRampShader.EqualInterval)
    shader_function.setColorRampItemList(ramp_items)

    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(shader_function)

    return QgsSingleBandPseudoColorRenderer(layer.dataProvider(), band, raster_shader)
