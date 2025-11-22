
from inventor_utils.enums import enum_name, is_type_of
from inventor_utils.geometry import Parameter
from win32com.client import constants, CastTo

class ExtentWrapper:
    type: str
    """Wrapper for Inventor Extent objects."""
    def __init__(self) -> None:
        self.inventor_extent = None

    @classmethod
    def from_inventor(cls, extent) -> None:
        raise NotImplementedError("abstract method")
        pass
    def to_dict(self) -> dict:
        print("ExtentWrapper.to_dict not implemented")
        return {}
        pass

class ExtentFactory:
    @staticmethod
    def from_inventor(extent) -> ExtentWrapper:
        extent_type_name = extent.Type
        if is_type_of(extent, "AngleExtent"):
            return AngleExtentWrapper.from_inventor(extent)
        elif is_type_of(extent, "DistanceExtent"):
            return DistanceExtentWrapper.from_inventor(extent)
        elif is_type_of(extent, "ToExtent"):
            return ToExtentWrapper.from_inventor_extent(extent)
        else:
            raise ValueError(f"Unsupported extent type: {extent_type_name}")




class AngleExtentWrapper(ExtentWrapper):
    angle: Parameter
    direction: str
    @classmethod
    def from_inventor(cls,extent): # type: ignore
        
        if is_type_of(extent, "AngleExtent") is False:
            raise ValueError("Extent is not of type AngleExtent")
        instance = cls()
        instance.type = "AngleExtent"
        instance.inventor_extent = CastTo(extent, "AngleExtent")
        instance.angle = Parameter(extent.Angle)
        instance.direction = enum_name(extent.Direction) # type: ignore
        return instance

    def to_dict(self) -> dict:
        return {
            "type": "AngleExtent",
            "angle": self.angle,
            "direction": self.direction,
        }
    pass


class DistanceExtentWrapper(ExtentWrapper):
    distance: Parameter
    direction: str
    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "DistanceExtent") is False:
            raise ValueError("Extent is not of type DistanceExtent")
        instance = cls()
        instance.type = "DistanceExtent"
        instance.inventor_extent = CastTo(extent, "DistanceExtent")
        instance.distance = Parameter(extent.Distance)
        instance.direction = enum_name(extent.Direction) # type: ignore
        return instance
    def to_dict(self) -> dict:
        d = {}
        d['type'] = "DistanceExtent"
        d["distance"] = self.distance
        d["direction"] = self.direction
        return d
    pass

class ToExtentWrapper(ExtentWrapper):
    to_entity: dict
    direction: str
    extend_to_face: bool


    @classmethod    
    def from_inventor_extent(cls,extent): # type: ignore
        if is_type_of(extent, "ToExtent") is False:
            raise ValueError("Extent is not of type ToExtent")
        instance = cls()
        instance.type = "ToExtent"
        instance.inventor_extent = CastTo(extent, "ToExtent")
        to_entity = getattr(instance.inventor_extent, "ToEntity")
        if to_entity is None:
            raise ValueError("ToEntity is None in ToExtent")
        # 判断当前entity 是否为Faces 或者 Edges 集合类型 类型
        is_faces_collection = hasattr(to_entity, "Count") and hasattr(
            to_entity, "Item"
        )
        if is_faces_collection:
            try:
                from inventor_utils.metadata import collect_face_metadata
                entity = to_entity.Item(1)
                instance.to_entity = collect_face_metadata(entity)
            except Exception:
                raise ValueError(
                    f"ToEntity Item(1) is not Face,Currently only Face is supported"
                )
        else:
            raise ValueError("ToEntity is not a collection")
        return instance

    def to_dict(self) -> dict:
        d = {}
        d['type'] = "ToExtent"
        d["to_entity"] = self.to_entity
        d["direction"] = self.direction
        d["extend_to_face"] = self.extend_to_face
        return d 
    pass

class FullSweepExtentWrapper(ExtentWrapper):
    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "FullSweepExtent") is False:
            raise ValueError("Extent is not of type FullSweepExtent")
        instance = cls()
        instance.type = "FullSweepExtent"
        instance.inventor_extent = CastTo(extent, "FullSweepExtent")
        return instance
    def to_dict(self) -> dict:
        return {
            "type": "FullSweepExtent",
        }


class ThroughAllExtentWrapper(ExtentWrapper):
    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "ThroughAllExtent") is False:
            raise ValueError("Extent is not of type ThroughAllExtent")
        instance = cls()
        instance.type = "ThroughAllExtent"
        instance.inventor_extent = CastTo(extent, "ThroughAllExtent")
        #todo: add properties
        return instance

    def to_dict(self) -> dict:
        return {
            "type": "ThroughAllExtent",
        }
    pass

