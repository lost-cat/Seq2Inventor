"""Object-oriented wrappers for Autodesk Inventor Part Features.

These wrappers provide safer attribute access, typed dispatch by feature kind,
printing and serialization helpers.
"""

from __future__ import annotations
import json
from typing import Any, Dict, Optional, List, Type, TextIO
from win32com.client import constants, CastTo

from inventor_utils.enums import (
    enum_name,
    extent_type_name,
    is_type_of,
    operation_name,
)
from inventor_utils.extent_types import ExtentFactory, ExtentWrapper
from inventor_utils.geometry import (
    Arc2d,
    BSplineCurve2d,
    CircleCurve2d,
    Curve2d,
    LineSegment2d,
    Parameter,
    PlaneEntityWrapper,
    Point2D,
    AxisEntityWrapper,
    SketchPoint,
)
from inventor_utils.indexing import EntityIndexHelper
from inventor_utils.metadata import (
    collect_edge_metadata,
    collect_entity_metadata,
    collect_face_metadata,
)
from inventor_utils.reference import get_reference_key_str
from inventor_utils.utils import _json_default, clear_selection_in_inventor_app

# --------------- Printing helper -----------------


def _emit(line: str, out: Optional[TextIO] = None) -> None:
    if out is None:
        print(line)
    else:
        out.write(line + "\n")


class SafeGetMixin:
    def _safe_get(self, obj: Any, attr: str):
        try:
            if hasattr(obj, attr):
                return True, getattr(obj, attr)
        except Exception:
            pass
        return False, None


class InventorObjectWrapper(SafeGetMixin):
    data: Dict[str, Any]
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        self.i_object = i_object
        self.entity_index_helper = entity_index_helper
        self.data = {}

    def to_dict(self) -> Dict[str, Any]:
        if self.i_object is None:
            return self.data
        if hasattr(self.i_object, "GetReferenceKey"):
            self.data["ReferenceKey"] = get_reference_key_str(self.i_object)
        return self.data
    
    def from_dict(self, d: Dict[str, Any],entity_index_helper: Optional[EntityIndexHelper] = None) -> None:
        self.data = d
        self.i_object = None  # Placeholder; actual reconstruction not implemented
        self.entity_index_helper = entity_index_helper


class ProfileEntity(InventorObjectWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["CurveType"] = enum_name(getattr(self.i_object, "CurveType"))
        if self.i_object.StartSketchPoint is not None:
            self.data["StartSketchPoint"] = SketchPoint(self.i_object.StartSketchPoint)
        if self.i_object.EndSketchPoint is not None:
            self.data["EndSketchPoint"] = SketchPoint(self.i_object.EndSketchPoint)
        if self.data["CurveType"] == "kCircularArcCurve2d":
            self.data["Curve"] = Arc2d(self.i_object.Curve)
        elif self.data["CurveType"] == "kLineSegmentCurve2d":
            self.data["Curve"] = LineSegment2d(self.i_object.Curve)
        elif self.data["CurveType"] == "kCircleCurve2d":
            self.data["Curve"] = CircleCurve2d(self.i_object.Curve)
        elif self.data["CurveType"] == "kBSplineCurve2d":
            self.data["Curve"] = BSplineCurve2d(self.i_object.Curve)
        else:
            print(f"Warning: Unhandled CurveType {self.data['CurveType']}")
            self.data["Curve"] = None

        return self.data
    
    def start_point(self) -> Optional[Point2D]:
        if "StartSketchPoint" in self.data:
            return self.data["StartSketchPoint"]
        return None
    
    def end_point(self) -> Optional[Point2D]:
        if "EndSketchPoint" in self.data:
            return self.data["EndSketchPoint"]
        return None
    
    def curve(self) -> Optional[Curve2d]:
        if "Curve" in self.data:
            return self.data["Curve"]
        return None
    
    def curve_type(self) -> Optional[str]:
        if "CurveType" in self.data:
            return self.data["CurveType"]
        return None


# ------------------ Profile Wrappers ------------------
class ProfilePathWrapper(InventorObjectWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["Closed"] = getattr(self.i_object, "Closed", False)
        self.data["IsTextBoxPath"] = getattr(self.i_object, "IsTextBoxPath", False)
        self.data["EntityCount"] = getattr(self.i_object, "Count", 0)
        self.data["PathEntities"] = []
        for i in range(1, self.data["EntityCount"] + 1):
            try:
                ent = self.i_object.Item(i)
            except Exception:

                continue
            self.data["PathEntities"].append(
                ProfileEntity(ent, entity_index_helper=self.entity_index_helper)
            )
        return self.data

    def curve_count(self) -> Optional[int]:
        if "PathEntities" in self.data:
            return len(self.data["PathEntities"])
        return None
    
    def get_curve_entity(self, index: int) -> Optional[ProfileEntity]:
        if "PathEntities" in self.data:
            if 0 <= index < len(self.data["PathEntities"]):
                return self.data["PathEntities"][index]
        return None


class ProfileWrapper(InventorObjectWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        ok_parent, sketch = self._safe_get(self.i_object, "Parent")

        if ok_parent and sketch is not None:
            ok_nm, sk_name = self._safe_get(sketch, "Name")
            if ok_nm:
                self.data["sketchName"] = sk_name
                planar_sketch = CastTo(sketch, "PlanarSketch")
                sketch_plane = PlaneEntityWrapper(
                    planar_sketch, entity_index_helper=self.entity_index_helper
                )
                self.data["SketchPlane"] = sketch_plane.to_dict()

        self.data["ProfilePaths"] = []
        try:
            count = getattr(self.i_object, "Count", 0)
        except Exception:
            count = 0
        for i in range(1, count + 1):
            try:
                profile_path = self.i_object.Item(i)
            except Exception:
                continue
            self.data["ProfilePaths"].append(
                ProfilePathWrapper(
                    profile_path, entity_index_helper=self.entity_index_helper
                ).to_dict()
            )
        return self.data

    def sketch_name(self) -> Optional[str]:
        if "sketchName" in self.data:
            return self.data["sketchName"]
        return None
    
    def sketch_plane(self) -> Optional[PlaneEntityWrapper]:
        if "SketchPlane" in self.data:
            return PlaneEntityWrapper.from_dict(self.data["SketchPlane"], None)
        return None

    def path_count(self) -> Optional[int]:
        if "ProfilePaths" in self.data:
            return len(self.data["ProfilePaths"])
        return None
    
    def get_path(self, index: int) -> Optional[ProfilePathWrapper]:
        if "ProfilePaths" in self.data:
            if 0 <= index < len(self.data["ProfilePaths"]):
                profile_wrapper = ProfilePathWrapper(None, entity_index_helper=self.entity_index_helper)
                return profile_wrapper.from_dict(self.data["ProfilePaths"][index], self.entity_index_helper)
        return None



class PathEntityWrapper(InventorObjectWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(collect_entity_metadata(self.i_object))
        return data



class PathWrapper(InventorObjectWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["PathEntities"] = []
        try:
            count = getattr(self.i_object, "Count", 0)
        except Exception:
            count = 0
        for i in range(1, count + 1):
            try:
                path_entity = self.i_object.Item(i)
            except Exception:
                continue
            data["PathEntities"].append(
                PathEntityWrapper(
                    path_entity, entity_index_helper=self.entity_index_helper
                ).to_dict()
            )
        return data



# ------------------ Feature Wrappers ------------------





class BaseFeatureWrapper(InventorObjectWrapper):
    friendly_type: str = "Feature"
    data:Dict
    def __init__(self, i_object, entity_index_helper=None) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        self.feature = i_object

    def to_dict(self) -> Dict[str, Any]:
        self.data = super().to_dict()
        self.data["type"] = self.friendly_type
        okn, name = self._safe_get(self.feature, "Name")
        if okn:
            self.data["name"] = name
        return self.data
   


class ExtrudeFeatureWrapper(BaseFeatureWrapper):
    friendly_type = "ExtrudeFeature"

    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "ExtrudeFeature")

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()

        defn = self.feature.Definition
        self.data["operation"] = operation_name(defn.Operation) or defn.Operation
        self.data["extent"] = ExtentFactory.from_inventor(defn.Extent).to_dict()
        self.data["extentType"] = extent_type_name(defn.ExtentType) or defn.ExtentType
        self.data["isTwoDirectional"] = defn.IsTwoDirectional
        if self.data["isTwoDirectional"]:
            if hasattr(defn, "ExtentTwoType"):
                self.data["extentTwoType"] = extent_type_name(defn.ExtentTwoType) or defn.ExtentTwoType
                self.data["extentTwo"] = ExtentFactory.from_inventor(defn.ExtentTwo).to_dict()

        # Profile
        ok_p, prof = self._safe_get(defn, "Profile")
        if ok_p and prof is not None:
            self.data["profile"] = ProfileWrapper(
                prof, entity_index_helper=self.entity_index_helper
            ).to_dict()
        return self.data
    

    def operation(self) -> str:
        if 'operation' in self.data:
            return self.data['operation']
        return ""
    
    def extent_type(self) -> str:
        if 'extentType' in self.data:
            return self.data['extentType']
        return ""
    
    def extent(self) -> Optional[ExtentWrapper]:
        if 'extent' in self.data:
            return ExtentFactory.from_dict(self.data['extent'])
        return None
    
    def is_two_directional(self) -> bool:
        if 'isTwoDirectional' in self.data:
            return self.data['isTwoDirectional']
        return False
    def extent_two(self) -> Optional[Dict[str, Any]]:
        if 'extentTwo' in self.data:
            return self.data['extentTwo']
        return None
    def extent_two_type(self) -> str:
        if 'extentTwoType' in self.data:
            return self.data['extentTwoType']
        return ""
    
    def profile(self) -> Optional[ProfileWrapper]:
        if 'profile' in self.data:
            profile_wrapper = ProfileWrapper(None, entity_index_helper=self.entity_index_helper)
            return profile_wrapper.from_dict(self.data['profile'], self.entity_index_helper)
        return None



class RevolveFeatureWrapper(BaseFeatureWrapper):
    friendly_type = "RevolveFeature"

    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "RevolveFeature")

    def to_dict(self) -> Dict[str, Any]:

        super().to_dict()
        self.data["featureType"] = "RevolveFeature"
        self.data["axisEntity"] = AxisEntityWrapper(
            self.feature.AxisEntity, entity_index_helper=self.entity_index_helper
        ).to_dict()


        _, self.data["name"] = self._safe_get(self.feature, "Name")
        self.data["extentType"] = extent_type_name(self.feature.ExtentType)
        self.data["extent"] = ExtentFactory.from_inventor(self.feature.Extent).to_dict()

        if self.feature.IsTwoDirectional:
            self.data["isTwoDirectional"] = True
            self.data["extentTwoType"] = (
                extent_type_name(self.feature.ExtentTwoType)
                or self.feature.ExtentTwoType
            )
            self.data["extentTwo"] = ExtentFactory.from_inventor(
                self.feature.ExtentTwo
            ).to_dict()

        self.data["operation"] = (
            operation_name(self.feature.Operation) or self.feature.Operation
        )

        ok_prof, prof = self._safe_get(self.feature, "Profile")
        if ok_prof and prof is not None:
            self.data["profile"] = ProfileWrapper(
                prof, entity_index_helper=self.entity_index_helper
            ).to_dict()

        return self.data
    
    def axis_entity(self) -> Optional[AxisEntityWrapper]:
        if 'axisEntity' in self.data:
            return AxisEntityWrapper.from_dict(self.data['axisEntity'], None)
        return None
    
    def operation(self) -> str:
        if 'operation' in self.data:
            return self.data['operation']
        return ""
    def extent_type(self) -> str:
        if 'extentType' in self.data:
            return self.data['extentType']
        return ""
    def extent(self) -> Optional[ExtentWrapper]:
        if 'extent' in self.data:
            return ExtentFactory.from_dict(self.data['extent'])
        return None
    def is_two_directional(self) -> bool:
        if 'isTwoDirectional' in self.data:
            return self.data['isTwoDirectional']
        return False
    def extent_two_type(self) -> str:
        if 'extentTwoType' in self.data:
            return self.data['extentTwoType']
        return ""
    def extent_two(self) -> Optional[Dict[str, Any]]:
        if 'extentTwo' in self.data:
            return self.data['extentTwo']
        return None
    def profile(self) -> Optional[ProfileWrapper]:
        if 'profile' in self.data:
            profile_wrapper = ProfileWrapper(None, entity_index_helper=self.entity_index_helper)
            return profile_wrapper.from_dict(self.data['profile'], self.entity_index_helper)
        return None



class FilletFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, entity_index_helper=None) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        self.friendly_type = "FilletFeature"
        if self.feature is not None:
            self.feature = CastTo(i_object, "FilletFeature")

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["featureType"] = "FilletFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        fillet_def = self.feature.FilletDefinition
        self.data["filletType"] = enum_name(getattr(fillet_def, "FilletType", None))
        if self.data["filletType"] == "kEdgeFillet":
            count = getattr(fillet_def, "EdgeSetCount", 0)
            self.data["edgeSets"] = []
            for i in range(1, count + 1):
                edge_set = fillet_def.EdgeSetItem(i)
                const_edge_set = CastTo(edge_set, "FilletConstantRadiusEdgeSet")
                if const_edge_set is not None:
                    radius = Parameter(getattr(const_edge_set, "Radius", None))
                    edges = []
                    edge_collection = getattr(const_edge_set, "Edges", None)
                    if edge_collection is not None:
                        edge_count = getattr(edge_collection, "Count", 0)
                        for j in range(1, edge_count + 1):
                            try:
                                edge = edge_collection.Item(j)
                                edges.append(collect_edge_metadata(edge))
                            except Exception as e:
                                print(
                                    f"Error processing edge in fillet {self.data['name']}: {e}"
                                )
                                continue
                    self.data["edgeSets"].append({"radius": radius, "edges": edges})

        ok, val = self._safe_get(self.feature, "Radius")
        if ok:
            self.data["radius"] = val
        return self.data

    def edge_set_count(self) -> int:
        if 'edgeSets' in self.data:
            return len(self.data['edgeSets'])
        return 0
    
    def get_edge_set(self, index: int) -> Optional[Dict[str, Any]]:
        if 'edgeSets' in self.data:
            if 0 <= index < len(self.data['edgeSets']):
                return self.data['edgeSets'][index]
        return None
    


class ChamferFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "ChamferFeature")
        self.friendly_type = "ChamferFeature"

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["featureType"] = "ChamferFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        chamfer_def = self.feature.Definition
        self.data["chamferType"] = enum_name(getattr(chamfer_def, "DefinitionType", None))
        if self.data["chamferType"] == "kDistance":
            _, distance = self._safe_get(chamfer_def, "Distance")
            self.data["distance"] = Parameter(distance)
        elif self.data["chamferType"] == "kTwoDistances":
            _, distance1 = self._safe_get(chamfer_def, "DistanceOne")
            _, distance2 = self._safe_get(chamfer_def, "DistanceTwo")
            self.data["distanceOne"] = Parameter(distance1)
            self.data["distanceTwo"] = Parameter(distance2)
            self.data["face"] = collect_face_metadata(chamfer_def.Face)
        elif self.data["chamferType"] == "kDistanceAndAngle":
            self.data["distance"] = Parameter(chamfer_def.Distance)
            self.data["angle"] = Parameter(chamfer_def.Angle)
            self.data["face"] = collect_face_metadata(chamfer_def.Face)
            from inventor_utils.utils import select_entity_in_inventor_app
            select_entity_in_inventor_app(chamfer_def.Face)
            pass
        else:
            raise NotImplementedError(
                f"Chamfer type {self.data['chamferType']} not implemented in to_dict"
            )
        chamfered_edges = chamfer_def.ChamferedEdges
        for i in range(1, getattr(chamfered_edges, "Count", 0) + 1):
            try:
                edge = chamfered_edges.Item(i)
                if "edges" not in self.data:
                    self.data["edges"] = []
                self.data["edges"].append(collect_edge_metadata(edge))
                from inventor_utils.utils import select_entity_in_inventor_app
                select_entity_in_inventor_app(edge,False)
            except Exception as e:
                print(f"Error processing edge in chamfer {self.data['name']}: {e}")
                continue
        return self.data
    
    def chamfer_type(self) -> str:
        if 'chamferType' in self.data:
            return self.data['chamferType']
        return ""
    
    def distance(self) -> Optional[Parameter]:
        if 'distance' in self.data:
            return Parameter.from_dict(self.data['distance'])
        if 'distanceOne' in self.data:
            return Parameter.from_dict(self.data['distanceOne'])
        return None
    
    def distance_two(self) -> Optional[Parameter]:
        if 'distanceTwo' in self.data:
            return Parameter.from_dict(self.data['distanceTwo'])
        return None
    
    def angle(self) -> Optional[Parameter]:
        if 'angle' in self.data:
            return Parameter.from_dict(self.data['angle'])
        return None
    
    def face(self) -> Optional[Dict[str, Any]]:
        if 'face' in self.data:
            return self.data['face']
        return None
    
    def edge_count(self) -> int:
        if 'edges' in self.data:
            return len(self.data['edges'])
        return 0
    
    def get_edge(self, index: int) -> Optional[Dict[str, Any]]:
        if 'edges' in self.data:
            if 0 <= index < len(self.data['edges']):
                return self.data['edges'][index]
        return None


class HoleFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, entity_index_helper=None) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "HoleFeature")
        self.friendly_type = "HoleFeature"

    def to_dict(self) -> Dict[str, Any]:
        self.data = super().to_dict()
        self.data["type"] = "HoleFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        self.data["holeType"] = enum_name(self.feature.HoleType)  # type: ignore
        if self.data["holeType"] != "kDrilledHole":
            raise NotImplementedError(
                f"Hole type {self.data['holeType']} not implemented in to_dict"
            )
        self.data["extentType"] = extent_type_name(self.feature.ExtentType)
        self.data["extent"] = ExtentFactory.from_inventor(self.feature.Extent).to_dict()
        self.data["isFlatBottomed"] = self.feature.FlatBottom
        if not  self.data["isFlatBottomed"]:
            if self.feature.BottomTipAngle is not None:
                self.data["bottomTipAngle"] = Parameter(self.feature.BottomTipAngle)

        planar_sketch = CastTo(self.feature.Sketch, "PlanarSketch")
        self.data["sketchPlane"] = PlaneEntityWrapper(
            planar_sketch, entity_index_helper=self.entity_index_helper
        ).to_dict()
        self.data["placementType"] = enum_name(self.feature.PlacementType)

        hole_center_points = self.feature.HoleCenterPoints
        self.data["holeCenterPoints"] = []
        for i in range(1, getattr(hole_center_points, "Count", 0) + 1):
            try:
                pt = Point2D.from_inventor(hole_center_points.Item(i).Geometry)
                self.data["holeCenterPoints"].append(pt)
            except Exception as e:
                print(f"Error processing hole center point in hole {self.data['name']}: {e}")
                continue

        self.data["isTapped"] = self.feature.Tapped
        if not self.data["isTapped"]:
            self.data["holeDiameter"] = Parameter(self.feature.HoleDiameter)
        else:
            raise NotImplementedError("Tapped holes not implemented in to_dict")

        self.feature.SetEndOfPart(False)
        self.data["depth"] = self.feature.Depth
        self.feature.SetEndOfPart(True)

        return self.data

    def hole_type(self) -> str:
        if 'holeType' in self.data:
            return self.data['holeType']
        return ""
    
    def extent_type(self) -> str:
        if 'extentType' in self.data:
            return self.data['extentType']
        return ""
    
    def extent(self) -> Optional[ExtentWrapper]:
        if 'extent' in self.data:
            return ExtentFactory.from_dict(self.data['extent'])
        return None
    
    def sketch_plane(self) -> Optional[PlaneEntityWrapper]:
        if 'sketchPlane' in self.data:
            return PlaneEntityWrapper.from_dict(self.data['sketchPlane'], self.entity_index_helper)
        return None
    
    def hole_point_count(self) -> int:
        if 'holeCenterPoints' in self.data:
            return len(self.data['holeCenterPoints'])
        return 0
    def get_hole_point(self, index: int) -> Optional[Dict[str, Any]]:
        if 'holeCenterPoints' in self.data:
            if 0 <= index < len(self.data['holeCenterPoints']):
                return self.data['holeCenterPoints'][index]
        return None
    
    def hole_diameter(self) -> Optional[Parameter]:
        if 'holeDiameter' in self.data:
            return Parameter.from_dict(self.data['holeDiameter'])
        return None
    
    def is_flat_bottomed(self) -> bool:
        if 'isFlatBottomed' in self.data:
            return self.data['isFlatBottomed']
        return False
    def bottom_tip_angle(self) -> Optional[Parameter]:
        if 'bottomTipAngle' in self.data:
            return Parameter.from_dict(self.data['bottomTipAngle'])
        return None
    
    def depth(self) -> Optional[float]:
        if 'depth' in self.data:
            return self.data['depth']
        return None


@DeprecationWarning
class ThreadFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, entity_index_helper=None) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "ThreadFeature")
        self.friendly_type = "ThreadFeature"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["type"] = "ThreadFeature"
        _, d["name"] = self._safe_get(self.feature, "Name")
        # Additional properties can be added here
        return d


class ShellFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "ShellFeature")
        self.friendly_type = "ShellFeature"

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["type"] = "ShellFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        shell_def = self.feature.Definition
        self.data["direction"] = enum_name(getattr(shell_def, "Direction", None))
        self.data["thickness"] = Parameter(getattr(shell_def, "Thickness", None))
        self.data["inputFaces"] = []
        for i in range(1, shell_def.InputFaces.Count + 1):
            face = shell_def.InputFaces.Item(i)
            self.data["inputFaces"].append(collect_face_metadata(face))
        # Additional properties can be added here

        return self.data
    
    def direction(self) -> str:
        if 'direction' in self.data:
            return self.data['direction']
        return ""
    
    def thickness(self) -> Optional[Parameter]:
        if 'thickness' in self.data:
            return Parameter.from_dict(self.data['thickness'])
        return None
    
    def input_face_count(self) -> int:
        if 'inputFaces' in self.data:
            return len(self.data['inputFaces'])
        return 0
    
    def get_input_face(self, index: int) -> Optional[Dict[str, Any]]:
        if 'inputFaces' in self.data:
            if 0 <= index < len(self.data['inputFaces']):
                return self.data['inputFaces'][index]
        return None



class MirrorFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "MirrorFeature")
        self.friendly_type = "MirrorFeature"

    def to_dict(self) -> Dict[str, Any]:
        self.data = super().to_dict()
        self.data["type"] = "MirrorFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        mirror_def = self.feature.Definition
        if is_type_of(mirror_def.MirrorPlaneEntity, "WorkPlane"):
            self.data["mirrorPlane"] = PlaneEntityWrapper.from_work_plane(
                mirror_def.MirrorPlaneEntity,
                entity_index_helper=self.entity_index_helper,
            ).to_dict()
            self.data["isMirrorPlaneFace"] = False
        else:  # is planar face
            self.data["mirrorPlane"] = collect_face_metadata(mirror_def.MirrorPlaneEntity)
            self.data["isMirrorPlaneFace"] = True

        self.data["computeType"] = enum_name(getattr(mirror_def, "ComputeType", None))
        self.data["isMirrorBody"] = mirror_def.MirrorOfBody
        if not self.data["isMirrorBody"]:
            features_to_mirror = []
            for i in range(1, mirror_def.ParentFeatures.Count + 1):
                feat = mirror_def.ParentFeatures.Item(i)
                features_to_mirror.append(getattr(feat, "Name", "<unknown>"))
            self.data["featuresToMirror"] = features_to_mirror
        else:
            self.data["removeOriginal"] = mirror_def.RemoveOriginal
            self.data["operation"] = enum_name(getattr(mirror_def, "Operation", None))

        return self.data
    
    def is_mirror_body(self) -> bool:
        if 'isMirrorBody' in self.data:
            return self.data['isMirrorBody']
        return False
    def features_to_mirror(self) -> Optional[List[str]]:
        if 'featuresToMirror' in self.data:
            return self.data['featuresToMirror']
        return None
    
    def remove_original(self) -> Optional[bool]:
        if 'removeOriginal' in self.data:
            return self.data['removeOriginal']
        return None
    
    def operation(self) -> Optional[str]:
        if 'operation' in self.data:
            return self.data['operation']
        return None
    
    def compute_type(self) -> Optional[str]:
        if 'computeType' in self.data:
            return self.data['computeType']
        return None
    
    def is_mirror_plane_face(self) -> bool:
        if 'isMirrorPlaneFace' in self.data:
            return self.data['isMirrorPlaneFace']
        return False
    def mirror_plane(self) -> Dict[str, Any] | PlaneEntityWrapper:
        if not self.is_mirror_plane_face():
            return PlaneEntityWrapper.from_dict(self.data['mirrorPlane'], self.entity_index_helper)
        else:
            return self.data['mirrorPlane']
        return None


class RectangularPatternFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "RectangularPatternFeature")
        self.friendly_type = "RectangularPatternFeature"

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["type"] = "RectangularPatternFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        defn = self.feature.Definition
        self.data['xCount'] = Parameter(defn.XCount)
        self.data['xSpacing'] = Parameter(defn.XSpacing)
        self.data['xNaturalDirection'] = defn.NaturalXDirection
        x_direction_entity = defn.XDirectionEntity
        self.data['xDirectionEntity'] = collect_entity_metadata(x_direction_entity)
        self.data['xSpacingType'] = enum_name(defn.XDirectionSpacingType)
        self.data['isPatternOfBody'] = defn.PatternOfBody
        if not self.data["isPatternOfBody"]:
            features_to_pattern = []
            for i in range(1, defn.ParentFeatures.Count + 1):
                feat = defn.ParentFeatures.Item(i)
                features_to_pattern.append(getattr(feat, "Name", "<unknown>"))
            self.data["featuresToPattern"] = features_to_pattern

        return self.data
    
    def x_count(self) -> Optional[Parameter]:
        if 'xCount' in self.data:
            return Parameter.from_dict(self.data['xCount'])
        return None
    def x_spacing(self) -> Optional[Parameter]:
        if 'xSpacing' in self.data:
            return Parameter.from_dict(self.data['xSpacing'])
        return None
    def x_natural_direction(self) -> Optional[bool]:
        if 'xNaturalDirection' in self.data:
            return self.data['xNaturalDirection']
        return None
    def x_direction_entity(self) -> Optional[Dict[str, Any]]:
        if 'xDirectionEntity' in self.data:
            return self.data['xDirectionEntity']
        return None
    
    def x_spacing_type(self) -> Optional[str]:
        if 'xSpacingType' in self.data:
            return self.data['xSpacingType']
        return None
    
    def is_pattern_of_body(self) -> Optional[bool]:
        if 'isPatternOfBody' in self.data:
            return self.data['isPatternOfBody']
        return None
    
    def features_to_pattern(self) -> Optional[List[str]]:
        if 'featuresToPattern' in self.data:
            return self.data['featuresToPattern']
        return None


class CircularPatternFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "CircularPatternFeature")
        self.friendly_type = "CircularPatternFeature"

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        self.data["type"] = "CircularPatternFeature"
        _, self.data["name"] = self._safe_get(self.feature, "Name")
        defn = self.feature.Definition
        self.data["isPatternOfBody"] = defn.PatternOfBody
        self.data["angle"] = Parameter(defn.Angle)
        self.data["count"] = Parameter(defn.Count)
        self.data["isNaturalAxisDirection"] = defn.NaturalRotationAxisDirection
        rotation_axis = defn.RotationAxis
        self.data["rotationAxis"] = collect_entity_metadata(rotation_axis)
        if not self.data["isPatternOfBody"]:
            features_to_pattern = []
            for i in range(1, defn.ParentFeatures.Count + 1):
                feat = defn.ParentFeatures.Item(i)
                features_to_pattern.append(getattr(feat, "Name", "<unknown>"))
            self.data["featuresToPattern"] = features_to_pattern
        return self.data
    
    def is_pattern_of_body(self) -> Optional[bool]:
        if 'isPatternOfBody' in self.data:
            return self.data['isPatternOfBody']
        return None
    
    def angle(self) -> Optional[Parameter]:
        if 'angle' in self.data:
            return Parameter.from_dict(self.data['angle'])
        return None
    
    def count(self) -> Optional[Parameter]:
        if 'count' in self.data:
            return Parameter.from_dict(self.data['count'])
        return None
    
    def is_natural_axis_direction(self) -> Optional[bool]:
        if 'isNaturalAxisDirection' in self.data:
            return self.data['isNaturalAxisDirection']
        return None
    
    def rotation_axis(self) -> Optional[Dict[str, Any]]:
        if 'rotationAxis' in self.data:
            return self.data['rotationAxis']
        return None
    
    def features_to_pattern(self) -> Optional[List[str]]:
        if 'featuresToPattern' in self.data:
            return self.data['featuresToPattern']
        return None
    


@DeprecationWarning
class SweepFeatureWrapper(BaseFeatureWrapper):
    def __init__(
        self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
    ) -> None:
        super().__init__(i_object, entity_index_helper=entity_index_helper)
        if self.feature is not None:
            self.feature = CastTo(i_object, "SweepFeature")
        self.friendly_type = "SweepFeature"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["type"] = "SweepFeature"
        _, d["name"] = self._safe_get(self.feature, "Name")
        is_solid_sweep = self.feature.IsSolidSweep
        if is_solid_sweep:
            raise NotImplementedError("Solid sweeps not implemented in to_dict")
        defn = self.feature.Definition
        d["operation"] = operation_name(defn.Operation)
        sweep_type = enum_name(defn.SweepType)
        d["sweepType"] = sweep_type
        if d["sweepType"] != "kPathSweepType":
            raise NotImplementedError(
                f"Sweep type {d['sweepType']} not implemented in to_dict"
            )
        # Profile
        ok_p, prof = self._safe_get(defn, "Profile")
        if ok_p and prof is not None:
            d["profile"] = ProfileWrapper(
                prof, entity_index_helper=self.entity_index_helper
            ).to_dict()
        # Path
        ok_path, path = self._safe_get(defn, "Path")
        if ok_path and path is not None:
            d["path"] = ProfilePathWrapper(
                path, entity_index_helper=self.entity_index_helper
            ).to_dict()
        return d

# class LoftFeatureWrapper(BaseFeatureWrapper):
#     def __init__(
#         self, i_object, entity_index_helper: Optional[EntityIndexHelper] = None
#     ) -> None:
#         super().__init__(i_object, entity_index_helper=entity_index_helper)
#         self.feature = CastTo(i_object, "LoftFeature")
#         self.friendly_type = "LoftFeature"

#     def to_dict(self) -> Dict[str, Any]:
#         d = super().to_dict()
#         d["type"] = "LoftFeature"
#         _, d["name"] = self._safe_get(self.feature, "Name")
#         defn = self.feature.Definition
#         d["operation"] = operation_name(defn.Operation) or defn.Operation
#         d["isSolid"] = defn.Solid
#         d["isClosed"] = defn.Closed
#         d["profileCount"] = defn.ProfileCount
#         d["profiles"] = []
#         for i in range(1, defn.ProfileCount + 1):
#             try:
#                 prof = defn.ProfileItem(i)
#                 d["profiles"].append(
#                     ProfileWrapper(
#                         prof, entity_index_helper=self.entity_index_helper
#                     ).to_dict()
#                 )
#             except Exception:
#                 continue
#         return d

# --------------- Factory -----------------

_WRAPPER_MAP: Dict[str, Type[BaseFeatureWrapper]] = {
    "ExtrudeFeature": ExtrudeFeatureWrapper,
    "RevolveFeature": RevolveFeatureWrapper,
    "FilletFeature": FilletFeatureWrapper,
    "ChamferFeature": ChamferFeatureWrapper,
    "HoleFeature": HoleFeatureWrapper,
    "ShellFeature": ShellFeatureWrapper,
    "MirrorFeature": MirrorFeatureWrapper,
    "RectangularPatternFeature": RectangularPatternFeatureWrapper,
    "CircularPatternFeature": CircularPatternFeatureWrapper,
    "SweepFeature": SweepFeatureWrapper,
}

class FeatureWrapperFactory:

    @staticmethod
    def get_type_by_name(type_name: str) -> Type[BaseFeatureWrapper]:
        if  not type_name.endswith("Feature"):
            type_name += "Feature"
        feature_class: Type[BaseFeatureWrapper] = _WRAPPER_MAP.get(type_name, BaseFeatureWrapper)
        return feature_class

    @staticmethod
    def from_inventor(i_object, entity_index_helper: Optional[EntityIndexHelper] = None) -> 'BaseFeatureWrapper':
        return wrap_feature(i_object, entity_index_helper=entity_index_helper)
    
    @staticmethod
    def from_dict(d: Dict[str, Any], entity_index_helper=None) -> 'BaseFeatureWrapper':
        feature_type = d.get("type", "")
        feature_class: Type[BaseFeatureWrapper]
        feature_class = FeatureWrapperFactory.get_type_by_name(feature_type)
        if feature_class is BaseFeatureWrapper:
            raise TypeError(f"UnSupported feature type: {feature_type}")
        instance = feature_class(None, entity_index_helper=entity_index_helper)
        instance.from_dict(d, entity_index_helper=entity_index_helper)
        return instance

def wrap_feature(
    raw_feature, entity_index_helper=None
) -> BaseFeatureWrapper:
    feature_type: Optional[str] = None
    try:
        tval = raw_feature.Type
        if tval == getattr(constants, "kExtrudeFeatureObject"):
            feature_type = "ExtrudeFeature"
        elif tval == getattr(constants, "kRevolveFeatureObject"):
            feature_type = "RevolveFeature"
        elif tval == getattr(constants, "kFilletFeatureObject"):
            feature_type = "FilletFeature"
        elif tval == getattr(constants, "kChamferFeatureObject"):
            feature_type = "ChamferFeature"
        elif tval == getattr(constants, "kHoleFeatureObject"):
            feature_type = "HoleFeature"
        elif tval == getattr(constants, "kShellFeatureObject"):
            feature_type = "ShellFeature"
        elif tval == getattr(constants, "kMirrorFeatureObject"):
            feature_type = "MirrorFeature"
        elif tval == getattr(constants, "kRectangularPatternFeatureObject"):
            feature_type = "RectangularPatternFeature"
        elif tval == getattr(constants, "kCircularPatternFeatureObject"):
            feature_type = "CircularPatternFeature"
        elif tval == getattr(constants, "kSweepFeatureObject"):
            feature_type = "SweepFeature"
    except Exception as e:
        print(f"Warning: Could not determine feature type: {e}")
        pass
    if feature_type is None or feature_type in ["ThreadFeature"]:
        raise TypeError(
            f"UnSupported feature type and kind could not be determined.{enum_name(raw_feature.Type)}"
        )
    cls = _WRAPPER_MAP.get(feature_type, BaseFeatureWrapper)
    return cls(raw_feature, entity_index_helper=entity_index_helper)


# --------------- Collection utilities -----------------


def features_to_dict_list(features, *, doc) -> List[Dict[str, Any]]:
    from inventor_utils.utils import _json_default, clear_selection_in_inventor_app
    from inventor_utils.app import pump_waiting_messages  # 新增
    out: List[Dict[str, Any]] = []
    entity_ref_helper = EntityIndexHelper(doc.ComponentDefinition)
    app = doc.ComponentDefinition.Application
    for feat in features:
        try:
            feat.SetEndOfPart(True)
        except Exception:
            print(f"Warning: Could not set EndOfPart on feature {feat.Name}")
            continue
        out.append(wrap_feature(feat, entity_index_helper=entity_ref_helper).to_dict())
        try:
            feat.SetEndOfPart(False)
        except Exception:
            print(f"Warning: Could not unset EndOfPart on feature {feat.Name}")
            pass
        entity_ref_helper.update_all()
        clear_selection_in_inventor_app(doc)
        if app is not None:
            try:
                from inventor_utils.app import doevents
                doevents(app)
            except Exception:
                pass
        else:
            pump_waiting_messages()
    features[-1].SetEndOfPart(False)
    return out


def normalize_feature_dicts(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize feature dicts for comparison by removing non-deterministic fields."""
    normalized: List[Dict[str, Any]] = []

    return normalized


def dump_features_as_json(features, path: str, *, doc=None, indent: int = 2) -> None:

    payload = features_to_dict_list(features, doc=doc)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=indent, default=_json_default)




__all__ = [
    "ProfileWrapper",
    "BaseFeatureWrapper",
    "ExtrudeFeatureWrapper",
    "RevolveFeatureWrapper",
    "FilletFeatureWrapper",
    "ChamferFeatureWrapper",
    "wrap_feature",
    "features_to_dict_list",
    "dump_features_as_json",
]
