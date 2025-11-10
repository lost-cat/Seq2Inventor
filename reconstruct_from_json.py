"""Reconstruct an Inventor part from a dumped features JSON.

Currently supports rebuilding basic ExtrudeFeatures with distance extents.
Other feature types are logged and skipped unless enough data exists.
"""
from __future__ import annotations
import json
import math
from typing import Any, Dict, List, Optional

from win32com.client import constants

from inventor_util import (
    add_sketch2d_arc,
    add_sketch2d_circle,
    add_sketch2d_line,
    add_work_axe,
    add_work_point,
    get_edge_by_index,
    get_face_by_index,
    get_feature_by_name,
    get_inventor_application,
    add_part_document,
    add_sketch,
    add_work_plane,
    transient_point_2d,
    transient_point_3d,
    transient_unit_vector_3d,
)


def _const(name: Optional[str], fallback: Optional[int] = None) -> Optional[int]:
    if not name:
        print(f"[const] Missing name; returning fallback {fallback}")
        return fallback
    return getattr(constants, name, fallback)


def _draw_path_on_sketch(sketch, path: Dict[str, Any]) -> None:
    entities: List[Dict[str, Any]] = path.get("PathEntities", [])
    app = sketch.Application
    previous_sketch_curve = None
    current_sketch_curve = None
    first_sketch_curve = None
    count = len(entities)

    geo_cons = getattr(sketch, "GeometricConstraints")

    curves = []
    # 当 Arc是顺时针时，需要交换起止点
    change_start_end = False
    for i, ent in enumerate(entities):
        ctype = ent.get("CurveType")
        sp = ent.get("StartSketchPoint")
        ep = ent.get("EndSketchPoint")
        curve = ent.get("Curve")
        if previous_sketch_curve:
            if change_start_end:
                sp2 = previous_sketch_curve.StartSketchPoint
                change_start_end = False
            else:
                sp2 = previous_sketch_curve.EndSketchPoint
        else:
            sp2 = transient_point_2d(app, sp['x'], sp['y']) if sp else None

        if i == count - 1:
            ep2 = first_sketch_curve.StartSketchPoint if first_sketch_curve else None
        else:
            ep2 = transient_point_2d(app, ep['x'], ep['y']) if ep else None
        try:
            if ctype == 'kLineSegmentCurve2d' and sp and ep:

                current_sketch_curve = add_sketch2d_line(sketch, sp2, ep2)
            elif ctype == 'kCircleCurve2d' and curve:
                center = curve.get('center') if isinstance(curve, dict) else None
                radius = curve.get('radius') if isinstance(curve, dict) else None
                if center and radius is not None:
                    cpt = transient_point_2d(app, center['x'], center['y'])
                    current_sketch_curve = add_sketch2d_circle(sketch, cpt, float(radius))
            elif ctype == 'kCircularArcCurve2d' and curve and sp:
                center = curve.get('center')
                sweep = curve.get('sweepAngle')
                start = curve.get('startAngle')
                r = curve.get('radius')
                is_counter_clock = sweep > 0
                if is_counter_clock is False: # 当 Arc是顺时针时，需要交换起止点
                    change_start_end = True
                cpt = transient_point_2d(app, center['x'], center['y'])

                current_sketch_curve = add_sketch2d_arc(sketch, cpt, sp2, ep2, is_counter_clock)
            else:
                print(f"[draw_path] Unhandled curve type {ctype}; skipping")
                pass
        except Exception:
            print(f"[draw_path] Failed to add entity {i+1}/{count} of type {ctype}; skipping")
            continue
        if current_sketch_curve is None:
            raise ValueError(f"[draw_path] Failed to create sketch curve for entity {i+1}/{count} of type {ctype}")


        # print(f"[draw_path] Created sketch curve for entity {i+1}/{count} of type {ctype}: {current_sketch_curve.StartSketchPoint.Geometry.X}, {current_sketch_curve.StartSketchPoint.Geometry.Y}"
        #       f" - {current_sketch_curve.EndSketchPoint.Geometry.X}, {current_sketch_curve.EndSketchPoint.Geometry.Y}")

        curves.append(current_sketch_curve)
        
        if i == 0:
            first_sketch_curve = current_sketch_curve
        # # if previous_sketch_curve :
        #     try:
        #         if hasattr(current_sketch_curve, 'StartSketchPoint') and hasattr(previous_sketch_curve, 'EndSketchPoint'):
        #             geo_cons.AddCoincident(current_sketch_curve.StartSketchPoint, previous_sketch_curve.EndSketchPoint)
        #     except Exception as e:
        #         print(f"[draw_path] Failed to add coincident constraint between entity {i} and {i+1}; skipping constraint: {e}")
        #         current_sketch_curve.StartSketchPoint.Merge(previous_sketch_curve.EndSketchPoint)
        previous_sketch_curve = current_sketch_curve

        # if i == count - 1 and first_sketch_curve and current_sketch_curve:
        #     try:
        #         if hasattr(current_sketch_curve, 'StartSketchPoint') and hasattr(first_sketch_curve, 'EndSketchPoint'):
        #             geo_cons.AddCoincident(current_sketch_curve.StartSketchPoint, first_sketch_curve.EndSketchPoint)
        #     except Exception as e:
        #         print(f"[draw_path] Failed to add coincident constraint between entity {i} and {i+1}; skipping constraint: {e}")
        #         current_sketch_curve.EndSketchPoint.Merge(first_sketch_curve.StartSketchPoint)





def _build_profile_from_json(com_def, profile: Dict[str, Any]):
    # Build or pick work plane from JSON if available
    work_plane = None
    plane_info = profile.get("SketchPlane")
    geometry_info = plane_info.get("geometry") if plane_info else None
    plane_ref_index = plane_info.get("index") if plane_info else None
    sketch = None
    ref_face = None
    if plane_ref_index is not None:
        try:
            ref_face = get_face_by_index(com_def, plane_ref_index)
        except Exception as e:
            print(f"[build_profile] Failed to get work plane by index {plane_ref_index}: {e}; will try geometry info if available")

    if  geometry_info:
        o = geometry_info.get("origin")
        ax = geometry_info.get("axis_x")
        ay = geometry_info.get("axis_y")

        origin = (float(o["x"]), float(o["y"]), float(o["z"]))
        x_axis = (float(ax["x"]), float(ax["y"]), float(ax["z"]))
        y_axis = (float(ay["x"]), float(ay["y"]), float(ay["z"]))

        if ref_face is not None:

            work_axis_x = add_work_axe(com_def=com_def, origin=origin, axis=x_axis)
            work_origin = add_work_point(com_def=com_def, point=origin)
            sketch = com_def.Sketches.AddWithOrientation(ref_face, work_axis_x,True,True,work_origin)
        else:
            work_plane = add_work_plane(com_def, origin, x_axis, y_axis)
            try:
                work_plane.Visible = False
                sketch = add_sketch(com_def, work_plane) if work_plane is not None else add_sketch(com_def)
            except Exception:
                pass

    if sketch is None:
        raise ValueError(f"[build_profile] Unable to create sketch for profile; missing or invalid plane reference.")

    for path in profile.get("ProfilePaths", []):
        _draw_path_on_sketch(sketch, path)
    # Build a solid profile from the sketch
    return sketch.Profiles.AddForSolid()


def _rebuild_extrude(com_def, feat: Dict[str, Any])-> Optional[Any]:
    prof_dict = feat.get("profile")
    if not prof_dict:
        print("[rebuild] Extrude missing profile; skipping")
        return
    try:
        profile = _build_profile_from_json(com_def, prof_dict)
    except Exception as e:
        print(f"[rebuild] Failed to build profile: {e}; skipping extrude")
        return

    op_name = feat.get("operation")  # e.g., 'kJoinOperation'
    op_const = _const(op_name, constants.kJoinOperation)
    ext_type = feat.get("extentType")  # e.g., 'kDistanceExtent'
    dir_name = feat.get("direction")  # e.g., 'kPositiveExtentDirection'
    dir_const = _const(dir_name, constants.kPositiveExtentDirection)

    # Distance primary
    dist_val = None
    dist = feat.get("distance")
    if isinstance(dist, dict):
        dist_val = dist.get("value")
    elif isinstance(dist, (int, float)):
        dist_val = dist
    if dist_val is None:
        dist_val = 1.0  # default 1 cm

    # Distance secondary (optional)
    dist2_val = None
    dist2 = feat.get("distanceTwo")
    if isinstance(dist2, dict):
        dist2_val = dist2.get("value")
    elif isinstance(dist2, (int, float)):
        dist2_val = dist2

    ext_feats = com_def.Features.ExtrudeFeatures
    ext_def = ext_feats.CreateExtrudeDefinition(profile, op_const)
    # Only handle distance extents for now
    ext_def.SetDistanceExtent(float(dist_val), dir_const)
    if dist2_val is not None:
        try:
            ext_def.SetDistanceExtentTwo(float(dist2_val))
        except Exception:
            pass
    out_feature = ext_feats.Add(ext_def)
    out_feature.Name = feat.get("name", out_feature.Name)

    return out_feature


def _rebuild_revolve(com_def, feat: Dict[str, Any]):
    prof_dict = feat.get("profile")
    if not prof_dict:
        print("[rebuild] Revolve missing profile; skipping")
        return
    try:
        profile = _build_profile_from_json(com_def, prof_dict)
    except Exception as e:
        print(f"[rebuild] Failed to build profile: {e}; skipping revolve")
        return

    op_name = feat.get("operation")  # e.g., 'kJoinOperation'
    op_const = _const(op_name, constants.kJoinOperation)
    axis_info = feat.get("axisEntity")
    revolve_direction = feat.get("direction") 
    revolve_direction_const = _const(revolve_direction, constants.kPositiveExtentDirection)

    if not axis_info:
        print("[rebuild] Revolve missing axisEntity; skipping")
        return
    try:
        axis_start = axis_info.get("start_point")
        axis_dir = axis_info.get("direction")
        if not (axis_start and axis_dir):
            print("[rebuild] Revolve axisEntity missing start_point or direction; skipping")
            return
        app  = com_def.Application
        start_pt = transient_point_3d(app,float(axis_start['x']), float(axis_start['y']), float(axis_start['z']))
        dir_vec = transient_unit_vector_3d(app, float(axis_dir['x']), float(axis_dir['y']), float(axis_dir['z']))
        work_axis = com_def.WorkAxes.AddFixed(start_pt, dir_vec)
    except Exception as e:
        print(f"[rebuild] Failed to parse revolve axisEntity: {e}; skipping")
        return

    angle_val = None
    angle = feat.get("angle")
    if isinstance(angle, dict):
        angle_val = angle.get("value")
    elif isinstance(angle, (int, float)):
        angle_val = angle
    if angle_val is None:
        angle_val = 360.0  # default full revolve
    
    radian = math.radians(angle_val)
    com_def.Features.RevolveFeatures.AddByAngle(profile, work_axis, radian, revolve_direction_const, op_const)




def _rebuild_fillet(com_def, feat: Dict[str, Any]):

    fillet_def = com_def.Features.FilletFeatures.CreateFilletDefinition()
    edge_sets = feat.get("edgeSets", [])
    for edge_set in edge_sets:
        edge_collection = com_def.Application.TransientObjects.CreateEdgeCollection()
        edges = edge_set.get("edges", [])
        for edge_info in edges:
            try:
                edge = get_edge_by_index(com_def,edge_info)
                edge_collection.Add(edge)
            except Exception as e:
                print(f"[rebuild] Failed to retrieve edge for fillet: {e}; skipping edge")
                continue
        if edge_collection.Count == 0:
            print("[rebuild] No valid edges found for fillet; skipping fillet")
            continue
        radius = edge_set.get("radius").get('value') if isinstance(edge_set.get("radius"), dict) else None
        if radius is None:
            print("[rebuild] Fillet edge set missing radius; skipping this edge set")
            continue
        fillet_def.AddConstantRadiusEdgeSet(edge_collection, float(radius))
    
        out_feature = com_def.Features.FilletFeatures.Add(fillet_def)
        out_feature.Name = feat.get("name", out_feature.Name)

    pass

def _rebuild_chamfer(com_def, feat: Dict[str, Any]):
    edges = feat.get("edges", [])
    edge_collection = com_def.Application.TransientObjects.CreateEdgeCollection()
    for edge_info in edges:
        try:
            edge = get_edge_by_index(com_def,edge_info)
            edge_collection.Add(edge)
            # Here you would add the edge to a chamfer definition
            # However, the ChamferFeatures API usage is not implemented here
            # as it requires more detailed handling similar to fillets.
        except Exception as e:
            print(f"[rebuild] Failed to retrieve edge for chamfer: {e}; skipping edge")
            continue
    chamfer_type = feat.get("chamferType")
    distance1 = None
    distance2 = None
    out_feature = None
    if chamfer_type == 'kDistance':
        distance1 = feat.get("distance").get('value')
    elif chamfer_type == 'kTwoDistance':
        distance1 = feat.get("distanceOne").get('value') 
        distance2 = feat.get("distanceTwo").get('value') 
    if distance1 is None:
        print("[rebuild] Chamfer missing distance1; skipping chamfer")
        return
    if chamfer_type == 'kDistance':
        out_feature = com_def.Features.ChamferFeatures.AddUsingDistance(edge_collection, float(distance1))
    elif chamfer_type == 'kTwoDistance':
        if distance2 is None:
            print("[rebuild] Chamfer missing distance2 for two-distance type; skipping chamfer")
            return
        face_index = feat.get("face")
        face = get_face_by_index(com_def, face_index)
        out_feature = com_def.Features.ChamferFeatures.AddUsingTwoDistances(edge_collection, face, float(distance1), float(distance2))
    if out_feature is None:
        print("[rebuild] Failed to create chamfer feature; skipping")
        raise RuntimeError("Chamfer feature creation failed")
    out_feature.Name = feat.get("name", out_feature.Name)
    pass


def _rebuild_hole(com_def, feat: Dict[str, Any]):
    depth = feat.get("depth")
    sketch_plane_info = feat.get("sketchPlane")
    if not sketch_plane_info:
        raise ValueError("[rebuild] Hole missing sketchPlane info; skipping")
    center_points = feat.get("holeCenterPoints", [])
    if not center_points:
        raise ValueError("[rebuild] Hole missing center points; skipping")
    
    
    
    pass

def reconstruct_from_json(json_path: str, *, app=None, new_part_name: str = "Reconstructed"):
    if app is None:
        app = get_inventor_application()
    if app is None:
        raise RuntimeError("Unable to get Inventor application")
    try:
        app.Visible = True
    except Exception:
        pass

    part, com_def = add_part_document(app, new_part_name)

    with open(json_path, 'r', encoding='utf-8') as f:
        features: List[Dict[str, Any]] = json.load(f)

    for i, feat in enumerate(features, start=1):
        ftype = feat.get("type")
        try:
            if ftype == "ExtrudeFeature":
                _rebuild_extrude(com_def, feat)
            elif ftype == "RevolveFeature":
                _rebuild_revolve(com_def, feat)
            elif ftype == "FilletFeature":
                _rebuild_fillet(com_def, feat)
            elif ftype == "ChamferFeature":
                _rebuild_chamfer(com_def, feat)
            else:
                print(f"[rebuild] Feature {i} type={ftype} not supported yet; skipping")
        except Exception as e:
            print(f"[rebuild] Failed to rebuild feature {i}: {e}")

    return part


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python reconstruct_from_json.py <features.json>")
        sys.exit(1)
    reconstruct_from_json(sys.argv[1])
