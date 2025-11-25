


import argparse
import glob
import os
import json
import tqdm

from inventor_utils.app import get_all_features, get_inventor_application, open_inventor_document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量从 Inventor 零件文件中提取特征并保存为 JSON 文件。")
    parser.add_argument("--part_dir", type=str, required=True, help="包含 Inventor 零件文件的目录路径。")
    parser.add_argument("--out_dir", type=str, default="output", help="输出 JSON 文件的目录路径，默认在零件目录同级创建 output 目录。")
    parser.add_argument("--start", type=int, default=0, help="起始索引,默认从第0个文件开始处理。")
    parser.add_argument("--count", type=int, default=100, help="最大处理数量")
    args = parser.parse_args()
    current_dir = os.path.abspath(os.path.dirname(__file__))
    part_dir = os.path.join(current_dir, args.part_dir)

    #在part dir 同级目录下创建 output 目录
    out_dir = os.path.join(os.path.dirname(part_dir), "output") if args.out_dir == "output" else os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # 收集所有 .ipt 文件（递归），并按路径排序保证稳定性
    all_part_files = glob.glob(os.path.join(part_dir, "**", "*.ipt"), recursive=True)
    all_part_files = sorted(all_part_files)

    # 按起始索引和最大数量限制截断
    if args.count is not None and args.count > 0:
        selected_files = all_part_files[args.start : args.start + args.count]
    else:
        selected_files = all_part_files
    failed_files = []
    pb = tqdm.tqdm(selected_files, total=len(selected_files), desc="Processing parts")
    app = get_inventor_application()
    if app is None:
        raise SystemExit("Inventor application not available.")
    app.Visible = True
    for part_file in pb:
        abs_path = os.path.abspath(part_file)
        part_doc = open_inventor_document(app, part_file)
        if part_doc is None:
            print(f"Failed to open document: {part_file}")
            continue
        features = get_all_features(part_doc)
        json_path = os.path.join(out_dir, os.path.basename(part_file).replace(".ipt", "_features.json"))
        from feature_wrappers import dump_features_as_json, wrap_feature
        try:
            if len(features) >=50:
                failed_files.append({part_file: "Too many features, skip"})
                continue
            dump_features_as_json(features, path=json_path, doc=part_doc)
        except Exception as e:
            print(f"Failed to dump features for {part_file}: {e}")
            failed_files.append({part_file: str(e)})
        #close document
        try:
            part_doc.Close(True)
        except Exception as e:
            print(f"Failed to close document {part_file}: {e}")
    # 保存失败文件列表
    failed_reason_json = os.path.join(out_dir, "failed_files.json")
    if not os.path.exists(failed_reason_json):
        
        with open(failed_reason_json, "w") as f:
            json.dump(failed_files, f, indent=4)
    else:
        existed_failed_files = []
        with open(failed_reason_json, "r") as f:
            existed_failed_files = json.load(f)
        existed_failed_files.extend(failed_files)
        with open(failed_reason_json, "w") as f:
            json.dump(existed_failed_files, f, indent=4)