import re

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import struct
import numpy as np

from osgeo import gdal


try:
    Pattern = re._pattern_type
except AttributeError:
    Pattern = re.Pattern  # Python 3.7+


DATETIME_FORMATS = {
    14: "%Y%m%d%H%M%S",
    12: "%Y%m%d%H%M",
    10: "%Y%m%d%H",
    8: "%Y%m%d",
    4: "%Y",
}


def to_datetime(s: str) -> datetime:
    try:
        time = datetime.strptime(s, DATETIME_FORMATS[len(s)])
    except (ValueError, KeyError):  # Try fullblown dateutil date parser
        raise ValueError(f"Unsupported datetime format: {s}")
    return time


def _groupdict(stem: str, pattern: str) -> Dict[str, str]:
    if pattern is not None:
        if isinstance(pattern, Pattern):
            d = pattern.match(stem).groupdict()
        else:
            pattern = pattern.lower()
            # Get the variables between curly braces
            in_curly = re.compile(r"{(.*?)}").findall(pattern)
            regex_parts = {key: f"(?P<{key}>[\\w.-]+)" for key in in_curly}
            # Format the regex string, by filling in the variables
            simple_regex = pattern.format(**regex_parts)
            re_pattern = re.compile(simple_regex)
            # Use it to get the required variables
            d = re_pattern.match(stem).groupdict()
    else:  # Default to "iMOD conventions": {name}_c{species}_{time}_l{layer}
        has_layer = bool(re.search(r"_l\d+$", stem))
        has_species = bool(
            re.search(r"conc_c\d{1,3}_\d{8,14}", stem)
        )  # We are strict in recognizing species
        try:  # try for time
            base_pattern = r"(?P<name>[\w-]+)"
            if has_species:
                base_pattern += r"_c(?P<species>[0-9]+)"
            base_pattern += r"_(?P<time>[0-9-]{6,})"
            if has_layer:
                base_pattern += r"_l(?P<layer>[0-9]+)"
            re_pattern = re.compile(base_pattern)
            d = re_pattern.match(stem).groupdict()
        except AttributeError:  # probably no time
            base_pattern = r"(?P<name>[\w-]+)"
            if has_species:
                base_pattern += r"_c(?P<species>[0-9]+)"
            if has_layer:
                base_pattern += r"_l(?P<layer>[0-9]+)"
            re_pattern = re.compile(base_pattern)
            d = re_pattern.match(stem).groupdict()
    return d


def decompose(path, pattern: str = None) -> Dict[str, Any]:
    r"""
    Parse a path, returning a dict of the parts, following the iMOD conventions.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the file. Upper case is ignored.
    pattern : str, regex pattern, optional
        If the path is not made up of standard paths, and the default decompose
        does not produce the right result, specify the used pattern here. See
        the examples below.

    Returns
    -------
    d : dict
        Dictionary with name of variable and dimensions

    Examples
    --------
    Decompose a path, relying on default conventions:

    >>> decompose("head_20010101_l1.idf")

    Do the same, by specifying a format string pattern, excluding extension:

    >>> decompose("head_20010101_l1.idf", pattern="{name}_{time}_l{layer}")

    This supports an arbitrary number of variables:

    >>> decompose("head_slr_20010101_l1.idf", pattern="{name}_{scenario}_{time}_l{layer}")

    The format string pattern will only work on tidy paths, where variables are
    separated by underscores. You can also pass a compiled regex pattern.
    Make sure to include the ``re.IGNORECASE`` flag since all paths are lowered.

    >>> import re
    >>> pattern = re.compile(r"(?P<name>[\w]+)L(?P<layer>[\d+]*)")
    >>> decompose("headL11", pattern=pattern)

    However, this requires constructing regular expressions, which is generally
    a fiddly process. The website https://regex101.com is a nice help.
    Alternatively, the most pragmatic solution may be to just rename your files.
    """
    path = Path(path)
    # We'll ignore upper case
    stem = path.stem.lower()

    d = _groupdict(stem, pattern)
    dims = list(d.keys())
    # If name is not provided, generate one from other fields
    if "name" not in d.keys():
        d["name"] = "_".join(d.values())
    else:
        dims.remove("name")

    # TODO: figure out what to with user specified variables
    # basically type inferencing via regex?
    # if purely numerical \d* -> int or float
    #    if \d*\.\d* -> float
    # else: keep as string

    # String -> type conversion
    if "layer" in d.keys():
        d["layer"] = int(d["layer"])
    if "time" in d.keys():
        d["time"] = to_datetime(d["time"])
    if "steady-state" in d["name"]:
        # steady-state as time identifier isn't picked up by <time>[0-9] regex
        d["name"] = d["name"].replace("_steady-state", "")
        d["time"] = "steady-state"
        dims.append("time")

    d["extension"] = path.suffix
    d["directory"] = path.parent
    d["dims"] = dims
    return d


def read_idf(path: str, pattern: str) -> Tuple[Dict[str, Any], np.ndarray]:
    """Read the IDF header information into a dictionary"""
    attrs = decompose(path, pattern)
    with open(path, "rb") as f:
        reclen_id = struct.unpack("i", f.read(4))[0]  # Lahey RecordLength Ident.
        if reclen_id == 1271:
            floatsize = intsize = 4
            floatformat = "f"
            intformat = "i"
            dtype = "float32"
            doubleprecision = False
        # 2296 was a typo in the iMOD manual. Keep 2296 around in case some IDFs
        # were written with this identifier to avoid possible incompatibility
        # issues.
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
    time: datetime.datetime or None
        The datetime encoded in the IDF filename.
    """
    attrs, values = read_idf(path, pattern=None)
    dtype = values.dtype
    if dtype == "float32":
        gdal_dtype = gdal.GDT_Float32
    elif dtype == "float64":
        gdal_dtype = gdal.GDT_Float64
    else:
        raise TypeError(f"IDF dtype should be float32 or float64. Got {dtype}")

    path = Path(path)
    tiff_path = (path.parent / (path.stem)).with_suffix(".tif")
    driver = gdal.GetDriverByName("GTiff")

    try:
        raster = driver.Create(
            str(tiff_path), attrs["ncol"], attrs["nrow"], 1, gdal_dtype
        )
        raster.SetGeoTransform(
            (attrs["xmin"], attrs["dx"], 0.0, attrs["ymax"], 0.0, attrs["dy"])
        )
        raster.SetProjection(crs_wkt)
        band = raster.GetRasterBand(1)
        band.SetNoDataValue(attrs["nodata"])
        band.WriteArray(values)
        band.FlushCache()
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

    return tiff_path
