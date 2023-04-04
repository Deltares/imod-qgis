import struct

import numpy as np

from osgeo import gdal


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


def convert_gdal_to_idf(path: str, idf_path: str, dtype):
    try:
        raster = gdal.Open(path)
        xmin, dx, x_rotation, ymax, y_rotation, dy = raster.GetGeoTransform()
        band = raster.GetRasterBand(1)
        values = band.ReadAsArray()
        nodata = band.GetNoDataValue()
        nband = raster.RasterCount
    finally:
        # Make sure GDAL closes the raster.
        try:
            del band
        except Exception:
            pass

        try:
            del raster
        except Exception:
            pass

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
