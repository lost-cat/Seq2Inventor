import h5py

from cad_utils.extrude import CADSequence
from inventor_util import *

app = get_inventor_application()
app.Visible = True
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


file = h5py.File('data/predict_fusion360_cad_vec/20591_20e06209_0000.h5', 'r')
# vec = remove_padding(file['ground_truth'])
vec_out = remove_padding(file['out_vec'])

# cad = CADSequence.from_vector(vec, is_numerical=True, n=256)
# seq = cad.seq
cad_out = CADSequence.from_vector(vec_out, is_numerical=True, n=256)
seq_out = cad_out.seq


# part_gt = create_inventor_model_from_sequence(seq, app)
#

part_out = create_inventor_model_from_sequence(seq_out, app)

