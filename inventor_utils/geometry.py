

from traitlets import Any
from inventor_utils.enums import is_type_of
from inventor_utils.transient import transient_point_3d, transient_unit_vector_3d

from .utils import _emit


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

        mag = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
        if mag == 0:
            return Point3D(0, 0, 0)
        return Point3D(self.x / mag, self.y / mag, self.z / mag)

    def cross(self, other: "Point3D") -> "Point3D":
        return Point3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )
    def to_dict(self):
        return {"x": self.x, "y": self.y, "z": self.z}
    @classmethod
    def from_dict(cls, d: dict) -> "Point3D":
        return cls(d.get("x",0), d.get("y",0), d.get("z",0))
    def to_tuple(self):
        return (self.x, self.y, self.z)

class Plane:
    origin: Point3D
    normal: Point3D

    def __init__(self, plane):
        self.plane = plane
        self.origin = Point3D.from_inventor(plane.RootPoint)
        self.normal = Point3D.from_inventor(plane.Normal)
    @classmethod
    def from_origin_normal(cls, origin, normal):
        instance = cls.__new__(cls)
        instance.plane = None
        instance.origin = origin if isinstance(origin, Point3D) else Point3D.from_inventor(origin)
        n = normal if isinstance(normal, Point3D) else Point3D.from_inventor(normal)
        instance.normal = n.unit()
        return instance

class PlaneEntityWrapper:
    origin: Point3D
    normal: Point3D
    axis_x: Point3D
    axis_y: Point3D
    
    def __init__(self, sketch, entity_index_helper):
        if not is_type_of(sketch, "PlanarSketch"):
            return
        self.plane = sketch.PlanarEntityGeometry
        if hasattr(sketch, "PlanarEntity"):
            self.plane_entity = sketch.PlanarEntity
        else:
            self.plane_entity = None
        self.origin = Point3D.from_inventor(sketch.OriginPointGeometry)
        self.normal = Point3D.from_inventor(self.plane.Normal)
        if sketch.AxisIsX:
            self.axis_x = Point3D.from_inventor(sketch.AxisEntityGeometry.Direction)
            self.axis_y = Point3D.from_inventor(
                self.plane.Normal.CrossProduct(sketch.AxisEntityGeometry.Direction)
            )
        else:
            self.axis_y = Point3D.from_inventor(sketch.AxisEntityGeometry.Direction)
            self.axis_x = Point3D.from_inventor(
                sketch.AxisEntityGeometry.Direction.CrossProduct(self.plane.Normal)
            )
        if self.plane_entity is not None and is_type_of(self.plane_entity, "Face"):
            try:
                # Local import to avoid circular dependency
                from .metadata import collect_face_metadata
                self.plane_entity_meta =  collect_face_metadata(self.plane_entity)

            except Exception as e:
                self.plane_entity_meta = None
                print(f"Warning: Unable to collect metadata for plane entity. Error: {e}")
        else:
            # print("Skip plane entity metadata collection.because plane_entity is None or not a Face.")
            self.plane_entity_meta = None
        pass

    def __repr__(self):
        return (
            f"SketchPlane(origin={self.origin}, normal={self.normal}, "
            f"axis_x={self.axis_x}, axis_y={self.axis_y})"
        )
    @classmethod
    def  from_work_plane(cls, work_plane, entity_index_helper = None):
        instance = cls.__new__(cls)
        app = work_plane.Application
        origin,axis_x,axis_y =  work_plane.GetPosition(transient_point_3d(app,0,0,0), transient_unit_vector_3d(app,0,0,0), transient_unit_vector_3d(app,0,0,0))
        instance.plane = work_plane.Plane
        instance.plane_entity = None  # No direct plane entity
        instance.origin = Point3D.from_inventor(origin)
        instance.normal = Point3D.from_inventor(instance.plane.Normal)
        instance.axis_x = Point3D.from_inventor(axis_x)
        instance.axis_y = Point3D.from_inventor(axis_y)
        # instance.entity_index_helper = entity_index_helper
        return instance


    
    @classmethod
    def from_dict(cls, d: dict, entity_index_helper) -> "PlaneEntityWrapper":
        instance = PlaneEntityWrapper.__new__(PlaneEntityWrapper)
        geom = d.get("geometry", {})
        origin = geom.get("origin", {})
        normal = geom.get("normal", {})
        axis_x = geom.get("axis_x", {})
        axis_y = geom.get("axis_y", {})
        instance.origin = Point3D(origin.get("x",0), origin.get("y",0), origin.get("z",0))
        instance.normal = Point3D(normal.get("x",0), normal.get("y",0), normal.get("z",0))
        instance.axis_x = Point3D(axis_x.get("x",0), axis_x.get("y",0), axis_x.get("z",0))
        instance.axis_y = Point3D(axis_y.get("x",0), axis_y.get("y",0), axis_y.get("z",0))
        instance.plane = None
        instance.plane_entity = None
        # instance.entity_index_helper = entity_index_helper
        index  = d.get("index")
        if index is not None:
            instance.plane_entity_meta = index
        return instance
    
    def to_dict(self):
        return {
            "geometry": {
                "origin": self.origin.to_dict(),
                "normal": self.normal.to_dict(),
                "axis_x": self.axis_x.to_dict(),
                "axis_y": self.axis_y.to_dict(),
            },
            "index": self.plane_entity_meta if hasattr(self, "plane_entity_meta") else None,
            "metaType": "PlaneEntity",
        }
    
    def to_work_plane(self, com_def):
        from .features import add_work_plane
        wp = add_work_plane(
            com_def,origin=self.origin.to_tuple(), x_axis=self.axis_x.to_tuple(), y_axis=self.axis_y.to_tuple()
        )
        return wp
    
    @classmethod
    def generate_plane_metadata(cls,origin:Point3D,normal:Point3D,axis_x, axis_y) -> dict:
        return {
            "geometry": {
                "origin": origin.to_dict(),
                "normal": normal.to_dict(),
                "axis_x": axis_x.to_dict() if axis_x else None,
                "axis_y": axis_y.to_dict() if axis_y else None,
            },
            "index": None,
            "metaType": "PlaneEntity",
        }



class AxisEntityWrapper:
    start_point: Point3D
    direction: Point3D
    axis_entity_meta: dict
    def __init__(self, axis_entity, entity_index_helper):
        self.entity_index_helper = entity_index_helper
        if is_type_of(axis_entity, "WorkAxis"):
            self.start_point = Point3D.from_inventor(axis_entity.Line.RootPoint)
            self.direction = Point3D.from_inventor(axis_entity.Line.Direction).unit()
        elif is_type_of(axis_entity, "SketchLine"):
            self.start_point = Point3D.from_inventor(axis_entity.Geometry3d.StartPoint)
            self.direction = Point3D.from_inventor(axis_entity.Geometry3d.Direction).unit()
        else:
            raise TypeError("Unsupported axis_entity type")
        self.axis_entity = axis_entity
        if self.axis_entity is not None and   is_type_of(self.axis_entity, "Edge"):

            try:
                # Local import to avoid circular dependency
                from .metadata import collect_edge_metadata
                self.axis_entity_meta =  collect_edge_metadata(self.axis_entity)
            except Exception as e:
                self.axis_entity_meta = {}
                print(f"Warning: Unable to collect metadata for axis entity. Error: {e}")
        else:
            self.axis_entity_meta = {}




    def __repr__(self):
        return f"RevolveAxis(start_point={self.start_point}, direction={self.direction})"

    @classmethod
    def from_dict(cls, d: dict, entity_index_helper) -> "AxisEntityWrapper":
        instance = AxisEntityWrapper.__new__(AxisEntityWrapper)
        start_point = d.get("axisInfo", {}).get("start_point", {})
        direction = d.get("axisInfo", {}).get("direction", {})
        instance.start_point = Point3D(start_point.get("x",0), start_point.get("y",0), start_point.get("z",0))
        instance.direction = Point3D(direction.get("x",0), direction.get("y",0), direction.get("z",0))
        # instance.axis_entity = entity_index_helper.select_entity_by_metadata(d.get("index"))
        instance.axis_entity_meta = d.get("index", {})
        instance.axis_entity = None # temporal set to None
        return instance
    def to_dict(self):
        return {
            'metaType':'AxisEntity',
            'axisInfo':{
            "start_point": self.start_point.to_dict(),
            "direction": self.direction.to_dict(),
            },
            "index": self.axis_entity_meta,
        }
    def to_work_axis(self, com_def):
        from .features import add_work_axe
        wp = add_work_axe(com_def,origin=self.start_point.to_tuple(), axis=self.direction.to_tuple()
        )
        return wp
    
    @classmethod
    def generate_axis_metadata(cls, start_point:Point3D, direction:Point3D) -> dict:
        return {
            'metaType':'AxisEntity',
            'axisInfo':{
            "start_point": start_point.to_dict(),
            "direction": direction.to_dict(),
            },
            "index": None,
        }


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
        from inventor_utils.enums import enum_name
        self._parameter = parameter
        self.name = parameter.Name
        self.value = parameter.ModelValue
        self.expression = parameter.Expression
        self.value_type = enum_name(parameter.ModelValueType)
        

    def __repr__(self):
        return f"Parameter(name={self.name}, value={self.value}, expression={self.expression}, value_type={self.value_type})"
    
    @staticmethod
    def from_dict(d: dict):
        instance = Parameter.__new__(Parameter)
        instance.name = d.get("name")
        instance.value = d.get("value")
        instance.expression = d.get("expression")
        instance.value_type = d.get("value_type") # type: ignore
        return instance



class Curve2d:
    def __init__(self, curve2d):
        self._curve2d = curve2d

    def __repr__(self):
        return f"Curve2d(type={type(self._curve2d)})"

    def pretty_print(self, prefix: str = "", out=None):
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
        return (
            f"Arc2d(center={self.center}, radius={self.radius}, "
            f"start_angle={self.start_angle}, sweep_angle={self.sweep_angle})"
        )

    def pretty_print(self, prefix: str = "", out=None):
        super().pretty_print(prefix, out=out)
        c = self.center
        _emit(
            f"{prefix}Arc2d: Center=({c.x:.3f}, {c.y:.3f}) Radius={self.radius:.3f} StartAngle={self.start_angle:.3f} SweepAngle={self.sweep_angle:.3f}",
            out=out,
        )


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

    def pretty_print(self, prefix: str = "", out=None):
        super().pretty_print(prefix, out=out)
        sp = self.start_point
        ep = self.end_point
        dir = self.direction
        _emit(
            f"{prefix}LineSegment2d: Start=({sp.x:.3f}, {sp.y:.3f}) End=({ep.x:.3f}, {ep.y:.3f}) Direction=({dir.x:.3f}, {dir.y:.3f})",
            out=out,
        )


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

    def pretty_print(self, prefix: str = "", out=None):
        super().pretty_print(prefix, out=out)
        c = self.center
        _emit(f"{prefix}CircleCurve2d: Center=({c.x:.3f}, {c.y:.3f}) Radius={self.radius:.3f}", out=out)


class BSplineCurve2d(Curve2d):
    def __init__(self, spline_curve2d):
        super().__init__(spline_curve2d)
        self._spline_curve2d = spline_curve2d

    def get_bspline_data(self):
        # Poles Double Input/output Double that specifies the poles of the B-Spline. 
        # Knots Double Input/output Double that specifies the knots of the B-Spline. 
        # Weights Double Input/output Double that specifies the B-spline's weights.
        poles,knots,weights =  self._spline_curve2d.GetBSplineData([], [], [])
        order, num_poles,num_knots, is_rational, is_periodic, is_closed  = self._spline_curve2d.GetBSplineInfo(0,0,0,False,False,False)
        return {
            'poles': poles,
            'knots': knots,
            'weights': weights,
            'order': order,
            'num_poles': num_poles,
            'num_knots': num_knots,
            'is_rational': is_rational,
            'is_periodic': is_periodic,
            'is_closed': is_closed,
        }



    def __repr__(self):
        return f"SplineCurve2d()"

    def pretty_print(self, prefix: str = "", out=None):
        super().pretty_print(prefix, out=out)
        _emit(f"{prefix}SplineCurve2d", out=out)