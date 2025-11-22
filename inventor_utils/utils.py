from typing import Optional, TextIO

import numpy as np



def _emit(line: str, out: Optional[TextIO] = None) -> None:
    if out is None:
        print(line)
    else:
        out.write(line + "\n")


def remove_padding(vec):
    commands = vec[:, 0].tolist()
    if 3 in commands:
        seq_len = commands.index(3)
        vec = vec[: seq_len + 1]
    return vec


def select_entity_in_inventor_app(entity):
    try:
        doc = entity.Application.ActiveDocument
        select_set = doc.SelectSet
        select_set.Clear()
        select_set.Select(entity)
    except Exception as e:
        print(f"Error selecting entity in Inventor app: {e}")


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




def _json_default(obj):
    from inventor_utils.geometry import (
        Parameter,
        Point2D,
        Point3D,
        Arc2d,
        LineSegment2d,
        CircleCurve2d,
        Curve2d,
        SketchPoint,
        AxisEntity,
    )
    from feature_wrappers import InventorObjectWrapper
    if isinstance(obj, Parameter):
        try:
            return {
                "name": obj.name,
                "value": obj.value,
                "expression": obj.expression,
                "valueType": obj.value_type,
            }
        except Exception:
            return {"value": getattr(obj, "value", None)}
    if isinstance(obj, SketchPoint):
        try:
            return {"x": obj.x, "y": obj.y}
        except Exception:
            return {}
    if isinstance(obj, Point2D):
        return {"x": obj.x, "y": obj.y}
    if isinstance(obj, Point3D):
        return {"x": obj.x, "y": obj.y, "z": obj.z}
    if isinstance(obj, Arc2d):
        c = obj.center
        return {
            "type": "Arc2d",
            "center": {"x": c.x, "y": c.y},
            "radius": obj.radius,
            "startAngle": obj.start_angle,
            "sweepAngle": obj.sweep_angle,
        }
    if isinstance(obj, LineSegment2d):
        sp = obj.start_point
        ep = obj.end_point
        data = {
            "type": "LineSegment2d",
            "start": {"x": sp.x, "y": sp.y},
            "end": {"x": ep.x, "y": ep.y},
        }
        try:
            d = obj.direction
            data["direction"] = {"x": d.x, "y": d.y}
        except Exception:
            pass
        return data
    if isinstance(obj, CircleCurve2d):
        c = obj.center
        return {
            "type": "CircleCurve2d",
            "center": {"x": c.x, "y": c.y},
            "radius": obj.radius,
        }
    if isinstance(obj, Curve2d):
        return {"type": "Curve2d"}

    if isinstance(obj, InventorObjectWrapper):
        return obj.to_dict()

    if isinstance(obj, AxisEntity):
        return obj.to_dict()
    raise TypeError(
        f"Object of type {obj.__class__.__name__} is not JSON serializable"
    )
