"""Object-oriented wrappers for Autodesk Inventor Part Features.

These wrappers provide safer attribute access, typed dispatch by feature kind,
printing and serialization helpers.
"""
from __future__ import annotations
import json
import math
from typing import Any, Dict, Optional, List, Type, TextIO
from win32com.client import constants, CastTo
from inventor_util import (
    enum_name,
    get_reference_key,
    get_reference_key_str,
    index_edge,
    index_face,
    is_extent_with_direction,
    operation_name,
    extent_direction_name,
    extent_type_name,
)
from  geometry_util import Arc2d, CircleCurve2d, Curve2d, LineSegment2d, Point3D, RevolveAxis, SketchPlane, SketchPoint, Parameter, Point2D

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
    def __init__(self, i_object) -> None:
        self.i_object = i_object

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if hasattr(self.i_object, "GetReferenceKey"):
            data["ReferenceKey"] = get_reference_key_str(self.i_object)
        return data
    
    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        if 'ReferenceKey' in d:
            _emit(f"{prefix}  ReferenceKey: {d['ReferenceKey']}", out)


class ProfileEntity(InventorObjectWrapper):
    def __init__(self, i_object) -> None:
        super().__init__(i_object)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["CurveType"] = enum_name(getattr(self.i_object, "CurveType"))
        if self.i_object.StartSketchPoint is not None:
            data["StartSketchPoint"] = SketchPoint(self.i_object.StartSketchPoint)

        if self.i_object.EndSketchPoint is not None:
            data["EndSketchPoint"] = SketchPoint(self.i_object.EndSketchPoint)
        if(data["CurveType"] == 'kCircularArcCurve2d'):
            data["Curve"] = Arc2d(self.i_object.Curve)
        elif(data["CurveType"] == 'kLineSegmentCurve2d'):
            data["Curve"] = LineSegment2d(self.i_object.Curve)
        elif(data["CurveType"] == 'kCircleCurve2d'):
            data["Curve"] = CircleCurve2d(self.i_object.Curve)
        else:
            print(f"Warning: Unhandled CurveType {data['CurveType']}")
            data["Curve"] = None

        return data
    

    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        t = d.get("CurveType", "?")
        sp = d.get("StartSketchPoint", None)
        ep = d.get("EndSketchPoint", None)
        sp_str = f"({sp.x:.3f}, {sp.y:.3f})" if sp else "(?, ?)"
        ep_str = f"({ep.x:.3f}, {ep.y:.3f})" if ep else "(?, ?)"

        _emit(f"{prefix}Curve: Type={t} Start={sp_str} End={ep_str}", out)
        super().pretty_print(prefix, out)
        curve: Optional[Curve2d] = d.get("Curve", None)
        if curve is not None:
            try:
                curve.pretty_print(prefix + "  ", out=out)
            except Exception:
                pass

# ------------------ Profile Wrappers ------------------
class ProfilePathWrapper(InventorObjectWrapper):
    def __init__(self, i_object) -> None:
        self.i_object = i_object


    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["Closed"] = getattr(self.i_object, "Closed", False)
        data["IsTextBoxPath"] = getattr(self.i_object, "IsTextBoxPath", False)
        data["EntityCount"] = getattr(self.i_object, "Count", 0)
        data["PathEntities"] = []
        for i in range(1, data["EntityCount"] + 1):
            try:
                ent = self.i_object.Item(i)
            except Exception:
                continue
            data["PathEntities"].append(ProfileEntity(ent))
        return data
    
    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        _emit(f"{prefix}ProfilePath: Closed={d.get('Closed',False)} IsTextBoxPath={d.get('IsTextBoxPath',False)} EntityCount={d.get('EntityCount',0)}", out)
        super().pretty_print(prefix, out)
        for j, ent in enumerate(d.get("PathEntities", []), start=1):
            _emit(f"{prefix}  Entity {j}:", out)
            ent.pretty_print(prefix + "    ", out)

        pass



class ProfileWrapper(InventorObjectWrapper):
    def __init__(self, i_object) -> None:
        super().__init__(i_object)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        ok_parent, sketch = self._safe_get(self.i_object, "Parent")

        if ok_parent and sketch is not None:
            ok_nm, sk_name = self._safe_get(sketch, "Name")
            if ok_nm:
                data["sketchName"] = sk_name
                planar_sketch = CastTo(sketch, "PlanarSketch")
                sketch_plane = SketchPlane(planar_sketch)
                data['SketchPlane'] = sketch_plane.to_dict()

        data["ProfilePaths"] = []
        try:
            count = getattr(self.i_object, "Count", 0)
        except Exception:
            count = 0
        for i in range(1, count + 1):
            try:
                profile_path = self.i_object.Item(i)
            except Exception:
                continue
            data["ProfilePaths"].append(ProfilePathWrapper(profile_path))
        return data

    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        _emit(f"{prefix}Profile: Paths={len(d.get('ProfilePaths', []))} Sketch={d.get('sketchName','<unknown>')}", out)
        if 'SketchPlane' in d:
            sp = d['SketchPlane']
            _emit(f"{prefix}  SketchPlane: Origin={sp['origin']} Normal={sp['normal']} AxisX={sp['axis_x']} AxisY={sp['axis_y']}", out)
        super().pretty_print(prefix, out)
        for j, ppw in enumerate(d.get("ProfilePaths", []), start=1):
            _emit(f"{prefix}  Path {j}:", out)
            ppw.pretty_print(prefix + "    ", out)

# ------------------ Feature Wrappers ------------------

class BaseFeatureWrapper(InventorObjectWrapper):
    friendly_type: str = "Feature"

    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object)
        self.feature = i_object
        self.doc = doc
        self._ids_cached: Optional[Dict[str, Any]] = None


    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = self.friendly_type
        okn, name = self._safe_get(self.feature, "Name")
        if okn:
            data["name"] = name
        return data

    # Default: print ids + name
    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        _emit(f"{prefix}{d.get('name','<unnamed>')} ({self.friendly_type})", out)
        super().pretty_print(prefix, out)

class ExtrudeFeatureWrapper(BaseFeatureWrapper):
    friendly_type = "ExtrudeFeature"

    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object, doc=doc)
        self.feature = CastTo(i_object, "ExtrudeFeature")

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        try:
            defn = self.feature.Definition
            d["operation"] = operation_name(defn.Operation) or defn.Operation
            d["extentType"] = extent_type_name(defn.ExtentType) or defn.ExtentType
            # Primary extent
            try:
                if defn.ExtentType == constants.kDistanceExtent:
                    dist_ext = CastTo(defn.Extent, "DistanceExtent")
                    d["distance"] = Parameter(getattr(dist_ext, "Distance", None))
                    dir_val = getattr(dist_ext, "Direction", None)
                    d["direction"] = extent_direction_name(dir_val) or dir_val
                else:
                    raise NotImplementedError(f"ExtentType {defn.ExtentType} not implemented")
            except Exception:
                pass
            try:
                if hasattr(defn, 'ExtentTwoType') and defn.ExtentTwoType == constants.kDistanceExtent:
                    dist_two = CastTo(defn.ExtentTwo, "DistanceExtent")
                    d["distanceTwo"] = Parameter(getattr(dist_two, "Distance", None))
                    dir2_val = getattr(dist_two, "Direction", None)
                    d["directionTwo"] = extent_direction_name(dir2_val) or dir2_val
            except Exception:
                pass
            # Profile
            ok_p, prof = self._safe_get(defn, "Profile")
            if ok_p and prof is not None:
                d["profile"] = ProfileWrapper(prof).to_dict()
        except Exception:
            pass
        return d

    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        super().pretty_print(prefix, out)
        for key in ("operation","extentType","direction","distance","directionTwo","distanceTwo"):
            if key in d:
                _emit(f"{prefix}  {key}: {d[key]}", out)
        if 'profile' in d:
            self.feature = CastTo(self.feature, "ExtrudeFeature")
            ProfileWrapper(self.feature.Definition.Profile).pretty_print(prefix + "  ", out)

class RevolveFeatureWrapper(BaseFeatureWrapper):
    friendly_type = "RevolveFeature"
    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object, doc=doc)
        self.feature = CastTo(i_object, "RevolveFeature")

    def to_dict(self) -> Dict[str, Any]:

        d = super().to_dict()
        d['featureType'] = 'RevolveFeature'
        d['axisEntity'] = RevolveAxis(self.feature.AxisEntity)

        try:
            _, d["name"] = self._safe_get(self.feature, "Name")
            d["extentType"] = extent_type_name(self.feature.ExtentType) or self.feature.ExtentType
            if d["extentType"] == 'kAngleExtent':
                angle_ext = CastTo(self.feature.Extent, "AngleExtent")
                d["angle"] = Parameter(getattr(angle_ext, "Angle", None))
                d["direction"] = extent_direction_name(getattr(angle_ext, "Direction", None)) or getattr(angle_ext, "Direction", None)
            else: # full  sweep
                d["angle"] = 360.0
                d["direction"] = "kPositiveExtentDirection"
            
            if self.feature.IsTwoDirectional:
                d["isTwoDirectional"] = True
                d["extentTwoType"] = extent_type_name(self.feature.ExtentTwoType) or self.feature.ExtentTwoType
                if d["extentTwoType"] == 'kAngleExtent':
                    angle_ext2 = CastTo(self.feature.ExtentTwo, "AngleExtent")
                    d["angleTwo"] = Parameter(getattr(angle_ext2, "Angle", None))
                    d["directionTwo"] = extent_direction_name(getattr(angle_ext2, "Direction", None)) or getattr(angle_ext2, "Direction", None)
                else: # full  sweep
                    d["angleTwo"] = 360.0
                    d["directionTwo"] = "kPositiveExtentDirection"
            
            d["operation"] = operation_name(self.feature.Operation) or self.feature.Operation

            ok_prof, prof = self._safe_get(self.feature, "Profile")
            if ok_prof and prof is not None:
                d["profile"] = ProfileWrapper(prof).to_dict()
        except Exception:
            pass
        return d

    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        super().pretty_print(prefix, out)
        for key in ("operation","extentType","direction","angle","isTwoDirectional","extentTwoType","directionTwo","angleTwo"):
            if key in d:
                _emit(f"{prefix}  {key}: {d[key]}", out)
        if 'profile' in d:
            self.feature = CastTo(self.feature, "RevolveFeature")
            ProfileWrapper(self.feature.Definition.Profile).pretty_print(prefix + "  ", out)

class SimpleValueFeatureWrapper(BaseFeatureWrapper):
    value_prop: str = ""
    label: str = "value"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.value_prop:
            ok, val = self._safe_get(self.feature, self.value_prop)
            if ok:
                d[self.label] = val
        return d

    def pretty_print(self, prefix: str = "", out: Optional[TextIO] = None) -> None:
        d = self.to_dict()
        _emit(f"{prefix}{d.get('name','<unnamed>')} ({self.friendly_type})", out)
        if self.label in d:
            _emit(f"{prefix}  {self.label}: {d[self.label]}", out)

class FilletFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object, doc=doc)
        self.friendly_type = "FilletFeature"
        self.feature = CastTo(i_object, "FilletFeature")

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['featureType'] = 'FilletFeature'
        _ , d['name'] = self._safe_get(self.feature, "Name")
        fillet_def = self.feature.FilletDefinition
        d['filletType'] = enum_name(getattr(fillet_def, "FilletType", None))
        if d['filletType'] == 'kEdgeFillet':
            count = getattr(fillet_def, "EdgeSetCount", 0)
            d['edgeSets'] = []
            for i in range(1, count + 1):
                edge_set =  fillet_def.EdgeSetItem(i)
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
                                edges.append(index_edge(edge))
                            except Exception as e:
                                print(f"Error processing edge in fillet {d['name']}: {e}")
                                continue
                    d['edgeSets'].append({
                        'radius': radius,
                        'edges': edges
                    })

        ok, val = self._safe_get(self.feature, "Radius")
        if ok:
            d['radius'] = val
        return d 
    
    def pretty_print(self, prefix: str = "", out: TextIO | None = None) -> None:      
        d = self.to_dict()
        _emit(f"{prefix}{d.get('name','<unnamed>')} ({self.friendly_type})", out)
        if 'filletType' in d:
            _emit(f"{prefix}  filletType: {d['filletType']}", out)
        if 'radius' in d:
            _emit(f"{prefix}  radius: {d['radius']}", out)
        if 'edgeSets' in d:
            for j, eset in enumerate(d['edgeSets'], start=1):
                _emit(f"{prefix}  EdgeSet {j}: radius={eset.get('radius', '?')} edges={len(eset.get('edges', []))}", out)
                for k, ek in enumerate(eset.get('edges', []), start=1):
                    _emit(f"{prefix}    Edge {k}: {ek}", out)
        super().pretty_print(prefix, out)

class ChamferFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object, doc=doc)
        self.feature = CastTo(i_object, "ChamferFeature")
        self.friendly_type = "ChamferFeature"

    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['featureType'] = 'ChamferFeature'
        _ , d['name'] = self._safe_get(self.feature, "Name")
        chamfer_def = self.feature.Definition
        d['chamferType'] = enum_name(getattr(chamfer_def, "DefinitionType", None))
        if d['chamferType'] == 'kDistance':
            _ , distance = self._safe_get(chamfer_def, "Distance")
            d['distance'] = Parameter(distance)
        elif d['chamferType'] == 'kTwoDistance':
            _, distance1 = self._safe_get(chamfer_def, "DistanceOne")
            _, distance2 = self._safe_get(chamfer_def, "DistanceTwo")
            d['distanceOne'] = Parameter(distance1)
            d['distanceTwo'] = Parameter(distance2)
            d['face'] = index_face(chamfer_def.Face)
        else:
            raise NotImplementedError(f"Chamfer type {d['chamferType']} not implemented in to_dict")
        chamfered_edges = chamfer_def.ChamferedEdges
        for i in range(1, getattr(chamfered_edges, "Count", 0) + 1):
            try:
                edge = chamfered_edges.Item(i)
                if 'edges' not in d:
                    d['edges'] = []
                d['edges'].append(index_edge(edge))

            except Exception as e:
                print(f"Error processing edge in chamfer {d['name']}: {e}")
                continue
        return d
    


class HoleFeatureWrapper(BaseFeatureWrapper):
    def __init__(self, i_object, doc=None) -> None:
        super().__init__(i_object, doc=doc)
        self.feature = CastTo(i_object, "HoleFeature")
        self.friendly_type = "HoleFeature"

    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['featureType'] = 'HoleFeature'
        _ , d['name'] = self._safe_get(self.feature, "Name")
        d['holeType'] =  enum_name(self.feature.HoleType) # type: ignore
        d['extentType'] = extent_type_name(self.feature.ExtentType)
        if d['extentType'] == 'kDistanceExtent':
            extent = CastTo(self.feature.Extent, "DistanceExtent")
            d['direction'] = extent_direction_name(getattr(extent, "Direction", None)) or getattr(extent, "Direction", None)
        else:
            raise NotImplementedError(f"Hole extent type {d['extentType']} not implemented in to_dict")
        d['isFlatBottomed'] = self.feature.FlatBottom
        if  not d['isFlatBottomed']:
            d['bottomTipAngle'] = Parameter(self.feature.BottomTipAngle)
        d['depth'] =self.feature.Depth
        d['sketchPlane'] = SketchPlane(self.feature.Sketch).to_dict()
        d['placementType'] = enum_name(self.feature.PlacementType)

        hole_center_points  = self.feature.HoleCenterPoints 
        d['holeCenterPoints'] = []
        for i in range(1, getattr(hole_center_points, "Count", 0) + 1):
            try:
                pt = Point2D.from_inventor(hole_center_points.Item(i).Geometry)
                d['holeCenterPoints'].append(pt)
            except Exception as e:
                print(f"Error processing hole center point in hole {d['name']}: {e}")
                continue
        
        d['isTapped'] = self.feature.Tapped
        if not d['isTapped']:
            d['holeDiameter'] = Parameter(self.feature.HoleDiameter)
        else:
            raise NotImplementedError("Tapped holes not implemented in to_dict")


        return d
    
    def pretty_print(self, prefix: str = "", out: TextIO | None = None) -> None:      
        d = self.to_dict()
        _emit(f"{prefix}{d.get('name','<unnamed>')} ({self.friendly_type})", out)
        super().pretty_print(prefix, out) 

# --------------- Factory -----------------

_WRAPPER_MAP: Dict[str, Type[BaseFeatureWrapper]] = {
    'ExtrudeFeature': ExtrudeFeatureWrapper,
    'RevolveFeature': RevolveFeatureWrapper,
    'FilletFeature': FilletFeatureWrapper,
    'ChamferFeature': ChamferFeatureWrapper,
    'HoleFeature': HoleFeatureWrapper,
}

def wrap_feature(raw_feature, *, kind: Optional[str] = None, doc=None) -> BaseFeatureWrapper:
    # Determine kind from constants if possible
    if kind is None:
        try:
            tval = raw_feature.Type
            # Reverse mapping via name suffix
            # We only attempt a few known constant names
            if tval == getattr(constants, 'kExtrudeFeatureObject'):
                kind = 'ExtrudeFeature'
            elif tval == getattr(constants, 'kRevolveFeatureObject'):
                kind = 'RevolveFeature'
            elif tval == getattr(constants, 'kFilletFeatureObject'):
                kind = 'FilletFeature'
            elif tval == getattr(constants, 'kChamferFeatureObject'):
                kind = 'ChamferFeature'
            elif tval == getattr(constants, 'kHoleFeatureObject'):
                kind = 'HoleFeature'
        except Exception as e:
            print(f"Warning: Could not determine feature type: {e}")
            pass
    if kind is None:
        raise TypeError(f"UnSupported feature type and kind could not be determined.{raw_feature.Type}")
    cls = _WRAPPER_MAP.get(kind, BaseFeatureWrapper)
    return cls(raw_feature, doc=doc)

# --------------- Collection utilities -----------------

def features_to_dict_list(features, *, doc=None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for feat in features:
        if  feat.Type == constants.kHoleFeatureObject:
            feat.SetEndOfPart(False)
        else:
            feat.SetEndOfPart(True)
        
        out.append(wrap_feature(feat, doc=doc).to_dict())

    return out




def dump_features_as_json(features, path: str, *, doc=None, indent: int = 2) -> None:
    payload = features_to_dict_list(features, doc=doc)


    def _json_default(obj):
        if isinstance(obj, Parameter):
            try:
                return {
                    'name': obj.name,
                    'value': obj.value,
                    'expression': obj.expression,
                    'valueType': obj.value_type,
                }
            except Exception:
                return {'value': getattr(obj, 'value', None)}
        if isinstance(obj, SketchPoint):
            try:
                return {'x': obj.x, 'y': obj.y}
            except Exception:
                return {}
        if isinstance(obj, Point2D):
            return {'x': obj.x, 'y': obj.y}
        if isinstance(obj, Point3D):
            return {'x': obj.x, 'y': obj.y, 'z': obj.z}
        if isinstance(obj, Arc2d):
            c = obj.center
            return {
                'type': 'Arc2d',
                'center': {'x': c.x, 'y': c.y},
                'radius': obj.radius,
                'startAngle': obj.start_angle,
                'sweepAngle': obj.sweep_angle,
            }
        if isinstance(obj, LineSegment2d):
            sp = obj.start_point
            ep = obj.end_point
            data = {
                'type': 'LineSegment2d',
                'start': {'x': sp.x, 'y': sp.y},
                'end': {'x': ep.x, 'y': ep.y},
            }
            try:
                d = obj.direction
                data['direction'] = {'x': d.x, 'y': d.y}
            except Exception:
                pass
            return data
        if isinstance(obj, CircleCurve2d):
            c = obj.center
            return {
                'type': 'CircleCurve2d',
                'center': {'x': c.x, 'y': c.y},
                'radius': obj.radius,
            }
        if isinstance(obj, Curve2d):
            return {'type': 'Curve2d'}
        
        if isinstance(obj, InventorObjectWrapper):
            return obj.to_dict()
        
        if isinstance(obj, RevolveAxis):
            return obj.to_dict()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=indent, default=_json_default)

def dump_features_pretty(features, path: str, *, doc=None) -> None:
    """Write a human-friendly pretty print of features to a file."""
    with open(path, 'w', encoding='utf-8') as f:
        for feat in features:
            try:
                wrap_feature(feat, doc=doc).pretty_print(out=f)
            except Exception:
                continue

__all__ = [
    'ProfileWrapper',
    'BaseFeatureWrapper', 'ExtrudeFeatureWrapper', 'RevolveFeatureWrapper',
    'FilletFeatureWrapper', 'ChamferFeatureWrapper',
    'wrap_feature', 'features_to_dict_list', 'dump_features_as_json', 'dump_features_pretty'
]
