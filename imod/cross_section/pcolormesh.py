from __future__ import division

from PyQt5.QtGui import QColor
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
from pyqtgraph import functions as fn
from pyqtgraph.graphicsItems.GraphicsObject import GraphicsObject
from pyqtgraph.Point import Point
from pyqtgraph import getConfigOption


class PColorMeshItem(GraphicsObject):
    def __init__(self, *args, **kwargs):
        """
        Create a pseudocolor plot with convex polygons.
        Modified from: https://github.com/pyqtgraph/pyqtgraph/blob/5eb671217c295178de255b1fece56379cdef8235/pyqtgraph/graphicsItems/PColorMeshItem.py

        Parameters
        ----------
        x: np.ndarray
            1D array containing the horizontal coordinates of the polygons
        top, bottom : np.ndarray, optional, default None
            2D array containing the vertical coordinates of the polygons
        z : np.ndarray
            2D array containing the value which will be maped into the polygons
            colors.

            Polygon vertices:

                (x[j], top[1, j])         (x[j+1], top[i, j+1])
                                +---------+
                                | z[i, j] |
                                +---------+
                (x[j], bottom[i, j])      (x[j+1], bottom[i, j+1])

        colorshader : Union[QgsColorShader, ImodColorShader]
            Colorramp used to map the z value to colors.
        edgecolors : dict, default None
            The color of the edges of the polygons.
            Default None means no edges.
            The dict may contains any arguments accepted by :func:`mkColor() <pyqtgraph.mkColor>`.
            Example:

                ``mkPen(color='w', width=2)``

        antialiasing : bool, default False
            Whether to draw edgelines with antialiasing.
            Note that if edgecolors is None, antialiasing is always False.
        """

        GraphicsObject.__init__(self)
        self.qpicture = None  ## rendered picture for display
        self.axisOrder = getConfigOption('imageAxisOrder')

        if 'edgecolors' in kwargs.keys():
            self.edgecolors = kwargs['edgecolors']
        else:
            self.edgecolors = None

        if 'antialiasing' in kwargs.keys():
            self.antialiasing = kwargs['antialiasing']
        else:
            self.antialiasing = False

        if 'colorshader' not in kwargs.keys():
            raise ValueError("colorshader not provided")
        else:
            self.colorshader = kwargs['colorshader']

        # If some data have been sent we directly display it
        if len(args)>0:
            self.setData(*args)

    def _prepareData(self, x, top, bottom, z):
        """
        Check the shape of the data.
        Return a set of 2d array x, y, z ready to be used to draw the picture.
        """
        if not top.shape == bottom.shape:
            raise ValueError(
                "top and bottom must have same shape. "
                f"Got instead: {top.shape} versus {bottom.shape}"
            )
        if not len(top.shape) == 2:
            raise ValueError("top and bottom must be 2D")
        if not len(z.shape) == 2:
            raise ValueError("z must be 2D")
        if not len(x.shape) == 1:
            raise ValueError("x must be 1D")
        if not x.shape[0] == top.shape[1]:
            raise ValueError(
                "top and bottom must have same size along second dimension as x. "
                f"Got instead {top.shape} versus {x.shape}"
            )
        if not z.shape[1] == (x.shape[0] - 1):
            raise ValueError(
                "z must be one smaller along second dimension than x. "
                f"Got instead {z.shape} versus {x.shape}"
            )
        self.x = x
        self.top = top
        self.bottom = bottom
        self.z = z

    def setData(self, x, top, bottom, z):
        """
        Set the data to be drawn.

        Parameters
        ----------
        x: np.ndarray
            1D array containing the horizontal coordinates of the polygons
        top, bottom : np.ndarray, optional, default None
            2D array containing the vertical coordinates of the polygons
        z : np.ndarray
            2D array containing the value which will be maped into the polygons
            colors.

            Polygon vertices:

                (x[j], top[1, j])         (x[j+1], top[i, j+1])
                                +---------+
                                | z[i, j] |
                                +---------+
                (x[j], bottom[i, j])      (x[j+1], bottom[i, j+1])
        """
        self._prepareData(x, top, bottom, z)
        self.qpicture = QtGui.QPicture()
        painter = QtGui.QPainter(self.qpicture)
        # We set the pen of all polygons once
        if self.edgecolors is None:
            painter.setPen(fn.mkPen(QtGui.QColor(0, 0, 0, 0)))
        else:
            painter.setPen(fn.mkPen(self.edgecolors))
            if self.antialiasing:
                painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Go through all the data and draw the polygons accordingly
        for yi in range(self.z.shape[0]):
            for xi in range(z.shape[1]):
                left = self.x[xi]
                right = self.x[xi + 1]
                upper = self.top[yi, xi]
                lower = self.bottom[yi, xi]
                value = self.z[yi, xi]
                to_draw, r, g, b, alpha = self.colorshader.shade(value)
                to_draw = to_draw and not any(np.isnan(e) for e in (left, right, upper, lower, value))
                if not to_draw:
                    continue
                color = QColor(r, g, b, alpha)
                painter.setBrush(fn.mkBrush(color))
                polygon = QtGui.QPolygonF(
                    [
                        QtCore.QPointF(left, lower),
                        QtCore.QPointF(right, lower),
                        QtCore.QPointF(right, upper),
                        QtCore.QPointF(left, upper),
                     ],
                )
                painter.drawConvexPolygon(polygon)

        painter.end()
        self.update()
        self.prepareGeometryChange()
        self.informViewBoundsChanged()

    def paint(self, p, *args):
        if self.z is None:
            return
        p.drawPicture(0, 0, self.qpicture)

    def setBorder(self, b):
        self.border = fn.mkPen(b)
        self.update()

    def width(self):
        if self.x is None:
            return None
        return np.max(self.x)

    def height(self):
        if self.y is None:
            return None
        return np.max(self.y)

    def boundingRect(self):
        if self.qpicture is None:
            return QtCore.QRectF(0., 0., 0., 0.)
        return QtCore.QRectF(self.qpicture.boundingRect())
