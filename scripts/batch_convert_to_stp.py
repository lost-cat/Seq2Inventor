

from inventor_utils.app import com_sta, open_inventor_document, set_inventor_silent


if __name__ == "__main__":
    import os
    import win32com.client
    from inventor_util import get_inventor_application
    from inventor_utils.utils import export_to_step
    import argparse
    import glob
    import tqdm
    parser = argparse.ArgumentParser(description="Batch convert Inventor parts to STEP format.")
    parser.add_argument("ipt_dir", nargs='+', help="Directory containing .ipt files to convert.")
    parser.add_argument("--output_dir", default=".", help="Directory to save converted STEP files.")
    args = parser.parse_args()
    ipt_dir = args.ipt_dir
    output_dir = args.output_dir
    ipt_files = glob.glob(os.path.join(ipt_dir,"**/*.ipt"), recursive=True)
    print(f"Found {len(ipt_files)} .ipt files to convert.")
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
            rel_path = os.path.relpath(part_file, start=os.path.commonpath(ipt_dir))
            output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".step")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                export_to_step(part_doc, output_path)
            except Exception as e:
                print(f"Failed to export {part_file} to STEP: {e}")
        
            part_doc.Close(True)
        set_inventor_silent(app, False)
        