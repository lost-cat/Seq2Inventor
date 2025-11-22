import math
from typing import Tuple

from .geometry import Point3D
from .enums import enum_name


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


def collect_face_metadata(face, tol: float = 1e-3) -> dict:
    metadata = {}
    st = getattr(face, "SurfaceType", None)
    if st is None:
        raise ValueError("Face has no SurfaceType")
    st = enum_name(st)
    face_evaluator = face.Evaluator
    area = _round_val(face_evaluator.Area, tol)

    box = face.Evaluator.RangeBox
    lo = _pt_key3(Point3D.from_inventor(box.MinPoint), tol)
    hi = _pt_key3(Point3D.from_inventor(box.MaxPoint), tol)
    centroid = tuple(_round_val((a + b) / 2.0, tol) for a, b in zip(lo, hi))
    orient = []
    _, orient = face_evaluator.GetNormal([0.5, 0.5], orient)
    orient = tuple(_round_val(c, tol) for c in orient)
    utangent = []
    v_tangent = []
    _, utangent, v_tangent = face_evaluator.GetFirstDerivatives([0.5, 0.5], utangent, v_tangent)

    metadata = {
        "surfaceType": st,
        "area": area,
        "centroid": centroid,
        "orientation": orient,
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
        "geometryType": t_name,
        "length": length,
        "midpoint": mid,
        "adjacentFaceTypes": tuple(adj_faces),
        "endpoints": ends,
    }


def is_face_meta_similar(meta1: dict, meta2: dict, tol: float = 1e-3) -> tuple[bool, str]:
    if meta1["surfaceType"] != meta2["surfaceType"]:
        return False, "surfaceType not match"
    if abs(meta1["area"] - meta2["area"]) > tol:
        return False, "area not match"
    for a, b in zip(meta1["centroid"], meta2["centroid"]):
        if abs(a - b) > tol:
            return False, "centroid not match"
    for a, b in zip(meta1["orientation"], meta2["orientation"]):
        if abs(a - b) > tol:
            return False, "orientation not match"
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
