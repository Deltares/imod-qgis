from osgeo import ogr
import pandas as pd


def read_arrow(path):
    dataset = ogr.Open(path)
    layer = dataset.GetLayer(0)
    stream = layer.GetArrowStreamAsNumPy()
    data = stream.GetNextRecordBatch()
    return pd.DataFrame(data=data)
