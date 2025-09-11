from inventor_util import (
    ExtrudeDirection,
    ExtrudeType,
    add_chamfer_feature,
    add_extrude_feature,
    add_fillet_feature,
    add_part_document,
    add_profile,
    add_sketch,
    add_sketch2d_circle,
    add_sketch2d_line,
    add_work_plane,
    create_extrude_definition,
    get_face_area,
    filter_face_by_normal_and_centroid,
    get_face_centroid,
    get_face_normal,
    get_inventor_application,
    transient_point_2d,
)

reference_key_content = None

if __name__ == "__main__":

    app = get_inventor_application()
    app.Visible = True
    part, com_def = add_part_document(app, "test")
    reference_key_content = part.ReferenceKeyManager.CreateKeyContext()
    p1 = transient_point_2d(app, 0, 0)
    p2 = transient_point_2d(app, 1, 0)
    p3 = transient_point_2d(app, 1, 1)
    p4 = transient_point_2d(app, 0, 1)
    p5 = transient_point_2d(app, 0.5, 0.5)
    plane = add_work_plane(com_def, (0, 0, 0), (1, 0, 0), (0, 1, 0))
    plane.Visible = False
    sketch_inventor = add_sketch(com_def, plane)
    line1 = add_sketch2d_line(sketch_inventor, p1, p2)
    line2 = add_sketch2d_line(sketch_inventor, line1.EndSketchPoint, p3)
    line3 = add_sketch2d_line(sketch_inventor, line2.EndSketchPoint, p4)
    line4 = add_sketch2d_line(sketch_inventor, line3.EndSketchPoint, p5)
    line5 = add_sketch2d_line(sketch_inventor, line4.EndSketchPoint, p1)
    # line6 = add_sketch2d_line(sketch_inventor, line5.EndSketchPoint, p1)
    line5.EndSketchPoint.Merge(line1.StartSketchPoint)
    profile = add_profile(sketch_inventor)
    ext_def = create_extrude_definition(
        com_def, profile, 3, 0, ExtrudeType.NewBody, ExtrudeDirection.Positive
    )
    feature = add_extrude_feature(com_def, ext_def)


    EndFace = feature.EndFaces.Item(1)
    normal = get_face_normal(EndFace)

    print(normal)
    centroid = get_face_centroid(EndFace)
    print(centroid)
    area = get_face_area(EndFace)
    print(area)

    face = filter_face_by_normal_and_centroid(feature.Faces, normal, centroid)
    if face is not None:
        print(face.TransientKey)
    else:
        print("face not found")
   

    # Get the end face of the extrude feature
    start_face = feature.SideFaces.Item(2)
    print(f"pre edge count {start_face.Edges.Count}, key : {start_face.TransientKey}")

    # for i in range(1,start_face.Edges.Count + 1):
    #     print(start_face.Edges.Item(i).TransientKey)
    #     reference_key =  get_reference_key(start_face.Edges.Item(i),reference_key_content)
    #     print(part.ReferenceKeyManager.KeyToString(reference_key))
    #     entity  = get_entity_by_reference_key(part,reference_key,reference_key_content)
        # print(start_face.Edges.Item(i).StartVertex.Point)
        # print(start_face.Edges.Item(i).EndVertex.Point)

    new_sketch = add_sketch(com_def, start_face)

    # Add a new line to the new sketch
    new_p1 = transient_point_2d(app, 0.5, 0.5)

    new_circle= add_sketch2d_circle(new_sketch, new_p1, 0.4)
    profile1 = add_profile(new_sketch)
    ext_def1 = create_extrude_definition(com_def, profile1, 2,0, ExtrudeType.Cut,
                                        ExtrudeDirection.Negative)
    feature1 = add_extrude_feature(com_def, ext_def1)
    print(face.TransientKey)
    print(feature1.SideFaces.Count)
    print(feature1.StartFaces.Count)
    print(f"after edge count {start_face.Edges.Count}, key : {start_face.TransientKey}")
    # # print(feature1.SideFaces.Item(1).TransientKey)
    # for i in range(1,start_face.Edges.Count + 1):
    #     print(start_face.Edges.Item(i).TransientKey)
    #     reference_key = []
    #     reference_key = start_face.Edges.Item(i).GetReferenceKey(reference_key,reference_key_content)
    #     print(part.ReferenceKeyManager.KeyToString(reference_key))
        # print(start_face.Edges.Item(i).StartVertex.Point)
        # print(start_face.Edges.Item(i).EndVertex.Point)


  
    # print(feature1.Faces.Count)
    start_face2 = feature.EndFaces.Item(1)

    # Create a new sketch on the end face
    new_sketch2 = add_sketch(com_def, start_face2)

    # Add a new circle to the new sketch

    new_circle2= add_sketch2d_circle(new_sketch2, new_p1, 0.3)
    profile2 = add_profile(new_sketch2)
    ext_def2 = create_extrude_definition(com_def, profile2, 1,0, ExtrudeType.NewBody,
                                        ExtrudeDirection.Positive)
    feature2 = add_extrude_feature(com_def, ext_def2)



    # print(feature2.EndFaces.Item(1).TransientKey)
    edge = feature2.EndFaces.Item(1).Edges.Item(1)

    feature3 = add_fillet_feature(com_def, edge, 0.1)
    # print(feature2.EndFaces.Item(1).TransientKey)

    print(feature2.StartFaces.Item(1).TransientKey)
    reference_key = []
    reference_key = feature2.StartFaces.Item(1).GetReferenceKey(reference_key,reference_key_content)
    print(part.ReferenceKeyManager.KeyToString(reference_key))
    edge = feature2.StartFaces.Item(1).Edges.Item(1)
    feature4 = add_chamfer_feature(com_def, edge, 0.1)
    print(feature2.StartFaces.Item(1).TransientKey)
    reference_key = []
    reference_key = feature2.StartFaces.Item(1).GetReferenceKey(reference_key,reference_key_content)
    print(part.ReferenceKeyManager.KeyToString(reference_key))
    pass
