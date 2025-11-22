import argparse
import glob
import json
import os
import sys
import h5py
import tqdm

from cad_utils.extrude import CADSequence
from cad_utils.macro import EXT_IDX
from inventor_utils.app import add_part_document, save__inventor_document, get_inventor_application
from inventor_utils.features import create_inventor_model_from_sequence
from enum import Enum

from inventor_utils.utils import remove_padding

class InventorModelStatus(Enum):
    VEC_CONVERSION_FAILED = "Vector conversion failed"
    INVENTOR_API_CALL_FAILED = "Inventor API call failed"
    SUCCESS = "Success"


def load_vec(
    file_path, b_remove_padding=True, name="out_vec", b_return_gt=False, gt_name=None
):
    with h5py.File(file_path, "r") as file:
        vec = file[name]
        if b_remove_padding:
            vec = remove_padding(vec)

        if b_return_gt and gt_name is not None:
            vec_gt = file[gt_name]
            if b_remove_padding:
                vec_gt = remove_padding(vec_gt)
            return vec, vec_gt
    return vec
    pass


def vec2inventor(vec, com_def) -> InventorModelStatus:
    try:
        cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
        seq = cad_seq.seq
    except Exception as e:
        print("Error:", e)
        return InventorModelStatus.VEC_CONVERSION_FAILED

    try:
        create_inventor_model_from_sequence(seq, com_def=com_def)
    except Exception as e:
        print("Error:", e)
        return InventorModelStatus.INVENTOR_API_CALL_FAILED

    return InventorModelStatus.SUCCESS


def process_one(file_path,app):
    vec = load_vec(file_path, b_return_gt=False,name="out_vec")
    part, com_def = add_part_document(app, 'test')
    status = vec2inventor(vec, com_def)
    return status, part

def parse_deepcad_dataset(data_dir,app):
    file_paths = glob.glob(os.path.join(data_dir, "**/*.h5"), recursive=True)
    vec_conversion_failed_file_path = []
    inventor_api_call_file_path = []
    pbar = tqdm.tqdm(file_paths)

    for file_path in pbar:
        data_id = os.path.basename(file_path).split(".")[0]
        pbar.set_description(f"Processing: {data_id}")
        status, part = process_one(file_path,app)
        if status == InventorModelStatus.VEC_CONVERSION_FAILED:
            vec_conversion_failed_file_path.append(file_path)
        elif status == InventorModelStatus.INVENTOR_API_CALL_FAILED:
            inventor_api_call_file_path.append(file_path)
        else:
            save_path = file_path.replace(".h5", ".ipt")
            save__inventor_document(part, save_path)

        part.Close(True)

    output = {
        "vec_conversion_failed_path": vec_conversion_failed_file_path,
        "inventor_api_call_failed_path": inventor_api_call_file_path,
    }
    json.dump(output, open("output.json", "w"), indent=4)


def IR_check(app, file_paths, get_data_id=lambda x: x.split("/")[-1].split(".")[0]):
    valid_count = 0
    total_count = 0
    pbar = tqdm.tqdm(file_paths)
    for file_path in pbar:
        vec, vec_gt = load_vec(file_path, b_return_gt=True, gt_name="ground_truth")
        data_id = get_data_id(file_path)
        doc, com_def = add_part_document(app, data_id + "out")
        try:
            cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
            seq = cad_seq.seq
            create_inventor_model_from_sequence(seq, com_def=com_def)
            valid_count += 1
            doc.Close(True)
        except Exception as e:

            print("Error:", e, file_path)
            doc.Close(True)
        total_count += 1
        pbar.set_description(f"Valid: {valid_count}, Total: {total_count}")
    return valid_count, total_count


def single_debug(app, file_path):
    with h5py.File(file_path, "r") as file:
        vec = file["out_vec"]
        vec_gt = file["ground_truth"]
        vec = remove_padding(vec)
        vec_gt = remove_padding(vec_gt)
        data_id = os.path.join(
            file_path.split("/")[-2], file_path.split("/")[-1].split(".")[0]
        )
        part, com_def = add_part_document(app, data_id + "out")
        cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
        cad_seq
        seq = cad_seq.seq
        create_inventor_model_from_sequence(seq, com_def=com_def)
        app.ActiveView.Fit()
        # input("Press Enter to continue...")
        # part.Close(True)


def IR_CACAL(app, data_dir):

    file_paths = glob.glob(os.path.join(data_dir, "**/*.h5"), recursive=True)
    file_paths = ["data/test_deepcad_cad_vec_NAT/0098/00980343.h5"]
    single_debug(file_paths[0])
    sys.exit()
    valid_count, total_count = IR_check(app, file_paths)
    print(f"Valid: {valid_count}, Total: {total_count}")
    IR = valid_count / total_count
    print(f"IR: {IR}")


def get_ext_count(vec):
    commands = vec[:, 0]
    ext_count = (commands == EXT_IDX).sum()
    return ext_count


def cherry_pick(app, data_dir, file, allowed_ext_count=3, start_idx=0, end_idx=None):
    with open(file, "r") as f:
        wished = json.load(f)

    if end_idx is None:
        end_idx = len(wished)
    pbar = tqdm.tqdm(wished[start_idx:end_idx])
    selected = []
    for w in pbar:
        data_id = os.path.join(w.split("/")[-2], w.split("/")[-1].split(".")[0])
        file_path = os.path.join(data_dir, data_id + ".h5")
        print(file_path)
        pbar.set_description(f"Processing: {data_id}")
        pbar.set_postfix({"Selected": len(selected)})

        with h5py.File(file_path, "r") as file:
            vec_deepcad = file["out_vec"]
            vec_gt = file["ground_truth"]
            vec_deepcad = remove_padding(vec_deepcad)
            vec_gt = remove_padding(vec_gt)
            ext_count = get_ext_count(vec_gt)
            if ext_count < allowed_ext_count:
                continue

            selected.append(data_id)
            try:
                part_gt, com_def_gt = add_part_document(
                    app, data_id.replace("\\", "_") + "_gt"
                )
                cad_seq_gt = CADSequence.from_vector(vec_gt, is_numerical=True, n=256)
                seq_gt = cad_seq_gt.seq
                create_inventor_model_from_sequence(seq_gt, com_def=com_def_gt)
                app.ActiveView.Fit()
            except Exception as e:
                print("Error:", e, file_path)
                part_gt.Close(True)
                continue

        
            our_file = os.path.join( 'data/test_deepcad_cad_vec_NAT', data_id + ".h5")
            with h5py.File(our_file, "r") as f:
                vec_ours = f["out_vec"]
                vec_ours = remove_padding(vec_ours)
                try:
                    part_ours, com_def_ours = add_part_document(
                        app, data_id.replace("\\", "_") + "_o"
                    )
                    cad_seq_ours = CADSequence.from_vector(vec_ours, is_numerical=True, n=256)
                    seq_ours = cad_seq_ours.seq
                    create_inventor_model_from_sequence(seq_ours, com_def=com_def_ours)
                except:
                    print("Error:", file_path)
                    part_ours.Close(True)
                    continue
            try:
                    part, com_def = add_part_document(
                        app, data_id.replace("\\", "_") + "_deepcad"
                    )
                    cad_seq = CADSequence.from_vector(vec_deepcad, is_numerical=True, n=256)
                    seq = cad_seq.seq
                    create_inventor_model_from_sequence(seq, com_def=com_def)
            except Exception as e:
                    print("Error:", e, file_path)
                    part.Close(True)
         


if __name__ == "__main__":
    app = get_inventor_application()
    app.Visible = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data/test_deepcad_cad_vec_PC")

    args = parser.parse_args()
    data_dir = args.data_dir
    save_dir = 'F:/inventor'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # You can now specify start_idx and end_idx for cherry_pick, e.g.:
    cherry_pick(app, args.data_dir, 'data/wished.json', start_idx=600, end_idx=700)
