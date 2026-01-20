


import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is importable when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from feature_encoder import FeatureEncoder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--json_dir","")
    parser.add_argument("--output_dir")

    
    args = parser.parse_args()
    json_dir = args.json_dir
    out_dir = args.output_dir
    import glob
    json_files = glob.glob(os.path.join(json_dir,"**/*.json"),recursive=True)
    print(f"total {len(json_files)}")
    import tqdm
    pbar = tqdm.tqdm(json_files)
    failed_reasons = {}
    for json_path in pbar:
        # 获取当前json文件的名字
        base_name = os.path.basename(json_path)
        #去除后缀
        base_name_without_ext = os.path.splitext(base_name)[0]
        out_path_dir = os.path.join(out_dir,base_name_without_ext)
        os.makedirs(out_path_dir,exist_ok=True)
        out_json_path = os.path.join(out_path_dir,base_name.replace('.json','.vecjson'))
        encoder = FeatureEncoder()
        try:
            with open(json_path,'r',encoding='utf-8') as f:
                features = json.load(f)
            payload = encoder.encode(features)
            with open(out_json_path,"w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            failed_reasons[json_path] = str(e)
        
    failed_reason_path =  os.path.join(out_dir,"failed_reason.json")
    with open(failed_reason_path,"w", encoding="utf-8") as f:
        json.dump(failed_reasons, f, ensure_ascii=False,indent=2)
    print(f"failed cases are written to {failed_reason_path}")
    


        

            




    
