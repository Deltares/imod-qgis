from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
from pyqtgraph import functions as fn
from pyqtgraph.graphicsItems.GraphicsObject import GraphicsObject
from pyqtgraph.Point import Point
from pyqtgraph import getConfigOption
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients  # List of colormaps
from pyqtgraph.colormap import ColorMap


class BoreholePlotItem(GraphicsObject):
    def __init__(self, *args, **kwargs):
        """
        Parameters
        ----------
        x: np.ndarray
            1D array containing the horizontal coordinates
        y: list of np.ndarray
            list of 1D array containing the vertical coordinates
        z: list of np.ndarray
            list of 1D array containing which value will be mapped into the
            rectangle colors
        width: float
            with of the boreholes
        """
        GraphicsObject.__init__(self)
        self.qpicture = None
        self.axisOrder = getConfigOption("imageAxisOrder")
        self.edgecolors = kwargs.pop("edgecolors", None)
        if len(args) > 0:
            self.setData(*args)

    def _prepareData(self, x, y, z, width):
        if not (len(x) == len(y) == len(z)):
            raise ValueError("Lengths of x, y, z must match")
        self.x = x
        self.y = y
        self.z = z
        self.borehole_width = width

    def setData(self, x, y, z, width):
        self._prepareData(x, y, z, width)
        self.qpicture = QtGui.QPicture()
        p = QtGui.QPainter(self.qpicture)
        if self.edgecolors is None:
            p.setPen(fn.mkPen(QtGui.QColor(0, 0, 0, 0)))
        else:
            p.setPen(fn.mkPen(self.edgecolors))

        for midx, topbot in zip(self.x, self.y):
            left = midx - 0.5 * self.borehole_width
            right = midx + 0.5 * self.borehole_width
            for top, bottom in zip(topbot[:-1], topbot[1:]):
                r = np.random.randint(low=0, high=255)
                g = np.random.randint(low=0, high=255)
                b = np.random.randint(low=0, high=255)
                p.setBrush(fn.mkBrush(QtGui.QColor(r, g, b)))
                rect = QtCore.QRectF(
                    QtCore.QPointF(left, top),
                    QtCore.QPointF(right, bottom),
                )
                p.drawRect(rect)

        p.end()
        self.update()

    def paint(self, p, *args):
        if self.x is None or self.y is None or self.z is None:
            return
        p.drawPicture(0, 0, self.qpicture)

    def setBorder(self, b):
        self.border = fn.mkPen(b)
        self.update()

    def width(self):
        if self.x is None:
            return None
        return np.max(self.x) + 0.5 * self.borehole_width

    def height(self):
        if self.y is None:
            return None
        return np.max(self.y)

    def boundingRect(self):
        if self.qpicture is None:
            return QtCore.QRectF(0.0, 0.0, 0.0, 0.0)
        return QtCore.QRectF(self.qpicture.boundingRect())
