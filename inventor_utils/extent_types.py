
from inventor_utils.enums import enum_name, is_type_of
from inventor_utils.geometry import Parameter, PlaneEntityWrapper
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
    @classmethod
    def from_dict(cls, d: dict):
        raise NotImplementedError("abstract method")

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
        elif is_type_of(extent, "FullSweepExtent"):
            return FullSweepExtentWrapper.from_inventor(extent)
        elif is_type_of(extent, "ThroughAllExtent"):
            return ThroughAllExtentWrapper.from_inventor(extent)
        elif is_type_of(extent, "FromToExtent"):
            return FromToExtentWrapper.from_inventor(extent)
        elif is_type_of(extent, "ToNextExtent"):
            return ToNextExtentWrapper.from_inventor(extent)
        else:
            raise ValueError(f"Unsupported extent type: {enum_name(extent_type_name)}")




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
    @classmethod
    def from_dict(cls, d: dict) -> None:
       instance = cls()
       instance.angle = Parameter.from_dict(d.get("angle", {}))
       instance.direction = d.get("direction", "")




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
        instance.distance = Parameter(instance.inventor_extent.Distance)
        instance.direction = enum_name(instance.inventor_extent.Direction) # type: ignore
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
        
        instance.direction = enum_name(instance.inventor_extent.Direction) # type: ignore
        instance.extend_to_face = instance.inventor_extent.ExtendToFace
        return instance

    def to_dict(self) -> dict:
        d = {}
        d['type'] = "ToExtent"
        d["toEntity"] = self.to_entity
        d["direction"] = self.direction
        d["extendToFace"] = self.extend_to_face
        return d 
    pass

class ToNextExtentWrapper(ExtentWrapper):
    direction: str

    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "ToNextExtent") is False:
            raise ValueError("Extent is not of type ToNextExtent")
        instance = cls()
        instance.type = "ToNextExtent"
        instance.inventor_extent = CastTo(extent, "ToNextExtent")
        instance.direction = enum_name(instance.inventor_extent.Direction) # type: ignore
        return instance
    def to_dict(self) -> dict:
        return {
            "type": "ToNextExtent",
            'direction': self.direction,
        }


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
    direction: str
    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "ThroughAllExtent") is False:
            raise ValueError("Extent is not of type ThroughAllExtent")
        instance = cls()
        instance.type = "ThroughAllExtent"
        instance.inventor_extent = CastTo(extent, "ThroughAllExtent")
        instance.direction = enum_name(instance.inventor_extent.Direction) # type: ignore
        return instance

    def to_dict(self) -> dict:
        return {
            "type": "ThroughAllExtent",
            "direction": self.direction,
        }
    pass

class FromToExtentWrapper(ExtentWrapper):
    from_face: dict
    is_from_face_work_plane: bool
    extend_from_face :bool
    to_face: dict
    is_to_face_work_plane: bool
    extend_to_face :bool

    @classmethod
    def from_inventor(cls,extent): # type: ignore
        if is_type_of(extent, "FromToExtent") is False:
            raise ValueError("Extent is not of type FromToExtent")
        instance = cls()
        instance.type = "FromToExtent"
        instance.inventor_extent = CastTo(extent, "FromToExtent")
        from inventor_utils.metadata import collect_face_metadata
        if is_type_of(instance.inventor_extent.FromFace, "Face") is True:
            instance.from_face = collect_face_metadata(instance.inventor_extent.FromFace)
            instance.is_from_face_work_plane = False
        else:
            instance.from_face = PlaneEntityWrapper.from_work_plane(instance.inventor_extent.FromFace, None).to_dict()
            instance.is_from_face_work_plane = True
        if is_type_of(instance.inventor_extent.ToFace, "Face") is True:
            instance.to_face = collect_face_metadata(instance.inventor_extent.ToFace)
            instance.is_to_face_work_plane = False
        else:
            instance.to_face = PlaneEntityWrapper.from_work_plane(instance.inventor_extent.ToFace, None).to_dict()
            instance.is_to_face_work_plane = True
        instance.extend_from_face = instance.inventor_extent.ExtendFromFace
        instance.extend_to_face = instance.inventor_extent.ExtendToFace
        return instance

    def to_dict(self) -> dict:
        return {
            "type": "FromToExtent",
            "fromFace": self.from_face,
            "toFace": self.to_face,
            "isFromFaceWorkPlane": self.is_from_face_work_plane,
            "isToFaceWorkPlane": self.is_to_face_work_plane,
            "extendFromFace": self.extend_from_face,
            "extendToFace": self.extend_to_face,
        }
    pass
