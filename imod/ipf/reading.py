import pathlib
import numpy as np
import pandas as pd
import csv
import io


TIMESERIES = 1
BOREHOLE = 2


def read_ipf(path, **kwargs):
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

    # Standardize x and y names
    xcol, ycol = df.columns[:2]
    idcol = df.columns[int(indexcol) - 1]
    return df.rename(columns={xcol: "x", ycol: "y", idcol: "timeseries_id"}), ext


def _read_associated_header(f):
    nrow = int(f.readline().strip())
    line = f.readline()
    try:
        # csv.reader parse one line
        # this catches commas in quotes
        ncol, itype = map(int, map(str.strip, next(csv.reader([line]))))
    # itype can be implicit, in which case it's a timeseries
    except ValueError:
        ncol = int(line.strip())
        itype = TIMESERIES

    # use pandas for csv parsing: stuff like commas within quotes
    lines = [f.readline() for _ in range(ncol)]
    lines = "".join(lines)
 
    metadata = pd.read_csv(
        io.StringIO(lines),
        delim_whitespace=False,
        header=None,
        nrows=ncol,
        skipinitialspace=True,
    )

    # header description possibly includes nodata
    usecols = np.arange(ncol)[pd.notnull(metadata[0])]
    metadata = metadata.iloc[usecols, :] 
    # Collect column names and nodata values
    colnames = []
    na_values = {}
    for colname, nodata in metadata.values:
        na_values[colname] = [nodata, "-"]  # "-" seems common enough to ignore
        if isinstance(colname, str):
            colnames.append(colname.strip())
        else:
            colnames.append(colname)

    # Sniff the first line of the data block
    #position = f.tell()
    return itype, nrow, usecols, colnames, na_values


def read_associated_timeseries(path, **kwargs):
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
        itype, nrow, usecols, colnames, na_values = _read_associated_header(f)
        if itype != TIMESERIES:
            raise ValueError(f"{path.name}: has itype {itype} and is not a timeseries")

        itype_kwargs = {
            "delim_whitespace": False,
            "header": None,
            "names": colnames,
            "usecols": usecols,
            "nrows": nrow,
            "na_values": na_values,
            "skipinitialspace": True,
            "dtype": {colnames[0]: str}, # yyyymmdd or yyyymmddhhmmss
        }
        itype_kwargs.update(kwargs)
        df = pd.read_csv(f, **itype_kwargs)

        time_column = colnames[0]
        len_date = len(df[time_column].iloc[0])
        if len_date == 14:
            df["datetime"] = pd.to_datetime(df[time_column], format="%Y%m%d%H%M%S")
        elif len_date == 8:
            df["datetime"] = pd.to_datetime(df[time_column], format="%Y%m%d")
        else:
            raise ValueError(
                f"{path.name}: datetime format must be yyyymmddhhmmss or yyyymmdd"
            )

    return df


def readlastline(path):
    # from: https://stackoverflow.com/questions/3346430/what-is-the-most-efficient-way-to-get-first-and-last-line-of-a-text-file
    # Note: f.seek() requires binary read
    with open(path, "rb") as f:
        f.seek(-2, 2)              # Jump to the second last byte.
        while f.read(1) != b"\n":  # Until EOL is found ...
            f.seek(-2, 1)          # ... jump back, over the read byte plus one more.
        line = f.read()            # Read all data from this point on.)
    return line.decode("utf-8")    


def sniff_timeseries_window(path):
    path = pathlib.Path(path)
    with open(path) as f:
        f.readline()  # nrow
        line = f.readline()
        try:
            # csv.reader parse one line
            # this catches commas in quotes
            ncol, itype = map(int, map(str.strip, next(csv.reader([line]))))
        # itype can be implicit, in which case it's a timeseries
        except ValueError:
            ncol = int(line.strip())
            itype = TIMESERIES

        # If it's not a timseries, exit 
        if itype != TIMESERIES:
            return None, None
    
        # Skip the column names, jump to the start of the data
        for _ in range(ncol):
            f.readline()

        firstline = f.readline()
        datetime_start = str.strip(next(csv.reader([firstline]))[0])
    
    lastline = readlastline(path)
    datetime_end = str.strip(next(csv.reader([lastline]))[0])

    return datetime_start, datetime_end


def read_associated_borehole(path, **kwargs):
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
        itype, nrow, usecols, colnames, na_values = _read_associated_header(f)
        if itype != BOREHOLE:
            raise ValueError(f"{path.name}: has itype {itype} and is not a borehole")

        itype_kwargs = {
            "delim_whitespace": False,
            "header": None,
            "names": colnames,
            "usecols": usecols,
            "nrows": nrow,
            "na_values": na_values,
            "skipinitialspace": True,
            "dtype": {colnames[0]: np.float64}, # z: top of layer
        }
        itype_kwargs.update(kwargs)
        df = pd.read_csv(f, **itype_kwargs)

    return df
