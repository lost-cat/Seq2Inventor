import argparse
import glob
import json
import os
import sys
import h5py
import tqdm

from cad_utils.extrude import CADSequence
from cad_utils.macro import EXT_IDX
from inventor_util import *

#
#
# p1 = transient_point_2d(app, 0, 0)
# p2 = transient_point_2d(app, 1, 0)
# p3 = transient_point_2d(app, 1, 1)
# p4 = transient_point_2d(app, 0, 1)
#
# line1 = add_sketch2d_line(sketch_inventor, p1, p2)
# line2 = add_sketch2d_line(sketch_inventor, line1.EndSketchPoint, p3)
# line3 = add_sketch2d_line(sketch_inventor, line2.EndSketchPoint, p4)
# line4 = add_sketch2d_line(sketch_inventor, line3.EndSketchPoint, p1)
# line4.EndSketchPoint.Merge(line1.StartSketchPoint)
# profile = add_profile(sketch_inventor)
# ext_def = create_extrude_definition(com_def, profile, 3, ExtrudeType.NewBody,
#                                     ExtrudeDirection.Positive)
# feature = add_extrude_feature(com_def, ext_def)


# file = h5py.File('data/predict_fusion360_cad_vec/20591_20e06209_0000.h5', 'r')
# # vec = remove_padding(file['ground_truth'])
# vec_out = remove_padding(file['out_vec'])

# # cad = CADSequence.from_vector(vec, is_numerical=True, n=256)
# # seq = cad.seq
# cad_out = CADSequence.from_vector(vec_out, is_numerical=True, n=256)
# seq_out = cad_out.seq


# # part_gt = create_inventor_model_from_sequence(seq, app)
# #

# part_out = create_inventor_model_from_sequence(seq_out, app)
# app.ActiveView.Fit()


# input("Press Enter to continue...")
# part_out.Close(True)
# file.close()



def load_vec(file_path,b_remove_padding=True,b_return_gt=False):
    with h5py.File(file_path, "r") as file:
        vec = file["out_vec"]
        if b_remove_padding:
            vec = remove_padding(vec)

        if b_return_gt:
            vec_gt = file["ground_truth"]
            if b_remove_padding:
                vec_gt = remove_padding(vec_gt)
            return vec,vec_gt
    return vec
    pass



def IR_check(app,file_paths):
    valid_count = 0
    total_count = 0
    pbar = tqdm.tqdm(file_paths)
    for file_path in pbar:
        vec,vec_gt = load_vec(file_path,b_return_gt=True)
        data_id =   os.path.join(file_path.split('/')[-2],file_path.split('/')[-1].split('.')[0]) 
        part, com_def = add_part_document(app,data_id+'out')
        try:
            cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
            seq = cad_seq.seq
            create_inventor_model_from_sequence(seq, com_def=com_def)
            valid_count += 1
            part.Close(True)
        except Exception as e:
            
            print("Error:", e, file_path)
            part.Close(True)
        total_count += 1
        pbar.set_description(f"Valid: {valid_count}, Total: {total_count}")
    return valid_count, total_count


def single_debug(app,file_path):
    with h5py.File(file_path, "r") as file:
        vec = file["out_vec"]
        vec_gt = file["ground_truth"]
        vec = remove_padding(vec)
        vec_gt = remove_padding(vec_gt)
        data_id =   os.path.join(file_path.split('/')[-2],file_path.split('/')[-1].split('.')[0]) 
        part, com_def = add_part_document(app,data_id+'out')
        cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
        cad_seq
        seq = cad_seq.seq
        create_inventor_model_from_sequence(seq, com_def=com_def)
        app.ActiveView.Fit()
        # input("Press Enter to continue...")
        # part.Close(True)

def IR_CACAL(app,data_dir):

    file_paths = glob.glob(os.path.join(data_dir, "**/*.h5"), recursive=True)
    file_paths= ['data/test_deepcad_cad_vec_NAT/0098/00980343.h5']
    single_debug(file_paths[0])
    sys.exit()
    valid_count, total_count = IR_check(app,file_paths)
    print(f"Valid: {valid_count}, Total: {total_count}")
    IR = valid_count / total_count
    print(f"IR: {IR}")


def get_ext_count(vec):
    commands  = vec[:, 0]
    ext_count = (commands == EXT_IDX).sum()
    return ext_count




def cherry_pick(app,data_dir,file ,allowed_ext_count=3):
    with open(file, 'r') as f:
        wished = json.load(f)

    pbar  = tqdm.tqdm(wished)
    selected = []
    for w in pbar:
        data_id =   os.path.join(w.split('/')[-2],w.split('/')[-1].split('.')[0])
        file_path = os.path.join(data_dir, data_id+'.h5')
        print(file_path)
        pbar.set_description(f"Processing: {data_id}")
        pbar.set_postfix({"Selected": len(selected)})

        with h5py.File(file_path, "r") as file:
            vec = file["out_vec"]
            vec_gt = file["ground_truth"]
            vec = remove_padding(vec)
            vec_gt = remove_padding(vec_gt)
            ext_count = get_ext_count(vec)
            if ext_count < allowed_ext_count:
                continue

            selected.append(data_id)

            
            try:
                part, com_def = add_part_document(app, data_id.replace('\\', '_')+'_out')
                cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
                seq = cad_seq.seq
                create_inventor_model_from_sequence(seq, com_def=com_def)   
            except Exception as e:
                print("Error:", e, file_path)
                part.Close(True)

            try:
                part_gt, com_def_gt = add_part_document(app, data_id.replace('\\', '_')+'_gt')
                cad_seq_gt = CADSequence.from_vector(vec_gt, is_numerical=True, n=256)
                seq_gt = cad_seq_gt.seq
                create_inventor_model_from_sequence(seq_gt, com_def=com_def_gt)
                app.ActiveView.Fit()
            except Exception as e:
                print("Error:", e, file_path)
                part_gt.Close(True)
   

if __name__ == "__main__":
    app = get_inventor_application()
    app.Visible = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data/test_deepcad_cad_vec_PC")

    args = parser.parse_args()
    data_dir = args.data_dir
    single_debug(app=app,file_path=os.path.join(data_dir,'0004/00045203.h5'))
    # cherry_pick(app,args.data_dir,'data/wished.json')
