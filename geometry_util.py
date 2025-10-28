


from typing import Optional, TextIO
from inventor_util import enum_name, index_face

# --------------- Printing helper -----------------

def _emit(line: str, out: Optional[TextIO] = None) -> None:
    if out is None:
        print(line)
    else:
        out.write(line + "\n")
class Point2D:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point2D(x={self.x}, y={self.y})"

    @classmethod
    def from_inventor(cls, point2d):
        return cls(point2d.X, point2d.Y)

class Point3D:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"Point3D(x={self.x}, y={self.y}, z={self.z})"

    @classmethod
    def from_inventor(cls, point3d):
        return cls(point3d.X, point3d.Y, point3d.Z)
    
    def unit(self):
        import math
        mag = math.sqrt(self.x**2 + self.y**2 + self.z**2)
        if mag == 0:
            return Point3D(0, 0, 0)
        return Point3D(self.x/mag, self.y/mag, self.z/mag)
    
    def cross(self, other: 'Point3D') -> 'Point3D':
        return Point3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )

class SketchPlane:
    def __init__(self, sketch):
        self.work_plane = sketch.PlanarEntityGeometry
        self.plane_entity = sketch.PlanarEntity
        self.origin = Point3D.from_inventor(sketch.OriginPointGeometry)
        self.normal = Point3D.from_inventor(self.work_plane.Normal)
        if sketch.AxisIsX:
            self.axis_x = Point3D.from_inventor(sketch.AxisEntityGeometry.Direction)
            # 右手法则 xyz
            self.axis_y = Point3D.from_inventor(self.work_plane.Normal.CrossProduct(sketch.AxisEntityGeometry.Direction))
        else:
            self.axis_y = Point3D.from_inventor(sketch.AxisEntityGeometry.Direction)
            # 右手法则 xyz
            self.axis_x = Point3D.from_inventor(sketch.AxisEntityGeometry.Direction.CrossProduct(self.work_plane.Normal))


    def plane_entity_ref(self):
        try:
            return index_face(self.plane_entity)
        except Exception as e:
            print(f"Error indexing plane entity: {e}")
            return None

    def __repr__(self):
        return (f"SketchPlane(origin={self.origin}, normal={self.normal}, "
                f"axis_x={self.axis_x}, axis_y={self.axis_y})")
    

class RevolveAxis:
    def __init__(self, axis_entity):
        self.axis_entity = axis_entity

    @property
    def geometry(self):
        if  hasattr(self.axis_entity, 'Geometry3d'): # axis_entity is SketchLine 
            return self.axis_entity.Geometry3d
        elif hasattr(self.axis_entity, 'Line'): # axis_entity is WorkAxis
            return self.axis_entity.Line
        else:
            raise ValueError("Unknown axis entity type")
    @property
    def start_point(self):
        if hasattr(self.geometry, 'StartPoint'):
            return Point3D.from_inventor(self.geometry.StartPoint)
        elif hasattr(self.geometry, 'RootPoint'):
            return Point3D.from_inventor(self.geometry.RootPoint)
        else:
            raise ValueError("Unknown geometry type for start point")


    @property
    def direction(self):
        dir = Point3D.from_inventor(self.geometry.Direction)
        return dir.unit()

    def __repr__(self):
        return (f"RevolveAxis(start_point={self.start_point}, "
                f"direction={self.direction})")


class SketchPoint:
    def __init__(self, sketch_point):
        self._sketch_point = sketch_point

    @property
    def geometry(self):
        return Point2D.from_inventor(self._sketch_point.Geometry)

    @property
    def x(self):
        return self.geometry.x

    @property
    def y(self):
        return self.geometry.y
    
    def __repr__(self):
        return f"SketchPoint(x={self.x}, y={self.y})"


class Parameter:
    def __init__(self, parameter):
        self._parameter = parameter

    @property
    def name(self):
        return self._parameter.Name

    @property
    def value(self):
        return self._parameter.ModelValue
    
    @property
    def expression(self):
        return self._parameter.Expression

    @property
    def  value_type(self):
        return  enum_name(self._parameter.ModelValueType)

    def __repr__(self):
        return f"Parameter(name={self.name}, value={self.value}, expression={self.expression}, value_type={self.value_type})"
    
class Curve2d:
    def __init__(self, curve2d):
        self._curve2d = curve2d

    def __repr__(self):
        return f"Curve2d(type={type(self._curve2d)})"
    
    def pretty_print(self, prefix="", out=None):
        pass


class Arc2d(Curve2d):
    def __init__(self, arc2d):
        super().__init__(arc2d)
        self._arc2d = arc2d

    @property
    def center(self):
        return Point2D.from_inventor(self._arc2d.Center)

    @property
    def radius(self):
        return self._arc2d.Radius

    @property
    def start_angle(self):
        return self._arc2d.StartAngle

    @property
    def sweep_angle(self):
        return self._arc2d.SweepAngle

    def __repr__(self):
        return (f"Arc2d(center={self.center}, radius={self.radius}, "
                f"start_angle={self.start_angle}, sweep_angle={self.sweep_angle})")

    def pretty_print(self, prefix="", out=None):
        super().pretty_print(prefix, out=out)
        c = self.center
        _emit(f"{prefix}Arc2d: Center=({c.x:.3f}, {c.y:.3f}) Radius={self.radius:.3f} StartAngle={self.start_angle:.3f} SweepAngle={self.sweep_angle:.3f}", out=out)


class LineSegment2d(Curve2d):
    def __init__(self, line_segment2d):
        super().__init__(line_segment2d)
        self._line_segment2d = line_segment2d
    @property
    def start_point(self):
        return Point2D.from_inventor(self._line_segment2d.StartPoint)

    @property
    def end_point(self):
        return Point2D.from_inventor(self._line_segment2d.EndPoint)
    
    @property
    def direction(self):
        return Point2D.from_inventor(self._line_segment2d.Direction)

    def __repr__(self):
        return f"LineSegment2d(start_point={self.start_point}, end_point={self.end_point})"
    
    def pretty_print(self, prefix="", out=None):
        super().pretty_print(prefix, out=out)
        sp = self.start_point
        ep = self.end_point
        dir = self.direction
        _emit(f"{prefix}LineSegment2d: Start=({sp.x:.3f}, {sp.y:.3f}) End=({ep.x:.3f}, {ep.y:.3f}) Direction=({dir.x:.3f}, {dir.y:.3f})", out=out)



class CircleCurve2d(Curve2d):
    def __init__(self, circle_curve2d):
        super().__init__(circle_curve2d)
        self._circle_curve2d = circle_curve2d

    @property
    def center(self):
        return Point2D.from_inventor(self._circle_curve2d.Center)

    @property
    def radius(self):
        return self._circle_curve2d.Radius

    def __repr__(self):
        return f"CircleCurve2d(center={self.center}, radius={self.radius})"

    def pretty_print(self, prefix="", out=None):
        super().pretty_print(prefix, out=out)
        c = self.center
        _emit(f"{prefix}CircleCurve2d: Center=({c.x:.3f}, {c.y:.3f}) Radius={self.radius:.3f}", out=out)