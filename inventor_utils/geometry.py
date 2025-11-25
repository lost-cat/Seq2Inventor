

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


    def to_tuple(self):
        return (self.x, self.y, self.z)


class PlaneEntity:
    def __init__(self, sketch, entity_index_helper):
        self.plane = sketch.PlanarEntityGeometry
        self.plane_entity = sketch.PlanarEntity
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
        self.entity_index_helper = entity_index_helper
        if self.plane_entity is None:
            try:
                # Local import to avoid circular dependency
                from .metadata import collect_face_metadata

                self.plane_entity_ref =  collect_face_metadata(self.plane_entity)
            except Exception:
                self.plane_entity_ref = None
                print("Warning: Unable to collect metadata for plane entity.")
        
        pass

    def __repr__(self):
        return (
            f"SketchPlane(origin={self.origin}, normal={self.normal}, "
            f"axis_x={self.axis_x}, axis_y={self.axis_y})"
        )
    @classmethod
    def  from_work_plane(cls, work_plane, entity_index_helper):
        instance = cls.__new__(cls)
        app = work_plane.Application
        origin,axis_x,axis_y =  work_plane.GetPosition(transient_point_3d(app,0,0,0), transient_unit_vector_3d(app,0,0,0), transient_unit_vector_3d(app,0,0,0))
        instance.plane = work_plane.Plane
        instance.plane_entity = None  # No direct plane entity
        instance.origin = Point3D.from_inventor(origin)
        instance.normal = Point3D.from_inventor(instance.plane.Normal)
        instance.axis_x = Point3D.from_inventor(axis_x)
        instance.axis_y = Point3D.from_inventor(axis_y)
        instance.entity_index_helper = entity_index_helper
        return instance

    def to_dict(self):
        return {
            "geometry": {
                "origin": self.origin,
                "normal": self.normal,
                "axis_x": self.axis_x,
                "axis_y": self.axis_y,
            },
            "index": self.plane_entity_ref if hasattr(self, "plane_entity_ref") else None,
        }
    
    @classmethod
    def from_dict(cls, d: dict, entity_index_helper) -> "PlaneEntity":
        instance = PlaneEntity.__new__(PlaneEntity)
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
        instance.entity_index_helper = entity_index_helper
        index  = d.get("index")
        if index is not None:
            instance.plane_entity_ref = index
        return instance


class AxisEntity:
    def __init__(self, axis_entity, entity_index_helper):
        self.axis_entity = axis_entity
        self.entity_index_helper = entity_index_helper

    @property
    def geometry(self):
        if hasattr(self.axis_entity, "Geometry3d"):
            return self.axis_entity.Geometry3d
        elif hasattr(self.axis_entity, "Line"):
            return self.axis_entity.Line
        else:
            raise ValueError("Unknown axis entity type")

    @property
    def start_point(self):
        if hasattr(self.geometry, "StartPoint"):
            return Point3D.from_inventor(self.geometry.StartPoint)
        elif hasattr(self.geometry, "RootPoint"):
            return Point3D.from_inventor(self.geometry.RootPoint)
        else:
            raise ValueError("Unknown geometry type for start point")

    @property
    def direction(self):
        dir = Point3D.from_inventor(self.geometry.Direction)
        return dir.unit()

    def __repr__(self):
        return f"RevolveAxis(start_point={self.start_point}, direction={self.direction})"

    def axis_entity_ref(self):
        try:
            # Local import to avoid circular dependency
            from .metadata import collect_edge_metadata

            return collect_edge_metadata(self.axis_entity)
        except Exception:
            return None

    def to_dict(self):
        return {
            "start_point": {"x": self.start_point.x, "y": self.start_point.y, "z": self.start_point.z},
            "direction": {"x": self.direction.x, "y": self.direction.y, "z": self.direction.z},
            "index": self.axis_entity_ref(),
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

    # Backward-compatible aliases expected by external imports
    SketchPlane = PlaneEntity
    RevolveAxis = AxisEntity
