import json
import math
import argparse
from typing import Any, Dict, List, Tuple

from feature_wrappers import ExtrudeFeatureWrapper, FeatureWrapperFactory, RevolveFeatureWrapper
from inventor_utils.extent_types import ExtentFactory, ExtentWrapper
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

def check(vlaue:str|dict|None)->bool:
    if vlaue is None:
        return False
    if isinstance(vlaue,str) and vlaue.strip()=="":
        return False
    if isinstance(vlaue,dict) and len(vlaue)==0:
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


def add_selection(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    meta_data: dict,
    is_face: bool,
) -> int:
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Selection"], 0.0, 0)
    push_kv(*seq, KEY["IDX"], idx, 0.0, 0)
    if is_face:
        push_kv(*seq, KEY["SELECT_ENTITY"], ENTITY_ID["Face"], 0.0, 0)
        face_type = meta_data.get("surfaceType", "kUnknownSurface")
        push_kv(
            *seq,
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
    return idx + 1
    pass


def add_instr_boundary(seq_keys, seq_val_ids, seq_val_floats, seq_is_num, begin=True):
    if begin:
        push_kv(
            seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_B"], 0, 0.0, 0
        )
    else:
        push_kv(
            seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_E"], 0, 0.0, 0
        )


# 3) 编码各指令
def add_sketch_start(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    sketch_plane: Dict[str, Any],
) -> int:
    sp = sketch_plane or {}
    index = sp.get("index")


    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["SketchStart"], 0.0, 0)
    push_kv(*seq, KEY["IDX"], idx, 0.0, 0)
    idx+=1
    if index:
        select_idx = idx
        idx = add_selection(seq, select_idx, index, is_face=True)
        push_kv(*seq,KEY['PARENT'],select_idx,0.0,0)
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
            push_kv(*seq, KEY[k], 0, rnd(v), 1)
    add_instr_boundary(*seq, begin=False)
    return idx 


def add_sketch_end(
    seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int
) -> int:
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["SketchEnd"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], parent_idx,0.0, 0)
    add_instr_boundary(*seq, begin=False)
    return idx 


def add_line(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    parent_idx: int,
    ent: Dict[str, Any],
) -> int:
    sp = ent.get("StartSketchPoint", {})
    ep = ent.get("EndSketchPoint", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Line"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], parent_idx,0.0, 0)
    push_kv(*seq, KEY["SPX"], 0, rnd(sp.get("x", 0)), 1)
    push_kv(*seq, KEY["SPY"], 0, rnd(sp.get("y", 0)), 1)
    push_kv(*seq, KEY["EPX"], 0, rnd(ep.get("x", 0)), 1)
    push_kv(*seq, KEY["EPY"], 0, rnd(ep.get("y", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx


def add_arc(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    parent_idx: int,
    ent: Dict[str, Any],
) -> int:
    curve = ent.get("Curve") or {}
    c = curve.get("center", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Arc"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], parent_idx,0.0, 0)
    push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
    push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
    push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
    push_kv(*seq, KEY["SA"], 0, rnd(curve.get("startAngle", 0)), 1)
    push_kv(*seq, KEY["SW"], 0, rnd(curve.get("sweepAngle", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx


def add_circle(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    parent_idx: int,
    ent: Dict[str, Any],
) -> int:
    curve = ent.get("Curve") or {}
    c = curve.get("center", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Circle"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], parent_idx,0.0, 0)
    push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
    push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
    push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx


def encode_profile(seq, idx: int, feat: Dict[str, Any]) -> Tuple[int, int]:
    profile = feat.get("profile") or {}
    sketch_plane = profile.get("SketchPlane") or {}

    sketch_idx = idx
    idx = add_sketch_start(seq, idx, sketch_plane)
    for path in profile.get("ProfilePaths", []):
        for ent in path.get("PathEntities", []):
            ctype = ent.get("CurveType")
            if ctype == "kLineSegmentCurve2d":
                idx = add_line(seq, idx, sketch_idx, ent)
            elif ctype == "kCircularArcCurve2d":
                idx = add_arc(seq, idx, sketch_idx, ent)
            elif ctype == "kCircleCurve2d":
                idx = add_circle(seq, idx, sketch_idx, ent)
    idx = add_sketch_end(seq, idx, parent_idx=sketch_idx)
    return idx, sketch_idx


def add_extent(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    extent: Dict[str, Any] | ExtentWrapper,
) -> int:
    extent_idx = idx
    idx += 1
    if isinstance(extent, dict):
        extent_wrapper = ExtentFactory.from_dict(extent)
    else:
        extent_wrapper = extent
    if extent_wrapper is None:
        raise ValueError("Unsupported extent type")
    kvs = extent_wrapper.extract_kvs()
    for ent_key, ent_meta in kvs.get("entities", {}).items():
        if ent_key not in KEY.values():
            raise ValueError(f"Unknown entity key: {ent_key}")
        ent_meta_type = ent_meta.get("metaType")
        if ent_meta_type is not "Face" and ent_meta_type is not "Edge":
            raise ValueError(f"Unsupported entity type for extent selection: {ent_meta_type}")
        selection_idx = idx
        idx = add_selection(
            seq,
            selection_idx,
            ent_meta,
            is_face=(ent_meta.get("metaType") == "Face"),
        )
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Extent"], 0.0, 0)
    push_kv(*seq, KEY["IDX"], extent_idx, 0.0, 0)
    for k, v in kvs.get("nums", {}).items():
        if k not in KEY.values():
            raise ValueError(f"Unknown numeric key: {k}")
        push_kv(*seq, k, 0, rnd(v), 1)
    for k, v in kvs.get("enums", {}).items():
        if k not in KEY.values():
            raise ValueError(f"Unknown enum key: {k}")
        push_kv(*seq, k, int(v), 0.0, 0)

    for k, v in kvs.get("entity_indices", {}).items():
        if k not in KEY.values():
            raise ValueError(f"Unknown entity index key: {k}")
        push_kv(*seq, k, v, 0.0, 0)
    
    add_instr_boundary(*seq, begin=False)
    return idx
    

def add_extrude(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    sketch_idx: int,
    feat: Dict[str, Any],
) -> int:
    extrude_idx = idx # reserve extrude feature idx
    idx += 1
    extrude_wrapper = FeatureWrapperFactory.from_dict(feat)
    if not isinstance(extrude_wrapper, ExtrudeFeatureWrapper):
        raise ValueError("Feature is not an ExtrudeFeatureWrapper")
    operation =  extrude_wrapper.operation()
    extent_type = extrude_wrapper.extent_type()
    if not check(operation) or not check(extent_type):
        raise ValueError("Extrude feature missing operation or extentType")
    extent = extrude_wrapper.extent()
    if extent is None:
        raise ValueError("Extrude feature missing extent")
    extent_one_idx = idx
    idx = add_extent(seq, extent_one_idx, extent)
    is_two_direction = extrude_wrapper.is_two_directional()
    if is_two_direction:
        extent_two = extrude_wrapper.extent_two()
        extent_two_type = extrude_wrapper.extent_two_type()
        if extent_two is None or not check(extent_two_type):
            raise ValueError("Extrude feature missing extentTwo or extentTwoType for two-directional extrude")
        extent_two_idx = idx
        idx = add_extent(seq, extent_two_idx, extent_two)
    else:
        extent_two = None
        extent_two_type = ""
        extent_two_idx = None


    add_instr_boundary(*seq, begin=True)

    push_kv(*seq, KEY["TYPE"], TYPE_ID["Extrude"], 0.0, 0)
    push_kv(*seq, KEY["IDX"], extrude_idx, 0.0, 0)
    # idx += 1  已经在上面预留的时候加1了
    push_kv(*seq, KEY["PARENT"], 0, float(sketch_idx), 1)
    push_kv(*seq, KEY["OP"], OP_ID.get(operation, 0), 0.0, 0)
    push_kv(*seq, KEY["EXTENT_ONE_TYPE"], EXTENT_ID.get(extent_type, 0), 0.0, 0)
    push_kv(*seq, KEY["EXTENT_ONE"], extent_one_idx, 0.0,0)
    push_kv(*seq, KEY['ISTWO_DIRECTIONAL'],1 if is_two_direction else 0,0.0,0)
    if is_two_direction and extent_two is not None and  extent_two_idx is not None:
        push_kv(*seq, KEY["EXTENT_TWO_TYPE"], EXTENT_ID.get(extent_two_type, 0), 0.0, 0)
        push_kv(*seq, KEY["EXTENT_TWO"], extent_two_idx, 0.0,0)
    add_instr_boundary(*seq, begin=False)
    return idx


def add_revolve(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    sketch_idx: int,
    feat: Dict[str, Any],
) -> int:
    revolve_wrapper = FeatureWrapperFactory.from_dict(feat)
    if not isinstance(revolve_wrapper, RevolveFeatureWrapper):
        raise ValueError("Feature is not a RevolveFeatureWrapper")
    operation =  revolve_wrapper.operation()
    axis_entity = revolve_wrapper.axis_entity()
    if not check(operation) or axis_entity is None:
        raise ValueError("Revolve feature missing operation or axisEntity")
    start_point = axis_entity.start_point 
    direction = axis_entity.direction

    

    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Revolve"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"],sketch_idx,0.0, 0)
    push_kv(*seq, KEY["OP"], OP_ID.get(operation, 0), 0.0, 0)
    ang = f(feat, "angle", 2 * math.pi)
    if abs(ang) > 2 * math.pi + 1e-6:
        ang = math.radians(ang)
    push_kv(*seq, KEY["DIST"], 0, rnd(ang), 1)  # 用 DIST 作为 angle 槽（或新增 ANG 键）
    push_kv(*seq, KEY["DIR"], DIR_ID.get(feat.get("direction"), 1), 0.0, 0)
    add_instr_boundary(*seq, begin=False)
    return idx + 1


def add_fillet(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    parent_idx: int,
    feat: Dict[str, Any],
) -> int:
    for es in feat.get("edgeSets", []):
        rad = f(es, "radius", 0.0)
        for e in es.get("edges", []):
            add_instr_boundary(*seq, begin=True)
            push_kv(*seq, KEY["TYPE"], TYPE_ID["Fillet"], 0.0, 0)
            push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
            push_kv(*seq, KEY["R"], 0, rnd(rad), 1)
            push_kv(*seq, KEY["SBR"], 0, float(e.get("surfaceBodyRank", 0)), 1)
            push_kv(*seq, KEY["ER"], 0, float(e.get("edgeRank", 0)), 1)
            add_instr_boundary(*seq, begin=False)
            idx += 1
    return idx


def add_chamfer(
    seq: Tuple[List[int], List[int], List[float], List[int]],
    idx: int,
    parent_idx: int,
    feat: Dict[str, Any],
) -> int:
    d1 = f(feat, "distance", 0.0)
    for e in feat.get("edges", []):
        add_instr_boundary(*seq, begin=True)
        push_kv(*seq, KEY["TYPE"], TYPE_ID["Chamfer"], 0.0, 0)
        push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
        push_kv(*seq, KEY["DIST"], 0, rnd(d1), 1)
        push_kv(*seq, KEY["SBR"], 0, float(e.get("surfaceBodyRank", 0)), 1)
        push_kv(*seq, KEY["ER"], 0, float(e.get("edgeRank", 0)), 1)
        add_instr_boundary(*seq, begin=False)
        idx += 1
    return idx


def encode(features: List[Dict[str, Any]]) -> Dict[str, List]:
    seq_keys: List[int] = [KEY["BOS"]]
    seq_val_ids: List[int] = [0]
    seq_val_floats: List[float] = [0.0]
    seq_is_num: List[int] = [0]

    seq = (seq_keys, seq_val_ids, seq_val_floats, seq_is_num)
    idx = 1
    last_solid_idx = 0

    for feat in features:
        t = feat.get("type")
        if t in ("ExtrudeFeature", "RevolveFeature", "HoleFeature"):
            idx, sketch_idx = encode_profile(seq, idx, feat)
            if t == "ExtrudeFeature":
                idx = add_extrude(seq, idx, sketch_idx, feat)
                last_solid_idx = idx - 1
            elif t == "RevolveFeature":
                idx = add_revolve(seq, idx, sketch_idx, feat)
                last_solid_idx = idx - 1
        elif t == "FilletFeature":
            idx = add_fillet(seq, idx, last_solid_idx, feat)
        elif t == "ChamferFeature":
            idx = add_chamfer(seq, idx, last_solid_idx, feat)
        else:
            # 其他特征可在此扩展
            continue

    seq_keys.append(KEY["EOS"])
    seq_val_ids.append(0)
    seq_val_floats.append(0.0)
    seq_is_num.append(0)
    return {
        "key_ids": seq_keys,
        "val_ids": seq_val_ids,  # 仅离散值使用
        "val_floats": seq_val_floats,  # 仅连续值使用
        "is_numeric": seq_is_num,  # 1=连续值, 0=离散值
        "vocab": {
            "KEY": KEY,
            "TYPE_ID": TYPE_ID,
            "OP_ID": OP_ID,
            "DIR_ID": DIR_ID,
            "EXTENT_ID": EXTENT_ID,
        },
    }  # type: ignore


def main():
    ap = argparse.ArgumentParser("encode_kv")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        feats = json.load(f)
    payload = encode(feats)

    with open(args.outp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if args.pretty else None)
    print(f"wrote KV sequence to {args.outp} (len={len(payload['key_ids'])})")


if __name__ == "__main__":
    main()
