
import json
import math
import argparse
from typing import Any, Dict, List, Tuple

# 1) 词表：键ID与离散值ID
KEY = {
    "BOS": 1, "EOS": 2, "INS_B": 3, "INS_E": 4,
    "TYPE": 10, "IDX": 11, "PARENT": 12, "OP": 13, "DIR": 14, "EXT": 15,
    "OX": 20, "OY": 21, "OZ": 22, "NX": 23, "NY": 24, "NZ": 25,
    "XX": 26, "XY": 27, "XZ": 28, "YX": 29, "YY": 30, "YZ": 31,
    "SPX": 40, "SPY": 41, "EPX": 42, "EPY": 43, "CX": 44, "CY": 45, "R": 46, "SA": 47, "SW": 48,
    "DIST": 49, "DIST2": 50, "SBR": 60, "ER": 61, "FBR": 62, "FR": 63,
}

TYPE_ID = {
    "SketchStart": 1, "Line": 2, "Arc": 3, "Circle": 4, "SketchEnd": 5,
    "Extrude": 10, "Revolve": 11, "Chamfer": 12, "Fillet": 13,
}

OP_ID = {
    "kNewBodyOperation": 0, "kJoinOperation": 1, "kCutOperation": 2, "kIntersectOperation": 3,
}

DIR_ID = {"kPositiveExtentDirection": 1, "kNegativeExtentDirection": -1, "kSymmetricExtentDirection": 0}
EXTENT_ID = {"kDistanceExtent": 0}

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

def push_kv(seq_keys: List[int], seq_val_ids: List[int], seq_val_floats: List[float], seq_is_num: List[int],
            key_id: int, val_id: int = 0, val_float: float = 0.0, is_num: int = 0):
    seq_keys.append(key_id)
    seq_val_ids.append(int(val_id) if not is_num else 0)
    seq_val_floats.append(float(val_float) if is_num else 0.0)
    seq_is_num.append(1 if is_num else 0)

def add_instr_boundary(seq_keys, seq_val_ids, seq_val_floats, seq_is_num, begin=True):
    if begin:
        push_kv(seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_B"], 0, 0.0, 0)
    else:
        push_kv(seq_keys, seq_val_ids, seq_val_floats, seq_is_num, KEY["INS_E"], 0, 0.0, 0)

# 3) 编码各指令
def add_sketch_start(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, sketch_plane: Dict[str, Any]) -> int:
    seq_keys, seq_vids, seq_vfloats, seq_isnum = seq
    add_instr_boundary(*seq, begin=True)
    push_kv(seq_keys,seq_vids,seq_vfloats,seq_isnum, KEY["TYPE"], TYPE_ID["SketchStart"], 0.0, 0)
    push_kv(seq_keys,seq_vids,seq_vfloats,seq_isnum, KEY["IDX"], 0, idx, 1)  # IDX 作为连续/指针值（也可离散化）
    sp = (sketch_plane or {})
    geom = sp.get("geometry")
    index = sp.get("index")
    if geom:
        o = geom.get("origin", {}); n = geom.get("normal", {}); ax = geom.get("axis_x", {}); ay = geom.get("axis_y", {})
        for k, v in (("OX", o.get("x", 0)), ("OY", o.get("y", 0)), ("OZ", o.get("z", 0)),
                     ("NX", n.get("x", 0)), ("NY", n.get("y", 0)), ("NZ", n.get("z", 0)),
                     ("XX", ax.get("x", 0)), ("XY", ax.get("y", 0)), ("XZ", ax.get("z", 0)),
                     ("YX", ay.get("x", 0)), ("YY", ay.get("y", 0)), ("YZ", ay.get("z", 0))):
            push_kv(seq_keys, seq_vids, seq_vfloats, seq_isnum, KEY[k], 0, rnd(v), 1)
    elif index:
        push_kv(*seq, KEY["FBR"], 0, float(index.get("surfaceBodyRank", 0)), 1)
        push_kv(*seq, KEY["FR"], 0, float(index.get("faceRank", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_sketch_end(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int) -> int:
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["SketchEnd"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_line(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int, ent: Dict[str, Any]) -> int:
    sp = ent.get("StartSketchPoint", {}); ep = ent.get("EndSketchPoint", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Line"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
    push_kv(*seq, KEY["SPX"], 0, rnd(sp.get("x", 0)), 1)
    push_kv(*seq, KEY["SPY"], 0, rnd(sp.get("y", 0)), 1)
    push_kv(*seq, KEY["EPX"], 0, rnd(ep.get("x", 0)), 1)
    push_kv(*seq, KEY["EPY"], 0, rnd(ep.get("y", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_arc(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int, ent: Dict[str, Any]) -> int:
    curve = ent.get("Curve") or {}
    c = curve.get("center", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Arc"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
    push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
    push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
    push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
    push_kv(*seq, KEY["SA"], 0, rnd(curve.get("startAngle", 0)), 1)
    push_kv(*seq, KEY["SW"], 0, rnd(curve.get("sweepAngle", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_circle(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int, ent: Dict[str, Any]) -> int:
    curve = ent.get("Curve") or {}
    c = curve.get("center", {})
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Circle"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(parent_idx), 1)
    push_kv(*seq, KEY["CX"], 0, rnd(c.get("x", 0)), 1)
    push_kv(*seq, KEY["CY"], 0, rnd(c.get("y", 0)), 1)
    push_kv(*seq, KEY["R"], 0, rnd(curve.get("radius", 0)), 1)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

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

def add_extrude(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, sketch_idx: int, feat: Dict[str, Any]) -> int:
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Extrude"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(sketch_idx), 1)
    push_kv(*seq, KEY["OP"], OP_ID.get(feat.get("operation"), 0), 0.0, 0)
    push_kv(*seq, KEY["EXT"], EXTENT_ID.get(feat.get("extentType"), 0), 0.0, 0)
    push_kv(*seq, KEY["DIST"], 0, rnd(f(feat, "distance", 0.0)), 1)
    push_kv(*seq, KEY["DIR"], DIR_ID.get(feat.get("direction"), 1), 0.0, 0)
    if feat.get("distanceTwo") is not None:
        push_kv(*seq, KEY["DIST2"], 0, rnd(f(feat, "distanceTwo", 0.0)), 1)
    if feat.get("directionTwo") is not None:
        push_kv(*seq, KEY["DIR"], DIR_ID.get(feat.get("directionTwo"), 1), 0.0, 0)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_revolve(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, sketch_idx: int, feat: Dict[str, Any]) -> int:
    add_instr_boundary(*seq, begin=True)
    push_kv(*seq, KEY["TYPE"], TYPE_ID["Revolve"], 0.0, 0)
    push_kv(*seq, KEY["PARENT"], 0, float(sketch_idx), 1)
    push_kv(*seq, KEY["OP"], OP_ID.get(feat.get("operation"), 0), 0.0, 0)
    ang = f(feat, "angle", 2*math.pi)
    if abs(ang) > 2*math.pi + 1e-6:
        ang = math.radians(ang)
    push_kv(*seq, KEY["DIST"], 0, rnd(ang), 1)  # 用 DIST 作为 angle 槽（或新增 ANG 键）
    push_kv(*seq, KEY["DIR"], DIR_ID.get(feat.get("direction"), 1), 0.0, 0)
    add_instr_boundary(*seq, begin=False)
    return idx + 1

def add_fillet(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int, feat: Dict[str, Any]) -> int:
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

def add_chamfer(seq: Tuple[List[int], List[int], List[float], List[int]], idx: int, parent_idx: int, feat: Dict[str, Any]) -> int:
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
        if t in ("ExtrudeFeature", "RevolveFeature","HoleFeature"):
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

    seq_keys.append(KEY["EOS"]); seq_val_ids.append(0); seq_val_floats.append(0.0); seq_is_num.append(0)
    return {
        "key_ids": seq_keys,
        "val_ids": seq_val_ids,         # 仅离散值使用
        "val_floats": seq_val_floats,   # 仅连续值使用
        "is_numeric": seq_is_num,       # 1=连续值, 0=离散值
        "vocab": {"KEY": KEY, "TYPE_ID": TYPE_ID, "OP_ID": OP_ID, "DIR_ID": DIR_ID, "EXTENT_ID": EXTENT_ID},
    } # type: ignore


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
