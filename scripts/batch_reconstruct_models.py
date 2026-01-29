
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


def _save_step(part_doc, ipt_path: Path, i: int, is_last: bool) -> None:
    
    if not is_last:
        ipt_path = ipt_path.with_name(f"{ipt_path.stem}_step_{i}.ipt")
    try:
        part_doc.SaveAs(str(ipt_path), False)
    except Exception as e:
        _emit(f"[error] Save step {i}: {e}")


def process_single_json(json_path: Path,app, keep_steps: bool = False) -> Dict[str, str]:
    features = _load_features(str(json_path))
    status ={}
    if not features:
        status["error"] = f"No features in {json_path}"
        return status

    out_ipt_path = json_path.with_suffix(".ipt")

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
            _save_step(part, out_ipt_path, i ,i == len(features))

    try:
        part.Close(True)
    except Exception as e:
        _emit(f"[warning] Failed to close part document: {e}")
        status["warning_close"] = f"Failed to close part document: {e}"
        pass
    return status



def process_folder(data_root: Path, output_root: Optional[str] = None, start: int = 0, keep_steps: bool = False
                   ,postfix = '') -> List[Tuple[str, Dict[str, str]]]:
    # Ensure data_root is a Path object
    data_root = data_root.resolve()
    subdir_names = [p.name for p in data_root.iterdir() if p.is_dir()]
    print("subdirectories:", subdir_names)
    subdir_names = sorted(subdir_names)
    if start > 0:
        subdir_names = subdir_names[start:]
    
    results: List[Tuple[str, Dict[str, str]]] = []
    # Initialize COM and app once for the whole batch
    with com_sta():
        app = get_inventor_application()
        if app is None:
            raise RuntimeError("Inventor application is not available")
        set_inventor_silent(app, True)
        try:
            pb = tqdm.tqdm(subdir_names, desc="Reconstructing models", unit="file")
            for jp in pb:
                pb.set_postfix(file=os.path.basename(jp))
                try:
                    json_path = data_root / jp / (jp + postfix + ".json")
                    if not json_path.exists():
                        raise FileNotFoundError(f"JSON file does not exist: {json_path}")

                    status = process_single_json(json_path, app, keep_steps=keep_steps)
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
    parser.add_argument("--data_root", type=str, help="Path to features JSON file or folder containing JSON files.")
    parser.add_argument("--start", type=int, default=0, help="Starting index for processing files in a folder.")
    parser.add_argument("--keep_steps", action="store_true", help="Keep intermediate step files (IPT) after reconstruction.")
    parser.add_argument("--postfix", type=str, default="", help="Postfix to append to JSON filenames when processing a folder.")
    args = parser.parse_args()
    data_root = args.data_root
    data_root = Path(data_root)
    if not data_root.exists():
        raise SystemExit(f"data_root {data_root} does not exist.")
    start = args.start
    keep_steps = args.keep_steps
    postfix = args.postfix
    results = []
    if data_root.is_dir():
        results = process_folder(data_root, start=start, keep_steps=keep_steps, postfix=postfix)

    result_file = data_root / "reconstruction_results.json"
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        _emit(f"[error] Failed to write results to {result_file}: {e}")





if __name__ == "__main__":
    raise SystemExit(main())
