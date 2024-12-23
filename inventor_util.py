from copy import copy
from enum import Enum

import numpy as np
import win32com.client
from win32com.client import constants

from cad_utils.curves import Line, Circle, Arc
from cad_utils.macro import EXTENT_TYPE, EXTRUDE_OPERATIONS
from win32com.client.gencache import EnsureDispatch


def get_inventor_application():
    try:
        # Get the Inventor application object.
        inv_app = win32com.client.GetActiveObject("Inventor.Application")
        EnsureDispatch("Inventor.Application")
    except Exception as e:
        try:
            print("Warning: Unable to get active Inventor.Application object.", e)
            inv_app = win32com.client.Dispatch("Inventor.Application")
            EnsureDispatch("Inventor.Application")

        except Exception as e:
            print("Error: Unable to get Inventor.Application object.", e)
            return None
    return inv_app


def create_inventor_model_from_sequence(seq,com_def):
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


def add_part_document(app,name):
    if app is None:
        app = get_inventor_application()

    part = app.Documents.Add(constants.kPartDocumentObject, "", True)
    part = win32com.client.CastTo(part, "PartDocument")
    part.DisplayName = name
    part
    com_def = part.ComponentDefinition
    return part, com_def


def add_sketch(com_def, work_plane=None):
    if work_plane is None:
        work_plane = com_def.WorkPlanes.Item(3)
    sketch = com_def.Sketches.Add(work_plane)
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


def add_work_plane(com_def, origin, x_axis, y_axis):
    origin = transient_point_3d(com_def.Application, *origin)
    x_axis = transient_unit_vector_3d(com_def.Application, *x_axis)
    y_axis = transient_unit_vector_3d(com_def.Application, *y_axis)
    work_plane = com_def.WorkPlanes.AddFixed(origin, x_axis, y_axis)
    return work_plane


def add_profile(sketch):
    profile = sketch.Profiles.AddForSolid()
    return profile


def create_extrude_definition(com_def, profile, distance1, distance2,
                              extrude_type: ExtrudeType,
                              extrude_direction: ExtrudeDirection):
    extrude_def = (com_def.Features.ExtrudeFeatures.
                   CreateExtrudeDefinition(profile, extrude_type.get_type()))
    extrude_def.SetDistanceExtent(distance1, extrude_direction.get_direction())
    if extrude_direction == ExtrudeDirection.Symmetric:
        extrude_def.SetDistanceExtentTwo(distance2)
    return extrude_def


def convert_to_extrude_inventor(com_def, extrude_op):
    profile = copy(extrude_op.profile)
    profile.denormalize(extrude_op.sketch_size)
    sketch_plane = copy(extrude_op.sketch_plane)
    sketch_plane.origin = extrude_op.sketch_pos

    plane = add_work_plane(com_def, sketch_plane.origin,
                           sketch_plane.x_axis, sketch_plane.y_axis)
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
    

    extrude_def = create_extrude_definition(com_def, profile_inventor, extrude_op.extent_one,
                                            extrude_op.extent_two,
                                            extrude_type, extrude_dir)
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
        curve_inv = sketch.SketchArcs.AddByThreePoints(start_point, mid_point, end_point)
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


def remove_padding(vec):
    commands = vec[:, 0].tolist()
    if 3 in commands:
        seq_len = commands.index(3)
        vec = vec[:seq_len+1]
    return vec

# todo: implement this
def save__inventor_document(doc, file_path):
    doc.SaveAs(file_path, False)
    pass