import os
from typing import Optional, TextIO

import numpy as np
import win32com.client

from inventor_utils.enums import _const, is_type_of




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


def select_entity_in_inventor_app(entity, clear_selection: bool = True):
    try:
        doc = entity.Application.ActiveDocument
        select_set = doc.SelectSet
        if clear_selection:
            select_set.Clear()
        select_set.Select(entity)
    except Exception as e:
        print(f"Error selecting entity in Inventor app: {e}")

def clear_selection_in_inventor_app(doc):
    try:
        select_set = doc.SelectSet
        select_set.Clear()
    except Exception as e:
        print(f"Error clearing selection in Inventor app: {e}")

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


def export_to_step(part, filepath: str):
    if part is None:
        raise ValueError("part is None")

    part.Activate()
    app = part.Parent
    if app is None:
        raise ValueError("part.Application is missing")

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(filepath)) or "."
    os.makedirs(out_dir, exist_ok=True)

    # STEP translator GUID from Inventor API docs
    STEP_ADDIN_ID = "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"
    translator = app.ApplicationAddIns.ItemById(STEP_ADDIN_ID)
    translator = win32com.client.CastTo(translator, "TranslatorAddIn")
    if translator is None:
        raise RuntimeError("STEP translator add-in not found")
    if not translator.Activated:
        translator.Activate()

    trans_objs = app.TransientObjects
    context = trans_objs.CreateTranslationContext()
    #kFileBrowseIOMechanism
    options = trans_objs.CreateNameValueMap()

    if translator.HasSaveCopyAsOptions(part, context, options):
        try:
            protocol_type = options.Value("ApplicationProtocolType")
            protocol_type = 3  # 3 = AP 214 - Automotive Design
            
            context.Type = _const("kFileBrowseIOMechanism")

        except Exception:
            pass

    data_medium = trans_objs.CreateDataMedium()
    data_medium.FileName = filepath
    translator.SaveCopyAs(part, context, options, data_medium)

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
        AxisEntityWrapper,
        BSplineCurve2d,
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
    if isinstance(obj, BSplineCurve2d):
        return {
            'type': 'BSplineCurve2d',
            'bSplineData': obj.get_bspline_data(),

        }
    if isinstance(obj, Curve2d):
        return {"type": "Curve2d"}
    
    if isinstance(obj, InventorObjectWrapper):
        return obj.to_dict()

    if isinstance(obj, AxisEntityWrapper):
        return obj.to_dict()
    raise TypeError(
        f"Object of type {obj.__class__.__name__} is not JSON serializable"
    )


def get_feature_by_name(com_def, feature_name):
    features = com_def.Features
    for i in range(1, features.Count + 1):
        feat = features.Item(i)
        if feat.Name == feature_name:
            return feat
    return None