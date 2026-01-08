import math
from typing import Tuple

import numpy

from .geometry import AxisEntityWrapper, Point3D
from .enums import enum_name, is_type_of


def _normalize_vector(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    norm = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if norm < 1e-12:
        raise ValueError("Cannot normalize near-zero vector")
    return (v[0] / norm, v[1] / norm, v[2] / norm)

def _round_val(x: float, tol: float = 1e-3) -> float:
    try:
        return 0.0 if x is None else round(float(x), max(0, int(-math.log10(tol))))
    except Exception:
        return 0.0


def _pt_key3(p: Point3D, tol: float = 1e-3):
    try:
        return (_round_val(p.x, tol), _round_val(p.y, tol), _round_val(p.z, tol))
    except Exception:
        return (0.0, 0.0, 0.0)

def collect_entity_metadata(entity, tol: float = 1e-3) -> dict:
    if is_type_of(entity, "Face"):
        return collect_face_metadata(entity, tol)
    if is_type_of(entity, "Edge"):
        return collect_edge_metadata(entity, tol)
    
    if is_type_of(entity, "WorkAxis"):
        return AxisEntityWrapper(entity,None).to_dict()
    
    if is_type_of(entity, "WorkPlane"):
        from .geometry import PlaneEntityWrapper
        return PlaneEntityWrapper.from_work_plane(entity,None).to_dict()
    
    raise ValueError(f"Unsupported entity type {enum_name(entity.Type)} for metadata collection")


def _compute_mid_uv(face):
    ev = face.Evaluator
    # 基于参数域矩形
    try:
        rect = ev.ParamRangeRect  # Box2d
        u_min = rect.MinPoint.X
        v_min = rect.MinPoint.Y
        u_max = rect.MaxPoint.X
        v_max = rect.MaxPoint.Y
        u_mid = (u_min + u_max) / 2.0
        v_mid = (v_min + v_max) / 2.0
    except Exception:
        print("[debug] Failed to get ParamRangeRect for face; using default mid UV (0.5, 0.5)")
        u_mid = 0.5
        v_mid = 0.5
    
    return u_mid, v_mid


def get_face_plane(face) -> Tuple[Tuple[float,float,float], Tuple[float, float, float]]:
    """尝试从面上获取一个平面表示（点+法向量），仅适用于平面面"""
    st = getattr(face, "SurfaceType", None)
    if st is None:
        raise ValueError("Face has no SurfaceType")
    st = enum_name(st)
    if st == "kPlaneSurface":
        geometry = face.Geometry
        root_point = geometry.RootPoint
        normal_vec = geometry.Normal
    else:
        raise ValueError("Face is not a plane surface")
    
    return  (
        (_round_val(root_point.X), _round_val(root_point.Y), _round_val(root_point.Z)),
        (_round_val(normal_vec.X), _round_val(normal_vec.Y), _round_val(normal_vec.Z)),
    )

def get_axis_from_face(face) -> Tuple[Tuple[float,float,float], Tuple[float, float, float]]:
    """尝试从面上获取一个轴线表示（点+方向），仅适用于具有轴线的曲面类型"""
    st = getattr(face, "SurfaceType", None)
    if st is None:
        raise ValueError("Face has no SurfaceType")
    st = enum_name(st)
    base_point = None
    axis_vector = None
    if st == "kCylinderSurface" or st == "kConeSurface" or st == "kTorusSurface":
        cylinder = face.Geometry
        base_point = cylinder.BasePoint
        axis_vector = cylinder.AxisVector
    else:
        raise ValueError("Face surface type does not have an axis line")

    
    return (
        (_round_val(base_point.X), _round_val(base_point.Y), _round_val(base_point.Z)),
        (_round_val(axis_vector.X), _round_val(axis_vector.Y), _round_val(axis_vector.Z)),
    )


def collect_face_metadata(face, tol: float = 1e-3) -> dict:
    metadata = {}
    st = getattr(face, "SurfaceType", None)
    if st is None:
        raise ValueError("Face has no SurfaceType")
    st = enum_name(st)
    face_evaluator = face.Evaluator
    area = _round_val(face_evaluator.Area, tol)
    
    #获取曲面 UV 中心坐标
    range_box = face.Evaluator.RangeBox
    uv_box = face_evaluator.ParamRangeRect
    uv_center = _compute_mid_uv(face)

    centroid = [0, 0, 0]
    _, centroid = face_evaluator.GetPointAtParam([*uv_center],centroid)
    centroid = tuple(_round_val(c, tol) for c in centroid)
    orient = []
    _, orient = face_evaluator.GetNormal([*uv_center], orient)
    orient = tuple(_round_val(c, tol) for c in orient)
    utangent = []
    v_tangent = []
    _, utangent, v_tangent = face_evaluator.GetFirstDerivatives([*uv_center], utangent, v_tangent)
    # 针对具有“轴”的曲面类型，尝试提取轴线（起点+方向）
    axis_info = None
    try:
        axis_point, axis_dir = get_axis_from_face(face)
        axis_info = {
            "point": {
                "x": axis_point[0],
                "y": axis_point[1],
                "z": axis_point[2],
            },
            "direction": {
                "x": axis_dir[0],
                "y": axis_dir[1],
                "z": axis_dir[2],
            }
        }
    except Exception:
        pass  # 忽略无法提取轴线的情况

    plane_info = None
    try:
        plane_point, plane_normal = get_face_plane(face)
        plane_info = {
            "point": {
                "x": plane_point[0],
                "y": plane_point[1],
                "z": plane_point[2],
            },
            "normal": {
                "x": plane_normal[0],
                "y": plane_normal[1],
                "z": plane_normal[2],
            }
        }
    except Exception:
        pass  # 忽略无法提取平面的情况
        
    metadata = {
        "metaType": "Face",
        "surfaceType": st,
        "area": area,
        "centroid": centroid,
        "orientation": orient,
        "axisInfo": axis_info if axis_info is not None else None,
        "planeInfo": plane_info if plane_info is not None else None,
        'rangeBox': {
            'minPoint': (_round_val(range_box.MinPoint.X, tol), _round_val(range_box.MinPoint.Y, tol), _round_val(range_box.MinPoint.Z, tol)),
            'maxPoint': (_round_val(range_box.MaxPoint.X, tol), _round_val(range_box.MaxPoint.Y, tol), _round_val(range_box.MaxPoint.Z, tol)),
        },
        'uvBox': {
            'minPoint': ( _round_val(uv_box.MinPoint.X, tol), _round_val(uv_box.MinPoint.Y, tol)),
            'maxPoint': ( _round_val(uv_box.MaxPoint.X, tol), _round_val(uv_box.MaxPoint.Y, tol)),
        },
    }
    return metadata


def get_edge_axis(edge) -> Tuple[Tuple[float,float,float], Tuple[float, float, float]]:
    """尝试从边上获取一个轴线表示（点+方向），仅适用于直线边"""
    t = getattr(edge, "GeometryType", None)
    if t is None:
        raise ValueError("Edge has no GeometryType")
    t_name = enum_name(t)
    if t_name != "kLineCurve" and t_name != "kLineSegmentCurve":
        raise ValueError("Edge is not a line segment")
    
    line = edge.Geometry
    root_point = line.RootPoint if t_name == "kLineCurve" else line.StartPoint
    direction = line.Direction
    
    return (
        (_round_val(root_point.X), _round_val(root_point.Y), _round_val(root_point.Z)),
        (_round_val(direction.X), _round_val(direction.Y), _round_val(direction.Z)),
    )

def collect_edge_metadata(edge, tol: float = 1e-3) -> dict:
    t = getattr(edge, "GeometryType", None)
    if t is None:
        raise ValueError("Edge has no GeometryType")
    t_name = enum_name(t)

    sp = Point3D.from_inventor(edge.StartVertex.Point)
    ep = Point3D.from_inventor(edge.StopVertex.Point)
    spk = _pt_key3(sp, tol)
    epk = _pt_key3(ep, tol)
    ends = tuple(sorted((spk, epk)))

    edge_evaluator = edge.Evaluator
    start_param, end_param = edge_evaluator.GetParamExtents(0, 1)
    mid_param = (start_param + end_param) / 2.0
    mid_pt = []
    _, mid_pt = edge_evaluator.GetPointAtParam([mid_param], mid_pt)
    mid = tuple(_round_val(c, tol) for c in mid_pt)
    length = edge_evaluator.GetLengthAtParam(start_param, end_param, 0.0)

    adj_faces = []
    faces = edge.Faces
    for i in range(1, getattr(faces, "Count", 0) + 1):
        f = faces.Item(i)
        st = getattr(f, "SurfaceType", None)
        if st is None:
            raise ValueError("Adjacent face has no SurfaceType")
        adj_faces.append(enum_name(st))
    adj_faces.sort()

    axis_info = None
    try:
        axis_point, axis_dir = get_edge_axis(edge)
        axis_info = {
            "point": {
                "x": axis_point[0],
                "y": axis_point[1],
                "z": axis_point[2],
            },
            "direction": {
                "x": axis_dir[0],
                "y": axis_dir[1],
                "z": axis_dir[2],
            }
        }
    except Exception:
        pass  # 忽略无法提取轴线的情况

    return {
        "metaType": "Edge",
        "geometryType": t_name,
        "length": length,
        "midpoint": mid,
        "adjacentFaceTypes": tuple(adj_faces),
        "endpoints": ends,
        "axisInfo": axis_info if axis_info is not None else None,
    }

def are_collinear(v1, v2, tol=1e-9):
    """使用点积判断三维向量是否共线（忽略方向差异）"""
    import numpy as np
    v1 = np.asarray(v1, dtype=float)
    v2 = np.asarray(v2, dtype=float)
    if v1.shape != (3,) or v2.shape != (3,):
        raise ValueError("需要长度为3的向量")
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 < tol or n2 < tol:
        return False  # 约定近零向量不判定共线
    r = abs(np.dot(v1, v2)) / (n1 * n2)  # 理论上共线 => r = 1
    return (1.0 - r) <= tol  # r 足够接近 1



def is_face_meta_similar(meta1: dict, meta2: dict, tol: float = 1e-3) -> tuple[bool, str]:
    if meta1["surfaceType"] != meta2["surfaceType"]:
        return False, "surfaceType not match"
    if abs(meta1["area"] - meta2["area"]) > tol:
        return False, "area not match"
    for a, b in zip(meta1["centroid"], meta2["centroid"]):
        if abs(a - b) > tol:
            return False, "centroid not match"
    # 判断包围盒是否一致
    # rangeBox
    rb1 = meta1['rangeBox']
    rb2 = meta2['rangeBox']
    for a, b in zip(rb1['minPoint'], rb2['minPoint']):
        if abs(a - b) > tol:
            return False, "rangeBox minPoint not match"    
    for a, b in zip(rb1['maxPoint'], rb2['maxPoint']):
        if abs(a - b) > tol:
            return False, "rangeBox maxPoint not match"    
    return True, ""


def is_edge_meta_similar(meta1: dict, meta2: dict, tol: float = 1e-3) -> tuple[bool, str]:
    if meta1["geometryType"] != meta2["geometryType"]:
        return False, "geometryType not match"
    if abs(meta1["length"] - meta2["length"]) > tol:
        return False, "length not match"
    for a, b in zip(meta1["midpoint"], meta2["midpoint"]):
        if abs(a - b) > tol:
            return False, "midpoint not match"
    for a, b in zip(meta1["adjacentFaceTypes"], meta2["adjacentFaceTypes"]):
        if a != b:
            return False, "adjacentFaceTypes not match"
    for a, b in zip(meta1["endpoints"][0], meta2["endpoints"][0]):
        if abs(a - b) > tol:
            return False, "endpoint[0] not match"
    for a, b in zip(meta1["endpoints"][1], meta2["endpoints"][1]):
        if abs(a - b) > tol:
            return False, "endpoint[1] not match"
    return True, ""



def get_plane_normal_from_metadata(meta_data: dict):
    meta_type = meta_data.get("metaType", None)
    if meta_type == "Face":# 只有平面面才有法向量
        plane_info = meta_data.get("planeInfo", None)
        if plane_info is None:
            raise ValueError("Face metadata missing planeInfo for normal extraction")
        normal = plane_info['normal']
        return _normalize_vector((normal['x'], normal['y'], normal['z']))
    elif meta_type == "Edge": # 我们把直线边的方向当作法向量
        axis_info = meta_data.get("axisInfo", None)
        if axis_info is None:
            raise ValueError("Edge metadata missing axisInfo for normal extraction")
        direction = axis_info['direction']
        return _normalize_vector((direction['x'], direction['y'], direction['z']))
    elif meta_type == "AxisEntity": # 把轴线方向当作法向量
        dir = meta_data['direction']
        if isinstance(dir, dict):
            dir = (float(dir.get("x", 0.0)), float(dir.get("y", 0.0)), float(dir.get("z", 0.0)))
        elif isinstance(dir, (list, tuple)):
            if len(dir) != 3:
                raise ValueError("AxisEntity metadata 'direction' must be a 3-element sequence")
            dir = (float(dir[0]), float(dir[1]), float(dir[2]))
        if dir is None:
            raise ValueError("AxisEntity metadata missing direction")
        return _normalize_vector(dir)
    elif meta_type == "PlaneEntity": # 把平面法向量当作法向量
        normal = meta_data['geometry']['normal']
        original = meta_data['geometry']['origin']
        if normal is None:
            raise ValueError("WorkPlane metadata missing normal")
        # 可能是嵌套的字典
        if isinstance(normal, dict):
            normal = (float(normal.get("x", 0.0)), float(normal.get("y", 0.0)), float(normal.get("z", 0.0)))
        # 也可能直接是序列
        elif isinstance(normal, (list, tuple)):
            if len(normal) != 3:
                raise ValueError("PlaneEntity metadata 'normal' must be a 3-element sequence")
            normal = (float(normal[0]), float(normal[1]), float(normal[2]))
        else:
            raise ValueError("PlaneEntity metadata 'normal' has unexpected format")
        return _normalize_vector(normal)
    else:
        raise ValueError(f"Unsupported metaType {meta_type} for normal extraction")

def get_axis_direction_from_metadata(meta_data: dict):
    meta_type = meta_data.get("metaType", None)
    if meta_type == "Edge": # 我们把直线边的方向当作轴线方向
        axis_info = meta_data.get("axisInfo", None)
        if axis_info is None:
            raise ValueError("Edge metadata missing axisInfo for direction extraction")
        direction = axis_info['direction']
        return _normalize_vector((direction['x'], direction['y'], direction['z']))
    elif meta_type == "AxisEntity": 
        dir = meta_data['direction']
        if isinstance(dir, dict):
            dir = (float(dir.get("x", 0.0)), float(dir.get("y", 0.0)), float(dir.get("z", 0.0)))
        elif isinstance(dir, (list, tuple)):
            if len(dir) != 3:
                raise ValueError("AxisEntity metadata 'direction' must be a 3-element sequence")
            dir = (float(dir[0]), float(dir[1]), float(dir[2]))
        if dir is None:
            raise ValueError("AxisEntity metadata missing direction")
        return _normalize_vector(dir)
    elif meta_type == "Face": # 把圆柱面等的轴线当作轴线方向
        axis_info = meta_data.get("axisInfo", None)
        if axis_info is None:
            raise ValueError("Face metadata missing axisInfo for direction extraction")
        direction = axis_info['direction']
        return _normalize_vector((direction['x'], direction['y'], direction['z']))
    else:
        raise ValueError(f"Unsupported metaType {meta_type} for axis direction extraction")


def get_axis_origin_from_metadata(meta_data: dict)-> Tuple[float, float, float]:
    meta_type = meta_data.get("metaType", None)
    origin = None
    if meta_type == "PlaneEntity":
        geometry = meta_data['geometry']
        origin = geometry['origin']
        if origin is None:
            raise ValueError("PlaneEntity metadata missing origin")
        # 可能是嵌套的字典
        if isinstance(origin, dict):
            origin = (float(origin.get("x", 0.0)), float(origin.get("y", 0.0)), float(origin.get("z", 0.0)))
        # 也可能直接是序列
        elif isinstance(origin, (list, tuple)):
            if len(origin) != 3:
                raise ValueError("PlaneEntity metadata 'origin' must be a 3-element sequence")
            origin = (float(origin[0]), float(origin[1]), float(origin[2]))
        else:
            raise ValueError("PlaneEntity metadata 'origin' has unexpected format")
        return origin
    elif meta_type == "AxisEntity":
        origin = meta_data['start_point']
        if origin is None:
            raise ValueError("AxisEntity metadata missing point")
        # 可能是嵌套的字典
        if isinstance(origin, dict):
            origin = (float(origin.get("x", 0.0)), float(origin.get("y", 0.0)), float(origin.get("z", 0.0)))
        # 也可能直接是序列
        elif isinstance(origin, (list, tuple)):
            if len(origin) != 3:
                raise ValueError("AxisEntity metadata 'point' must be a 3-element sequence")
            origin = (float(origin[0]), float(origin[1]), float(origin[2]))
        else:
            raise ValueError("AxisEntity metadata 'point' has unexpected format")
        return origin
    elif meta_type == "Face":
        axis_info = meta_data.get("axisInfo", None)
        if axis_info is None:
            raise ValueError("Face metadata missing axisInfo for origin extraction")
        origin = axis_info['point']
        return (origin['x'], origin['y'], origin['z'])
    elif meta_type == "Edge":
        axis_info = meta_data.get("axisInfo", None)
        if axis_info is None:
            raise ValueError("Edge metadata missing axisInfo for origin extraction")
        origin = axis_info['point']
        return (origin['x'], origin['y'], origin['z'])
    else:
        raise ValueError(f"Unsupported metaType {meta_type} for axis origin extraction")

            

        
