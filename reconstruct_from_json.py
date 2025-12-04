"""Reconstruct an Inventor part from a dumped features JSON.

Currently supports rebuilding basic ExtrudeFeatures with distance extents.
Other feature types are logged and skipped unless enough data exists.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional

from win32com.client import constants

from inventor_utils.app import add_part_document, get_inventor_application
from inventor_utils.enums import _const
from inventor_utils.features import (
    add_sketch2d_arc,
    add_sketch2d_bspline,
    add_sketch2d_circle,
    add_sketch2d_line,
    add_sketch2d_point,
    add_work_axe,
    add_work_plane,
    add_work_point,
)

from inventor_utils.geometry import PlaneEntityWrapper
from inventor_utils.indexing import EntityIndexHelper, get_feature_by_name
from inventor_utils.transient import (
    add_sketch,
    transient_obj_collection,
    transient_point_2d,
    transient_point_3d,
    transient_unit_vector_3d,
)
from inventor_utils.utils import select_entity_in_inventor_app


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
            sp2 = transient_point_2d(app, sp["x"], sp["y"]) if sp else None

        if i == count - 1:
            ep2 = first_sketch_curve.StartSketchPoint if first_sketch_curve else None
        else:
            ep2 = transient_point_2d(app, ep["x"], ep["y"]) if ep else None


        try:
            if ctype == "kLineSegmentCurve2d" and sp and ep:

                current_sketch_curve = add_sketch2d_line(sketch, sp2, ep2)
            elif ctype == "kCircleCurve2d" and curve:
                center = curve.get("center") if isinstance(curve, dict) else None
                radius = curve.get("radius") if isinstance(curve, dict) else None
                if center and radius is not None:
                    cpt = transient_point_2d(app, center["x"], center["y"])
                    current_sketch_curve = add_sketch2d_circle(
                        sketch, cpt, float(radius)
                    )
            elif ctype == "kCircularArcCurve2d" and curve and sp:
                center = curve.get("center")
                sweep = curve.get("sweepAngle")
                start = curve.get("startAngle")
                r = curve.get("radius")
                is_counter_clock = sweep > 0
                if is_counter_clock is False:  # 当 Arc是顺时针时，需要交换起止点
                    change_start_end = True
                cpt = transient_point_2d(app, center["x"], center["y"])

                current_sketch_curve = add_sketch2d_arc(
                    sketch, cpt, sp2, ep2, is_counter_clock
                )
            elif ctype == "kBSplineCurve2d" and curve:
                current_sketch_curve = add_sketch2d_bspline(sketch, curve['bSplineData'],sp2,ep2)
                pass
            else:
                print(f"[draw_path] Unhandled curve type {ctype}; skipping")
                pass
        except Exception:
            print(
                f"[draw_path] Failed to add entity {i+1}/{count} of type {ctype}; skipping"
            )
            continue
        if current_sketch_curve is None:
            raise ValueError(
                f"[draw_path] Failed to create sketch curve for entity {i+1}/{count} of type {ctype}"
            )

        curves.append(current_sketch_curve)

        if i == 0:
            first_sketch_curve = current_sketch_curve

        previous_sketch_curve = current_sketch_curve


def _build_profile_from_json(
    com_def, profile: Dict[str, Any], entity_index_helper: EntityIndexHelper
):
    # Build or pick work plane from JSON if available
    work_plane = None
    plane_info = profile.get("SketchPlane")
    geometry_info = plane_info.get("geometry") if plane_info else None
    plane_ref_index = plane_info.get("index") if plane_info else None
    sketch = None
    ref_face = None
    if plane_ref_index is not None:
        try:
            ref_face = entity_index_helper.select_face_by_meta(plane_ref_index)
        except Exception as e:
            print(
                f"[build_profile] Failed to get work plane by index {plane_ref_index}: {e}; will try geometry info if available"
            )

    if geometry_info:
        o = geometry_info.get("origin")
        ax = geometry_info.get("axis_x")
        ay = geometry_info.get("axis_y")

        origin = (float(o["x"]), float(o["y"]), float(o["z"]))
        x_axis = (float(ax["x"]), float(ax["y"]), float(ax["z"]))
        y_axis = (float(ay["x"]), float(ay["y"]), float(ay["z"]))

        if ref_face is not None:

            work_axis_x = add_work_axe(com_def=com_def, origin=origin, axis=x_axis)
            work_origin = add_work_point(com_def=com_def, point=origin)
            sketch = com_def.Sketches.AddWithOrientation(
                ref_face, work_axis_x, True, True, work_origin
            )
        else:
            work_plane = add_work_plane(com_def, origin, x_axis, y_axis)
            try:
                work_plane.Visible = False
                sketch = (
                    add_sketch(com_def, work_plane)
                    if work_plane is not None
                    else add_sketch(com_def)
                )
            except Exception:
                pass

    if sketch is None:
        raise ValueError(
            f"[build_profile] Unable to create sketch for profile; missing or invalid plane reference."
        )

    for path in profile.get("ProfilePaths", []):
        _draw_path_on_sketch(sketch, path)
    # Build a solid profile from the sketch
    return sketch.Profiles.AddForSolid()


def _rebuild_extrude(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
) -> Optional[Any]:

    prof_dict = feat.get("profile")
    if not prof_dict:
        print("[rebuild] Extrude missing profile; skipping")
        return
    try:
        profile = _build_profile_from_json(
            com_def, prof_dict, entity_index_helper=entity_index_helper
        )
    except Exception as e:
        print(f"[rebuild] Failed to build profile: {e}; skipping extrude")
        return

    ext_feats = com_def.Features.ExtrudeFeatures
    op_name = feat.get("operation")  # e.g., 'kJoinOperation'
    op_const = _const(op_name, constants.kJoinOperation)
    ext_type = feat.get("extentType")  # e.g., 'kDistanceExtent'
    extent = feat.get("extent")
    if extent is None:
        raise ValueError("[rebuild] Extrude missing extent; skipping extrude")
    dir_name = extent.get("direction")  # e.g., 'kPositiveExtentDirection'
    dir_const = _const(dir_name, constants.kPositiveExtentDirection)
    ext_def = None
    ext_def = ext_feats.CreateExtrudeDefinition(profile, op_const)
    if ext_type == "kDistanceExtent":
        dist = extent.get("distance")
        if dist is None:
            raise ValueError("[rebuild] Extrude missing distance; skipping extrude")
        ext_def.SetDistanceExtent(dist["expression"], dir_const)

        if feat["isTwoDirectional"]:
            dist2 = extent.get("distanceTwo")
            if dist2 is not None:
                ext_def.SetDistanceExtentTwo(dist2["expression"])
    elif ext_type == "kToExtent":
        #   d['type'] = "ToExtent"
        # d["toEntity"] = self.to_entity
        # d["direction"] = self.direction
        # d["extendToFace"] = self.extend_to_face
        extend_to_face: bool = extent.get("extendToFace")  # type: ignore
        to_entity = entity_index_helper.select_face_by_meta(extent.get("toEntity"))
        # select_entity_in_inventor_app(to_entity)
        if to_entity is None:
            raise ValueError(
                "[rebuild] Extrude missing toEntity for ToExtent; skipping extrude"
            )
        ext_def.SetToExtent(to_entity, extend_to_face)
    elif ext_type == "kFromToExtent":
        if extent.get("isFromFaceWorkPlane") is False:
            from_face = entity_index_helper.select_face_by_meta(extent.get("fromFace"))
        else:
            work_plane = PlaneEntityWrapper.from_dict(
                extent.get("fromFace"), entity_index_helper=entity_index_helper
            )
            from_face = add_work_plane(
                com_def,
                work_plane.origin.to_tuple(),
                work_plane.axis_x.to_tuple(),
                work_plane.axis_y.to_tuple(),
            )

        if extent.get("isToFaceWorkPlane") is False:
            to_face = entity_index_helper.select_face_by_meta(extent.get("toFace"))
        else:
            work_plane = PlaneEntityWrapper.from_dict(
                extent.get("toFace"), entity_index_helper=entity_index_helper
            )
            to_face = add_work_plane(
                com_def,
                work_plane.origin.to_tuple(),
                work_plane.axis_x.to_tuple(),
                work_plane.axis_y.to_tuple(),
            )

        if from_face is None or to_face is None:
            raise ValueError(
                "[rebuild] Extrude missing fromFace or toFace for FromToExtent; skipping extrude"
            )

        extend_from_face: bool = extent.get("extendFromFace")  # type: ignore
        extend_to_face: bool = extent.get("extendToFace")  # type: ignore
        ext_def.SetFromToExtent(from_face, extend_from_face, to_face, extend_to_face)
    elif ext_type == "kToNextExtent":
        surface_body = com_def.SurfaceBodies.Item(1)
        ext_def.SetToNextExtent(dir_const, surface_body)

    out_feature = ext_feats.Add(ext_def)
    out_feature.Name = feat.get("name", out_feature.Name)

    return out_feature


def _rebuild_revolve(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
) -> Optional[Any]:
    prof_dict = feat.get("profile")
    if not prof_dict:
        print("[rebuild] Revolve missing profile; skipping")
        return
    try:
        profile = _build_profile_from_json(
            com_def, prof_dict, entity_index_helper=entity_index_helper
        )
    except Exception as e:
        print(f"[rebuild] Failed to build profile: {e}; skipping revolve")
        return

    op_name = feat.get("operation")  # e.g., 'kJoinOperation'
    op_const = _const(op_name, constants.kJoinOperation)
    extent_type = feat.get("extentType")  # e.g., 'kAngleExtent'
    extent = feat.get("extent")
    if extent is None:
        raise ValueError("[rebuild] Revolve missing extent; skipping revolve")

    axis_info = feat.get("axisEntity")
    if not axis_info:
        print("[rebuild] Revolve missing axisEntity; skipping")
        return
    try:
        axis_start = axis_info.get("start_point")
        axis_dir = axis_info.get("direction")
        if not (axis_start and axis_dir):
            print(
                "[rebuild] Revolve axisEntity missing start_point or direction; skipping"
            )
            return
        app = com_def.Application
        start_pt = transient_point_3d(
            app, float(axis_start["x"]), float(axis_start["y"]), float(axis_start["z"])
        )
        dir_vec = transient_unit_vector_3d(
            app, float(axis_dir["x"]), float(axis_dir["y"]), float(axis_dir["z"])
        )
        work_axis = com_def.WorkAxes.AddFixed(start_pt, dir_vec)
    except Exception as e:
        print(f"[rebuild] Failed to parse revolve axisEntity: {e}; skipping")
        return

    if extent_type == "kAngleExtent":
        angle = extent.get("angle")
        revolve_direction = extent.get("direction")
        revolve_direction_const = _const(
            revolve_direction, constants.kPositiveExtentDirection
        )
        if angle is None:
            raise ValueError("[rebuild] Revolve missing angle; skipping revolve")
        com_def.Features.RevolveFeatures.AddByAngle(
            profile, work_axis, angle["expression"], revolve_direction_const, op_const
        )
    elif extent_type == "kFullSweepExtent":
        com_def.Features.RevolveFeatures.AddFull(profile, work_axis, op_const)


def _rebuild_fillet(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
):

    fillet_def = com_def.Features.FilletFeatures.CreateFilletDefinition()
    edge_sets = feat.get("edgeSets", [])
    for edge_set in edge_sets:
        edge_collection = com_def.Application.TransientObjects.CreateEdgeCollection()
        edges = edge_set.get("edges", [])
        for edge_info in edges:
            try:
                edge = entity_index_helper.select_edge_by_meta(edge_info)
                edge_collection.Add(edge)
            except Exception as e:
                print(
                    f"[rebuild] Failed to retrieve edge for fillet: {e}; skipping edge"
                )
                continue
        if edge_collection.Count == 0:
            raise ValueError(
                "[rebuild] No valid edges found for fillet; skipping fillet"
            )
        radius = edge_set.get("radius")
        if radius is None:
            raise ValueError(
                "[rebuild] Fillet edge set missing radius; skipping this edge set"
            )
        fillet_def.AddConstantRadiusEdgeSet(edge_collection, radius["expression"])

    out_feature = com_def.Features.FilletFeatures.Add(fillet_def)
    out_feature.Name = feat.get("name", out_feature.Name)

    pass


def _rebuild_chamfer(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
):
    edges = feat.get("edges", [])
    edge_collection = com_def.Application.TransientObjects.CreateEdgeCollection()
    for edge_info in edges:
        try:
            edge = entity_index_helper.select_edge_by_meta(edge_info)
            select_entity_in_inventor_app(edge, False)
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
    if chamfer_type == "kDistance":
        distance1 = feat.get("distance")
    elif chamfer_type == "kTwoDistance":
        distance1 = feat.get("distanceOne")
        distance2 = feat.get("distanceTwo")
    elif chamfer_type == "kDistanceAndAngle":
        distance1 = feat.get("distance")
        
    if distance1 is None:
        print("[rebuild] Chamfer missing distance1; skipping chamfer")
        return
    if chamfer_type == "kDistance":
        out_feature = com_def.Features.ChamferFeatures.AddUsingDistance(
            edge_collection, distance1["expression"]
        )
    elif chamfer_type == "kTwoDistance":
        if distance2 is None:
            print(
                "[rebuild] Chamfer missing distance2 for two-distance type; skipping chamfer"
            )
            return
        face_index = feat.get("face")
        face = entity_index_helper.select_face_by_meta(face_index)
        out_feature = com_def.Features.ChamferFeatures.AddUsingTwoDistances(
            edge_collection, face, distance1["expression"], distance2["expression"]
        )
    elif chamfer_type == "kDistanceAndAngle":
        angle = feat.get("angle")
        if angle is None:
            print(
                "[rebuild] Chamfer missing angle for distance-and-angle type; skipping chamfer"
            )
            return
        face_index = feat.get("face")
        face = entity_index_helper.select_face_by_meta(face_index)
        select_entity_in_inventor_app(face, False) # debug

        out_feature = com_def.Features.ChamferFeatures.AddUsingDistanceAndAngle(
            edge_collection, face, distance1["expression"], angle["expression"]
        )
    if out_feature is None:
        print("[rebuild] Failed to create chamfer feature; skipping")
        raise RuntimeError("Chamfer feature creation failed")
    out_feature.Name = feat.get("name", out_feature.Name)
    pass


def _rebuild_hole(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
):
    depth = feat.get("depth")
    plane_info = feat.get("sketchPlane")

    if not plane_info:
        raise ValueError("[rebuild] Hole missing sketchPlane info; skipping")
    center_points = feat.get("holeCenterPoints", [])
    if not center_points:
        raise ValueError("[rebuild] Hole missing center points; skipping")
    extent_type = feat.get("extentType")
    extent = feat.get("extent")
    if extent is None:
        raise ValueError("[rebuild] Hole missing extent; skipping")
    hole_type = feat.get("holeType")
    if extent_type is None or hole_type is None:
        raise ValueError("[rebuild] Hole missing extentType or holeType; skipping")

    if extent_type not in ["kDistanceExtent", "kThroughAllExtent"]:
        raise ValueError(
            f"[rebuild] Hole extentType {extent_type} not supported; skipping"
        )
    if hole_type not in ["kDrilledHole"]:
        raise ValueError(f"[rebuild] Hole holeType {hole_type} not supported; skipping")

    work_plane = None
    geometry_info = plane_info.get("geometry") if plane_info else None
    plane_ref_index = plane_info.get("index") if plane_info else None
    sketch = None
    ref_face = None
    if plane_ref_index is not None:
        try:
            ref_face = entity_index_helper.select_face_by_meta(plane_ref_index)
        except Exception as e:
            print(
                f"[build_profile] Failed to get work plane by index {plane_ref_index}: {e}; will try geometry info if available"
            )

    if geometry_info:
        o = geometry_info.get("origin")
        ax = geometry_info.get("axis_x")
        ay = geometry_info.get("axis_y")
        origin = (float(o["x"]), float(o["y"]), float(o["z"]))
        x_axis = (float(ax["x"]), float(ax["y"]), float(ax["z"]))
        y_axis = (float(ay["x"]), float(ay["y"]), float(ay["z"]))

        if ref_face is not None:

            work_axis_x = add_work_axe(com_def=com_def, origin=origin, axis=x_axis)
            work_origin = add_work_point(com_def=com_def, point=origin)
            sketch = com_def.Sketches.AddWithOrientation(
                ref_face, work_axis_x, True, True, work_origin
            )
        else:
            work_plane = add_work_plane(com_def, origin, x_axis, y_axis)
            try:
                work_plane.Visible = False
                sketch = (
                    add_sketch(com_def, work_plane)
                    if work_plane is not None
                    else add_sketch(com_def)
                )
            except Exception:
                pass
    if sketch is None:
        raise ValueError(
            f"[build_sketch] Unable to create sketch for profile; missing or invalid plane reference."
        )

    hole_points_collection = (
        com_def.Application.TransientObjects.CreateObjectCollection()
    )
    for center_info in center_points:
        app = com_def.Application
        center_pt = transient_point_2d(
            app, float(center_info["x"]), float(center_info["y"])
        )
        sketch_point = add_sketch2d_point(sketch, center_pt, is_hole_center=True)
        hole_points_collection.Add(sketch_point)

    placement = com_def.Features.HoleFeatures.CreateSketchPlacementDefinition(
        hole_points_collection
    )

    out_feature = None
    diameter = feat["holeDiameter"]
    if extent_type == "kDistanceExtent":
        extent_dir = extent.get("direction")
        is_flat_bottom = feat.get("isFlatBottomed")
        flat_angle = None
        if not is_flat_bottom:
            flat_angle = feat.get("bottomTipAngle")

        out_feature = com_def.Features.HoleFeatures.AddDrilledByDistanceExtent(
            placement,
            diameter["expression"],
            depth,
            _const(extent_dir),
            is_flat_bottom,
            flat_angle["expression"] if flat_angle else None,
        )
    elif extent_type == "kThroughAllExtent":
        direction = extent.get("direction")
        out_feature = com_def.Features.HoleFeatures.AddDrilledByThroughAllExtent(
            placement,
            diameter["expression"],
            _const(direction),
        )
    else:
        raise ValueError(
            f"[rebuild] Hole extentType {extent_type} not supported; skipping"
        )

    out_feature.Name = feat.get("name", out_feature.Name)

    pass


def _rebuild_shell(
    com_def,
    feat: Dict[str, Any],
    entity_index_helper: EntityIndexHelper,
):
    input_faces = feat.get("inputFaces", [])
    thickness = feat.get("thickness")
    direction = feat.get("direction")
    if not input_faces or thickness is None or direction is None:
        raise ValueError("[rebuild] Shell missing inputFaces or thickness; skipping")
    face_collection = com_def.Application.TransientObjects.CreateFaceCollection()
    for face_info in input_faces:
        try:
            face = entity_index_helper.select_face_by_meta(face_info)
            face_collection.Add(face)
        except Exception as e:
            print(f"[rebuild] Failed to retrieve face for shell: {e}; skipping face")
            continue
    shell_defn = com_def.Features.ShellFeatures.CreateShellDefinition(
        face_collection, thickness["expression"], _const(direction)
    )
    out_feature = com_def.Features.ShellFeatures.Add(shell_defn)
    out_feature.Name = feat.get("name", out_feature.Name)

    return out_feature
    pass


def _rebuild_mirror(
    com_def,
    feat: Dict[str, Any],
    entity_index_helper: EntityIndexHelper,
):
    is_mirror_body = feat.get("isMirrorBody")
    mirror_plane_info = feat.get("mirrorPlane")
    is_mirror_plane_face = feat.get("isMirrorPlaneFace")
    compute_type = feat.get("computeType")

    if (
        mirror_plane_info is None
        or is_mirror_body is None
        or is_mirror_plane_face is None
        or compute_type is None
    ):
        raise ValueError(
            "[rebuild] Mirror missing mirrorPlane or isMirrorBody; skipping"
        )
    mirror_entity = None
    if is_mirror_plane_face:
        mirror_face = entity_index_helper.select_face_by_meta(mirror_plane_info)
        mirror_entity = mirror_face
    else:
        origin_info = mirror_plane_info.get("geometry").get("origin")
        axis_x_info = mirror_plane_info.get("geometry").get("axis_x")
        axis_y_info = mirror_plane_info.get("geometry").get("axis_y")
        origin = (
            float(origin_info["x"]),
            float(origin_info["y"]),
            float(origin_info["z"]),
        )
        axis_x = (
            float(axis_x_info["x"]),
            float(axis_x_info["y"]),
            float(axis_x_info["z"]),
        )
        axis_y = (
            float(axis_y_info["x"]),
            float(axis_y_info["y"]),
            float(axis_y_info["z"]),
        )
        mirror_entity = add_work_plane(com_def, origin, axis_x, axis_y)

    if mirror_entity is None:
        raise ValueError("[rebuild] Unable to create mirror entity; skipping")
    parent_features = transient_obj_collection(com_def.Application)
    if is_mirror_body:
        mirror_body = com_def.SurfaceBodies.Item(1)
        parent_features.Add(mirror_body)
    else:
        raise NotImplementedError("Mirroring specific features is not implemented yet.")
    mirror_def = com_def.Features.MirrorFeatures.CreateDefinition(
        parent_features,
        mirror_entity,
        _const(compute_type),
    )
    if is_mirror_body:
        remove_original = feat.get("removeOriginal")
        operation = feat.get("operation")
        if remove_original is None or operation is None:
            raise ValueError(
                "[rebuild] Mirror missing removeOriginal or operation But IsMirrorBody; skipping"
            )
        mirror_def.RemoveOriginal = remove_original
        mirror_def.Operation = _const(operation)

    out_feature = com_def.Features.MirrorFeatures.AddByDefinition(mirror_def)
    out_feature.Name = feat.get("name", out_feature.Name)
    return out_feature
    pass


def _rebuild_circular_pattern(com_def, feat, entity_index_helper: EntityIndexHelper):
    is_pattern_body = feat.get("isPatternOfBody")
    axis_info = feat.get("rotationAxis")
    axis_entity = entity_index_helper.select_entity_by_meta(axis_info)
    if axis_entity is None:
        raise ValueError("[rebuild] CircularPattern missing axisEntity; skipping")

    parent_entities = transient_obj_collection(com_def.Application)
    if is_pattern_body:
        pattern_body = com_def.SurfaceBodies.Item(1)
        parent_entities.Add(pattern_body)
    else:
        parent_features_info = feat.get("featuresToPattern", [])
        for feature_info in parent_features_info:
            feature = get_feature_by_name(com_def, feature_info)
            parent_entities.Add(feature)

    is_natural_x_dir = feat.get("isNaturalAxisDirection")
    count = feat.get("count")
    angle = feat.get("angle")
    if is_natural_x_dir is None or count is None or angle is None:
        raise ValueError(
            "[rebuild] CircularPattern missing isNaturalAxisDirection, count or angle; skipping"
        )
    pattern_def = com_def.Features.CircularPatternFeatures.CreateDefinition(
        parent_entities,
        axis_entity,
        is_natural_x_dir,
        count["expression"],
        angle["expression"],
    )
    out_feature = com_def.Features.CircularPatternFeatures.AddByDefinition(pattern_def)
    out_feature.Name = feat.get("name", out_feature.Name)

def _rebuild_rectangular_pattern(com_def, feat, entity_index_helper: EntityIndexHelper):
    is_pattern_body = feat.get("isPatternOfBody")
    x_direction_entity_info = feat.get("xDirectionEntity")
    x_count = feat.get("xCount")
    x_spacing = feat.get("xSpacing")
    x_natural_dir = feat.get("xNaturalDirection")
    x_spacing_type = feat.get("xSpacingType")
    x_spacing_type = _const(x_spacing_type)
    if (
        x_direction_entity_info is None
        or x_count is None
        or x_spacing is None
        or x_natural_dir is None
        or x_spacing_type is None
    ):
        raise ValueError(
            "[rebuild] RectangularPattern missing xDirectionEntity, xCount, xSpacing, xNaturalDirection or xSpacingType; skipping"
        )
    

    x_direction_entity = entity_index_helper.select_entity_by_meta(x_direction_entity_info)
    if x_direction_entity is None:
        raise ValueError("[rebuild] RectangularPattern missing xDirectionEntity; skipping")
    
    parent_entities = transient_obj_collection(com_def.Application)
    if is_pattern_body:
        pattern_body = com_def.SurfaceBodies.Item(1)
        parent_entities.Add(pattern_body)
    else:
        parent_features_info = feat.get("featuresToPattern", [])
        for feature_info in parent_features_info:
            feature = get_feature_by_name(com_def, feature_info)
            parent_entities.Add(feature)
    pattern_def = com_def.Features.RectangularPatternFeatures.CreateDefinition(
        parent_entities,
        x_direction_entity,
        x_natural_dir,
        x_count["expression"],
        x_spacing["expression"],
        x_spacing_type,
    ) 
    out_feature = com_def.Features.RectangularPatternFeatures.AddByDefinition(pattern_def)
    out_feature.Name = feat.get("name", out_feature.Name)

def _rebuild_sweep(com_def, feat, entity_index_helper=None):
    raise NotImplementedError("Sweep feature reconstruction not implemented yet.")


def _rebuild_feature(
    com_def, feat: Dict[str, Any], entity_index_helper: EntityIndexHelper
):
    ftype = feat.get("type")
    if ftype == "ExtrudeFeature":
        return _rebuild_extrude(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "RevolveFeature":
        return _rebuild_revolve(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "FilletFeature":
        return _rebuild_fillet(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "ChamferFeature":
        return _rebuild_chamfer(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "HoleFeature":
        return _rebuild_hole(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "ShellFeature":
        return _rebuild_shell(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "MirrorFeature":
        return _rebuild_mirror(com_def, feat, entity_index_helper=entity_index_helper)
    elif ftype == "CircularPatternFeature":
        return _rebuild_circular_pattern(
            com_def, feat, entity_index_helper=entity_index_helper
        )
    elif ftype == 'RectangularPatternFeature':
        return _rebuild_rectangular_pattern(
            com_def, feat, entity_index_helper=entity_index_helper
        )
    elif ftype == "SweepFeature":
        return _rebuild_sweep(com_def, feat, entity_index_helper=entity_index_helper)
    else:
        print(f"[rebuild] Feature type={ftype} not supported yet; skipping")
        return None

def reconstruct_from_json(
    json_path: str, *, app=None, new_part_name: str = "Reconstructed"
):
    if app is None:
        app = get_inventor_application()
    if app is None:
        raise RuntimeError("Unable to get Inventor application")
    try:
        app.Visible = True
    except Exception:
        pass

    part, com_def = add_part_document(app, new_part_name)

    with open(json_path, "r", encoding="utf-8") as f:
        features: List[Dict[str, Any]] = json.load(f)
    entity_index_helper = EntityIndexHelper(com_def=com_def)
    for i, feat in enumerate(features, start=1):
        ftype = feat.get("type")

        try:
            _rebuild_feature(com_def, feat, entity_index_helper=entity_index_helper)
        except Exception as e:
            print(f"[rebuild] Failed to rebuild feature {i}: {e}")
        entity_index_helper.update_all()
    return part


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python reconstruct_from_json.py <features.json>")
        json_path = r"E:\Python\PyProjects\Seq2Inventor\test_inventor_1_features.json"

        reconstruct_from_json(json_path)
    else:
        json_path = sys.argv[1]
        reconstruct_from_json(json_path)
