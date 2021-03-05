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
    LegendType: str = "Continuous"
    ColorScheme: Optional[str] = "Heatmap"
    ScaleType: Optional[str] = "Linear"
    RgbPointData: str = ""
    NanColor: str = "1 1 1"

@dataclass
class DataSet(Aggregate):
    Name: str
    legend: Optional[Union[Legend]] = None
    Time: int = 0
    TargetType: str = "Cell"
    DataType: str = "ScalarDouble"
    Origin: str = "fromFile"

@dataclass
class DataSetList(Aggregate):
    dataset: List[DataSet]

@dataclass
class BoundingBox(Aggregate):
    XMin : Union[Attribute, str] = "-1e9"
    XMax : Union[Attribute, str] = "1e9"
    YMin : Union[Attribute, str] = "-1e9"
    YMax : Union[Attribute, str] = "1e9"
    ZMin : Union[Attribute, str] = "-1e9"
    ZMax : Union[Attribute, str] = "1e9"

@dataclass
class GridModel(Aggregate):
    guid: Union[Attribute, str]
    Name: str
    Url: str
    LayerIndex: int
    Uri: str
    datasetlist: DataSetList
    boundingbox: BoundingBox = BoundingBox()
    Type: str = "Layered Ugrid"
    GridIndex: int = 0

@dataclass
class ExplorerModelList(Aggregate):
    gridmodel: List[GridModel]

@dataclass
class Viewer(Aggregate):
    type: Union[Attribute, str] = "2D"
    explorermodellist: Optional[ExplorerModelList] = None

@dataclass
class IMOD6(Aggregate):
    Version: Union[Attribute, str] = "8"
    viewer: List[Viewer] = None

#%%iMOD commands
@dataclass
class ModelToLoad(Aggregate):
    guid: Union[Attribute, str] = ""

@dataclass
class OutputObject(Aggregate):
    guid: Union[Attribute, str] = ""

@dataclass
class Polyline(Aggregate):
    polyline: List[float]

@dataclass
class Polylines(Aggregate):
    polyline_list: List[Polyline]

@dataclass
class CreateFenceDiagram(Aggregate):
    modelsToCut: List[str]
    polylines: Polylines
    outputobject: OutputObject

@dataclass 
class ImodCommand(Aggregate):
    """type: ["AddToExplorer", "LoadExplorerModel", "CreateFenceDiagram"]
    """
    Version: Union[Attribute, str] = "8"
    type: Union[Attribute, str] = ""
    guid: Union[Attribute, str] = ""
    viewer: Optional[List[Viewer]] = None
    modeltoload: Optional[List[ModelToLoad]] = None #List as a hack to get an aggregate with only attributes in the xml file
    createfencediagram: Optional[CreateFenceDiagram] = None


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
        element_name=datacls.__name__,
        cls=datacls,
        child_processors=children,
        alias=datacls.__name__.lower(),
        required=element_required,
    )
## %%
#@dataclass
#class ModelToLoad(Aggregate):
#   guid: Union[Attribute, str] = ""
#
#@dataclass 
#class ImodCommand(Aggregate):
#   """type: ["AddToExplorer", "LoadExplorerModel", "CreateFenceDiagram"]
#   """
#   #model_To_Load: ModelToLoad
#   modeltoload: List[ModelToLoad]
#   type: Union[Attribute, str] = ""
#
#
#if True:
#    #model_to_load = ModelToLoad(guid="aaaaaaaaaaaa")
#    model_to_load = ModelToLoad()
#    command = ImodCommand(modeltoload = [model_to_load], type = "LoadExplorerModel")
#    processor = make_processor(ImodCommand)
#
#    print(xml.serialize_to_string(processor, command, indent='   '))
## %%
#