#%%Importing
import abc
from dataclasses import dataclass
from typing import Union, List, Optional

import declxml as xml


class Aggregate(abc.ABC):
    pass


class Attribute(abc.ABC):
    pass


#%%Mapcanvas
@dataclass
class Legend(Aggregate):
    Discrete: bool = False
    ColorScheme: Optional[str] = "Heatmap"
    ScaleType: Optional[str] = "Linear"
    RgbPointData: str = ""
    NanColor: str = "1 1 1"

@dataclass
class DataSet(Aggregate):
    Name: str
    Time: int = 0
    TargetType: str = "Cell"
    DataType: str = "ScalarDouble"
    Origin: str = "fromFile"
    legend: Union[Legend, str] = ""

@dataclass
class DataSetList(Aggregate):
    dataset: List[DataSet]

@dataclass
class GridModel(Aggregate):
    Name: str
    Url: str
    LayerIndex: int
    Uri: str
    datasetlist: DataSetList
    Type: str = "Layered Ugrid"
    GridIndex: int = 0

@dataclass
class ExplorerModelList(Aggregate):
    gridmodel: List[GridModel]

@dataclass
class Viewer(Aggregate):
    type: Union[Attribute, str] = "2D"
    explorermodellist: Union[ExplorerModelList, str] = ""

@dataclass
class IMOD6(Aggregate):
    version: Union[Attribute, str] = "7.0"
    viewer: List[Viewer] = None

#%%Mappings
type_mapping = {
    bool: xml.boolean,
    float: xml.floating_point,
    int: xml.integer,
    str: xml.string,
}

name_mapping = {}

# name_mapping = {
#     NoData: "noData",
#     NoDataList: "noDataList",
#     KeywordList: "keywordList",
#     ProjectCrs: "projectCrs",
#     TransformContext: "transformContext",
#     EvaluateDefaultValues: "evaluateDefaultValues",
#     HomePath: "homePath",
#     Layer_Tree_Group_Leaf: "layer-tree-group",
#     Layer_Tree_Group_Root: "layer-tree-group",
#     SrcDest: "srcDest",
#     SpatialRefSys_Property: "SpatialRefSys",
# }

#%%Functions
# Following dataformats are now supported:
# ("Any" is both Aggregate and Primitive here, where "Primitive" is a placeholder for anything type_mapping)
# -Optional[List[Any]]
# -Optional[Union[Attribute, Primitive]]
# -List[Any]
# -Union[Attribute, Primitive]
# -Optional[Any]
# -Any


def unpack(vartype):
    # List[str] -> [typing.List[str], str]
    # Optional[List[Layer_Tree_Group_Leaf]] -> [Optional[List[Layer_Tree_Group_Leaf]], List[Layer_Tree_Group_Leaf], Layer_Tree_Group_Leaf]
    # ... and so forth
    # An attribute is returned as is:
    # Union[Attribute, str] -> [Union[Attribute, str]]
    # and:
    # List[Union[Attribute, str]] -> [List[Union[Attribute, str], Union[Attribute, str]]
    # i.e. the attribute information is maintained.
    yield vartype
    while hasattr(vartype, "__args__"):
        if is_attribute(vartype):
            return vartype
        vartype = vartype.__args__[0]
        yield vartype


def is_aggregate(vartype):
    try:
        return issubclass(vartype, Aggregate)
    except TypeError:
        return False


def is_required(vartype):
    # Optional is a Union[..., NoneType]
    NoneType = type(None)
    return not (hasattr(vartype, "__args__") and (vartype.__args__[-1] is NoneType))


def is_attribute(vartype):
    try:
        return issubclass(vartype, Attribute)
    except TypeError:
        return hasattr(vartype, "__args__") and (vartype.__args__[0] is Attribute)


def is_list(vartype):
    return hasattr(vartype, "__origin__") and (vartype.__origin__ is list)


def qgis_xml_name(datacls):
    # the qgis xml entries have dashes rather than underscores but dashes aren't
    # valid Python syntax.
    return name_mapping.get(datacls, datacls.__name__.lower().replace("_", "-"))


def process_primitive(name, vartype, datacls, required):
    field_kwargs = {
        "element_name": ".",
        "attribute": name.replace("_", "-"),
        "alias": name,
        "required": required,
        "default": False if required else None,
    }

    if is_attribute(datacls):
        xml_type = type_mapping[vartype]
    elif is_attribute(vartype):
        xml_type = type_mapping[vartype.__args__[1]]
    else:
        xml_type = type_mapping[vartype]
        field_kwargs["element_name"] = field_kwargs.pop("attribute")

    field = xml_type(**field_kwargs)
    return field

def make_processor(datacls: type, element_required: bool = True):
    """
    This is a utility to automate setting up of xml_preprocessors from the
    dataclass annotations. Nested aggregate types are dealt with via recursion.
    """

    children = []
    for name, vartype in datacls.__annotations__.items():
        required = element_required and is_required(vartype)
        type_info = [a for a in unpack(vartype)]
        if len(type_info) > 0:
            vartype = type_info[-1]

        # recursive case: an aggregate type
        if any(is_aggregate(a) for a in type_info):
            child = make_processor(vartype, required)
        # base case: a primitive type
        else:
            child = process_primitive(name, vartype, datacls, required)

        # Deal with arrays
        if any(is_list(a) for a in type_info):
            children.append(xml.array(child))
        else:
            children.append(child)

    return xml.user_object(
        element_name=qgis_xml_name(datacls),
        cls=datacls,
        child_processors=children,
        alias=datacls.__name__.lower(),
        required=element_required,
    )

