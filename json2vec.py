"""Convert exported feature JSON into vectors for ML, split into two parts:

Part A: Sketch vectors (per entity)
- Each unique profile/sketch gets a sketch_id
- Rows: sketch_id, path_idx, entity_idx, one-hot entity type (line/arc/circle/other),
  geometry values (line: start/end/length; arc: center/radius/angles/start/end; circle: center/radius),
  and optional sketch plane normal

Part B: Feature vectors (per feature)
- Each feature gets a feature_id
- Categorical encodings (type/operation/extent/direction) and numeric params (distance/angle/etc)
- References:
  - Extrude/Revolve reference sketch_id used by the feature
  - Fillet/Chamfer reference source feature_id (best-effort; set -1 if unknown)

Usage:
	python json2vec.py input.json output_prefix [--npz out.npz]

Outputs:
	output_prefix_sketches.csv
	output_prefix_features.csv
	optional NPZ with arrays: X_sketch, X_feature and headers
"""
from __future__ import annotations
import json
import math
import csv
import sys
from typing import Any, Dict, List, Tuple, Optional
import numpy as np

# --- configuration: known categories ---
FEATURE_TYPES = ["ExtrudeFeature", "RevolveFeature", "FilletFeature", "ChamferFeature"]
OPERATIONS = [
	"kJoinOperation",
	"kCutOperation",
	"kNewBodyOperation",
	"kIntersectOperation",
]
EXTENT_TYPES = ["kDistanceExtent", "kOneSideFeatureExtentType", "kSymmetricFeatureExtentType", "kTwoSidesFeatureExtentType"]
DIRECTIONS = ["kPositiveExtentDirection", "kNegativeExtentDirection", "kSymmetricExtentDirection"]

# Sketch entity types
ENTITY_TYPES = ["Line", "Arc", "Circle", "Other"]


def one_hot_index(value: Optional[str], categories: List[str]) -> List[int]:
	vec = [0] * len(categories)
	if value is None:
		return vec
	try:
		i = categories.index(value)
		vec[i] = 1
	except ValueError:
		pass
	return vec


def safe_float(v: Any) -> Optional[float]:
	try:
		return float(v)
	except Exception:
		return None


def bbox_and_counts_from_profile(profile: Dict[str, Any]) -> Tuple[float, float, float, float, int, int, int, int, float]:
	"""Compute bbox (minx,miny,maxx,maxy), counts: path_count, entity_count, n_arcs, n_lines, approx_area_total"""
	minx = miny = float("inf")
	maxx = maxy = float("-inf")
	path_count = 0
	entity_count = 0
	n_arcs = 0
	n_lines = 0
	total_area = 0.0

	for path in profile.get("ProfilePaths", []) or []:
		path_count += 1
		entities = path.get("PathEntities", []) or []
		entity_count += len(entities)
		# For area: gather vertices assuming entity endpoints form polygon; fall back gracefully
		poly_pts: List[Tuple[float, float]] = []
		for ent in entities:
			ctype = ent.get("CurveType")
			if ctype and ctype.startswith("kCircularArc"):
				n_arcs += 1
				# approximate arc by its endpoints
				sp = ent.get("StartSketchPoint")
				ep = ent.get("EndSketchPoint")
				if sp and ep:
					sx, sy = float(sp.get("x", 0.0)), float(sp.get("y", 0.0))
					ex, ey = float(ep.get("x", 0.0)), float(ep.get("y", 0.0))
					poly_pts.append((sx, sy))
					poly_pts.append((ex, ey))
					minx = min(minx, sx, ex)
					miny = min(miny, sy, ey)
					maxx = max(maxx, sx, ex)
					maxy = max(maxy, sy, ey)
			elif ctype and ctype.startswith("kLine"):
				n_lines += 1
				sp = ent.get("StartSketchPoint")
				ep = ent.get("EndSketchPoint")
				if sp and ep:
					sx, sy = float(sp.get("x", 0.0)), float(sp.get("y", 0.0))
					ex, ey = float(ep.get("x", 0.0)), float(ep.get("y", 0.0))
					poly_pts.append((sx, sy))
					poly_pts.append((ex, ey))
					minx = min(minx, sx, ex)
					miny = min(miny, sy, ey)
					maxx = max(maxx, sx, ex)
					maxy = max(maxy, sy, ey)
			elif ctype and ctype.startswith("kCircle"):
				# circle approximate by bounding box
				curve = ent.get("Curve") or {}
				center = curve.get("center") or {}
				r = safe_float(curve.get("radius")) or 0.0
				cx, cy = float(center.get("x", 0.0)), float(center.get("y", 0.0))
				minx = min(minx, cx - r)
				miny = min(miny, cy - r)
				maxx = max(maxx, cx + r)
				maxy = max(maxy, cy + r)
				# approximate area
				total_area += math.pi * (r ** 2)
				poly_pts.append((cx + r, cy))
			else:
				# unknown: try endpoints
				sp = ent.get("StartSketchPoint")
				ep = ent.get("EndSketchPoint")
				if sp:
					sx, sy = float(sp.get("x", 0.0)), float(sp.get("y", 0.0))
					minx = min(minx, sx)
					miny = min(miny, sy)
					maxx = max(maxx, sx)
					maxy = max(maxy, sy)
					poly_pts.append((sx, sy))
				if ep:
					ex, ey = float(ep.get("x", 0.0)), float(ep.get("y", 0.0))
					minx = min(minx, ex)
					miny = min(miny, ey)
					maxx = max(maxx, ex)
					maxy = max(maxy, ey)
					poly_pts.append((ex, ey))
		# compute polygon area (shoelace) if we have at least 3 unique points
		if len(poly_pts) >= 3:
			# remove consecutive duplicates and reduce
			unique = []
			for p in poly_pts:
				if not unique or unique[-1] != p:
					unique.append(p)
			if len(unique) >= 3:
				area = 0.0
				for i in range(len(unique)):
					x1, y1 = unique[i]
					x2, y2 = unique[(i + 1) % len(unique)]
					area += x1 * y2 - x2 * y1
				total_area += abs(area) / 2.0

	if minx == float("inf"):
		minx = miny = maxx = maxy = 0.0

	return minx, miny, maxx, maxy, path_count, entity_count, n_arcs, n_lines, total_area


def feature_to_vector(feat: Dict[str, Any], *, sketch_ref_map: Dict[str, int], last_solid_feature_id: Optional[int]) -> Tuple[List[float], List[str], Optional[int]]:
	"""Convert a single feature dict to a numeric vector and return header names and referenced ids.

	Returns (vec, headers, ref_id) where ref_id is the referenced sketch_id (for Extrude/Revolve)
	or referenced feature_id (for Fillet/Chamfer). Also returns updated last_solid_feature_id externally.
	"""
	vec: List[float] = []
	headers: List[str] = []

	# Type one-hot
	t = feat.get("type")
	onehot_t = one_hot_index(t, FEATURE_TYPES)
	for i, v in enumerate(onehot_t):
		headers.append(f"type_{FEATURE_TYPES[i]}")
		vec.append(float(v))

	# Operation one-hot
	op = feat.get("operation")
	onehot_op = one_hot_index(op, OPERATIONS)
	for i, v in enumerate(onehot_op):
		headers.append(f"op_{OPERATIONS[i]}")
		vec.append(float(v))

	# ExtentType one-hot
	ext = feat.get("extentType")
	onehot_ext = one_hot_index(ext, EXTENT_TYPES)
	for i, v in enumerate(onehot_ext):
		headers.append(f"extent_{EXTENT_TYPES[i]}")
		vec.append(float(v))

	# Direction one-hot
	dirv = feat.get("direction")
	onehot_dir = one_hot_index(dirv, DIRECTIONS)
	for i, v in enumerate(onehot_dir):
		headers.append(f"dir_{DIRECTIONS[i]}")
		vec.append(float(v))

	# Distances
	dist_val = None
	dist = feat.get("distance")
	if isinstance(dist, dict):
		dist_val = safe_float(dist.get("value"))
	elif isinstance(dist, (int, float)):
		dist_val = float(dist)
	if dist_val is None:
		dist_val = 0.0
	headers.append("distance")
	vec.append(dist_val)

	dist2_val = None
	dist2 = feat.get("distanceTwo")
	if isinstance(dist2, dict):
		dist2_val = safe_float(dist2.get("value"))
	elif isinstance(dist2, (int, float)):
		dist2_val = float(dist2)
	if dist2_val is None:
		dist2_val = 0.0
	headers.append("distanceTwo")
	vec.append(dist2_val)

	# Profile stats
	profile = feat.get("profile") or {}
	minx, miny, maxx, maxy, path_count, entity_count, n_arcs, n_lines, total_area = bbox_and_counts_from_profile(profile)
	headers += ["minx", "miny", "maxx", "maxy", "path_count", "entity_count", "n_arcs", "n_lines", "approx_area"]
	vec += [minx, miny, maxx, maxy, float(path_count), float(entity_count), float(n_arcs), float(n_lines), float(total_area)]

	# Sketch plane normal (if provided)
	sk_plane = profile.get("SketchPlane") or {}
	normal = sk_plane.get("normal") or {}
	nx = safe_float(normal.get("x")) or 0.0
	ny = safe_float(normal.get("y")) or 0.0
	nz = safe_float(normal.get("z")) or 0.0
	headers += ["sk_nx", "sk_ny", "sk_nz"]
	vec += [nx, ny, nz]

	# Basic derived features: bbox size, aspect ratio
	width = maxx - minx
	height = maxy - miny
	headers += ["width", "height", "aspect"]
	vec += [width, height, (width / height) if height != 0 else 0.0]

	# References
	ref_id: Optional[int] = None
	if t in ("ExtrudeFeature", "RevolveFeature"):
		# Map profile ReferenceKey (preferred) or sketchName to sketch_id
		key = None
		if isinstance(profile, dict):
			key = profile.get("ReferenceKey") or profile.get("sketchName")
		if key is not None and key in sketch_ref_map:
			ref_id = sketch_ref_map[key]
		headers.append("ref_sketch_id")
		vec.append(float(ref_id if ref_id is not None else -1))
		# Track last solid feature id outside
	elif t in ("FilletFeature", "ChamferFeature"):
		# Best-effort: reference the last solid feature id (extrude/revolve) if not explicitly provided
		headers.append("ref_feature_id")
		vec.append(float(last_solid_feature_id if last_solid_feature_id is not None else -1))
	# Revolve-specific numeric: angle if present
	if t == "RevolveFeature":
		ang = feat.get("angle")
		vec.append(float(ang) if isinstance(ang, (int, float)) else 0.0)
		headers.append("revolve_angle")

	return vec, headers, ref_id


def json_to_vectors(json_obj: Any) -> Tuple[List[List[float]], List[str], List[List[float]], List[str]]:
	"""Convert loaded JSON into two matrices:
	- sketch_rows, sketch_header: per-entity sketch vectors with sketch_id
	- feature_rows, feature_header: per-feature vectors with references
	"""
	features = json_obj
	if isinstance(json_obj, dict):
		features = json_obj.get("features", [])

	# 1) Build sketch inventory (unique profiles) and per-entity rows
	sketch_id_map: Dict[str, int] = {}
	sketch_rows: List[List[float]] = []
	sketch_header: List[str] = []
	next_sk_id = 1

	def entity_to_row(sketch_id: int, path_idx: int, ent_idx: int, ent: Dict[str, Any], plane_normal: Tuple[float, float, float]) -> Tuple[List[float], List[str]]:
		row: List[float] = []
		hdr: List[str] = []
		# identifiers
		hdr += ["sketch_id", "path_idx", "entity_idx"]
		row += [float(sketch_id), float(path_idx), float(ent_idx)]
		# entity type one-hot
		ctype = ent.get("CurveType", "") or ""
		if ctype.startswith("kLine"):
			ent_type = "Line"
		elif ctype.startswith("kCircle") and not ctype.startswith("kCircularArc"):
			ent_type = "Circle"
		elif ctype.startswith("kCircularArc"):
			ent_type = "Arc"
		else:
			ent_type = "Other"
		oh = one_hot_index(ent_type, ENTITY_TYPES)
		for i, v in enumerate(oh):
			hdr.append(f"ent_{ENTITY_TYPES[i]}")
			row.append(float(v))
		# geometry
		nx, ny, nz = plane_normal
		if ent_type == "Line":
			sp = ent.get("StartSketchPoint") or {}
			ep = ent.get("EndSketchPoint") or {}
			sx, sy = safe_float(sp.get("x")) or 0.0, safe_float(sp.get("y")) or 0.0
			ex, ey = safe_float(ep.get("x")) or 0.0, safe_float(ep.get("y")) or 0.0
			length = math.hypot(ex - sx, ey - sy)
			hdr += ["sx", "sy", "ex", "ey", "length"]
			row += [sx, sy, ex, ey, length]
		elif ent_type == "Arc":
			curve = ent.get("Curve") or {}
			center = curve.get("center") or {}
			radius = safe_float(curve.get("radius")) or 0.0
			start_ang = safe_float(curve.get("startAngle")) or 0.0
			sweep = safe_float(curve.get("sweepAngle")) or 0.0
			sp = ent.get("StartSketchPoint") or {}
			ep = ent.get("EndSketchPoint") or {}
			sx, sy = safe_float(sp.get("x")) or 0.0, safe_float(sp.get("y")) or 0.0
			ex, ey = safe_float(ep.get("x")) or 0.0, safe_float(ep.get("y")) or 0.0
			cx, cy = safe_float(center.get("x")) or 0.0, safe_float(center.get("y")) or 0.0
			hdr += ["cx", "cy", "radius", "startAngle", "sweepAngle", "sx", "sy", "ex", "ey"]
			row += [cx, cy, radius, start_ang, sweep, sx, sy, ex, ey]
		elif ent_type == "Circle":
			curve = ent.get("Curve") or {}
			center = curve.get("center") or {}
			radius = safe_float(curve.get("radius")) or 0.0
			cx, cy = safe_float(center.get("x")) or 0.0, safe_float(center.get("y")) or 0.0
			hdr += ["cx", "cy", "radius"]
			row += [cx, cy, radius]
		else:
			# minimal placeholders
			hdr += ["geo0", "geo1", "geo2", "geo3"]
			row += [0.0, 0.0, 0.0, 0.0]
		# plane normal for sketch context
		hdr += ["sk_nx", "sk_ny", "sk_nz"]
		row += [nx, ny, nz]
		return row, hdr

	# Collect unique profiles and emit sketch rows
	for feat in (features or []):
		prof = (feat or {}).get("profile") or {}
		if not prof:
			continue
		key = prof.get("ReferenceKey") or prof.get("sketchName")
		if key is None:
			continue
		if key not in sketch_id_map:
			sketch_id_map[key] = next_sk_id
			next_sk_id += 1
		sk_id = sketch_id_map[key]
		normal = prof.get("SketchPlane", {}).get("normal", {})
		plane_normal = (
			safe_float(normal.get("x")) or 0.0,
			safe_float(normal.get("y")) or 0.0,
			safe_float(normal.get("z")) or 0.0,
		)
		for p_idx, path in enumerate(prof.get("ProfilePaths", []) or [], start=1):
			for e_idx, ent in enumerate(path.get("PathEntities", []) or [], start=1):
				row, hdr = entity_to_row(sk_id, p_idx, e_idx, ent, plane_normal)
				if not sketch_header:
					sketch_header = hdr
				sketch_rows.append(row)

	# 2) Feature rows with references
	feature_rows: List[List[float]] = []
	feature_header: List[str] = []
	last_solid_feature_id: Optional[int] = None
	for f_idx, feat in enumerate(features or [], start=1):
		vec, hdr, ref = feature_to_vector(feat, sketch_ref_map=sketch_id_map, last_solid_feature_id=last_solid_feature_id)
		# prepend feature_id
		vec = [float(f_idx)] + vec
		hdr = ["feature_id"] + hdr
		if not feature_header:
			feature_header = hdr
		feature_rows.append(vec)
		# update last solid feature id
		t = feat.get("type")
		if t in ("ExtrudeFeature", "RevolveFeature"):
			last_solid_feature_id = f_idx

	return sketch_rows, sketch_header, feature_rows, feature_header


def main(argv):
	if len(argv) < 3:
		print("Usage: python json2vec.py input.json output_prefix [--npz out.npz]")
		return 1
	inp = argv[1]
	out_prefix = argv[2]
	out_npz = None
	if len(argv) >= 5 and argv[3] == "--npz":
		out_npz = argv[4]
	with open(inp, 'r', encoding='utf-8') as f:
		data = json.load(f)
	sk_rows, sk_hdr, f_rows, f_hdr = json_to_vectors(data)
	# write sketches CSV
	out_sk_csv = f"{out_prefix}_sketches.csv"
	with open(out_sk_csv, 'w', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerow(sk_hdr)
		for r in sk_rows:
			writer.writerow(r)
	# write features CSV
	out_feat_csv = f"{out_prefix}_features.csv"
	with open(out_feat_csv, 'w', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerow(f_hdr)
		for r in f_rows:
			writer.writerow(r)
	if out_npz:
		X_sk = np.array(sk_rows, dtype=float) if sk_rows else np.zeros((0, len(sk_hdr)), dtype=float)
		X_f = np.array(f_rows, dtype=float) if f_rows else np.zeros((0, len(f_hdr)), dtype=float)
		np.savez(out_npz, X_sketch=X_sk, header_sketch=np.array(sk_hdr, dtype=object), X_feature=X_f, header_feature=np.array(f_hdr, dtype=object))
	print(f"Wrote {len(sk_rows)} sketch-entity rows to {out_sk_csv}")
	print(f"Wrote {len(f_rows)} feature rows to {out_feat_csv}")
	if out_npz:
		print(f"Wrote npz to {out_npz}")
	return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv))

