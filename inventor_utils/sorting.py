import math
from typing import List

from .metadata import _pt_key3, _round_val
from .reference import get_reference_key_str
from .geometry import Point3D


def edge_canonical_key(edge, tol: float = 1e-3):
    t = getattr(edge, "GeometryType", None)
    try:
        sp = Point3D.from_inventor(edge.StartVertex.Point)
        ep = Point3D.from_inventor(edge.EndVertex.Point)
        spk = _pt_key3(sp, tol)
        epk = _pt_key3(ep, tol)
        ends = tuple(sorted((spk, epk)))
        mid = tuple(_round_val((a + b) / 2.0, tol) for a, b in zip(spk, epk))
        chord = math.dist(spk, epk)
    except Exception:
        ends = ((0, 0, 0), (0, 0, 0))
        mid = (0, 0, 0)
        chord = 0.0
    rad = 0.0
    try:
        g = edge.Geometry
        if hasattr(g, "Radius"):
            rad = _round_val(g.Radius, tol)
    except Exception:
        pass
    adj_faces = []
    try:
        faces = edge.Faces
        for i in range(1, getattr(faces, "Count", 0) + 1):
            f = faces.Item(i)
            st = getattr(f, "SurfaceType", None)
            adj_faces.append(int(st) if st is not None else -1)
        adj_faces.sort()
    except Exception:
        pass
    return (
        int(t) if t is not None else -1,
        _round_val(rad, tol),
        _round_val(chord, tol),
        mid,
        tuple(adj_faces),
        ends,
    )


def face_canonical_key(face, tol: float = 1e-3):
    st = None
    area = 0.0
    centroid = (0, 0, 0)
    orient = (0, 0, 0)
    extra = (0.0,)
    try:
        face_evaluator = face.Evaluator
        g = face.Geometry
        st = getattr(face, "SurfaceType", None)
        try:
            area = _round_val(face_evaluator.Area, tol)
        except Exception:
            area = 0.0
        try:
            box = face.Evaluator.RangeBox
            lo = _pt_key3(Point3D.from_inventor(box.MinPoint), tol)
            hi = _pt_key3(Point3D.from_inventor(box.MaxPoint), tol)
            centroid = tuple(_round_val((a + b) / 2.0, tol) for a, b in zip(lo, hi))
        except Exception:
            centroid = (0, 0, 0)
        if hasattr(g, "Normal"):
            orient = _pt_key3(Point3D.from_inventor(g.Normal), tol)
        elif hasattr(g, "AxisVector"):
            orient = _pt_key3(Point3D.from_inventor(g.AxisVector), tol)
        if hasattr(g, "Radius"):
            extra = (_round_val(g.Radius, tol),)
    except Exception:
        pass
    return (
        _round_val(area, tol),
        centroid,
        orient,
        extra,
        int(st) if st is not None else -1,
    )


def body_canonical_key(body, tol: float = 1e-3):
    vol = area = 0.0
    centroid = (0.0, 0.0, 0.0)
    bbox = (0.0, 0.0, 0.0)
    nf = ne = 0
    try:
        mp = getattr(body, "MassProperties", None)
        if mp:
            vol = _round_val(getattr(mp, "Volume", 0.0), tol)
            c = getattr(mp, "CenterOfMass", None)
            if c:
                centroid = _pt_key3(c, tol)
        area = _round_val(getattr(body, "Area", 0.0), tol)
    except Exception:
        pass
    try:
        rb = getattr(body, "RangeBox", None)
        if rb:
            lo = _pt_key3(rb.MinPoint, tol)
            hi = _pt_key3(rb.MaxPoint, tol)
            bbox = (
                _round_val(hi[0] - lo[0], tol),
                _round_val(hi[1] - lo[1], tol),
                _round_val(hi[2] - lo[2], tol),
            )
    except Exception:
        pass
    try:
        nf = int(getattr(getattr(body, "Faces", None), "Count", 0))
        ne = int(getattr(getattr(body, "Edges", None), "Count", 0))
    except Exception:
        nf = ne = 0
    face_types = []
    try:
        faces = getattr(body, "Faces", None)
        if faces:
            for i in range(1, min(5, faces.Count) + 1):
                f = faces.Item(i)
                try:
                    st = getattr(f, "SurfaceType", None)
                    face_types.append(int(st) if st is not None else -1)
                except Exception:
                    face_types.append(-1)
            face_types.sort()
    except Exception:
        pass
    return (vol, area, centroid, bbox, nf, ne, tuple(face_types))


def stable_sorted_edges(body, tol: float = 1e-3, prefer_refkey: bool = False):
    edges = [body.Edges.Item(i) for i in range(1, getattr(body.Edges, "Count", 0) + 1)]
    if prefer_refkey:
        try:
            return sorted(edges, key=lambda e: get_reference_key_str(e))
        except Exception:
            pass
    return sorted(edges, key=lambda e: edge_canonical_key(e, tol))


def stable_sorted_faces(body, tol: float = 1e-3, prefer_refkey: bool = False):
    faces = [body.Faces.Item(i) for i in range(1, getattr(body.Faces, "Count", 0) + 1)]
    if prefer_refkey:
        try:
            return sorted(faces, key=lambda f: get_reference_key_str(f))
        except Exception:
            pass
    return sorted(faces, key=lambda f: face_canonical_key(f, tol))


def stable_sorted_bodies(feature, tol: float = 1e-3, prefer_refkey: bool = False):
    bodies = (
        getattr(feature, "ResultBodies", None)
        or getattr(feature, "SurfaceBodies", None)
        or getattr(feature, "Bodies", None)
    )
    if not bodies:
        return []
    arr = [bodies.Item(i) for i in range(1, getattr(bodies, "Count", 0) + 1)]
    if prefer_refkey:
        try:
            return sorted(arr, key=lambda b: get_reference_key_str(b))
        except Exception:
            pass
    return sorted(arr, key=lambda b: body_canonical_key(b, tol))


def body_stable_rank_in_feature(feature, body, tol: float = 1e-3) -> int:
    sorted_b = stable_sorted_bodies(feature, tol)
    if not sorted_b:
        return -1
    try:
        key = get_reference_key_str(body)
        if key:
            for idx, b in enumerate(sorted_b, start=1):
                try:
                    if get_reference_key_str(b) == key:
                        return idx
                except Exception:
                    continue
    except Exception:
        pass

    target = body_canonical_key(body, tol)
    for idx, b in enumerate(sorted_b, start=1):
        if body_canonical_key(b, tol) == target:
            return idx
    return -1
