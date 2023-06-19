# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import struct
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import numpy as np
from osgeo import gdal


class NewGeoTiff:
    """
    Implements enter and exit to make sure the GDAL dataset is closed.
    """

    def __init__(self, path: str, nrow: int, ncol: int, dtype: type):
        self.__raster__ = None
        self.path = path
        self.nrow = nrow
        self.ncol = ncol
        if dtype == "float32":
            self.gdal_dtype = gdal.GDT_Float32
        elif dtype == "float64":
            self.gdal_dtype = gdal.GDT_Float64
        else:
            raise TypeError(f"IDF dtype should be float32 or float64. Got {dtype}")

    def __enter__(self):
        driver = gdal.GetDriverByName("GTiff")
        self.__raster__ = driver.Create(
            self.path, self.ncol, self.nrow, 1, self.gdal_dtype
        )
        return self

    def __exit__(self, *_):
        self.__raster__ = None

    def set_transform(self, xmin: float, dx: float, ymax: float, dy: float) -> None:
        self.__raster__.SetGeoTransform((xmin, dx, 0.0, ymax, 0.0, dy))

    def set_crs(self, crs_wkt: str) -> None:
        self.__raster__.SetProjection(crs_wkt)

    def write_array(self, values: np.ndarray, nodata: float) -> None:
        band = self.__raster__.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        band.WriteArray(values)
        band.FlushCache()


class ReadOnlyRaster:
    """
    Implements enter and exit to make sure the GDAL dataset is closed.
    """

    def __init__(self, path: str):
        self.__raster__ = None
        self.path = path

    def __enter__(self):
        self.__raster__ = gdal.Open(self.path)
        return self

    def __exit__(self, *_):
        self.__raster__ = None

    def get_transform(self) -> Tuple[float]:
        return self.__raster__.GetGeoTransform()

    def read_array(self) -> Tuple[np.ndarray, Union[int, float, None]]:
        band = self.__raster__.GetRasterBand(1)
        values = band.ReadAsArray()
        nodata = band.GetNoDataValue()
        return values, nodata

    @property
    def nband(self) -> int:
        return self.__raster__.RasterCount


def read_idf(path: str) -> Tuple[Dict[str, Any], np.ndarray]:
    """Read the IDF header information into a dictionary"""
    attrs = {}
    with open(path, "rb") as f:
        reclen_id = struct.unpack("i", f.read(4))[0]  # Lahey RecordLength Ident.
        if reclen_id == 1271:
            floatsize = intsize = 4
            floatformat = "f"
            intformat = "i"
            dtype = "float32"
            doubleprecision = False
        elif reclen_id == 2295:
            floatsize = intsize = 8
            floatformat = "d"
            intformat = "q"
            dtype = "float64"
            doubleprecision = True
        else:
            raise ValueError(
                f"Not a supported IDF file: {path}\n"
                "Record length identifier should be 1271 or 2295, "
                f"received {reclen_id} instead."
            )

        # Header is fully doubled in size in case of double precision ...
        # This means integers are also turned into 8 bytes
        # and requires padding with some additional bytes
        if doubleprecision:
            f.read(4)  # not used

        ncol = struct.unpack(intformat, f.read(intsize))[0]
        nrow = struct.unpack(intformat, f.read(intsize))[0]
        attrs["xmin"] = struct.unpack(floatformat, f.read(floatsize))[0]
        attrs["xmax"] = struct.unpack(floatformat, f.read(floatsize))[0]
        attrs["ymin"] = struct.unpack(floatformat, f.read(floatsize))[0]
        attrs["ymax"] = struct.unpack(floatformat, f.read(floatsize))[0]
        # dmin and dmax are recomputed during writing
        f.read(floatsize)  # dmin, minimum data value present
        f.read(floatsize)  # dmax, maximum data value present
        nodata = struct.unpack(floatformat, f.read(floatsize))[0]
        attrs["nodata"] = nodata
        # flip definition here such that True means equidistant
        # equidistant IDFs
        ieq = not struct.unpack("?", f.read(1))[0]
        itb = struct.unpack("?", f.read(1))[0]
        if not ieq:
            raise ValueError(f"Non-equidistant IDF are not supported: {path}\n")

        f.read(2)  # not used
        if doubleprecision:
            f.read(4)  # not used

        # dx and dy are stored positively in the IDF
        # dy is made negative here to be consistent with the nonequidistant case
        attrs["dx"] = struct.unpack(floatformat, f.read(floatsize))[0]
        attrs["dy"] = -struct.unpack(floatformat, f.read(floatsize))[0]

        if itb:
            attrs["top"] = struct.unpack(floatformat, f.read(floatsize))[0]
            attrs["bot"] = struct.unpack(floatformat, f.read(floatsize))[0]

        # These are derived, remove after using them downstream
        attrs["ncol"] = ncol
        attrs["nrow"] = nrow
        attrs["dtype"] = dtype

        values = np.reshape(np.fromfile(f, dtype, nrow * ncol), (nrow, ncol))

    return attrs, values


def write(path, a, spatial_reference, nodata=1.0e20, dtype=np.float32):
    """
    Write a 2D numpy array to an IDF file.

    Parameters
    ----------
    path : str or Path
        Path to the IDF file to be written
    a : np.ndarray
    spatial_reference: tuple
        dx, xmin, xmax, dy, ymin, ymax
    nodata : float, optional
        Nodata value in the saved IDF files. Xarray uses nan values to represent
        nodata, but these tend to work unreliably in iMOD(FLOW).
        Defaults to a value of 1.0e20.
    dtype : type, ``{np.float32, np.float64}``, default is ``np.float32``.
        Whether to write single precision (``np.float32``) or double precision
        (``np.float64``) IDF files.
    """
    if a.ndim != 2:
        raise ValueError("Array to write must be 2D.")

    # Header is fully doubled in size in case of double precision ...
    # This means integers are also turned into 8 bytes
    # and requires padding with some additional bytes
    data_dtype = a.dtype
    if dtype == np.float64:
        if data_dtype != np.float64:
            a = a.astype(np.float64)
        reclenid = 2295
        floatformat = "d"
        intformat = "q"
        doubleprecision = True
    elif dtype == np.float32:
        reclenid = 1271
        floatformat = "f"
        intformat = "i"
        doubleprecision = False
        if data_dtype != np.float32:
            a = a.astype(np.float32)
    else:
        raise ValueError("Invalid dtype, IDF allows only np.float32 and np.float64")

    with open(path, "wb") as f:
        f.write(struct.pack("i", reclenid))  # Lahey RecordLength Ident.
        if doubleprecision:
            f.write(struct.pack("i", reclenid))
        nrow, ncol = a.shape
        f.write(struct.pack(intformat, ncol))
        f.write(struct.pack(intformat, nrow))

        dx, xmin, xmax, dy, ymin, ymax = spatial_reference
        f.write(struct.pack(floatformat, xmin))
        f.write(struct.pack(floatformat, xmax))
        f.write(struct.pack(floatformat, ymin))
        f.write(struct.pack(floatformat, ymax))
        f.write(struct.pack(floatformat, float(a.min())))  # dmin
        f.write(struct.pack(floatformat, float(a.max())))  # dmax
        f.write(struct.pack(floatformat, nodata))

        ieq = True  # equidistant
        f.write(struct.pack("?", not ieq))  # ieq

        itb = False
        f.write(struct.pack("?", itb))
        f.write(struct.pack("xx"))  # not used
        if doubleprecision:
            f.write(struct.pack("xxxx"))  # not used

        f.write(struct.pack(floatformat, abs(dx)))
        f.write(struct.pack(floatformat, abs(dy)))
        a.tofile(f)
    return


def convert_idf_to_gdal(path: str, crs_wkt: str) -> Path:
    """
    Read the contents of an iMOD IDF file and write it to a GeoTIFF, next to
    the IDF. This is similar to how iMOD treats ASCII files.

    Parameters
    ----------
    path: str
        Path to the IDF file.
    crs_wkt: str
        Desired CRS to write in the created GeoTIFF. IDFs do not have a CRS on
        their own, one must be provided.

    Returns
    -------
    tiff_path: pathlib.Path
        Path to the newly created GeoTIFF file.
    """
    attrs, values = read_idf(path)

    path = Path(path)
    tiff_path = (path.parent / (path.stem)).with_suffix(".tif")
    with NewGeoTiff(
        path=str(tiff_path),
        nrow=attrs["nrow"],
        ncol=attrs["ncol"],
        dtype=values.dtype,
    ) as raster:
        raster.set_transform(
            xmin=attrs["xmin"],
            dx=attrs["dx"],
            ymax=attrs["ymax"],
            dy=attrs["dy"],
        )
        raster.set_crs(crs_wkt)
        raster.write_array(values, attrs["nodata"])

    return tiff_path


def convert_gdal_to_idf(path: str, idf_path: str, dtype):
    """
    Read the content of a single-band GDAL supported raster file and write it
    to an IDF file.

    Parameters
    ----------
    path: str
        Path to the GDAL raster file.
    idf_path: str
        Path to the IDF file that will be created.
    dtype: np.float32 or np.float64
        Data type of the output IDF file.
    """
    with ReadOnlyRaster(path) as raster:
        xmin, dx, x_rotation, ymax, y_rotation, dy = raster.get_transform()
        values, nodata = raster.read_array()
        nband = raster.nband

    if x_rotation != 0 or y_rotation != 0:
        raise ValueError("IDFs do not support rotated rasters")
    if nband != 1:
        raise ValueError("IDFs can contain only the data of a single band")

    nrow, ncol = values.shape
    xmax = xmin + dx * ncol
    ymin = ymax + dy * nrow

    # Make sure the IDF nodata value is supported.
    IDF_NODATA = 1.0e20
    if nodata is None:
        pass
    elif np.isnan(nodata):
        values[np.isnan(nodata)] = IDF_NODATA
    else:
        values[values == nodata] = IDF_NODATA

    write(
        path=idf_path,
        a=values.astype(dtype),
        spatial_reference=(dx, xmin, xmax, dy, ymin, ymax),
        nodata=IDF_NODATA,
        dtype=dtype,
    )
    return
