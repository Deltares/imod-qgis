# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
import csv
import io
import pathlib
from enum import IntEnum
from typing import Any, List, TextIO, Tuple

import numpy as np
import pandas as pd


class IpfType(IntEnum):
    TIMESERIES = 1
    BOREHOLE = 2


def read_ipf_header(path: pathlib.Path) -> Tuple[int, int, List[str], int, str]:
    with open(path) as f:
        nrow = int(f.readline().strip())
        ncol = int(f.readline().strip())
        colnames = [f.readline().strip().strip("'").strip('"') for _ in range(ncol)]
        line = f.readline()
        indexcol, ext = map(str.strip, next(csv.reader([line])))
    indexcol = int(indexcol) - 1  # Python is 0-based
    return nrow, ncol, colnames, indexcol, ext


def read_ipf(path: str, **kwargs) -> Tuple[pd.DataFrame, str]:
    """
    Read one IPF file to a single pandas.DataFrame

    Parameters
    ----------
    path: pathlib.Path or str
        globpath for IPF files to read.
    **kwargs : keyword arguments
        Forwarded as keyword arguments to ``pandas.read_csv()``
    """
    path = pathlib.Path(path)
    with open(path) as f:
        nrow = int(f.readline().strip())
        ncol = int(f.readline().strip())
        colnames = [f.readline().strip().strip("'").strip('"') for _ in range(ncol)]
        line = f.readline()
        indexcol, ext = map(str.strip, next(csv.reader([line])))

        position = f.tell()
        line = f.readline()
        f.seek(position)

        ipf_kwargs = {
            "delim_whitespace": False,
            "header": None,
            "names": colnames,
            "nrows": nrow,
            "skipinitialspace": True,
        }
        ipf_kwargs.update(kwargs)
        df = pd.read_csv(f, **ipf_kwargs)

    # Standardize column names
    xcol, ycol = df.columns[:2]
    idcol = df.columns[int(indexcol) - 1]  # IPFs are 1-based, python is 0-based
    return df.rename(columns={xcol: "x", ycol: "y", idcol: "indexcolumn"}), ext


def read_associated_header(
    f: TextIO,
) -> Tuple[int, int, List[int], List[str], List[Any]]:
    nrow = int(f.readline().strip())
    line = f.readline()
    try:
        # csv.reader parse one line
        # this catches commas in quotes
        ncol, itype = map(int, map(str.strip, next(csv.reader([line]))))
        itype = IpfType(itype)
    # itype can be implicit, in which case it's a timeseries
    except ValueError:
        ncol = int(line.strip())
        itype = IpfType.TIMESERIES

    # use pandas for csv parsing: stuff like commas within quotes
    # Can't use pandas with the file handle directly, due to a pandas bug
    lines = "".join([f.readline() for _ in range(ncol)])
    metadata = pd.read_csv(
        io.StringIO(lines),
        delim_whitespace=False,
        header=None,
        nrows=ncol,
        skipinitialspace=True,
    )

    # header description possibly includes nodata
    usecols = np.arange(ncol)[pd.notna(metadata[0])]
    metadata = metadata.iloc[usecols, :]
    # Collect column names and nodata values
    colnames = []
    na_values = {}
    for colname, nodata in metadata.to_numpy():
        na_values[colname] = [nodata, "-"]  # "-" seems common enough to ignore
        if isinstance(colname, str):
            colnames.append(colname.strip())
        else:
            colnames.append(colname)

    return itype, nrow, usecols, colnames, na_values


def read_associated_timeseries(path: str, **kwargs) -> pd.DataFrame:
    """
    Read an IPF associated timeseries file (TXT), itype=1.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to associated file.
    kwargs : dict
        Dictionary containing the ``pandas.read_csv()`` keyword arguments for the
        associated (TXT) file (e.g. `{"delim_whitespace": True}`).

    Returns
    -------
    pandas.DataFrame
    """

    # deal with e.g. incorrect capitalization
    path = pathlib.Path(path).resolve()

    with open(path) as f:
        itype, nrow, usecols, colnames, na_values = read_associated_header(f)
        if itype != IpfType.TIMESERIES:
            raise ValueError(f"{path.name}: has itype {itype} and is not a timeseries")

        itype_kwargs = {
            "delim_whitespace": False,
            "header": None,
            "names": colnames,
            "usecols": usecols,
            "nrows": nrow,
            "na_values": na_values,
            "skipinitialspace": True,
            "dtype": {colnames[0]: str},  # yyyymmdd or yyyymmddhhmmss
        }
        itype_kwargs.update(kwargs)
        df = pd.read_csv(f, **itype_kwargs)

        time_column = colnames[0]
        len_date = len(df[time_column].iloc[0])
        if len_date == 14:
            df.index = pd.to_datetime(df[time_column], format="%Y%m%d%H%M%S")
        elif len_date == 8:
            df.index = pd.to_datetime(df[time_column], format="%Y%m%d")
        else:
            raise ValueError(
                f"{path.name}: datetime format must be yyyymmddhhmmss or yyyymmdd"
            )

    return df


def read_associated_borehole(path: str, **kwargs) -> pd.DataFrame:
    """
    Read an IPF associated borehole file (TXT), itype=2.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to associated file.
    kwargs : dict
        Dictionary containing the ``pandas.read_csv()`` keyword arguments for the
        associated (TXT) file (e.g. `{"delim_whitespace": True}`).

    Returns
    -------
    pandas.DataFrame
    """

    # deal with e.g. incorrect capitalization
    path = pathlib.Path(path).resolve()

    with open(path) as f:
        itype, nrow, usecols, colnames, na_values = read_associated_header(f)
        if itype != IpfType.BOREHOLE:
            raise ValueError(f"{path.name}: has itype {itype} and is not a borehole")

        itype_kwargs = {
            "delim_whitespace": False,
            "header": None,
            "names": colnames,
            "usecols": usecols,
            "nrows": nrow,
            "na_values": na_values,
            "skipinitialspace": True,
            "dtype": {colnames[0]: np.float64},  # z: top of layer
        }
        itype_kwargs.update(kwargs)
        df = pd.read_csv(f, **itype_kwargs)

    return df
