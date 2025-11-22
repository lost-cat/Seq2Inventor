import numpy as np


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


def transient_vector_3d(app, x,y,z):
    return app.TransientGeometry.CreateVector(x, y, z)


def transient_unit_vector_3d(app, x, y, z):
    return app.TransientGeometry.CreateUnitVector(x, y, z)

def transient_obj_collection(app):
    return app.TransientObjects.CreateObjectCollection()

