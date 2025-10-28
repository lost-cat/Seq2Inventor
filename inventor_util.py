from copy import copy
from enum import Enum
from functools import lru_cache
import math
from typing import Any, Optional

import numpy as np
import win32com.client
from win32com.client import constants
# Removed unused import for EnsureDispatch

from cad_utils.curves import Line, Circle, Arc
from cad_utils.macro import EXTENT_TYPE, BODY_OPERATIONS
from geometry_util import Point3D


class ExtentType(Enum):
    kNegativeExtentDirection = 20994
    kPositiveExtentDirection = 20993
    kSymmetricExtentDirection = 20995

class CurveType(Enum):
    kBSplineCurve2d = 5256      # Curve2d bspline type.
    kCircleCurve2d = 5252       # Curve2d circle type.
    kCircularArcCurve2d = 5253  # Curve2d circular arc type.
    kEllipseFullCurve2d = 5254  # Curve2d ellipse full type.
    kEllipticalArcCurve2d = 5255  # Curve2d elliptical arc type.
    kLineCurve2d = 5250         # Curve2d line type.
    kLineSegmentCurve2d = 5251  # Curve2d line segment type.
    kPolylineCurve2d = 5257     # Curve2d polyline type.
    kUnknownCurve2d = 5249      # Curve2d unknown type.


def get_reference_key_str(entity):
    part = entity.Application.ActiveDocument
    reference_manager = part.ReferenceKeyManager
    key_context = reference_manager.CreateKeyContext()
    key = get_reference_key(entity, key_context)
    key_str = get_string_reference_key(key, reference_manager)
    return key_str

def get_entity_by_reference_key(doc, key, key_context):

    entity = None
    context = None
    status, _, entity, context = doc.ReferenceKeyManager.CanBindKeyToObject(key, key_context, entity, context)
    if (status):
        return entity
    else:
        return None
    pass

def get_string_reference_key(reference_key, reference_key_manager):

    string, location = reference_key_manager.KeyToString(reference_key)
    return string
    pass

def get_reference_key(entity, key_context):

    key = []
    key = entity.GetReferenceKey(key, key_context)
    return key
    pass


def get_face_by_transient_key(com_def, key):
    """
    Retrieves a face from a component definition by its transient key.

    Args:
        com_def: The component definition object containing the surface bodies.
        key: The transient key of the face to be retrieved.

    Returns:
        The face object with the specified transient key if found, otherwise None.
    """
    faces = com_def.SurfaceBodies.Item(1).Faces
    for i in range(1, faces.Count + 1):
        face = faces.Item(i)
        if face.TransientKey == key:
            return face
    return None

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


def edge_canonical_key(edge, tol: float = 1e-3):
    """跨文档可复现的 Edge 排序键（可能有并列，需配合更多字段打破）"""
    t = getattr(edge, "GeometryType", None)
    # 端点/中点/长度/半径
    try:
        sp = Point3D.from_inventor(edge.StartVertex.Point); ep = Point3D.from_inventor(edge.EndVertex.Point)
        spk = _pt_key3(sp, tol); epk = _pt_key3(ep, tol)
        # 端点无序（线段方向不影响）：按字典序把小的放前面
        ends = tuple(sorted((spk, epk)))
        mid = tuple(_round_val((a+b)/2.0, tol) for a, b in zip(spk, epk))
        chord = math.dist(spk, epk)
    except Exception:
        ends = ((0,0,0),(0,0,0)); mid = (0,0,0); chord = 0.0
    rad = 0.0
    try:
        g = edge.Geometry
        if hasattr(g, "Radius"):
            rad = _round_val(g.Radius, tol)
    except Exception:
        pass
    # 相邻面类型（排序后作为键的一部分）
    adj_faces = []
    try:
        faces = edge.Faces
        for i in range(1, getattr(faces, "Count", 0)+1):
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

def face_canonical_key(face, tol: float = 1e-6):
    """跨文档可复现的 Face 排序键"""
    st = None; area = 0.0; centroid = (0,0,0); orient = (0,0,0); extra = (0.0,)
    try:
        face_evaluator = face.Evaluator
        g = face.Geometry
        st = getattr(face, "SurfaceType", None)
        # 面积与重心（有些版本 Area/PointOnFace 可用）
        try:
            area = _round_val(face_evaluator.Area, tol)
        except Exception:
            area = 0.0
  
        try:
            box = face.Evaluator.RangeBox
            lo = _pt_key3(Point3D.from_inventor(box.MinPoint), tol)
            hi = _pt_key3(Point3D.from_inventor(box.MaxPoint), tol)
            centroid = tuple(_round_val((a+b)/2.0, tol) for a, b in zip(lo, hi))
        except Exception:
            centroid = (0,0,0)
        # 方向信息（平面用法向，圆柱/圆锥用轴向，球面无方向）
        if hasattr(g, "Normal"):  # Plane
            orient = _pt_key3(Point3D.from_inventor(g.Normal), tol)
        elif hasattr(g, "AxisVector"):  # Cylinder/Cone
            orient = _pt_key3(Point3D.from_inventor(g.AxisVector), tol)
        # 半径（Cylinder/Sphere）
        if hasattr(g, "Radius"):
            extra = (_round_val(g.Radius, tol),)
    except Exception:
        pass
    return (
        int(st) if st is not None else -1,
        _round_val(area, tol),
        centroid,
        orient,
        extra,
    )

def body_canonical_key(body, tol: float = 1e-6):
    """
    跨文档可复现的 SurfaceBody 排序键（体积、面积、质心、包围盒尺寸、面/边数量、少量面类型快照）。
    """
    vol = area = 0.0
    centroid = (0.0, 0.0, 0.0)
    bbox = (0.0, 0.0, 0.0)
    nf = ne = 0
    # 体积、质心、表面积
    try:
        mp = getattr(body, "MassProperties", None)
        if mp:
            vol = _round_val(getattr(mp, "Volume", 0.0), tol)
            c = Point3D.from_inventor(getattr(mp, "CenterOfMass", None))
            if c:
                centroid = _pt_key3(c, tol)
        area = _round_val(getattr(body, "Area", 0.0), tol)
    except Exception:
        pass
    # 包围盒尺寸
    try:
        rb = getattr(body, "RangeBox", None)
        if rb:
            lo = _pt_key3(rb.MinPoint, tol)
            hi = _pt_key3(rb.MaxPoint, tol)
            bbox = (_round_val(hi[0] - lo[0], tol),
                    _round_val(hi[1] - lo[1], tol),
                    _round_val(hi[2] - lo[2], tol))
    except Exception:
        pass
    # 计数与少量面类型快照（打破并列）
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


def stable_sorted_edges(doc, body, tol: float = 1e-6, prefer_refkey: bool = True):
    """返回该 body 的 Edges 按稳定键排序的列表。"""
    edges = [body.Edges.Item(i) for i in range(1, getattr(body.Edges, "Count", 0)+1)]
    if prefer_refkey:
        # 同文档内：优先按 ReferenceKey 排序（最稳定）
        try:
            return sorted(edges, key=lambda e: get_reference_key_str(e))
        except Exception:
            pass
    # 跨文档排序键
    return sorted(edges, key=lambda e: edge_canonical_key(e, tol))


def stable_sorted_faces(body, tol: float = 1e-6, prefer_refkey: bool = False):
    faces = [body.Faces.Item(i) for i in range(1, getattr(body.Faces, "Count", 0)+1)]
    if prefer_refkey:
        try:
            return sorted(faces, key=lambda f: get_reference_key_str(f))
        except Exception:
            pass
    return sorted(faces, key=lambda f: face_canonical_key(f, tol))

def stable_sorted_bodies(feature, tol: float = 1e-6, prefer_refkey: bool = False):
    """
    返回特征的 SurfaceBodies/ResultBodies 按稳定键排序后的列表。
    同文档内可优先用 ReferenceKey;跨文档回退到几何键。
    """
    bodies = (getattr(feature, "ResultBodies", None)
              or getattr(feature, "SurfaceBodies", None)
              or getattr(feature, "Bodies", None))
    if not bodies:
        return []
    arr = [bodies.Item(i) for i in range(1, getattr(bodies, "Count", 0) + 1)]
    if prefer_refkey:
        try:
            return sorted(arr, key=lambda b: get_reference_key_str(b))
        except Exception:
            pass
    return sorted(arr, key=lambda b: body_canonical_key(b, tol))

def body_stable_rank_in_feature( feature, body, tol: float = 1e-6) -> int:
    """
    给定某个 body,返回它在稳定排序中的 1-based 序号；失败时返回 -1。
    """
    sorted_b = stable_sorted_bodies( feature, tol)
    if not sorted_b:
        return -1
    # 优先 refkey 精确匹配
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

    # 回退：几何键相同则命中（可能重复，取首个）
    target = body_canonical_key(body, tol)
    for idx, b in enumerate(sorted_b, start=1):
        if body_canonical_key(b, tol) == target:
            return idx
    return -1


def pick_edge_by_stable_ranks( feature, stable_body_rank: int, stable_edge_rank: int, tol: float = 1e-6):
    """
    按稳定排序选出指定 body 与其内的 edge(均为 1-based rank)。
    """
    bodies_sorted = stable_sorted_bodies(feature, tol)
    if not bodies_sorted or stable_body_rank < 1 or stable_body_rank > len(bodies_sorted):
        return None
    body = bodies_sorted[stable_body_rank - 1]
    edges_sorted = stable_sorted_edges(body, tol)
    if not edges_sorted or stable_edge_rank < 1 or stable_edge_rank > len(edges_sorted):
        return None
    return edges_sorted[stable_edge_rank - 1]

def pick_face_by_stable_ranks(part_doc, feature, stable_body_rank: int, stable_face_rank: int, tol: float = 1e-6):
    """
    按稳定排序选出指定 body 与其内的 face(均为 1-based rank)。
    """
    bodies_sorted = stable_sorted_bodies(feature, tol)
    if not bodies_sorted or stable_body_rank < 1 or stable_body_rank > len(bodies_sorted):
        return None
    body = bodies_sorted[stable_body_rank - 1]
    faces_sorted = stable_sorted_faces(body, tol)
    if not faces_sorted or stable_face_rank < 1 or stable_face_rank > len(faces_sorted):
        return None
    return faces_sorted[stable_face_rank - 1]


def get_edge_by_transient_key(com_def, key):
    edges = com_def.SurfaceBodies.Item(1).Edges
    for i in range(1, edges.Count + 1):
        edge = edges.Item(i)
        if edge.TransientKey == key:
            return edge
    return None


def get_face_normal(face):
    normal_params = [0.3, 0.3]
    normal = [0, 1, 0]
    normal_params, normal = face.Evaluator.GetNormal(normal_params, normal)
    return normal


def get_face_centroid(face):
    rect = face.Evaluator.ParamRangeRect
    max_uv = rect.MaxPoint
    min_uv = rect.MinPoint
    mid_uv = [(max_uv.X + min_uv.X) / 2, (max_uv.Y + min_uv.Y) / 2]
    center_point = [0, 0, 0]
    mid_uv, center_point = face.Evaluator.GetPointAtParam(mid_uv, center_point)
    return center_point


def get_face_area(face):
    return face.Evaluator.Area


def filter_face_by_normal_and_centroid(faces, normal, centroid):
    for i in range(1, faces.Count + 1):
        face = faces.Item(i)
        out_normal = get_face_normal(face)
        out_centroid = get_face_centroid(face)
        if np.allclose(normal, out_normal) and np.allclose(out_centroid, centroid):
            return face
    return None


def get_inventor_application():
    """Get or start Autodesk Inventor.Application with robust makepy handling.

    Tries EnsureDispatch first (so constants and typed wrappers are available).
    If EnsureDispatch fails due to a broken gen_py cache (e.g., CLSIDToClassMap),
    attempts to rebuild the cache, then retries. Finally falls back to dynamic
    Dispatch as a last resort.
    """
    try:
        from win32com.client import gencache
        try:
            return gencache.EnsureDispatch("Inventor.Application")
        except Exception:
            # Fall back to dynamic dispatch (no makepy)
            return win32com.client.Dispatch("Inventor.Application")
    except Exception as e:
        print("Error: Unable to get Inventor.Application object.", e)
        return None


def create_inventor_model_from_sequence(seq, com_def):
    for extrude_op in seq:
        ext_def = convert_to_extrude_inventor(com_def, extrude_op)

        feature = add_extrude_feature(com_def, ext_def)


class ExtrudeType(Enum):
    Join = 1
    Cut = 2
    NewBody = 3
    Intersect = 4

    def get_type(self):
        extrude_type = self
        ext_type_inventor = constants.kNewBodyOperation
        if extrude_type == ExtrudeType.Join:
            ext_type_inventor = constants.kJoinOperation
        elif extrude_type == ExtrudeType.Cut:
            ext_type_inventor = constants.kCutOperation
        elif extrude_type == ExtrudeType.Intersect:
            ext_type_inventor = constants.kIntersectOperation

        return ext_type_inventor


class ExtrudeDirection(Enum):
    Positive = 1
    Negative = 2
    Symmetric = 3

    def get_direction(self):
        extrude_dir = self
        ext_dir_inventor = constants.kPositiveExtentDirection
        if extrude_dir == ExtrudeDirection.Negative:
            ext_dir_inventor = constants.kNegativeExtentDirection
        elif extrude_dir == ExtrudeDirection.Symmetric:
            ext_dir_inventor = constants.kSymmetricExtentDirection

        return ext_dir_inventor


def add_part_document(app, name):
    if app is None:
        app = get_inventor_application()
    if app is None:
        raise RuntimeError("Inventor application is not available")
    part = app.Documents.Add(constants.kPartDocumentObject, "", True)
    try:
        part = win32com.client.CastTo(part, "PartDocument")
    except Exception:
        # Use dynamic object if cast fails (e.g., typelibs not generated yet)
        pass
    part.DisplayName = name
    com_def = part.ComponentDefinition
    return part, com_def


def add_sketch(com_def, work_plane=None):
    if work_plane is None:
        work_plane = com_def.WorkPlanes.Item(3)
    sketch = com_def.Sketches.Add(work_plane)
    return sketch


def add_sketch_from_last_extrude_end_face(com_def):
    faces = com_def.SurfaceBodies.Item(1).Faces
    face = faces.Item(faces.Count)
    sketch = com_def.Sketches.Add(face)
    return sketch


def transient_point_2d(app, x, y):
    return app.TransientGeometry.CreatePoint2d(x, y)


def transient_point_3d(app, x, y, z):
    return app.TransientGeometry.CreatePoint(x, y, z)


def transient_unit_vector_3d(app, x, y, z):
    return app.TransientGeometry.CreateUnitVector(x, y, z)


def add_sketch2d_line(sketch, start_point, end_point):
    line = sketch.SketchLines.AddByTwoPoints(start_point, end_point)
    return line


def add_sketch2d_circle(sketch, center, radius):
    circle = sketch.SketchCircles.AddByCenterRadius(center, radius)
    return circle

def add_sketch2d_arc(sketch, center, radius, start_angle, sweep_angle):
    arc = sketch.SketchArcs.AddByCenterStartSweepAngle(center, radius, start_angle, sweep_angle)
    return arc


def add_work_plane(com_def, origin, x_axis, y_axis):
    origin = transient_point_3d(com_def.Application, *origin)
    x_axis = transient_unit_vector_3d(com_def.Application, *x_axis)
    y_axis = transient_unit_vector_3d(com_def.Application, *y_axis)
    work_plane = com_def.WorkPlanes.AddFixed(origin, x_axis, y_axis)
    return work_plane


def add_profile(sketch):
    profile = sketch.Profiles.AddForSolid()
    return profile


def create_extrude_definition(
    com_def,
    profile,
    distance1,
    distance2,
    extrude_type: ExtrudeType,
    extrude_direction: ExtrudeDirection,
):
    extrude_def = com_def.Features.ExtrudeFeatures.CreateExtrudeDefinition(
        profile, extrude_type.get_type()
    )
    extrude_def.SetDistanceExtent(distance1, extrude_direction.get_direction())
    if extrude_direction == ExtrudeDirection.Symmetric:
        extrude_def.SetDistanceExtentTwo(distance2)
    return extrude_def


def convert_to_extrude_inventor(com_def, extrude_op):
    profile = copy(extrude_op.profile)
    profile.denormalize(extrude_op.sketch_size)
    sketch_plane = copy(extrude_op.sketch_plane)
    sketch_plane.origin = extrude_op.sketch_pos

    plane = add_work_plane(
        com_def, sketch_plane.origin, sketch_plane.x_axis, sketch_plane.y_axis
    )
    plane.Visible = False
    sketch_inventor = add_sketch(com_def, plane)

    profile_inventor = convert_to_inventor_profile(sketch_inventor, profile)
    extrude_type = convert_extrude_op_to_inventor(extrude_op.operation)
    extrude_dir = convert_extrude_dir_to_inventor(extrude_op.extent_type)
    if extrude_dir != ExtrudeDirection.Symmetric and extrude_op.extent_one < 0:
        extrude_op.extent_one = -extrude_op.extent_one
        if extrude_dir == ExtrudeDirection.Positive:
            extrude_dir = ExtrudeDirection.Negative
        else:
            extrude_dir = ExtrudeDirection.Positive

    extrude_def = create_extrude_definition(
        com_def,
        profile_inventor,
        extrude_op.extent_one,
        extrude_op.extent_two,
        extrude_type,
        extrude_dir,
    )
    return extrude_def


def convert_extrude_op_to_inventor(operation):
    if operation == EXTRUDE_OPERATIONS.index("NewBodyFeatureOperation"):
        extrude_type = ExtrudeType.NewBody
    elif operation == EXTRUDE_OPERATIONS.index("JoinFeatureOperation"):
        extrude_type = ExtrudeType.Join
    elif operation == EXTRUDE_OPERATIONS.index("CutFeatureOperation"):
        extrude_type = ExtrudeType.Cut
    elif operation == EXTRUDE_OPERATIONS.index("IntersectFeatureOperation"):
        extrude_type = ExtrudeType.Intersect
    else:
        raise ValueError("Invalid operation")

    return extrude_type


def convert_extrude_dir_to_inventor(direction):
    if direction == EXTENT_TYPE.index("OneSideFeatureExtentType"):
        extrude_dir = ExtrudeDirection.Positive
    elif direction == EXTENT_TYPE.index("SymmetricFeatureExtentType"):
        extrude_dir = ExtrudeDirection.Symmetric
    elif direction == EXTENT_TYPE.index("TwoSidesFeatureExtentType"):
        extrude_dir = ExtrudeDirection.Symmetric
    else:
        raise ValueError("Invalid direction")

    return extrude_dir


def add_chamfer_feature(com_def, edge, distance):
    """
    Adds a chamfer feature to the specified edge in the given component definition.

    Args:
        com_def: The component definition object where the chamfer feature will be added.
        edge: The edge object to which the chamfer feature will be applied.
        distance: The distance value for the chamfer feature.

    Returns:
        The created chamfer feature object.
    """
    edgeCollection = com_def.Application.TransientObjects.CreateEdgeCollection()
    edgeCollection.Add(edge)
    chamfer_feature = com_def.Features.ChamferFeatures.AddUsingDistance(
        edgeCollection, distance
    )
    return chamfer_feature


def add_revolve_feature(com_def, profile, axis_entity, angle, direction, operation):
    revolve_feature = com_def.Features.RevolveFeatures.AddByAngle(
        profile,
        axis_entity,
        angle,
        direction,
        operation
    )
    return revolve_feature


def add_fillet_feature(com_def, edge, radius):
    """
    Adds a fillet feature to the given edge with the specified radius.

    Parameters:
    com_def (ComponentDefinition): The component definition object.
    edge (Edge): The edge to which the fillet feature will be added.
    radius (float): The radius of the fillet.

    Returns:
    FilletFeature: The created fillet feature.
    """
    edgeCollection =com_def.Application.TransientObjects.CreateEdgeCollection()
    edgeCollection.Add(edge)
    fillet_feature = com_def.Features.FilletFeatures.AddSimple(edgeCollection, radius)
    return fillet_feature


def add_extrude_feature(com_def, extrude_def):
    extrude_feature = com_def.Features.ExtrudeFeatures.Add(extrude_def)
    return extrude_feature


def convert_to_inventor_curve(curve, sketch):
    if isinstance(curve, Line):
        if np.allclose(curve.start_point, curve.end_point):
            return -1
        start_point = transient_point_2d(sketch.Application, *curve.start_point)
        end_point = transient_point_2d(sketch.Application, *curve.end_point)
        curve_inv = add_sketch2d_line(sketch, start_point, end_point)
    elif isinstance(curve, Circle):
        center = transient_point_2d(sketch.Application, *curve.center)
        radius = curve.radius
        curve_inv = add_sketch2d_circle(sketch, center, radius)
    elif isinstance(curve, Arc):
        start_point = transient_point_2d(sketch.Application, *curve.start_point)
        mid_point = transient_point_2d(sketch.Application, *curve.mid_point)
        end_point = transient_point_2d(sketch.Application, *curve.end_point)
        curve_inv = sketch.SketchArcs.AddByThreePoints(
            start_point, mid_point, end_point
        )
    else:
        raise NotImplementedError(type(curve))
    return curve_inv
    pass


def convert_to_inventor_profile(sketch_inventor, profile):
    for loop in profile.children:
        curves = []
        curves_inv = []

        for curve in loop.children:
            curve_inv = convert_to_inventor_curve(curve, sketch_inventor)
            if curve_inv == -1:
                continue
            if len(curves) != 0 and not isinstance(curve, Circle):
                if isinstance(curves[-1], Circle):
                    continue
                curves_inv[-1].EndSketchPoint.Merge(curve_inv.StartSketchPoint)
            curves.append(curve)
            curves_inv.append(curve_inv)

        if not isinstance(curves[-1], Circle) and not isinstance(curves[0], Circle):
            curves_inv[0].StartSketchPoint.Merge(curves_inv[-1].EndSketchPoint)

    profile = add_profile(sketch_inventor)
    return profile
    pass


# ----------------------------
# Enum/Constants mapping utils
# ----------------------------

@lru_cache(maxsize=1)
def _constants_reverse_index():
    """Build a reverse index of Inventor constants: value -> [names].
    根据 win32com.client.__init__ 中 Constants 的实现，常量保存在
    constants.__dicts__ 列表中的多个字典里。这里遍历所有字典，
    收集以 'k' 开头的名称，并建立 value -> [names] 的反向索引。

    若一开始取不到（未生成类型库），会尝试懒加载一次 Inventor 的类型库。
    """

    def _collect():
        idx_local = {}
        try:
            dicts = getattr(constants, "__dicts__")
        except Exception:
            dicts = []
        for d in dicts or []:
            try:
                items = d.items()
            except Exception:
                continue
            for name, val in items:
                if not isinstance(name, str) or not name.startswith('k'):
                    continue
                # 仅保留整数型的值
                if isinstance(val, bool):
                    continue
                if not isinstance(val, int):
                    try:
                        import numbers
                        if not isinstance(val, numbers.Integral):
                            continue
                    except Exception:
                        continue
                idx_local.setdefault(val, set()).add(name)
        return idx_local

    idx = _collect()
    # 若为空，尝试通过 EnsureDispatch 触发类型库生成
    if not idx:
        try:
            from win32com.client import gencache
            try:
                gencache.EnsureDispatch("Inventor.Application")
            except Exception:
                pass
        except Exception:
            pass
        idx = _collect()

    # 冻结为排序列表，保证确定性
    return {k: sorted(v) for k, v in idx.items()}


def enum_names(value, prefix=None, suffix=None, contains=None):
    """Return all constant names matching the numeric value, optionally filtered.

    Filters:
      - prefix: only names starting with this
      - suffix: only names ending with this
      - contains: only names containing this substring
    """
    names = _constants_reverse_index().get(value, [])
    if prefix:
        names = [n for n in names if n.startswith(prefix)]
    if suffix:
        names = [n for n in names if n.endswith(suffix)]
    if contains:
        names = [n for n in names if contains in n]
    return names


def enum_name(value, prefix=None, suffix=None, contains=None, default=None):
    """Return a single best name for the enum value using optional filters.
    If multiple remain, return the first alphabetically; if none, default.
    """
    names = enum_names(value, prefix=prefix, suffix=suffix, contains=contains)
    if names:
        return names[0]
    return default


def object_type_name(value):
    """Map Inventor ObjectType numeric code to a friendly name (ends with 'Object')."""
    return enum_name(value, suffix='Object')


def operation_name(value):
    """Map operation enum (Join/Cut/NewBody/Intersect) to name (ends with 'Operation')."""
    return enum_name(value, suffix='Operation')


def extent_direction_name(value):
    """Map extent direction to name (ends with 'ExtentDirection')."""
    return enum_name(value, suffix='ExtentDirection')


def extent_type_name(value):
    """Map extent type to name; handles common suffixes."""
    return enum_name(value, suffix='Extent') or enum_name(value, suffix='ExtentType')


def map_values_to_names(values, *, prefix=None, suffix=None, contains=None):
    """Convenience to map a list/set of enum values to their names using filters."""
    return {v: enum_name(v, prefix=prefix, suffix=suffix, contains=contains) for v in values}


def remove_padding(vec):
    commands = vec[:, 0].tolist()
    if 3 in commands:
        seq_len = commands.index(3)
        vec = vec[: seq_len + 1]
    return vec


# todo: implement this
def save__inventor_document(doc, file_path):
    doc.SaveAs(file_path, False)
    pass


def open_inventor_document(app, file_path):
    """
    Opens an Inventor .ipt file using the provided Inventor application object.

    Args:
        app: The Inventor application object.
        file_path: The path to the .ipt file.

    Returns:
        The opened PartDocument object, or None if failed.
    """
    if app is None:
        app = get_inventor_application()
    if app is None:
        print("Error: Inventor application is not available.")
        return None
    try:
        part_doc = app.Documents.Open(file_path, True)
        try:
            part_doc = win32com.client.CastTo(part_doc, "PartDocument")
        except Exception:
            # If cast fails, continue with dynamic object
            pass
        return part_doc
    except Exception as e:
        print(f"Error opening Inventor document: {e}")
        return None
    
def get_all_features(doc):
    """
    获取该零件所有的feature,保证feature顺序与创建时一致
    Args:
        doc: Inventor PartDocument 对象
    Returns:
        features_list: 按创建顺序排列的所有 feature 对象列表
    """
    com_def = doc.ComponentDefinition
    features = com_def.Features
    features_list = []
    # 按照Features集合的顺序遍历
    for i in range(1, features.Count + 1):
        feature = features.Item(i)
        features_list.append(feature)
    return features_list



def index_edge(edge) -> dict:
    """
    获取edge在feature中的索引
    Args:
        edge: Inventor Edge 对象
    Returns:
        dict: 包含 surfaceBodyRank, edgeRank, featureName 的字典
    """
    surface_body = edge.Parent
    edge_rank = -1
    sorted_edges = stable_sorted_edges(surface_body,1e-3)
    for idx, e in enumerate(sorted_edges, start=1):
        if get_reference_key_str(e) == get_reference_key_str(edge):
            edge_rank = idx
            break

    created_by_feature = surface_body.CreatedByFeature
    surface_body_rank = -1
    sorted_bodies = stable_sorted_bodies(created_by_feature,1e-3)
    for idx, b in enumerate(sorted_bodies, start=1):
        if get_reference_key_str(b) == get_reference_key_str(surface_body):
            surface_body_rank = idx
            break
        
    if surface_body_rank == -1 or edge_rank == -1:
        print(f"Warning: Could not find edge rank or surface body rank for edge in feature {created_by_feature.Name}")
    return {"surfaceBodyRank": surface_body_rank, "edgeRank": edge_rank,"featureName": created_by_feature.Name}


def index_face(face) -> dict:
    """
    获取face在feature中的索引
    Args:
        face: Inventor Face 对象
    Returns:
        dict: 包含 surfaceBodyRank, faceRank, featureName 的字典
    """
    surface_body = face.Parent
    face_rank = -1
    sorted_faces = stable_sorted_faces(face.Parent,1e-3)
    for idx, f in enumerate(sorted_faces, start=1):
        if get_reference_key_str(f) == get_reference_key_str(face):
            face_rank = idx
            break
    
    surface_body_rank = -1
    created_by_feature = surface_body.CreatedByFeature
    sorted_bodies = stable_sorted_bodies(created_by_feature,1e-3)
    for idx, b in enumerate(sorted_bodies, start=1):
        if get_reference_key_str(b) == get_reference_key_str(surface_body):
            surface_body_rank = idx
            break
    

    if surface_body_rank == -1 or face_rank == -1:
        print(f"Warning: Could not find face index or surface body index for face in feature {created_by_feature.Name}")
    return {"surfaceBodyRank": surface_body_rank, "faceRank": face_rank,"featureName": created_by_feature.Name}

def get_face_by_index(com_def, face_index) -> Optional[Any]:
    """
    通过face的索引获取face对象
    Args:
        com_def: Inventor ComponentDefinition 对象
        face_index: face的索引
    Returns:
        face: Inventor Face 对象,如果没有找到则返回None
    """
    try:
        
        feature = get_feature_by_name(com_def, face_index['featureName'])
        if not feature:
            return None
        body = feature.SurfaceBodies.Item(face_index['surfaceBodyIndex'])
        return body.Faces.Item(face_index['faceIndex'])
    except Exception as e:
        print(f"Error in get_face_by_index: {e}")
        return None

def get_feature_by_name(com_def, feature_name):
    """
    通过feature的名字获取feature对象
    Args:
        com_def: Inventor ComponentDefinition 对象
        feature_name: feature的名字
    Returns:
        feature: Inventor Feature 对象,如果没有找到则返回None
    """
    features = com_def.Features
    for i in range(1, features.Count + 1):
        feature = features.Item(i)
        if feature.Name == feature_name:
            return feature
    return None