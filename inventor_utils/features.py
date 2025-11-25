from enum import Enum
from copy import copy

import numpy as np
from win32com.client import constants

from cad_utils.curves import Line, Circle, Arc
from cad_utils.macro import EXTENT_TYPE, BODY_OPERATIONS
from inventor_utils.transient import add_sketch, transient_point_2d




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


def add_chamfer_feature(com_def, edge, distance):
    edgeCollection = com_def.Application.TransientObjects.CreateEdgeCollection()
    edgeCollection.Add(edge)
    chamfer_feature = com_def.Features.ChamferFeatures.AddUsingDistance(
        edgeCollection, distance
    )
    return chamfer_feature


def add_revolve_feature(com_def, profile, axis_entity, angle, direction, operation):
    revolve_feature = com_def.Features.RevolveFeatures.AddByAngle(
        profile, axis_entity, angle, direction, operation
    )
    return revolve_feature


def add_fillet_feature(com_def, edge, radius):
    edgeCollection = com_def.Application.TransientObjects.CreateEdgeCollection()
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


def convert_extrude_op_to_inventor(operation):
    if operation == BODY_OPERATIONS.index("NewBodyFeatureOperation"):
        extrude_type = ExtrudeType.NewBody
    elif operation == BODY_OPERATIONS.index("JoinFeatureOperation"):
        extrude_type = ExtrudeType.Join
    elif operation == BODY_OPERATIONS.index("CutFeatureOperation"):
        extrude_type = ExtrudeType.Cut
    elif operation == BODY_OPERATIONS.index("IntersectFeatureOperation"):
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


def create_inventor_model_from_sequence(seq, com_def):
    for extrude_op in seq:
        ext_def = convert_to_extrude_inventor(com_def, extrude_op)
        feature = add_extrude_feature(com_def, ext_def)


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

def add_sketch2d_line(sketch, start_point, end_point):
    line = sketch.SketchLines.AddByTwoPoints(start_point, end_point)
    return line


def add_sketch2d_circle(sketch, center, radius):
    circle = sketch.SketchCircles.AddByCenterRadius(center, radius)
    return circle


def add_sketch2d_point(sketch, point, is_hole_center=True):
    sketch_point = sketch.SketchPoints.Add(point, is_hole_center)
    return sketch_point


def add_sketch2d_arc(sketch, *args):
    if len(args) == 4 and isinstance(args[1], (int, float, np.floating)):
        center, radius, start_angle, sweep_angle = args
        arc = sketch.SketchArcs.AddByCenterStartSweepAngle(
            center, radius, start_angle, sweep_angle
        )
        return arc
    if len(args) == 3:
        start_point, mid_point, end_point = args
        arc = sketch.SketchArcs.AddByThreePoints(start_point, mid_point, end_point)
        return arc
    if len(args) == 4:
        p1, p2, p3, is_counter_clockwise = args
        arc = sketch.SketchArcs.AddByCenterStartEndPoint(
            p1, p2, p3, is_counter_clockwise
        )
        return arc
    raise TypeError(
        "add_sketch2d_arc expected (center, radius, start_angle, sweep_angle) or (start_point, mid_point, end_point)"
    )


def add_work_plane(com_def, origin, x_axis, y_axis):
    from .transient import transient_point_3d, transient_unit_vector_3d

    origin = transient_point_3d(com_def.Application, *origin)
    x_axis = transient_unit_vector_3d(com_def.Application, *x_axis)
    y_axis = transient_unit_vector_3d(com_def.Application, *y_axis)
    work_plane = com_def.WorkPlanes.AddFixed(origin, x_axis, y_axis)
    return work_plane



def add_work_axe(com_def, origin, axis):
    from .transient import transient_point_3d, transient_unit_vector_3d

    origin = transient_point_3d(com_def.Application, *origin)
    _axis = transient_unit_vector_3d(com_def.Application, *axis)
    work_axe = com_def.WorkAxes.AddFixed(origin, _axis)
    return work_axe


def add_work_point(com_def, point):
    from .transient import transient_point_3d

    _point = transient_point_3d(com_def.Application, *point)
    work_point = com_def.WorkPoints.AddFixed(_point)
    return work_point


def add_profile(sketch):
    profile = sketch.Profiles.AddForSolid()
    return profile
