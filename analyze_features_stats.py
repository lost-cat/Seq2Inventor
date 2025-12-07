"""
Analyze feature types across JSON files in a folder.

Outputs:
- Aggregate feature type counts (CSV/JSON)
- Per-file presence (how many files contain a type) CSV/JSON
- Complexity buckets by distinct feature kinds per file CSV/JSON
- Optional charts (bar charts) saved as PNGs
- Single-file mode: feature count and distinct kinds for one JSON

Usage:
  python analyze_features_stats.py <folder_with_jsons> [--charts] [--out OUT_DIR]
"""
from __future__ import annotations
import os
import sys
import json
import csv
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional
import matplotlib.pyplot as plt  


def _emit(msg: str) -> None:
    print(msg)


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _load_features(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else (data.get("features") or [])


def analyze_folder(folder: str) -> Tuple[Dict[str, Counter], Counter, Counter, int, Dict[int, List[str]]]:
    """Return (per_file_counts, aggregate_counts, per_file_presence_counts, total_files, complexity_buckets).
    - per_file_counts: for each file, counts of each feature type
    - aggregate_counts: total occurrences of each feature type across all files
    - per_file_presence_counts: number of files that contain at least one of a feature type
    - total_files: number of JSON files scanned
    - complexity_buckets: map from distinct feature type count -> list of files having that many distinct types
    """
    per_file: Dict[str, Counter] = {}
    aggregate: Counter = Counter()
    presence: Counter = Counter()
    complexity_buckets: Dict[int, List[str]] = defaultdict(list)
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith('.json')]
    for jp in files:
        try:
            feats = _load_features(jp)
        except Exception as e:
            _emit(f"[warn] Failed to load {jp}: {e}")
            continue
        c = Counter()
        for feat in feats:
            t = feat.get("type") or feat.get("featureType") or "<unknown>"
            c[t] += 1
            aggregate[t] += 1
        # presence: feature types appearing at least once in this file
        for t in c.keys():
            presence[t] += 1
        per_file[jp] = c
        # complexity: number of distinct types in this file
        distinct = len(c.keys())
        complexity_buckets[distinct].append(jp)
    return per_file, aggregate, presence, len(files), complexity_buckets


def save_counts_csv(per_file: Dict[str, Counter], aggregate: Counter, presence: Counter, total_files: int, complexity_buckets: Dict[int, List[str]], out_dir: str) -> None:
    _ensure_dir(out_dir)
    # Aggregate CSV
    agg_csv = os.path.join(out_dir, "aggregate_feature_counts.csv")
    with open(agg_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["feature_type", "count"])
        for t, n in sorted(aggregate.items(), key=lambda x: (-x[1], x[0])):
            w.writerow([t, n])
    # Note: per-file detailed matrix CSV removed per request

    # Presence CSV: number of files containing each feature type and percentage
    pres_csv = os.path.join(out_dir, "per_file_presence_counts.csv")
    with open(pres_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["feature_type", "files_with_type", "percent_of_files"])
        for t, n in sorted(presence.items(), key=lambda x: (-x[1], x[0])):
            pct = (n / total_files * 100.0) if total_files else 0.0
            w.writerow([t, n, f"{pct:.2f}"])

    # Complexity CSV: bucket files by number of distinct feature types
    comp_csv = os.path.join(out_dir, "per_file_complexity_buckets.csv")
    with open(comp_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["distinct_feature_types", "file_count"])
        for k in sorted(complexity_buckets.keys()):
            w.writerow([k, len(complexity_buckets[k])])
    # Detailed list per bucket
    comp_list_csv = os.path.join(out_dir, "per_file_complexity_lists.csv")
    with open(comp_list_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["distinct_feature_types", "file"])
        for k in sorted(complexity_buckets.keys()):
            for jp in sorted(complexity_buckets[k]):
                w.writerow([k, jp])


def save_counts_json(per_file: Dict[str, Counter], aggregate: Counter, presence: Counter, total_files: int, complexity_buckets: Dict[int, List[str]], out_dir: str) -> None:
    _ensure_dir(out_dir)
    agg_json = os.path.join(out_dir, "aggregate_feature_counts.json")
    pres_json = os.path.join(out_dir, "per_file_presence_counts.json")
    comp_json = os.path.join(out_dir, "per_file_complexity_buckets.json")
    with open(agg_json, "w", encoding="utf-8") as f:
        json.dump(aggregate, f, ensure_ascii=False, indent=2)
    # per-file detailed JSON removed per request
    pres_payload = {
        "total_files": total_files,
        "presence_counts": dict(presence),
        "presence_percentage": {t: (presence[t] / total_files * 100.0) if total_files else 0.0 for t in presence},
    }
    with open(pres_json, "w", encoding="utf-8") as f:
        json.dump(pres_payload, f, ensure_ascii=False, indent=2)
    comp_payload = {
        "buckets": {str(k): sorted(v) for k, v in complexity_buckets.items()},
        "summary": {str(k): len(v) for k, v in complexity_buckets.items()},
    }
    with open(comp_json, "w", encoding="utf-8") as f:
        json.dump(comp_payload, f, ensure_ascii=False, indent=2)


def save_charts(per_file: Dict[str, Counter], aggregate: Counter, presence: Counter, total_files: int, complexity_buckets: Dict[int, List[str]], out_dir: str) -> None:
    _ensure_dir(out_dir)
    # Aggregate bar chart
    agg_png = os.path.join(out_dir, "aggregate_feature_counts.png")
    types = [t for t, _ in sorted(aggregate.items(), key=lambda x: (-x[1], x[0]))]
    counts = [aggregate[t] for t in types]
    plt.figure(figsize=(max(8, len(types)*0.6), 5))
    plt.bar(types, counts, color="#3b82f6")
    plt.xticks(rotation=45, ha='right')
    plt.ylabel("Count")
    plt.title("Aggregate Feature Counts")
    plt.tight_layout()
    plt.savefig(agg_png)
    plt.close()
    # Note: per-file matrix chart removed per request
    # Presence bar chart (files that contain each type)
    pres_png = os.path.join(out_dir, "per_file_presence_counts.png")
    types_p = [t for t, _ in sorted(presence.items(), key=lambda x: (-x[1], x[0]))]
    counts_p = [presence[t] for t in types_p]
    pcts_p = [(presence[t] / total_files * 100.0) if total_files else 0.0 for t in types_p]
    plt.figure(figsize=(max(8, len(types_p)*0.6), 5))
    plt.bar(types_p, counts_p, color="#10b981")
    plt.xticks(rotation=45, ha='right')
    plt.ylabel("Files with type")
    plt.title("Per-file Presence (count; % in tooltip)")
    # annotate percentages
    for i, v in enumerate(counts_p):
        plt.text(i, v, f"{pcts_p[i]:.1f}%", ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    plt.savefig(pres_png)
    plt.close()

    # Complexity distribution chart
    comp_png = os.path.join(out_dir, "per_file_complexity_distribution.png")
    ks = sorted(complexity_buckets.keys())
    vs = [len(complexity_buckets[k]) for k in ks]
    plt.figure(figsize=(8, 5))
    plt.bar([str(k) for k in ks], vs, color="#f59e0b")
    plt.xlabel("Distinct feature types per file")
    plt.ylabel("File count")
    plt.title("File Complexity Distribution")
    plt.tight_layout()
    plt.savefig(comp_png)
    plt.close()
    # removed block

def single_file_summary(json_path: str, out_dir: Optional[str] = None) -> Dict[str, Any]:
    feats = _load_features(json_path)
    c = Counter()
    for feat in feats:
        t = feat.get("type") or feat.get("featureType") or "<unknown>"
        c[t] += 1
    summary = {
        "file": json_path,
        "total_features": sum(c.values()),
        "distinct_feature_types": len(c.keys()),
        "counts": dict(c),
        "types": sorted(list(c.keys())),
    }
    if out_dir:
        _ensure_dir(out_dir)
        out_json = os.path.join(out_dir, "single_file_feature_summary.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: python analyze_features_stats.py <folder_or_json> [--charts] [--out OUT_DIR]")
        return 1
    src = argv[0]
    make_charts = any(a.lower() == "--charts" for a in argv[1:])
    out_dir = None
    for i, a in enumerate(argv[1:], start=1):
        if a.lower() == "--out" and i+1 < len(argv):
            out_dir = argv[i+1]
            break
    if os.path.isfile(src):
        # Single-file mode: compute feature count and kinds
        out_dir = out_dir or os.path.join(os.path.dirname(src), "feature_stats")
        summary = single_file_summary(src, out_dir)
        print(f"OK: single-file summary saved to {out_dir}")
        return 0
    if not os.path.isdir(src):
        print(f"Error: {src} is not a folder or file")
        return 2
    out_dir = out_dir or os.path.join(src, "feature_stats")
    per_file, aggregate, presence, total_files, complexity_buckets = analyze_folder(src)
    save_counts_csv(per_file, aggregate, presence, total_files, complexity_buckets, out_dir)
    save_counts_json(per_file, aggregate, presence, total_files, complexity_buckets, out_dir)
    if make_charts:
        save_charts(per_file, aggregate, presence, total_files, complexity_buckets, out_dir)
    print(f"OK: stats saved to {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
