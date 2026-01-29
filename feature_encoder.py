import math
from typing import Any, Dict, List, Optional, Tuple

from feature_wrappers import (
    ChamferFeatureWrapper,
    CircularPatternFeatureWrapper,
    ExtrudeFeatureWrapper,
    FeatureWrapperFactory,
    FilletFeatureWrapper,
    HoleFeatureWrapper,
    MirrorFeatureWrapper,
    RectangularPatternFeatureWrapper,
    RevolveFeatureWrapper,
    ShellFeatureWrapper,
)
from inventor_utils.extent_types import ExtentFactory, ExtentWrapper
from inventor_utils.geometry import AxisEntityWrapper, PlaneEntityWrapper, Point3D
from inventor_utils.metadata import (
    get_axis_direction_from_metadata,
    get_axis_origin_from_metadata,
    get_plane_normal_from_metadata,
)
from marco import *

__all__ = ["FeatureEncoder"]


# 2) 工具
def f(d: Dict, key: str, default=0.0) -> float:
    v = d.get(key)
    if isinstance(v, dict):
        return float(v.get("value", default))
    return float(v) if v is not None else float(default)


def rnd(x: float, tol: float = 1e-16) -> float:
    # 稳定四舍五入，避免训练抖动
    if x is None:
        return 0.0
    try:
        return round(float(x), max(0, int(-math.log10(tol))))
    except Exception:
        print(f"[rnd] Warning: cannot convert {x} to float")
        return 0.0


# 变长参数
def check_all(*values: Optional[Any]) -> bool:
    for v in values:
        if not check(v):
            return False
    return True


def check(value: Optional[Any]) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, dict) and len(value) == 0:
        return False
    return True


def push_kv(
    seq_keys: List[int],
    seq_val_ids: List[int],
    seq_val_floats: List[float],
    seq_is_num: List[int],
    key_id: int,
    val_id: int = 0,
    val_float: float = 0.0,
    is_num: int = 0,
):
    seq_keys.append(key_id)
    seq_val_ids.append(int(val_id) if not is_num else 0)
    seq_val_floats.append(float(val_float) if is_num else 0.0)
    seq_is_num.append(1 if is_num else 0)


def add_instr_boundary(seq_keys, seq_val_ids, seq_val_floats, seq_is_num, begin=True):
    if begin:
        push_kv(
            seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_B"], 0, 0.0, 0
        )
    else:
        push_kv(
            seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_E"], 0, 0.0, 0
        )


class FeatureEncoder:
    idx: int
    name2idx_map: Dict[str, List[int]]
    seq: Tuple[List[int], List[int], List[float], List[int]]

    def __init__(self):
        self.idx = 1  # 全局唯一ID，从1开始
        self.name2idx_map = {}
        self.seq = ([], [], [], [])

    def reserve_idx(self) -> int:
        current_idx = self.idx
        self.idx += 1
        return current_idx

    def init_seq(self):
        self.seq = ([], [], [], [])
        push_kv(*self.seq, KEY["BOS"], 0, 0.0, 0)

    def end_seq(self):
        push_kv(*self.seq, KEY["EOS"], 0, 0.0, 0)

    def encode(self, features: List[Dict[str, Any]]) -> Dict[str, List]:
        self.init_seq()

        for feat in features:
            t = feat.get("type")
            feat_idx = []
            feat_name = feat.get("name", "")
            if t in ("ExtrudeFeature", "RevolveFeature"):
                sketch_idx = self.encode_profile(feat)
                if t == "ExtrudeFeature":
                    feat_idx.append(self.add_extrude(sketch_idx, feat))
                elif t == "RevolveFeature":
                    feat_idx.append(self.add_revolve(sketch_idx, feat))
            elif t == "FilletFeature":
                fillet_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(fillet_wrapper, FilletFeatureWrapper):
                    raise ValueError("Feature is not a FilletFeatureWrapper")
                edge_set_count = fillet_wrapper.edge_set_count()
                fillet_idxs = []
                for edge_set_idx in range(edge_set_count):
                    idx = self.add_fillet(edge_set_idx, fillet_wrapper)
                    fillet_idxs.append(idx)
                feat_idx.extend(fillet_idxs)
            elif t == "ChamferFeature":
                chamfer_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(chamfer_wrapper, ChamferFeatureWrapper):
                    raise ValueError("Feature is not a ChamferFeatureWrapper")
                feat_idx.append(self.add_chamfer(chamfer_wrapper))
            elif t == "HoleFeature":
                hole_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(hole_wrapper, HoleFeatureWrapper):
                    raise ValueError("Feature is not a HoleFeatureWrapper")
                feat_idx.append(self.add_hole(hole_wrapper))

            elif t == "ShellFeature":
                shell_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(shell_wrapper, ShellFeatureWrapper):
                    raise ValueError("Feature is not a ShellFeatureWrapper")
                feat_idx.append(self.add_shell(shell_wrapper))

            elif t == "MirrorFeature":
                mirror_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(mirror_wrapper, MirrorFeatureWrapper):
                    raise ValueError("Feature is not a MirrorFeatureWrapper")
                feat_idx.append(self.add_mirror(mirror_wrapper))

            elif t == "RectangularPatternFeature":
                rect_pattern_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(
                    rect_pattern_wrapper, RectangularPatternFeatureWrapper
                ):
                    raise ValueError(
                        "Feature is not a RectangularPatternFeatureWrapper"
                    )
                feat_idx.append(self.add_rectangular_pattern(rect_pattern_wrapper))

            elif t == "CircularPatternFeature":
                circ_pattern_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(circ_pattern_wrapper, CircularPatternFeatureWrapper):
                    raise ValueError("Feature is not a CircularPatternFeatureWrapper")
                feat_idx.append(self.add_circular_pattern(circ_pattern_wrapper))
            else:
                raise ValueError(f"Unsupported feature type: {t}")

            if feat_name not in self.name2idx_map:
                self.name2idx_map[feat_name] = feat_idx

        self.end_seq()
        return {
            "key_ids": self.seq[0],
            "val_ids": self.seq[1],  # 仅离散值使用
            "val_floats": self.seq[2],  # 仅连续值使用
            "is_numeric": self.seq[3],  # 1=连续值, 0=离散值
            "vocab": {
                "KEY": KEY,
                "TYPE_ID": TYPE_ID,
                "OP_ID": OP_ID,
                "DIR_ID": DIR_ID,
                "EXTENT_ID": EXTENT_ID,
                "CHAMFER_TYPE_ID": CHAMFER_TYPE_ID,
                "PATTERN_SPACING_TYPE_ID": PATTERN_SPACING_TYPE_ID,
                "SURFACE_TYPE_ID": SURFACE_TYPE_ID,
                "EDGE_TYPE_ID": EDGE_TYPE_ID,
                "ENTITY_ID": ENTITY_ID,
            },
        }  # type: ignore

    def encode_profile(self, feat: Dict[str, Any]) -> int:
        seq = self.seq
        profile = feat.get("profile") or {}
        sketch_plane = profile.get("SketchPlane") or {}

        sketch_idx = self.add_sketch_start(sketch_plane)
        for path in profile.get("ProfilePaths", []):
            self.add_path_start()
            for ent in path.get("PathEntities", []):
                ctype = ent.get("CurveType")
                if ctype == "kLineSegmentCurve2d":
                    idx = self.add_line(ent)
                elif ctype == "kCircularArcCurve2d":
                    idx = self.add_arc(ent)
                elif ctype == "kCircleCurve2d":
                    idx = self.add_circle(ent)
            
            self.add_path_end()
            
        self.add_sketch_end(sketch_idx)

        return sketch_idx

    def add_path_end(self):
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["PathEnd"], 0.0, 0)
        add_instr_boundary(*self.seq, begin=False)

    def add_path_start(self):
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["PathStart"], 0.0, 0)
        add_instr_boundary(*self.seq, begin=False)

    def add_sketch_start(
        self,
        sketch_plane: Dict[str, Any],
    ) -> int:
        sp = sketch_plane or {}
        index = sp.get("index")
        ref_plane_idx = None
        if index:
            ref_plane_idx = self.add_selection(index, is_face=True)
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["SketchStart"], 0.0, 0)
        sketch_idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], sketch_idx, 0.0, 0)
        if index and ref_plane_idx is not None:
            push_kv(*self.seq, KEY["REFER_PLANE_IDX"], ref_plane_idx, 0.0, 0)
        geom = sp.get("geometry")
        if geom:
            o = geom.get("origin", {})
            n = geom.get("normal", {})
            ax = geom.get("axis_x", {})
            ay = geom.get("axis_y", {})
            for k, v in (
                ("OX", o.get("x", 0)),
                ("OY", o.get("y", 0)),
                ("OZ", o.get("z", 0)),
                ("NX", n.get("x", 0)),
                ("NY", n.get("y", 0)),
                ("NZ", n.get("z", 0)),
                ("XX", ax.get("x", 0)),
                ("XY", ax.get("y", 0)),
                ("XZ", ax.get("z", 0)),
                ("YX", ay.get("x", 0)),
                ("YY", ay.get("y", 0)),
                ("YZ", ay.get("z", 0)),
            ):
                push_kv(*self.seq, KEY[k], 0, rnd(v), 1)
        add_instr_boundary(*self.seq, begin=False)
        return sketch_idx

    def add_selection(
        self,
        meta_data: dict,
        is_face: bool,
    ) -> int:
        seq = self.seq
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["Selection"], 0.0, 0)
        idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], idx, 0.0, 0)
        if is_face:
            push_kv(*self.seq, KEY["SELECT_ENTITY"], ENTITY_ID["Face"], 0.0, 0)
            face_type = meta_data.get("surfaceType", "kUnknownSurface")
            push_kv(
                *self.seq,
                KEY["SURF_TYPE"],
                SURFACE_TYPE_ID.get(face_type, SURFACE_TYPE_ID["kUnknownSurface"]),
                0.0,
                0,
            )
            push_kv(*seq, KEY["AREA"], 0, rnd(meta_data.get("area", 0.0)), 1)
            centroid = meta_data.get("centroid", [0.0, 0.0, 0.0])
            push_kv(*seq, KEY["FACE_CENTROID_X"], 0, rnd(centroid[0]), 1)
            push_kv(*seq, KEY["FACE_CENTROID_Y"], 0, rnd(centroid[1]), 1)
            push_kv(*seq, KEY["FACE_CENTROID_Z"], 0, rnd(centroid[2]), 1)

        else:
            push_kv(*seq, KEY["SELECT_ENTITY"], ENTITY_ID["Edge"], 0.0, 0)
            edge_type = meta_data.get("geometryType", "kUnknownCurve")
            push_kv(
                *seq,
                KEY["EDGE_TYPE"],
                EDGE_TYPE_ID.get(edge_type, EDGE_TYPE_ID["kUnknownCurve"]),
                0.0,
                0,
            )
            start_point = meta_data["endpoints"][0]
            end_point = meta_data["endpoints"][1]
            mid_point = meta_data["midpoint"]
            length = meta_data["length"]
            push_kv(*seq, KEY["EDGE_LENGTH"], 0, rnd(length), 1)
            push_kv(*seq, KEY["EDGE_START_X"], 0, rnd(start_point[0]), 1)
            push_kv(*seq, KEY["EDGE_START_Y"], 0, rnd(start_point[1]), 1)
            push_kv(*seq, KEY["EDGE_START_Z"], 0, rnd(start_point[2]), 1)
            push_kv(*seq, KEY["EDGE_END_X"], 0, rnd(end_point[0]), 1)
            push_kv(*seq, KEY["EDGE_END_Y"], 0, rnd(end_point[1]), 1)
            push_kv(*seq, KEY["EDGE_END_Z"], 0, rnd(end_point[2]), 1)
            push_kv(*seq, KEY["EDGE_MIDPOINT_X"], 0, rnd(mid_point[0]), 1)
            push_kv(*seq, KEY["EDGE_MIDPOINT_Y"], 0, rnd(mid_point[1]), 1)
            push_kv(*seq, KEY["EDGE_MIDPOINT_Z"], 0, rnd(mid_point[2]), 1)

        add_instr_boundary(*seq, begin=False)
        return idx
        pass

    def add_sketch_end(self, sketch_idx):
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["SketchEnd"], 0.0, 0)
        push_kv(*seq, KEY["PARENT"], sketch_idx, 0.0, 0)
        add_instr_boundary(*seq, begin=False)

    def add_line(
        self,
        ent: Dict[str, Any],
    ):
        sp = ent.get("StartSketchPoint", {})
        ep = ent.get("EndSketchPoint", {})
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Line"], 0.0, 0)
        push_kv(*seq, KEY["SPX"], 0, rnd(sp.get("x", 0)), 1)
        push_kv(*seq, KEY["SPY"], 0, rnd(sp.get("y", 0)), 1)
        push_kv(*seq, KEY["EPX"], 0, rnd(ep.get("x", 0)), 1)
        push_kv(*seq, KEY["EPY"], 0, rnd(ep.get("y", 0)), 1)
        add_instr_boundary(*seq, begin=False)

    def add_arc(
        self,
        ent: Dict[str, Any],
    ):
        curve = ent.get("Curve") or {}
        c = curve.get("center", {})
        sp = ent.get("StartSketchPoint", {})
        ep = ent.get("EndSketchPoint", {})
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Arc"], 0.0, 0)
        push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
        push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
        push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
        push_kv(*seq, KEY["SA"], 0, rnd(curve.get("startAngle", 0)), 1)
        push_kv(*seq, KEY["SW"], 0, rnd(curve.get("sweepAngle", 0)), 1)
        push_kv(*seq,KEY['SPX'],0, rnd(sp.get("x",0)),1)
        push_kv(*seq,KEY['SPY'],0, rnd(sp.get("y",0)),1)
        push_kv(*seq,KEY['EPX'],0, rnd(ep.get("x",0)),1)
        push_kv(*seq,KEY['EPY'],0, rnd(ep.get("y",0)),1)



        add_instr_boundary(*seq, begin=False)

    def add_circle(
        self,
        ent: Dict[str, Any],
    ):
        curve = ent.get("Curve") or {}
        c = curve.get("center", {})
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Circle"], 0.0, 0)
        push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
        push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
        push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
        add_instr_boundary(*seq, begin=False)

    def add_point(
        self,
        ent: Dict[str, Any],
    ):
        x = ent.get("x", 0)
        y = ent.get("y", 0)
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Point"], 0.0, 0)
        push_kv(*seq, KEY["PX"], 0, rnd(x), 1)
        push_kv(*seq, KEY["PY"], 0, rnd(y), 1)
        add_instr_boundary(*seq, begin=False)

    def add_extrude(
        self,
        sketch_idx: int,
        feat: Dict[str, Any],
    ) -> int:
        seq = self.seq
        extrude_wrapper = FeatureWrapperFactory.from_dict(feat)
        if not isinstance(extrude_wrapper, ExtrudeFeatureWrapper):
            raise ValueError("Feature is not an ExtrudeFeatureWrapper")
        operation = extrude_wrapper.operation()
        extent_type = extrude_wrapper.extent_type()
        if not check(operation) or not check(extent_type):
            raise ValueError("Extrude feature missing operation or extentType")
        extent = extrude_wrapper.extent()
        if extent is None:
            raise ValueError("Extrude feature missing extent")
        extent_one_idx = self.add_extent(extent)
        is_two_direction = extrude_wrapper.is_two_directional()
        if is_two_direction:
            extent_two = extrude_wrapper.extent_two()
            extent_two_type = extrude_wrapper.extent_two_type()
            if extent_two is None or not check(extent_two_type):
                raise ValueError(
                    "Extrude feature missing extentTwo or extentTwoType for two-directional extrude"
                )
            extent_two_idx = self.add_extent(extent_two)
        else:
            extent_two = None
            extent_two_type = ""
            extent_two_idx = None

        add_instr_boundary(*seq, begin=True)

        push_kv(*seq, KEY["TYPE"], TYPE_ID["Extrude"], 0.0, 0)
        extrude_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], extrude_idx, 0.0, 0)
        push_kv(*seq, KEY["PARENT"], 0, float(sketch_idx), 1)
        push_kv(*seq, KEY["OP"], OP_ID.get(operation, 0), 0.0, 0)
        push_kv(*seq, KEY["EXTENT_ONE_TYPE"], EXTENT_ID.get(extent_type, 0), 0.0, 0)
        push_kv(*seq, KEY["EXTENT_ONE"], extent_one_idx, 0.0, 0)
        push_kv(*seq, KEY["ISTWO_DIRECTIONAL"], 1 if is_two_direction else 0, 0.0, 0)
        if is_two_direction and extent_two is not None and extent_two_idx is not None:
            push_kv(
                *seq, KEY["EXTENT_TWO_TYPE"], EXTENT_ID.get(extent_two_type, 0), 0.0, 0
            )
            push_kv(*seq, KEY["EXTENT_TWO"], extent_two_idx, 0.0, 0)
        add_instr_boundary(*seq, begin=False)
        return extrude_idx

    def add_extent(
        self,
        extent: Dict[str, Any] | ExtentWrapper,
    ) -> int:
        if isinstance(extent, dict):
            extent_wrapper = ExtentFactory.from_dict(extent)
        else:
            extent_wrapper = extent
        if extent_wrapper is None:
            raise ValueError("Unsupported extent type")
        kvs = extent_wrapper.extract_kvs()
        entity_idx_map = {}
        for ent_key, ent_meta in kvs.get("entities", {}).items():
            if ent_key not in KEY.values():
                raise ValueError(f"Unknown entity key: {ent_key}")
            ent_meta_type = ent_meta.get("metaType")
            if ent_meta_type != "Face" and ent_meta_type != "Edge":
                raise ValueError(
                    f"Unsupported entity type for extent selection: {ent_meta_type}"
                )
            select_idx = self.add_selection(
                ent_meta,
                is_face=(ent_meta.get("metaType") == "Face"),
            )
            entity_idx_map[ent_key] = select_idx
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Extent"], 0.0, 0)
        extent_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], extent_idx, 0.0, 0)
        for k, v in kvs.get("nums", {}).items():
            if k not in KEY.values():
                raise ValueError(f"Unknown numeric key: {k}")
            push_kv(*seq, k, 0, rnd(v), 1)
        for k, v in kvs.get("enums", {}).items():
            if k not in KEY.values():
                raise ValueError(f"Unknown enum key: {k}")
            push_kv(*seq, k, int(v), 0.0, 0)

        for k, v in kvs.get("entities", {}).items():
            if k not in KEY.values():
                raise ValueError(f"Unknown entity index key: {k}")
            push_kv(*seq, k, entity_idx_map[k], 0.0, 0)

        add_instr_boundary(*seq, begin=False)
        return extent_idx

    def add_revolve(
        self,
        sketch_idx: int,
        feat: Dict[str, Any],
    ) -> int:

        revolve_wrapper = FeatureWrapperFactory.from_dict(feat)
        if not isinstance(revolve_wrapper, RevolveFeatureWrapper):
            raise ValueError("Feature is not a RevolveFeatureWrapper")
        operation = revolve_wrapper.operation()
        axis_entity = revolve_wrapper.axis_entity()
        if not check(operation) or axis_entity is None:
            raise ValueError("Revolve feature missing operation or axisEntity")
        start_point = axis_entity.start_point
        direction = axis_entity.direction
        extent = revolve_wrapper.extent()
        extent_type = revolve_wrapper.extent_type()
        if extent is None or not check(extent_type):
            raise ValueError("Revolve feature missing extent")
        extent_idx = self.add_extent(extent)
        is_two_direction = revolve_wrapper.is_two_directional()
        if is_two_direction:
            extent_two = revolve_wrapper.extent_two()
            if extent_two is None:
                raise ValueError(
                    "Revolve feature missing extentTwo for two-directional revolve"
                )
            extent_two_idx = self.add_extent(extent_two)
            extent_two_type = revolve_wrapper.extent_two_type()
        else:
            extent_two = None
            extent_two_idx = None
            extent_two_type = ""
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Revolve"], 0.0, 0)
        revolve_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], revolve_idx, 0.0, 0)
        # idx += 1  已经在上面预留的时候加1了
        push_kv(*seq, KEY["PARENT"], sketch_idx, 0.0, 0)
        push_kv(*seq, KEY["OP"], OP_ID.get(operation, 0), 0.0, 0)
        push_kv(*seq, KEY["AXIS_X"], 0, rnd(start_point.x), 1)
        push_kv(*seq, KEY["AXIS_Y"], 0, rnd(start_point.y), 1)
        push_kv(*seq, KEY["AXIS_Z"], 0, rnd(start_point.z), 1)
        push_kv(*seq, KEY["AXIS_DIR_X"], 0, rnd(direction.x), 1)
        push_kv(*seq, KEY["AXIS_DIR_Y"], 0, rnd(direction.y), 1)
        push_kv(*seq, KEY["AXIS_DIR_Z"], 0, rnd(direction.z), 1)
        push_kv(*seq, KEY["EXTENT_ONE_TYPE"], EXTENT_ID.get(extent_type, 0), 0.0, 0)
        push_kv(*seq, KEY["EXTENT_ONE"], extent_idx, 0.0, 0)
        push_kv(*seq, KEY["ISTWO_DIRECTIONAL"], 1 if is_two_direction else 0, 0.0, 0)
        if (
            is_two_direction
            and extent_two is not None
            and extent_two_idx is not None
            and extent_two_type != ""
        ):
            push_kv(
                *seq, KEY["EXTENT_TWO_TYPE"], EXTENT_ID.get(extent_two_type, 0), 0.0, 0
            )
            push_kv(*seq, KEY["EXTENT_TWO"], extent_two_idx, 0.0, 0)

        add_instr_boundary(*seq, begin=False)
        return revolve_idx

    def add_fillet(
        self,
        edge_set_idx: int,
        fillet_wrapper: FilletFeatureWrapper,
    ) -> int:
        if not isinstance(fillet_wrapper, FilletFeatureWrapper):
            raise ValueError("Feature is not a FilletFeatureWrapper")
        edge_set = fillet_wrapper.get_edge_set(edge_set_idx)
        if edge_set is None:
            raise ValueError("Fillet feature missing edge set")
        radius = edge_set["radius"]
        edges = edge_set["edges"]
        edge_idxs = []
        for edge in edges:
            edge_idx = self.add_selection(edge, is_face=False)
            edge_idxs.append(edge_idx)
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Fillet"], 0, 0)
        fillet_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], fillet_idx, 0.0, 0)
        push_kv(*seq, KEY["RADIUS"], 0, rnd(radius["value"]), 1)
        for eidx in edge_idxs:
            push_kv(*seq, KEY["FILLET_EDGE_IDX"], eidx, 0.0, 0)
        add_instr_boundary(*seq, begin=False)

        return fillet_idx

    def add_chamfer(
        self,
        chamfer_wrapper: ChamferFeatureWrapper,
    ) -> int:
        if not isinstance(chamfer_wrapper, ChamferFeatureWrapper):
            raise ValueError("Feature is not a ChamferFeatureWrapper")
        chamfer_type = chamfer_wrapper.chamfer_type()
        if not check(chamfer_type):
            raise ValueError("Chamfer feature missing chamferType")
        if chamfer_type == "kDistanceAndAngle" or chamfer_type == "kTwoDistances":
            face = chamfer_wrapper.face()
            if face is None:
                raise ValueError("Chamfer feature missing face for kDistanceAndAngle")
            face_idx = self.add_selection(face, is_face=True)
        else:
            face_idx = None
        edge_count = chamfer_wrapper.edge_count()
        edge_idxs = []
        for edge_idx in range(edge_count):
            edge = chamfer_wrapper.get_edge(edge_idx)
            if edge is None:
                raise ValueError("Chamfer feature missing edge")
            selection_idx = self.add_selection(edge, is_face=False)
            edge_idxs.append(selection_idx)
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Chamfer"], 0, 0)
        chamfer_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], chamfer_idx, 0.0, 0)
        push_kv(*seq, KEY["CHAMFER_TYPE"], CHAMFER_TYPE_ID[chamfer_type], 0.0, 0)
        if chamfer_type == "kTwoDistances":
            dist_a, dist_b = chamfer_wrapper.distance(), chamfer_wrapper.distance_two()
            if dist_a is None or dist_b is None:
                raise ValueError("Chamfer feature missing distances for kTwoDistances")
            push_kv(*seq, KEY["CHAMFER_DIST_A"], 0, rnd(dist_a.value), 1)
            push_kv(*seq, KEY["CHAMFER_DIST_B"], 0, rnd(dist_b.value), 1)
            if face_idx is None:
                raise ValueError("Chamfer feature missing face for kTwoDistances")
            push_kv(*seq, KEY["CHAMFER_FACE_IDX"], face_idx, 0.0, 0)
        elif chamfer_type == "kDistanceAndAngle":
            distance, angle = chamfer_wrapper.distance(), chamfer_wrapper.angle()
            if distance is None or angle is None:
                raise ValueError(
                    "Chamfer feature missing distance or angle for kDistanceAndAngle"
                )
            push_kv(*seq, KEY["CHAMFER_DIST_A"], 0, rnd(distance.value), 1)
            push_kv(*seq, KEY["CHAMFER_ANGLE"], 0, rnd(angle.value), 1)
            if face_idx is None:
                raise ValueError("Chamfer feature missing face for kDistanceAndAngle")
            push_kv(*seq, KEY["CHAMFER_FACE_IDX"], face_idx, 0.0, 0)
        elif chamfer_type == "kDistance":
            distance = chamfer_wrapper.distance()
            if distance is None:
                raise ValueError("Chamfer feature missing distance for kDistance")
            push_kv(*seq, KEY["CHAMFER_DIST_A"], 0, rnd(distance.value), 1)
        else:
            raise ValueError(f"Unsupported chamfer type: {chamfer_type}")

        for eidx in edge_idxs:
            push_kv(*seq, KEY["CHAMFER_EDGE_IDX"], eidx, 0.0, 0)

        add_instr_boundary(*seq, begin=False)

        return chamfer_idx

    def add_hole(self, hole_wrapper) -> int:
        if not isinstance(hole_wrapper, HoleFeatureWrapper):
            raise ValueError("Feature is not a HoleFeatureWrapper")
        sketch = hole_wrapper.sketch_plane()
        if sketch is None:
            raise ValueError("Hole feature missing sketch plane")

        sketch_idx = self.add_sketch_start(sketch.to_dict())
        hole_point_count = hole_wrapper.hole_point_count()
        for hole_point_idx in range(hole_point_count):
            hole_point = hole_wrapper.get_hole_point(hole_point_idx)
            if hole_point is None:
                raise ValueError("Hole feature missing hole point")
            self.add_point(hole_point)
        self.add_sketch_end(sketch_idx=sketch_idx)
        diameter = hole_wrapper.hole_diameter()
        depth = hole_wrapper.depth()
        extent = hole_wrapper.extent()
        is_flat_bottom = hole_wrapper.is_flat_bottomed()
        if not is_flat_bottom:
            bottom_tip_angle = hole_wrapper.bottom_tip_angle()
        else:
            bottom_tip_angle = None
        if (
            diameter is None
            or extent is None
            or depth is None
        ):
            raise ValueError("Hole feature missing diameter, extent, or depth")

        extent_idx = self.add_extent(extent)
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Hole"], 0, 0)
        hole_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], hole_idx, 0.0, 0)
        push_kv(*seq, KEY["PARENT"], sketch_idx, 0.0, 0)
        push_kv(*seq, KEY["DIAMETER"], 0, rnd(diameter.value), 1)
        push_kv(*seq, KEY["HOLE_EXTENT"], extent_idx, 0.0, 0)
        push_kv(*seq, KEY["DEPTH"], 0, rnd(depth), 1)
        if is_flat_bottom is not None :
            if is_flat_bottom is False and bottom_tip_angle is None:
                is_flat_bottom = True  # default to True if angle is missing
            push_kv(
                *seq,
                KEY["IS_FLAT_BOTTOM"],
                1 if is_flat_bottom else 0,
                0.0,
                0,
            )
        if  is_flat_bottom  is False and bottom_tip_angle is not None:
            push_kv(*seq, KEY["BOTTOM_TIP_ANGLE"], 0, rnd(bottom_tip_angle.value), 1)
        add_instr_boundary(*seq, begin=False)
        return hole_idx

    def add_shell(self, shell_wrapper) -> int:
        if not isinstance(shell_wrapper, ShellFeatureWrapper):
            raise ValueError("Feature is not a ShellFeatureWrapper")
        thickness = shell_wrapper.thickness()
        direction = shell_wrapper.direction()
        if thickness is None or direction is None:
            raise ValueError("Shell feature missing thickness or direction")
        face_count = shell_wrapper.input_face_count()
        face_idxs = []
        for face_idx in range(face_count):
            face = shell_wrapper.get_input_face(face_idx)
            if face is None:
                raise ValueError("Shell feature missing input face")

            selection_idx = self.add_selection(face, is_face=True)
            face_idxs.append(selection_idx)
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Shell"], 0, 0)
        shell_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], shell_idx, 0.0, 0)
        push_kv(*seq, KEY["SHELL_THICKNESS"], 0, rnd(thickness.value), 1)
        push_kv(*seq, KEY["SHELL_DIRECTION"], SHELL_DIR_ID.get(direction, 0), 0.0, 0)
        for fidx in face_idxs:
            push_kv(*seq, KEY["SHELL_FACE_IDX"], fidx, 0.0, 0)
        
        add_instr_boundary(*seq, begin=False)

        return shell_idx

    def add_mirror(self, mirror_wrapper) -> int:
        if not isinstance(mirror_wrapper, MirrorFeatureWrapper):
            raise ValueError("Feature is not a MirrorFeatureWrapper")
        is_mirror_body = mirror_wrapper.is_mirror_body()
        is_mirror_plane_face = mirror_wrapper.is_mirror_plane_face()
        if is_mirror_plane_face:
            face_meta = mirror_wrapper.mirror_plane()
            if not isinstance(face_meta, dict):
                raise ValueError("Mirror feature mirror plane expected to be face metadata")
            
            
        mirror_plane = mirror_wrapper.mirror_plane()
        if mirror_plane is None:
            raise ValueError("Mirror feature missing mirror plane")
        mirror_plane_point = None
        mirror_plane_normal = None
        face_idx = None
        if isinstance(mirror_plane, dict): #is_mirror_plane_face == True
            face_meta = mirror_plane
            mirror_plane_normal = Point3D(
                face_meta["orientation"][0],
                face_meta["orientation"][1],
                face_meta["orientation"][2],
            )
            mirror_plane_point = Point3D(
                face_meta["centroid"][0],
                face_meta["centroid"][1],
                face_meta["centroid"][2],
            )
            face_idx = self.add_selection(
                face_meta, is_face=True
            )
        else:
            geom = mirror_plane.to_dict().get("geometry", {})
            o = geom.get("origin", {})
            n = geom.get("normal", {})
            mirror_plane_point = Point3D(
                rnd(o.get("x", 0)), rnd(o.get("y", 0)), rnd(o.get("z", 0))
            )
            mirror_plane_normal = Point3D(
                rnd(n.get("x", 0)), rnd(n.get("y", 0)), rnd(n.get("z", 0))
            )

        operation = None
        remove_original = None
        if mirror_plane_point is None or mirror_plane_normal is None:
            raise ValueError("Mirror feature missing mirror plane point or normal")
        if not is_mirror_body:
            feature_names = mirror_wrapper.features_to_mirror()
            if not feature_names:
                raise ValueError("Mirror feature missing features to mirror")
            feature_idxs = []
            for fname in feature_names:
                if fname in self.name2idx_map:
                    fidxs = self.name2idx_map[fname]
                    feature_idxs.extend(fidxs)
        else:
            feature_idxs = []
            operation = mirror_wrapper.operation()
            remove_original = mirror_wrapper.remove_original()
        
        compute_type = mirror_wrapper.compute_type()
        if not check(compute_type):
            raise ValueError("Mirror feature missing computeType")
        
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Mirror"], 0, 0)
        mirror_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], mirror_idx, 0.0, 0)
        push_kv(*seq, KEY["IS_MIRROR_BODY"], 1 if is_mirror_body else 0, 0.0, 0)
        push_kv(*seq, KEY["MIRROR_COMPUTE_TYPE"], PATTERN_COMPUTE_TYPE_ID.get(compute_type, 0), 0.0, 0) # type: ignore
        if is_mirror_plane_face and face_idx is not None:
            push_kv(*seq, KEY["MIRROR_PLANE_FACE_IDX"], face_idx, 0.0, 0)
        if not is_mirror_body:
            for fidx in feature_idxs:
                push_kv(*seq, KEY["MIRROR_FEATURE_IDX"], fidx, 0.0, 0)
        else:
            if operation is  None or remove_original is None:
                raise ValueError("Mirror feature missing operation or removeOriginal for body mirror")
            push_kv(*seq, KEY["REMOVE_ORIGINAL"], 1 if remove_original else 0, 0.0, 0)
            push_kv(*seq,KEY['MIRROR_OP'], OP_ID[operation], 0.0, 0)

        push_kv(*seq, KEY["MIRROR_PLANE_OX"], 0, mirror_plane_point.x, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_OY"], 0, mirror_plane_point.y, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_OZ"], 0, mirror_plane_point.z, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NX"], 0, mirror_plane_normal.x, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NY"], 0, mirror_plane_normal.y, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NZ"], 0, mirror_plane_normal.z, 1)
        add_instr_boundary(*seq, begin=False)

        return mirror_idx

    def add_rectangular_pattern(self, rectangular_pattern_wrapper) -> int:
        if not isinstance(
            rectangular_pattern_wrapper, RectangularPatternFeatureWrapper
        ):
            raise ValueError("Feature is not a RectangularPatternFeatureWrapper")
        is_pattern_of_body = rectangular_pattern_wrapper.is_pattern_of_body()
        x_count = rectangular_pattern_wrapper.x_count()
        x_spacing = rectangular_pattern_wrapper.x_spacing()
        is_natural_x = rectangular_pattern_wrapper.x_natural_direction()
        spacing_type = rectangular_pattern_wrapper.x_spacing_type()
        x_direction_entity = rectangular_pattern_wrapper.x_direction_entity()
        x_direction = None
        if x_direction_entity is None:
            raise ValueError("RectangularPattern feature missing xDirectionEntity")

        x_direction = get_plane_normal_from_metadata(x_direction_entity)

        if (
            not check(spacing_type)
            or x_count is None
            or x_spacing is None
            or not check(spacing_type)
            or is_natural_x is None
            or is_pattern_of_body is None
        ):
            raise ValueError(
                "RectangularPattern feature missing xCount, xSpacing, or xSpacingType"
            )

        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["RectPattern"], 0, 0)
        rectangular_pattern_idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], rectangular_pattern_idx, 0.0, 0)
        push_kv(
            *self.seq,
            KEY["RECT_IS_PATTERN_BODY"],
            1 if is_pattern_of_body else 0,
            0.0,
            0,
        )
        push_kv(*self.seq, KEY["RECT_X_COUNT"], x_count.value, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_X_SPACING"], 0, rnd(x_spacing.value), 1)
        push_kv(*self.seq, KEY["RECT_IS_NARTURE_X_DIR"], 1 if is_natural_x else 0, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_X_SPACING_TYPE"], PATTERN_SPACING_TYPE_ID[spacing_type], 0.0, 0)  # type: ignore
        push_kv(*self.seq, KEY["RECT_X_DIR_X"], 0, rnd(x_direction[0]), 1)
        push_kv(*self.seq, KEY["RECT_X_DIR_Y"], 0, rnd(x_direction[1]), 1)
        push_kv(*self.seq, KEY["RECT_X_DIR_Z"], 0, rnd(x_direction[2]), 1)
        if not is_pattern_of_body:
            feature_names = rectangular_pattern_wrapper.features_to_pattern()
            if not feature_names:
                raise ValueError(
                    "RectangularPattern feature missing features to pattern"
                )
            feature_idxs = []
            for fname in feature_names:
                if fname in self.name2idx_map:
                    fidxs = self.name2idx_map[fname]
                    feature_idxs.extend(fidxs)
            for fidx in feature_idxs:
                push_kv(*self.seq, KEY["RECT_FEATURE_IDX"], fidx, 0.0, 0)

        add_instr_boundary(*self.seq, begin=False)

        return rectangular_pattern_idx

    def add_circular_pattern(self, circular_pattern_wrapper) -> int:
        if not isinstance(circular_pattern_wrapper, CircularPatternFeatureWrapper):
            raise ValueError("Feature is not a CircularPatternFeatureWrapper")
        is_pattern_of_body = circular_pattern_wrapper.is_pattern_of_body()
        count = circular_pattern_wrapper.count()
        angle = circular_pattern_wrapper.angle()
        is_natural = circular_pattern_wrapper.is_natural_axis_direction()
        axis_entity = circular_pattern_wrapper.rotation_axis()
        axis_direction = None
        if axis_entity is None:
            raise ValueError("CircularPattern feature missing axisEntity")

        axis_direction = get_axis_direction_from_metadata(axis_entity)
        axis_origin = get_axis_origin_from_metadata(axis_entity)

        if not check_all(is_pattern_of_body, count, angle, is_natural):
            raise ValueError(
                "CircularPattern feature missing count, angle, or naturalDirection"
            )

        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["CircularPattern"], 0, 0)
        circular_pattern_idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], circular_pattern_idx, 0.0, 0)
        push_kv(
            *self.seq,
            KEY["CIRC_IS_PATTERN_BODY"],
            1 if is_pattern_of_body else 0,
            0.0,
            0,
        )
        push_kv(*self.seq, KEY["CIRC_COUNT"], count.value, 0.0, 0)  # type: ignore
        push_kv(*self.seq, KEY["CIRC_ANGLE"], 0, rnd(angle.value), 1)  # type: ignore
        push_kv(*self.seq, KEY["CIRC_NATURAL_DIR"], 1 if is_natural else 0, 0.0, 0)
        push_kv(*self.seq, KEY["CIRC_AXIS_DIR_X"], 0, rnd(axis_direction[0]), 1)
        push_kv(*self.seq, KEY["CIRC_AXIS_DIR_Y"], 0, rnd(axis_direction[1]), 1)
        push_kv(*self.seq, KEY["CIRC_AXIS_DIR_Z"], 0, rnd(axis_direction[2]), 1)
        push_kv(*self.seq, KEY["CIRC_AXIS_OX"], 0, rnd(axis_origin[0]), 1)
        push_kv(*self.seq, KEY["CIRC_AXIS_OY"], 0, rnd(axis_origin[1]), 1)
        push_kv(*self.seq, KEY["CIRC_AXIS_OZ"], 0, rnd(axis_origin[2]), 1)
        if not is_pattern_of_body:
            feature_names = circular_pattern_wrapper.features_to_pattern()
            if not feature_names:
                raise ValueError("CircularPattern feature missing features to pattern")
            feature_idxs = []
            for fname in feature_names:
                if fname in self.name2idx_map:
                    fidxs = self.name2idx_map[fname]
                    feature_idxs.extend(fidxs)
            for fidx in feature_idxs:
                push_kv(*self.seq, KEY["CIRC_FEATURE_IDX"], fidx, 0.0, 0)
        add_instr_boundary(*self.seq, begin=False)
        return circular_pattern_idx

    @classmethod
    def decode(cls, vec: Dict[str, List]) -> List[Dict[str, Any]]:
        def _rev_map(d: Dict[str, int]) -> Dict[int, str]:
            return {v: k for k, v in d.items()}

        key_ids: List[int] = vec.get("key_ids", [])
        val_ids: List[int] = vec.get("val_ids", [])
        val_floats: List[float] = vec.get("val_floats", [])
        is_numeric: List[int] = vec.get("is_numeric", [])
        vocab = vec.get("vocab", {})
        if not isinstance(vocab, dict):
            vocab = {}

        KEY_MAP = vocab.get("KEY", KEY)
        TYPE_ID_MAP = vocab.get("TYPE_ID", TYPE_ID)
        OP_ID_MAP = vocab.get("OP_ID", OP_ID)
        SHELL_DIR_ID_MAP = vocab.get("SHELL_DIR_ID", SHELL_DIR_ID)
        DIR_ID_MAP = vocab.get("DIR_ID", DIR_ID)
        EXTENT_ID_MAP = vocab.get("EXTENT_ID", EXTENT_ID)
        CHAMFER_TYPE_ID_MAP = vocab.get("CHAMFER_TYPE_ID", CHAMFER_TYPE_ID)
        PATTERN_SPACING_TYPE_ID_MAP = vocab.get(
            "PATTERN_SPACING_TYPE_ID", PATTERN_SPACING_TYPE_ID
        )
        SURFACE_TYPE_ID_MAP = vocab.get("SURFACE_TYPE_ID", SURFACE_TYPE_ID)
        EDGE_TYPE_ID_MAP = vocab.get("EDGE_TYPE_ID", EDGE_TYPE_ID)
        ENTITY_ID_MAP = vocab.get("ENTITY_ID", ENTITY_ID)
        PATTERN_COMPUTE_TYPE_ID_MAP = vocab.get(
            "PATTERN_COMPUTE_TYPE_ID", PATTERN_COMPUTE_TYPE_ID
        )

        KEY_R = _rev_map(KEY_MAP)
        TYPE_R = _rev_map(TYPE_ID_MAP)
        OP_R = _rev_map(OP_ID_MAP)
        DIR_ID_R = _rev_map(DIR_ID_MAP) if DIR_ID_MAP else {}
        SHELL_DIR_R = _rev_map(SHELL_DIR_ID_MAP) if SHELL_DIR_ID_MAP else {}
        EXTENT_R = _rev_map(EXTENT_ID_MAP)
        CHAMFER_R = _rev_map(CHAMFER_TYPE_ID_MAP) if CHAMFER_TYPE_ID_MAP else {}
        PATTERN_R = (
            _rev_map(PATTERN_SPACING_TYPE_ID_MAP) if PATTERN_SPACING_TYPE_ID_MAP else {}
        )
        SURFACE_R = _rev_map(SURFACE_TYPE_ID_MAP) if SURFACE_TYPE_ID_MAP else {}
        EDGE_R = _rev_map(EDGE_TYPE_ID_MAP) if EDGE_TYPE_ID_MAP else {}
        ENTITY_R = _rev_map(ENTITY_ID_MAP) if ENTITY_ID_MAP else {}
        PATTERN_COMPUTE_R = (
            _rev_map(PATTERN_COMPUTE_TYPE_ID_MAP)
            if PATTERN_COMPUTE_TYPE_ID_MAP
            else {}
        )

        repeat_keys = {
            "FILLET_EDGE_IDX",
            "CHAMFER_EDGE_IDX",
            "SHELL_FACE_IDX",
            "MIRROR_FEATURE_IDX",
            "RECT_FEATURE_IDX",
            "CIRC_FEATURE_IDX",
        }

        instructions: List[Dict[str, Any]] = []
        cur: Optional[Dict[str, Any]] = None
        for k, vi, vf, num in zip(key_ids, val_ids, val_floats, is_numeric):
            kname = KEY_R.get(k, str(k))
            if kname == "INS_B":
                cur = {"keys": {}, "lists": {}}
                continue
            if kname == "INS_E":
                if cur is not None:
                    t_id = cur["keys"].get("TYPE")
                    if t_id is not None:
                        cur["type_name"] = TYPE_R.get(int(t_id), str(t_id))
                    if "IDX" in cur["keys"]:
                        cur["idx"] = cur["keys"].get("IDX")
                    instructions.append(cur)
                cur = None
                continue
            if cur is None:
                continue
            val: Any = vf if num else vi
            if kname in repeat_keys:
                cur["lists"].setdefault(kname, []).append(val)
            else:
                cur["keys"][kname] = val

        selections: Dict[int, Dict[str, Any]] = {}
        for ins in instructions:
            if ins.get("type_name") != "Selection":
                continue
            keys = ins.get("keys", {})
            idx_val = keys.get("IDX")
            if idx_val is None:
                continue
            sel_idx = int(idx_val)
            ent_type_id = int(keys.get("SELECT_ENTITY", 0))
            ent_type_name = ENTITY_R.get(ent_type_id, "")
            sel: Dict[str, Any] = {"metaType": ent_type_name}
            if ent_type_name == "Face":
                surf_name = SURFACE_R.get(
                    int(keys.get("SURF_TYPE", 9)), "kUnknownSurface"
                )
                sel.update(
                    {
                        "surfaceType": surf_name,
                        "area": float(keys.get("AREA", 0.0)),
                        "centroid": (
                            float(keys.get("FACE_CENTROID_X", 0.0)),
                            float(keys.get("FACE_CENTROID_Y", 0.0)),
                            float(keys.get("FACE_CENTROID_Z", 0.0)),
                        ),
                        "orientation": None,
                    }
                )
            elif ent_type_name == "Edge":
                edge_name = EDGE_R.get(int(keys.get("EDGE_TYPE", 8)), "kUnknownCurve")
                sel.update(
                    {
                        "geometryType": edge_name,
                        "length": float(keys.get("EDGE_LENGTH", 0.0)),
                        "midpoint": (
                            float(keys.get("EDGE_MIDPOINT_X", 0.0)),
                            float(keys.get("EDGE_MIDPOINT_Y", 0.0)),
                            float(keys.get("EDGE_MIDPOINT_Z", 0.0)),
                        ),
                        "endpoints": (
                            (
                                float(keys.get("EDGE_START_X", 0.0)),
                                float(keys.get("EDGE_START_Y", 0.0)),
                                float(keys.get("EDGE_START_Z", 0.0)),
                            ),
                            (
                                float(keys.get("EDGE_END_X", 0.0)),
                                float(keys.get("EDGE_END_Y", 0.0)),
                                float(keys.get("EDGE_END_Z", 0.0)),
                            ),
                        ),
                    }
                )
            selections[sel_idx] = sel

        extents_raw: Dict[int, Dict[str, Any]] = {}
        for ins in instructions:
            if ins.get("type_name") != "Extent":
                continue
            keys = ins.get("keys", {})
            idx_val = keys.get("IDX")
            if idx_val is None:
                continue
            ex_idx = int(idx_val)
            extents_raw[ex_idx] = {
                "DIST": float(keys.get("DIST", 0.0)) if "DIST" in keys else None,
                "ANGLE": float(keys.get("ANGLE", 0.0)) if "ANGLE" in keys else None,
                "DIR": int(keys.get("DIR", 1)) if "DIR" in keys else None,
                "TOFACE_ID": (
                    int(keys.get("TOFACE_ID", 0)) if "TOFACE_ID" in keys else None
                ),
                "FROMFACE_ID": (
                    int(keys.get("FROMFACE_ID", 0)) if "FROMFACE_ID" in keys else None
                ),
                "IS_EXTEND_TO_FACE": (
                    int(keys.get("IS_EXTEND_TO_FACE", 0))
                    if "IS_EXTEND_TO_FACE" in keys
                    else 0
                ),
                "IS_EXTEND_FROM_FACE": (
                    int(keys.get("IS_EXTEND_FROM_FACE", 0))
                    if "IS_EXTEND_FROM_FACE" in keys
                    else 0
                ),
            }

        sketches: Dict[int, Dict[str, Any]] = {}
        cur_sketch: Optional[int] = None
        cur_path: Optional[List[Any]] = None
        for ins in instructions:
            tname = ins.get("type_name")
            keys = ins.get("keys", {})
            if tname == "SketchStart":
                sk_idx = keys.get("IDX")
                if sk_idx is None:
                    continue
                cur_sketch = int(sk_idx)
                sketches[cur_sketch] = {
                    "geom": {
                        "origin": (
                            float(keys.get("OX", 0.0)),
                            float(keys.get("OY", 0.0)),
                            float(keys.get("OZ", 0.0)),
                        ),
                        "normal": (
                            float(keys.get("NX", 0.0)),
                            float(keys.get("NY", 0.0)),
                            float(keys.get("NZ", 0.0)),
                        ),
                        "x": (
                            float(keys.get("XX", 1.0)),
                            float(keys.get("XY", 0.0)),
                            float(keys.get("XZ", 0.0)),
                        ),
                        "y": (
                            float(keys.get("YX", 0.0)),
                            float(keys.get("YY", 1.0)),
                            float(keys.get("YZ", 0.0)),
                        ),
                    },
                    "ref_plane_idx": (
                        int(keys.get("REFER_PLANE_IDX", 0))
                        if "REFER_PLANE_IDX" in keys
                        else None
                    ),
                    "paths": [],
                    "points": [],
                }
            elif tname == "PathStart" and cur_sketch is not None:
                # Start a new path for this sketch
                cur_path = []
            elif tname == "PathEnd" and cur_sketch is not None:
                # End the current path and add it to the sketch
                if cur_path is not None:
                    sketches[cur_sketch]["paths"].append(cur_path)
                cur_path = None
            elif tname in ("Line", "Arc", "Circle") and cur_sketch is not None:
                ent: Dict[str, Any] = {"t": tname, "keys": keys}
                if cur_path is None:
                    raise ValueError("Path entity found without starting a path")
                cur_path.append(ent)
            elif tname == "Point" and cur_sketch is not None:
                sketches[cur_sketch]["points"].append(
                    (float(keys.get("PX", 0.0)), float(keys.get("PY", 0.0)))
                )
            elif tname == "SketchEnd":
                cur_sketch = None

        def _param(name: str, val: float) -> Dict[str, Any]:
            PI = math.pi
            return {
                "name": name,
                "value": float(val),
                # "expression": f"{deg:.6f} deg" if is_angle else f"{val:.6f}",
                # Expression is not used currently
                "value_type": "kUnitless",
            }

        def _make_extent(ex_idx: int, type_name: str) -> Dict[str, Any]:
            raw = extents_raw.get(ex_idx, {})
            dir_name = (
                DIR_ID_R.get(int(raw.get("DIR", 1)), "kPositiveExtentDirection")
                if raw.get("DIR") is not None
                else None
            )
            if type_name == "kDistanceExtent":
                dist = raw.get("DIST", 0.0) or 0.0
                return {
                    "type": "DistanceExtent",
                    "distance": _param("Distance", dist),
                    "direction": dir_name,
                }
            if type_name == "kAngleExtent":
                ang = raw.get("ANGLE", 0.0) or 0.0
                return {
                    "type": "AngleExtent",
                    "angle": _param("Angle", ang),
                    "direction": dir_name,
                }
            if type_name == "kToNextExtent":
                return {"type": "ToNextExtent", "direction": dir_name}
            if type_name == "kThroughAllExtent":
                return {"type": "ThroughAllExtent", "direction": dir_name}
            if type_name == "kFullSweepExtent":
                return {"type": "FullSweepExtent"}
            if type_name == "kToExtent":
                to_id = raw.get("TOFACE_ID")
                return {
                    "type": "ToExtent",
                    "toEntity": selections.get(int(to_id), {}) if to_id else {},
                    "direction": dir_name,
                    "extendToFace": bool(raw.get("IS_EXTEND_TO_FACE", 0)),
                }
            if type_name == "kFromToExtent":
                from_id = raw.get("FROMFACE_ID")
                to_id = raw.get("TOFACE_ID")
                return {
                    "type": "FromToExtent",
                    "fromFace": selections.get(int(from_id), {}) if from_id else {},
                    "toFace": selections.get(int(to_id), {}) if to_id else {},
                    "isFromFaceWorkPlane": False,
                    "isToFaceWorkPlane": False,
                    "extendFromFace": bool(raw.get("IS_EXTEND_FROM_FACE", 0)),
                    "extendToFace": bool(raw.get("IS_EXTEND_TO_FACE", 0)),
                }
            return {"type": type_name}

        def _make_plane_geom(sk: Dict[str, Any]) -> Dict[str, Any]:
            geom = sk.get("geom", {})
            o = geom.get("origin", (0.0, 0.0, 0.0))
            n = geom.get("normal", (0.0, 0.0, 1.0))
            ax = geom.get("x", (1.0, 0.0, 0.0))
            ay = geom.get("y", (0.0, 1.0, 0.0))
            plane = {
                "geometry": {
                    "origin": {"x": o[0], "y": o[1], "z": o[2]},
                    "normal": {"x": n[0], "y": n[1], "z": n[2]},
                    "axis_x": {"x": ax[0], "y": ax[1], "z": ax[2]},
                    "axis_y": {"x": ay[0], "y": ay[1], "z": ay[2]},
                }
            }
            ref_idx_val = sk.get("ref_plane_idx")
            if ref_idx_val is not None:
                plane["index"] = selections.get(int(ref_idx_val), {})
            return plane
        
        def _make_paths(sk: Dict[str, Any]) -> List[Dict[str, Any]]:
            profile_paths = []
            for path in sk.get("paths", []):
                path_entities: List[Dict[str, Any]] = []
                for ent in path:
                    ekeys = ent.get("keys", {})
                    if ent.get("t") == "Line":
                        path_entities.append(
                            {
                                "CurveType": "kLineSegmentCurve2d",
                            "StartSketchPoint": {
                                "x": float(ekeys.get("SPX", 0.0)),
                                "y": float(ekeys.get("SPY", 0.0)),
                            },
                            "EndSketchPoint": {
                                "x": float(ekeys.get("EPX", 0.0)),
                                "y": float(ekeys.get("EPY", 0.0)),
                            },
                        }
                    )
                    elif ent.get("t") == "Circle":
                        path_entities.append(
                            {
                                "CurveType": "kCircleCurve2d",
                                "Curve": {
                                    "center": {
                                        "x": float(ekeys.get("CX", 0.0)),
                                        "y": float(ekeys.get("CY", 0.0)),
                                    },
                                    "radius": float(ekeys.get("R", 0.0)),
                                },
                            }
                        )
                    elif ent.get("t") == "Arc":
                        cx = float(ekeys.get("CX", 0.0))
                        cy = float(ekeys.get("CY", 0.0))
                        r = float(ekeys.get("R", 0.0))
                        sa = float(ekeys.get("SA", 0.0))
                        sw = float(ekeys.get("SW", 0.0))
                        sp = {}
                        sp["x"] = float(ekeys.get("SPX", 0.0))
                        sp["y"] = float(ekeys.get("SPY", 0.0))
                        ep = {}
                        ep["x"] = float(ekeys.get("EPX", 0.0))
                        ep["y"] = float(ekeys.get("EPY", 0.0))
                        path_entities.append(
                            {
                                "CurveType": "kCircularArcCurve2d",
                                "Curve": {
                                    "center": {"x": cx, "y": cy},
                                    "radius": r,
                                    "startAngle": sa,
                                    "sweepAngle": sw,
                                },
                                "StartSketchPoint": sp,
                                "EndSketchPoint": ep,
                            }
                        )
                profile_paths.append({"PathEntities": path_entities})

            return profile_paths
        
        def _make_profile(sketch_idx: int) -> Dict[str, Any]:
            sk = sketches.get(int(sketch_idx), None)
            if sk is None:
                return {}
            profile_paths = _make_paths(sk)
 
            profile = {
                "SketchPlane": _make_plane_geom(sk),
                "ProfilePaths": profile_paths,
            }
            return profile

        features: List[Dict[str, Any]] = []
        idx_to_name: Dict[int, str] = {}

        def _default_name(prefix: str, idx_val: Optional[int]) -> str:
            if idx_val is None:
                return f"{prefix}_{len(features)+1}"
            return f"{prefix}_{idx_val}"

        for ins in instructions:
            tname = ins.get("type_name")
            keys = ins.get("keys", {})
            lists = ins.get("lists", {})
            idx_val = ins.get("idx")

            if tname == "Extrude":
                parent = int(float(keys.get("PARENT", 0))) if "PARENT" in keys else 0
                prof = _make_profile(parent)
                ext_type_name = EXTENT_R.get(
                    int(keys.get("EXTENT_ONE_TYPE", 0)), "kDistanceExtent"
                )
                ext_idx = int(keys.get("EXTENT_ONE", 0)) if "EXTENT_ONE" in keys else 0
                extent = _make_extent(ext_idx, ext_type_name)
                feat: Dict[str, Any] = {
                    "type": "ExtrudeFeature",
                    "name": _default_name("Extrude", idx_val),
                    "operation": OP_R.get(int(keys.get("OP", 0)), "kJoinOperation"),
                    "extentType": ext_type_name,
                    "extent": extent,
                    "isTwoDirectional": bool(int(keys.get("ISTWO_DIRECTIONAL", 0))),
                    "profile": prof,
                }
                if feat["isTwoDirectional"]:
                    ext_two_idx = (
                        int(keys.get("EXTENT_TWO", 0)) if "EXTENT_TWO" in keys else 0
                    )
                    ext_two_type = EXTENT_R.get(
                        int(keys.get("EXTENT_TWO_TYPE", 0)), "kDistanceExtent"
                    )
                    feat["extentTwoType"] = ext_two_type
                    feat["extentTwo"] = _make_extent(ext_two_idx, ext_two_type)
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Revolve":
                parent = int(float(keys.get("PARENT", 0))) if "PARENT" in keys else 0
                prof = _make_profile(parent)
                ext_type_name = EXTENT_R.get(
                    int(keys.get("EXTENT_ONE_TYPE", 0)), "kAngleExtent"
                )
                ext_idx = int(keys.get("EXTENT_ONE", 0)) if "EXTENT_ONE" in keys else 0
                axis_entity = {
                    "metaType": "AxisEntity",
                    "axisInfo": {
                    "start_point": {
                        "x": float(keys.get("AXIS_X", 0.0)),
                        "y": float(keys.get("AXIS_Y", 0.0)),
                        "z": float(keys.get("AXIS_Z", 0.0)),
                    },
                    "direction": {
                        "x": float(keys.get("AXIS_DIR_X", 0.0)),
                        "y": float(keys.get("AXIS_DIR_Y", 0.0)),
                        "z": float(keys.get("AXIS_DIR_Z", 0.0)),
                    },
                    },
                    "index": None,
                }
                feat = {
                    "type": "RevolveFeature",
                    "name": _default_name("Revolve", idx_val),
                    "operation": OP_R.get(int(keys.get("OP", 0)), "kJoinOperation"),
                    "extentType": ext_type_name,
                    "extent": _make_extent(ext_idx, ext_type_name),
                    "isTwoDirectional": bool(int(keys.get("ISTWO_DIRECTIONAL", 0))),
                    "axisEntity": axis_entity,
                    "profile": prof,
                }
                if feat["isTwoDirectional"]:
                    ext_two_idx = (
                        int(keys.get("EXTENT_TWO", 0)) if "EXTENT_TWO" in keys else 0
                    )
                    ext_two_type = EXTENT_R.get(
                        int(keys.get("EXTENT_TWO_TYPE", 0)), "kAngleExtent"
                    )
                    feat["extentTwoType"] = ext_two_type
                    feat["extentTwo"] = _make_extent(ext_two_idx, ext_two_type)
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Fillet":
                radius = float(keys.get("RADIUS", 0.0))
                edge_ids = lists.get("FILLET_EDGE_IDX", [])
                edges = [selections.get(int(eid), {}) for eid in edge_ids]
                feat = {
                    "type": "FilletFeature",
                    "name": _default_name("Fillet", idx_val),
                    "edgeSets": [
                        {
                            "radius": _param("Radius", radius),
                            "edges": edges,
                        }
                    ],
                }
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Chamfer":
                c_type = CHAMFER_R.get(int(keys.get("CHAMFER_TYPE", 0)), "kDistance")
                edge_ids = lists.get("CHAMFER_EDGE_IDX", [])
                edges = [selections.get(int(eid), {}) for eid in edge_ids]
                feat = {
                    "type": "ChamferFeature",
                    "name": _default_name("Chamfer", idx_val),
                    "chamferType": c_type,
                    "edges": edges,
                }
                if c_type == "kTwoDistances":
                    feat["distanceOne"] = _param(
                        "DistanceOne", float(keys.get("CHAMFER_DIST_A", 0.0))
                    )
                    feat["distanceTwo"] = _param(
                        "DistanceTwo", float(keys.get("CHAMFER_DIST_B", 0.0))
                    )
                    face_id = keys.get("CHAMFER_FACE_IDX")
                    feat["face"] = selections.get(int(face_id), {}) if face_id else {}
                elif c_type == "kDistanceAndAngle":
                    feat["distance"] = _param(
                        "Distance", float(keys.get("CHAMFER_DIST_A", 0.0))
                    )
                    feat["angle"] = _param(
                        "Angle", float(keys.get("CHAMFER_ANGLE", 0.0))
                    )
                    face_id = keys.get("CHAMFER_FACE_IDX")
                    feat["face"] = selections.get(int(face_id), {}) if face_id else {}
                else:  # kDistance
                    feat["distance"] = _param(
                        "Distance", float(keys.get("CHAMFER_DIST_A", 0.0))
                    )
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Hole":
                parent = int(float(keys.get("PARENT", 0))) if "PARENT" in keys else 0
                sk = sketches.get(parent, {})
                plane = _make_plane_geom(sk) if sk else {}
                hole_points = [{"x": p[0], "y": p[1]} for p in sk.get("points", [])]
                ext_idx = (
                    int(keys.get("HOLE_EXTENT", 0)) if "HOLE_EXTENT" in keys else 0
                )
                raw_ext = extents_raw.get(ext_idx, {})
                # Infer extent type
                if raw_ext.get("DIST") not in (None, 0):
                    extent_type = "kDistanceExtent"
                else:
                    extent_type = "kThroughAllExtent"
                extent_obj = _make_extent(ext_idx, extent_type)
                feat = {
                    "type": "HoleFeature",
                    "name": _default_name("Hole", idx_val),
                    "holeType": "kDrilledHole",
                    "extentType": extent_type,
                    "extent": extent_obj,
                    "isFlatBottomed": bool(int(keys.get("IS_FLAT_BOTTOM", 0))),
                    "sketchPlane": plane,
                    "holeCenterPoints": hole_points,
                    "holeDiameter": _param(
                        "Diameter", float(keys.get("DIAMETER", 0.0))
                    ),
                    "depth": float(keys.get("DEPTH", 0.0)),
                }
                if not feat["isFlatBottomed"] and "BOTTOM_TIP_ANGLE" in keys:
                    feat["bottomTipAngle"] = _param(
                        "BottomTipAngle", float(keys.get("BOTTOM_TIP_ANGLE", 0.0))
                    )
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Shell":
                face_ids = lists.get("SHELL_FACE_IDX", [])
                faces = [selections.get(int(fid), {}) for fid in face_ids]
                feat = {
                    "type": "ShellFeature",
                    "name": _default_name("Shell", idx_val),
                    "thickness": _param(
                        "Thickness", float(keys.get("SHELL_THICKNESS", 0.0))
                    ),
                    "direction": SHELL_DIR_R.get(
                        int(keys.get("SHELL_DIRECTION", 1)), "kPositiveExtentDirection"
                    ),
                    "inputFaces": faces,
                }
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "Mirror":
                is_body = bool(int(keys.get("IS_MIRROR_BODY", 0)))
                if "MIRROR_PLANE_FACE_IDX" in keys:
                    face_id = int(keys.get("MIRROR_PLANE_FACE_IDX", 0))
                    plane = selections.get(face_id, {})
                else:
                    
                    plane = PlaneEntityWrapper.generate_plane_metadata(
                        origin=Point3D(
                            float(keys.get("MIRROR_PLANE_OX", 0.0)),
                            float(keys.get("MIRROR_PLANE_OY", 0.0)),
                            float(keys.get("MIRROR_PLANE_OZ", 0.0)),
                        ),
                        normal=Point3D(
                            float(keys.get("MIRROR_PLANE_NX", 0.0)),
                            float(keys.get("MIRROR_PLANE_NY", 0.0)),
                            float(keys.get("MIRROR_PLANE_NZ", 0.0)),
                        ),
                        axis_x=Point3D(1.0, 0.0, 0.0),
                        axis_y=Point3D(0.0, 1.0, 0.0),
                    )
                compute_type = PATTERN_COMPUTE_R.get(
                    int(keys.get("MIRROR_COMPUTE_TYPE", 0)), "kIdenticalCompute"
                )
                feat = {
                    "type": "MirrorFeature",
                    "name": _default_name("Mirror", idx_val),
                    "isMirrorBody": is_body,
                    "mirrorPlane": plane,
                    "isMirrorPlaneFace": "MIRROR_PLANE_FACE_IDX" in keys,
                    "computeType": compute_type,
                }
                if is_body:
                    feat["removeOriginal"] = bool(int(keys.get("REMOVE_ORIGINAL", 0)))
                    feat["operation"] = OP_R.get(
                        int(keys.get("MIRROR_OP", 0)), "kJoinOperation"
                    )
                else:
                    feat["featuresToMirror"] = [
                        idx_to_name.get(int(fid), f"Feature_{fid}")
                        for fid in lists.get("MIRROR_FEATURE_IDX", [])
                    ]
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]

            elif tname == "RectPattern":
                is_body = bool(int(keys.get("RECT_IS_PATTERN_BODY", 0)))
                x_count_val = keys.get(
                    "RECT_X_COUNT", keys.get("RECT_PATTERN_X_COUNT", 1)
                )
                x_spacing_val = keys.get(
                    "RECT_X_SPACING", keys.get("RECT_PATTERN_X_SPACING", 0.0)
                )
                spacing_type_id = int(
                    keys.get(
                        "RECT_X_SPACING_TYPE", keys.get("RECT_PATTERN_SPACING_TYPE", 0)
                    )
                )
                spacing_type = PATTERN_R.get(spacing_type_id, "kDefault")
                x_dir = (
                    float(keys.get("RECT_X_DIR_X", keys.get("RECT_DIR_X", 1.0))),
                    float(keys.get("RECT_X_DIR_Y", keys.get("RECT_DIR_Y", 0.0))),
                    float(keys.get("RECT_X_DIR_Z", keys.get("RECT_DIR_Z", 0.0))),
                )
                x_dir_meta = AxisEntityWrapper.generate_axis_metadata(
                    start_point=Point3D(0.0, 0.0, 0.0), # TODO: origin point?
                    direction=Point3D(x_dir[0], x_dir[1], x_dir[2]),
                )
                feat = {
                    "type": "RectangularPatternFeature",
                    "name": _default_name("RectPattern", idx_val),
                    "isPatternOfBody": is_body,
                    "xCount": _param("XCount", float(x_count_val)),
                    "xSpacing": _param("XSpacing", float(x_spacing_val)),
                    "xNaturalDirection": bool(
                        int(
                            keys.get(
                                "RECT_X_NATURAL_DIR",
                                keys.get("RECT_IS_NATURAL_X_DIR", 1),
                            )
                        )
                    ),
                    "xSpacingType": spacing_type,
                    "xDirectionEntity": x_dir_meta,
                }
                if not is_body:
                    feat["featuresToPattern"] = [
                        idx_to_name.get(int(fid), f"Feature_{fid}")
                        for fid in lists.get("RECT_FEATURE_IDX", [])
                    ]
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]
            elif tname == "CircularPattern":
                is_body = bool(int(keys.get("CIRC_IS_PATTERN_BODY", 0)))
                axis_dir = (
                    float(keys.get("CIRC_AXIS_DIR_X", 0.0)),
                    float(keys.get("CIRC_AXIS_DIR_Y", 0.0)),
                    float(keys.get("CIRC_AXIS_DIR_Z", 0.0)),
                )
                axis_origin = (
                    float(keys.get("CIRC_AXIS_OX", 0.0)),
                    float(keys.get("CIRC_AXIS_OY", 0.0)),
                    float(keys.get("CIRC_AXIS_OZ", 0.0)),
                )
                axis_meta = AxisEntityWrapper.generate_axis_metadata(
                    start_point=Point3D(
                        axis_origin[0], axis_origin[1], axis_origin[2]
                    ),
                    direction=Point3D(axis_dir[0], axis_dir[1], axis_dir[2]),
                )
                feat = {
                    "type": "CircularPatternFeature",
                    "name": _default_name("CircPattern", idx_val),
                    "isPatternOfBody": is_body,
                    "count": _param("Count", float(keys.get("CIRC_COUNT", 1))),
                    "angle": _param("Angle", float(keys.get("CIRC_ANGLE", 0.0))),
                    "isNaturalAxisDirection": bool(
                        int(keys.get("CIRC_NATURAL_DIR", 1))
                    ),
                    "rotationAxis": axis_meta,
                }
                if not is_body:
                    feat["featuresToPattern"] = [
                        idx_to_name.get(int(fid), f"Feature_{fid}")
                        for fid in lists.get("CIRC_FEATURE_IDX", [])
                    ]
                features.append(feat)
                if idx_val is not None:
                    idx_to_name[int(idx_val)] = feat["name"]



            else:
                continue
        return features


def main():
    raise RuntimeError("Use json2vec.py for CLI entry; FeatureEncoder is library-only")

