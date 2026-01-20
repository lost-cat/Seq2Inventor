

# Ensure repository root is on sys.path when running from scripts/
import os
import sys

from pathlib import Path
# Ensure project root is importable when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from inventor_utils.app import com_sta, open_inventor_document, set_inventor_silent

import win32com.client
from inventor_util import get_inventor_application
from inventor_utils.utils import export_to_step
import argparse
import glob
import tqdm

if __name__ == "__main__":



    parser = argparse.ArgumentParser(description="Batch convert Inventor parts to STEP format.")
    parser.add_argument("--ipt_dir", help="One or more directories containing .ipt files (flag form).")
    parser.add_argument("--output_dir", default=".", help="Directory to save converted STEP files.")
    parser.add_argument("--start", type=int, default=0, help="Index to start processing from.")
    args = parser.parse_args()
    ipt_dirs = []
    if args.ipt_dir:
        ipt_dirs.append(args.ipt_dir)
    if not ipt_dirs:
        parser.error("Please provide at least one IPT directory (--ipt_dir)")
    output_dir = args.output_dir
    # Gather all .ipt files from provided directories
    ipt_files = []
    for d in ipt_dirs:
        ipt_files.extend(glob.glob(os.path.join(d, "**", "*.ipt"), recursive=True))
    print(f"Found {len(ipt_files)} .ipt files to convert.")
    ipt_files = sorted(ipt_files)

    print(f"Processing {len(ipt_files)} files starting from index {args.start}.")
    if args.start > 0:
        ipt_files = ipt_files[args.start:]
    pbar = tqdm.tqdm(ipt_files)
    with com_sta():
        app = get_inventor_application()
        if app is None:
            raise SystemExit("Inventor application not available.")
        app.Visible = True
        set_inventor_silent(app, True)
        for part_file in pbar:
            part_doc = open_inventor_document(app, part_file)
            if part_doc is None:
                print(f"Failed to open document: {part_file}")
                continue
            # Compute relative path against the closest matching input dir
            base_dir = None
            for d in ipt_dirs:
                if part_file.startswith(os.path.abspath(d)):
                    base_dir = d
                    break
            base_dir = base_dir or ipt_dirs[0]
            rel_path = os.path.relpath(part_file, start=os.path.abspath(base_dir))
            output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".step")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                export_to_step(part_doc, output_path)
            except Exception as e:
                print(f"Failed to export {part_file} to STEP: {e}")
        
            part_doc.Close(True)
        set_inventor_silent(app, False)
        