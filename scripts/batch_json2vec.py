


import argparse
import json
import os
import sys
from pathlib import Path
from glob import glob
# Ensure project root is importable when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from feature_encoder import FeatureEncoder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--data_root", required=True, help="Directory to save output vector JSON files.")
    parser.add_argument("--decode", action="store_true", help="Decode vector JSON files back to feature JSON.")

    
    args = parser.parse_args()
    # json_dir = args.json_dir
    data_root = args.data_root
    data_root = Path(data_root)
    if not data_root.exists():
        raise SystemExit(f"data_root {data_root} does not exist.")

    # 获取 data_root 下面的所有文件夹,
    subdir_names = [p.name for p in data_root.iterdir() if p.is_dir()]
    print("subdirectories:", subdir_names)

    
    print(f"total {len(subdir_names)}")
    import tqdm
    pbar = tqdm.tqdm(subdir_names)
    failed_reasons = {}
    for subdir_name in pbar:
        input_json_path = data_root/subdir_name/(subdir_name + ".json")
        if not input_json_path.exists():
            failed_reasons[str(input_json_path)] = "input json file does not exist."
            continue

        out_vec_path = data_root/subdir_name/(subdir_name + ".vecjson")
        encoder = FeatureEncoder()
        try:
            with open(input_json_path,'r',encoding='utf-8') as f:
                features = json.load(f)
            payload = encoder.encode(features)
            with open(out_vec_path,"w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            if args.decode:
                decoded_json = FeatureEncoder.decode(payload)
                decoded_json_path = data_root/subdir_name/(subdir_name + "_decoded.json")
                with open(decoded_json_path,"w", encoding="utf-8") as f:
                    json.dump(decoded_json, f, ensure_ascii=False, indent=2)
        except Exception as e:
            failed_reasons[str(input_json_path)] = str(e)
        
    failed_reason_path =  data_root/"json2vec_failed_reason.json"
    with open(failed_reason_path,"w", encoding="utf-8") as f:
        json.dump(failed_reasons, f, ensure_ascii=False,indent=2)
    print(f"failed cases are written to {failed_reason_path}")
    


        

            




    
