import json
import math
import argparse
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
from inventor_utils.geometry import PlaneEntityWrapper, Point3D
from inventor_utils.metadata import get_axis_direction_from_metadata, get_axis_origin_from_metadata, get_plane_normal_from_metadata
from marco import *


# 2) 工具
def f(d: Dict, key: str, default=0.0) -> float:
    v = d.get(key)
    if isinstance(v, dict):
        return float(v.get("value", default))
    return float(v) if v is not None else float(default)


def rnd(x: float, tol: float = 1e-6) -> float:
    # 稳定四舍五入，避免训练抖动
    if x is None:
        return 0.0
    try:
        return round(float(x), max(0, int(-math.log10(tol))))
    except Exception:
        return 0.0

#变长参数
def check_all( *values: Optional[Any] ) -> bool:
    for v in values:
        if not check(v):
            return False
    return True

def check(vlaue: Optional[ Any] ) -> bool:
    if vlaue is None:
        return False
    if isinstance(vlaue, str) and vlaue.strip() == "":
        return False
    if isinstance(vlaue, dict) and len(vlaue) == 0:
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
            feat_idx =[]
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
                continue
            elif t == "ShellFeature":
                shell_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(shell_wrapper, ShellFeatureWrapper):
                    raise ValueError("Feature is not a ShellFeatureWrapper")
                feat_idx.append(self.add_shell(shell_wrapper))
                continue
            elif t == "MirrorFeature":
                mirror_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(mirror_wrapper, MirrorFeatureWrapper):
                    raise ValueError("Feature is not a MirrorFeatureWrapper")
                feat_idx.append(self.add_mirror(mirror_wrapper))
                # MirrorFeature 可在此扩展
                continue
            elif t == "RectangularPatternFeature":
                rect_pattern_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(rect_pattern_wrapper, RectangularPatternFeatureWrapper):
                    raise ValueError("Feature is not a RectangularPatternFeatureWrapper")
                feat_idx.append(self.add_rectangular_pattern(rect_pattern_wrapper))
                continue
            elif t == "CircularPatternFeature":
                circ_pattern_wrapper = FeatureWrapperFactory.from_dict(feat)
                if not isinstance(circ_pattern_wrapper, CircularPatternFeatureWrapper):
                    raise ValueError("Feature is not a CircularPatternFeatureWrapper")
                feat_idx.append(self.add_circular_pattern(circ_pattern_wrapper))
                continue
            else:
                raise ValueError(f"Unsupported feature type: {t}")
                continue
            
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
            for ent in path.get("PathEntities", []):
                ctype = ent.get("CurveType")
                if ctype == "kLineSegmentCurve2d":
                    idx = self.add_line(ent)
                elif ctype == "kCircularArcCurve2d":
                    idx = self.add_arc(ent)
                elif ctype == "kCircleCurve2d":
                    idx = self.add_circle(ent)
        self.add_sketch_end(sketch_idx)
        return sketch_idx

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
        if index  and ref_plane_idx is not None:
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
    def add_sketch_end(
        self, sketch_idx
    ) :
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
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Arc"], 0.0, 0)
        push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
        push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
        push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
        push_kv(*seq, KEY["SA"], 0, rnd(curve.get("startAngle", 0)), 1)
        push_kv(*seq, KEY["SW"], 0, rnd(curve.get("sweepAngle", 0)), 1)
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
            push_kv(*seq, KEY["EXTENT_TWO_TYPE"], EXTENT_ID.get(extent_two_type, 0), 0.0, 0)
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
            push_kv(*seq, KEY["EXTENT_TWO_TYPE"], EXTENT_ID.get(extent_two_type, 0), 0.0, 0)
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
        push_kv(*seq, KEY["RADIUS"], 0, rnd(radius), 1)
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
        if chamfer_type == "kDistanceAndAngle"  or chamfer_type == "kTwoDistances":
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
        if is_flat_bottom:
            bottom_tip_angle = hole_wrapper.bottom_tip_angle()
        else:
            bottom_tip_angle = None
        if diameter is None or extent is None or depth is None or (is_flat_bottom and bottom_tip_angle is None):
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
        push_kv(*seq,KEY["DEPTH"], 0, rnd(depth), 1)
        push_kv(*seq,KEY["IS_FLAT_BOTTOM"], 1 if hole_wrapper.is_flat_bottomed() else 0, 0.0, 0)
        if is_flat_bottom and bottom_tip_angle is not None:
            push_kv(*seq,KEY["BOTTOM_TIP_ANGLE"], 0, rnd(bottom_tip_angle.value), 1)
        add_instr_boundary(*seq, begin=False)
        return hole_idx

    def add_shell(self, shell_wrapper)-> int:
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
        push_kv(*seq, KEY["SHELL_DIRECTION"], DIR_ID.get(direction, 0), 0.0, 0)
        for fidx in face_idxs:
            push_kv(*seq, KEY["SHELL_FACE_IDX"], fidx, 0.0, 0)

        return shell_idx
    
    def add_mirror(self,mirror_wrapper) -> int:
        if not isinstance(mirror_wrapper, MirrorFeatureWrapper):
            raise ValueError("Feature is not a MirrorFeatureWrapper")
        is_mirror_body = mirror_wrapper.is_mirror_body()

        mirror_plane = mirror_wrapper.mirror_plane()

        if mirror_plane is None:
            raise ValueError("Mirror feature missing mirror plane")
        mirror_plane_point = None
        mirror_plane_normal = None
        if isinstance(mirror_plane, dict):
            face_meta = mirror_plane
            mirror_plane_normal = Point3D( face_meta['orientation'][0], face_meta['orientation'][1], face_meta['orientation'][2])
            mirror_plane_point = Point3D( face_meta['centroid'][0], face_meta['centroid'][1], face_meta['centroid'][2])
        else:
            geom = mirror_plane.to_dict().get("geometry", {})
            o = geom.get("origin", {})
            n = geom.get("normal", {})
            mirror_plane_point = Point3D(rnd(o.get("x", 0)), rnd(o.get("y", 0)), rnd(o.get("z", 0)))
            mirror_plane_normal = Point3D(rnd(n.get("x", 0)), rnd(n.get("y", 0)), rnd(n.get("z", 0)))


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
        seq = self.seq
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Mirror"], 0, 0)
        mirror_idx = self.reserve_idx()
        push_kv(*seq, KEY["IDX"], mirror_idx, 0.0, 0)
        push_kv(*seq, KEY["IS_MIRROR_BODY"], 1 if is_mirror_body else 0, 0.0, 0)
        if not is_mirror_body:
            for fidx in feature_idxs:
                push_kv(*seq, KEY["MIRROR_FEATURE_IDX"], fidx, 0.0, 0)
        else:
            remove_original = mirror_wrapper.remove_original()
            push_kv(*seq, KEY["REMOVE_ORIGINAL"], 1 if remove_original else 0, 0.0, 0)
        push_kv(*seq, KEY["MIRROR_PLANE_OX"], 0, mirror_plane_point.x, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_OY"], 0, mirror_plane_point.y, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_OZ"], 0, mirror_plane_point.z, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NX"], 0, mirror_plane_normal.x, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NY"], 0, mirror_plane_normal.y, 1)
        push_kv(*seq, KEY["MIRROR_PLANE_NZ"], 0, mirror_plane_normal.z, 1)
        add_instr_boundary(*seq, begin=False)

        return mirror_idx
    
    def add_rectangular_pattern(self, rectangular_pattern_wrapper) -> int:
        if not isinstance(rectangular_pattern_wrapper, RectangularPatternFeatureWrapper):
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
        


        if not check(spacing_type) or x_count is None or x_spacing is None or not check(spacing_type) or  is_natural_x is None or is_pattern_of_body is None:
            raise ValueError("RectangularPattern feature missing xCount, xSpacing, or xSpacingType")
        
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["RectPattern"], 0, 0)
        rectangular_pattern_idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], rectangular_pattern_idx, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_IS_PATTERN_BODY"], 1 if is_pattern_of_body else 0, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_X_COUNT"], x_count.value, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_X_SPACING"], 0, rnd(x_spacing.value), 1)
        push_kv(*self.seq, KEY["RECT_X_NATURAL_DIR"], 1 if is_natural_x else 0, 0.0, 0)
        push_kv(*self.seq, KEY["RECT_X_SPACING_TYPE"], PATTERN_SPACING_TYPE_ID[spacing_type], 0.0, 0) # type: ignore
        push_kv(*self.seq, KEY["RECT_X_DIR_X"], 0, rnd(x_direction[0]), 1)
        push_kv(*self.seq, KEY["RECT_X_DIR_Y"], 0, rnd(x_direction[1]), 1)
        push_kv(*self.seq, KEY["RECT_X_DIR_Z"], 0, rnd(x_direction[2]), 1)
        if not is_pattern_of_body:
            feature_names = rectangular_pattern_wrapper.features_to_pattern()
            if not feature_names:
                raise ValueError("RectangularPattern feature missing features to pattern")
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
            raise ValueError("CircularPattern feature missing count, angle, or naturalDirection")
        
        add_instr_boundary(*self.seq, begin=True)
        push_kv(*self.seq, KEY["TYPE"], TYPE_ID["CircPattern"], 0, 0)
        circular_pattern_idx = self.reserve_idx()
        push_kv(*self.seq, KEY["IDX"], circular_pattern_idx, 0.0, 0)
        push_kv(*self.seq, KEY["CIRC_IS_PATTERN_BODY"], 1 if is_pattern_of_body else 0, 0.0, 0)
        push_kv(*self.seq, KEY["CIRC_COUNT"], count.value, 0.0, 0) # type: ignore
        push_kv(*self.seq, KEY["CIRC_ANGLE"], 0, rnd(angle.value), 1) # type: ignore
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


def main():
    ap = argparse.ArgumentParser("encode_kv")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        feats = json.load(f)
    encoder = FeatureEncoder()

    payload = encoder.encode(feats)

    with open(args.outp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if args.pretty else None)
    print(f"wrote KV sequence to {args.outp} (len={len(payload['key_ids'])})")


if __name__ == "__main__":
    main()