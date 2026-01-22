
from __future__ import annotations
import argparse
from pathlib import Path
import sys


# Ensure project root is importable when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
    
from glob import glob
import os
import json
from typing import Any, Dict, List, Optional, Tuple

import tqdm
from win32com.client import CastTo, constants

from inventor_utils.app import com_sta, get_inventor_application, set_inventor_silent, pump_waiting_messages
from inventor_utils.indexing import EntityIndexHelper

# Reuse the feature rebuilders to ensure parity with reconstruct_from_json.py
import reconstruct_from_json as rfj


def _emit(msg: str) -> None:
    print(msg)


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _basename_no_ext(path: str) -> str:
    b = os.path.basename(path)
    n, _ = os.path.splitext(b)
    return n or "output"


def _load_features(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("features", [])


def _save_step(part_doc, out_dir: str, i: int) -> None:
    step_path = os.path.join(out_dir, f"step_{i:03d}.ipt")
    try:
        part_doc.SaveAs(step_path, False)
    except Exception as e:
        _emit(f"[error] Save step {i}: {e}")


def process_single_json(json_path: str,app, output_root: Optional[str] = None, keep_steps: bool = False) -> Dict[str, str]:
    json_path = json_path.strip()
    features = _load_features(json_path)
    status ={}
    if not features:
        status["error"] = f"No features in {json_path}"
        return status

    out_root = output_root.strip() if output_root else None
    if not out_root:
        out_root = os.path.dirname(json_path)
    out_dir = os.path.join(out_root, _basename_no_ext(json_path))
    _ensure_dir(out_dir)

    # Reuse provided app without reinitializing COM or toggling silent here
    # New part per JSON
    part = app.Documents.Add(constants.kPartDocumentObject, "", True)
    try:
        part = CastTo(part, "PartDocument")
    except Exception:
        status["error"] = "Failed to cast to PartDocument"
        return status
    com_def = part.ComponentDefinition
    helper = EntityIndexHelper(com_def)

    for i, feat in enumerate(features, start=1):
        try:
            rfj._rebuild_feature(com_def, feat, entity_index_helper=helper)
        except Exception as e:
            _emit(f"[rebuild] Failed {json_path} for feature {i}: {e}")
            status[f'error_step_{i}'] = f"Failed to rebuild feature {i}: {e}"
            break
        try:
            helper.update_all()
        except Exception as e:
            _emit(f"[error] Failed {json_path} to update entity index after feature {i}: {e}")
            status[f'error_step_{i}'] = f"Failed to update entity index after feature {i}: {e}"
            break

        pump_waiting_messages()
        if i == len(features) or keep_steps:
            _save_step(part, out_dir, i)

    try:
        part.Close(True)
    except Exception as e:
        _emit(f"[warning] Failed to close part document: {e}")
        status["warning_close"] = f"Failed to close part document: {e}"
        pass
    return status



def process_folder(folder: str, output_root: Optional[str] = None, start: int = 0, keep_steps: bool = False) -> List[Tuple[str, Dict[str, str]]]:
    folder = folder.strip()
    jsons = [p for p in glob(os.path.join(folder, "**", "*.json"), recursive=True) if p.endswith("_decoded.json")]
    jsons = sorted(jsons)
    if start > 0:
        jsons = jsons[start:]
    
    results: List[Tuple[str, Dict[str, str]]] = []
    # Initialize COM and app once for the whole batch
    with com_sta():
        app = get_inventor_application()
        if app is None:
            raise RuntimeError("Inventor application is not available")
        set_inventor_silent(app, True)
        try:
            pb = tqdm.tqdm(jsons, desc="Reconstructing models", unit="file")
            for jp in pb:
                pb.set_postfix(file=os.path.basename(jp))
                try:
                    status = process_single_json(jp, app, output_root, keep_steps)
                    results.append((jp, status))
                except Exception as e:
                    _emit(f"[batch] Failed {jp}: {e}")
                
                pb.refresh()
        finally:
            try:
                set_inventor_silent(app, False)
            except Exception:
                pass
    return results


def main():
    parser = argparse.ArgumentParser(description="Reconstruct Inventor models step-by-step from features JSON.")
    parser.add_argument("--source", type=str, help="Path to features JSON file or folder containing JSON files.")
    parser.add_argument("--output_root", type=str, nargs="?", default=None,
                        help="Output root directory. Defaults beside the JSON file(s).")
    parser.add_argument("--start", type=int, default=0, help="Starting index for processing files in a folder.")
    parser.add_argument("--keep_steps", action="store_true", help="Keep intermediate step files (IPT) after reconstruction.")
    args = parser.parse_args()
    src = args.source
    out = args.output_root
    start = args.start
    keep_steps = args.keep_steps
    if os.path.isdir(src):
        results = process_folder(src, out,start, keep_steps)
    else:
        results = process_single_json(src, out, keep_steps)

    result_file = os.path.join(os.path.dirname(out), "json2ipt.json") if out else "json2ipt.json"
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        _emit(f"[error] Failed to write results to {result_file}: {e}")





if __name__ == "__main__":
    raise SystemExit(main())
