from copy import copy
from enum import Enum

import numpy as np
import win32com.client
from win32com.client import constants
# from win32com.client import EnsureDispatch

from cad_utils.curves import Line, Circle, Arc
from cad_utils.macro import EXTENT_TYPE, EXTRUDE_OPERATIONS



def get_entity_by_reference_key(doc, key,KeyContext):

    entity = None
    context = None
    status,_,entity,context =  doc.ReferenceKeyManager.CanBindKeyToObject(key,KeyContext,entity,context)
    if(status):
        return entity
    else:
        return None
    pass

def get_string_reference_key(reference_key,part):

    string, location = part.ReferenceKeyManager.KeyToString(reference_key)
    return string
    pass

def get_reference_key(entity,KeyContext):

    key = []
    key = entity.GetReferenceKey(key,KeyContext)
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
    try:
        # Try to get the running Inventor application
        inv_app = win32com.client.Dispatch("Inventor.Application")
        # If Inventor is not running, this will start a new instance
    except Exception as e:
        print("Error: Unable to get Inventor.Application object.", e)
        return None
    return inv_app


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

    part = app.Documents.Add(constants.kPartDocumentObject, "", True)
    part = win32com.client.CastTo(part, "PartDocument")
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


def add_revolve_feature(com_def,profile, line_key):

    sketch= profile.Sketch
    pass


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
