import math
from typing import Tuple

import numpy

from .geometry import AxisEntityWrapper, Point3D
from .enums import enum_name, is_type_of


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
    metadata = {
        "metaType": "Face",
        "surfaceType": st,
        "area": area,
        "centroid": centroid,
        "orientation": orient,
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

    return {
        "metaType": "Edge",
        "geometryType": t_name,
        "length": length,
        "midpoint": mid,
        "adjacentFaceTypes": tuple(adj_faces),
        "endpoints": ends,
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
