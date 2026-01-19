# 1) 词表：键ID与离散值ID
KEY = {
    "BOS": 1,
    "EOS": 2,
    "INS_B": 3,
    "INS_E": 4,
    "TYPE": 10,
    "IDX": 11,
    "PARENT": 12,
    "OP": 13,

    "DIR": 14,
    #plane definition
    "OX": 20,
    "OY": 21,
    "OZ": 22,
    "NX": 23,
    "NY": 24,
    "NZ": 25,
    "XX": 26,
    "XY": 27,
    "XZ": 28,
    "YX": 29,
    "YY": 30,
    "YZ": 31,
    "REFER_PLANE_IDX": 32,
    # sketch entities
    "PX":38,
    "PY":39,
    "SPX": 40,
    "SPY": 41,
    "EPX": 42,
    "EPY": 43,
    "CX": 44,
    "CY": 45,
    "R": 46,
    "SA": 47,
    "SW": 48,
    #DistanceExtentWrapper
    "DIST": 49,
    #Selection
    "SELECT_ENTITY": 51,
    #face/edge metadata
    "AREA": 52,
    "SURF_TYPE": 53,
    "EDGE_TYPE": 54,
    "FACE_CENTROID_X": 55,
    "FACE_CENTROID_Y": 56,
    "FACE_CENTROID_Z": 57,
    "EDGE_LENGTH": 58,
    "EDGE_MIDPOINT_X": 59,
    "EDGE_MIDPOINT_Y": 60,
    "EDGE_MIDPOINT_Z": 61,
    "EDGE_START_X": 62,
    "EDGE_START_Y": 63,
    "EDGE_START_Z": 64,
    "EDGE_END_X": 65,
    "EDGE_END_Y": 66,
    "EDGE_END_Z": 67,
    #AngleExtentWrapper
    "ANGLE": 70,
    #ToExtentWrapper
    "TOFACE_ID": 71,
    "IS_EXTEND_TO_FACE": 72,
    #FromToExtentWrapper
    "IS_EXTEND_FROM_FACE": 73,
    "FROMFACE_ID": 74,
    #Extrude specific
    "EXTENT_ONE": 100,
    "EXTENT_ONE_TYPE": 101,
    "EXTENT_TWO": 102,
    "EXTENT_TWO_TYPE": 103,
    "ISTWO_DIRECTIONAL": 104,
    #Revolve specific
    "AXIS_X": 120,
    "AXIS_Y": 121,
    "AXIS_Z": 122,
    "AXIS_DIR_X": 123,
    "AXIS_DIR_Y": 124,
    "AXIS_DIR_Z": 125,
    #Fillet specific
    "RADIUS": 140,
    "FILLET_EDGE_IDX": 141,
    #Chamfer specific
    "CHAMFER_TYPE": 160,
    "CHAMFER_DIST_A": 161,
    "CHAMFER_DIST_B": 162,
    "CHAMFER_ANGLE": 163,
    "CHAMFER_FACE_IDX": 164,
    "CHAMFER_EDGE_IDX": 165,
    #Hole specific
    "DIAMETER": 180,
    "DEPTH": 181,
    "IS_FLAT_BOTTOM": 182,
    "BOTTOM_TIP_ANGLE": 183,
    "HOLE_EXTENT": 184,
    #Shell specific
    "SHELL_THICKNESS": 200,
    "SHELL_DIRECTION": 201,
    "SHELL_FACE_IDX": 202,
    #Mirror specific
    "IS_MIRROR_BODY": 220,
    "MIRROR_FEATURE_IDX": 221,
    "MIRROR_PLANE_OX": 222,
    "MIRROR_PLANE_OY": 223,
    "MIRROR_PLANE_OZ": 224,
    "MIRROR_PLANE_NX": 225,
    "MIRROR_PLANE_NY": 226,
    "MIRROR_PLANE_NZ": 227,
    "REMOVE_ORIGINAL": 228,
    #RectangularPattern specific
    "RECT_X_COUNT": 240,
    "RECT_X_SPACING": 241,
    "RECT_IS_PATTERN_BODY": 242,
    "RECT_IS_NARTURE_X_DIR": 243,
    "RECT_X_SPACING_TYPE": 244,
    "RECT_X_DIR_X": 248,
    "RECT_X_DIR_Y": 249,
    "RECT_X_DIR_Z": 250,
    "RECT_FEATURE_IDX": 251,
    "RECT_PATTERN_SPACING_TYPE": 252,
    #CircularPattern specific
    "CIRC_IS_PATTERN_BODY": 260,
    "CIRC_COUNT": 261,
    "CIRC_ANGLE": 262,
    "CIRC_NATURAL_DIR": 263,
    "CIRC_AXIS_DIR_X": 264,
    "CIRC_AXIS_DIR_Y": 265,
    "CIRC_AXIS_DIR_Z": 266,
    "CIRC_AXIS_OX": 267,
    "CIRC_AXIS_OY": 268,
    "CIRC_AXIS_OZ": 269,
    "CIRC_FEATURE_IDX": 270,
    





}

SURFACE_TYPE_ID = {
    "kBSplineSurface": 0,
    "kCoonsSurface": 1,
    "kConeSurface": 2,
    "kCylinderSurface": 3,
    "kEllipticalConeSurface": 4,
    "kEllipticalCylinderSurface": 5,
    "kPlaneSurface": 6,
    "kSphereSurface": 7,
    "kTorusSurface": 8,
    "kUnknownSurface": 9,
}
EDGE_TYPE_ID = {
    "kBSplineCurve": 0,
    "kCircleCurve": 1,
    "kCircularArcCurve": 2,
    "kEllipseFullCurve": 3,
    "kEllipticalArcCurve": 4,
    "kLineCurve": 5,
    "kLineSegmentCurve": 6,
    "kPolylineCurve": 7,
    "kUnknownCurve": 8,
}

ENTITY_ID = {
    "Face": 1,
    "Edge": 2,
}


TYPE_ID = {
    "SketchStart": 1,
    "Line": 2,
    "Arc": 3,
    "Circle": 4,
    "Point": 5,
    "SketchEnd": 9,
    "Extrude": 10,
    "Revolve": 11,
    "Chamfer": 12,
    "Fillet": 13,
    "Hole": 14,
    "Shell": 15,
    "Mirror": 16,
    "RectPattern": 17,
    "CircularPattern": 18,
    "Selection": 19,
    "Extent": 20,
}

OP_ID = {
    "kNewBodyOperation": 0,
    "kJoinOperation": 1,
    "kCutOperation": 2,
    "kIntersectOperation": 3,
}

DIR_ID = {
    "kPositiveExtentDirection": 1,
    "kNegativeExtentDirection": -1,
    "kSymmetricExtentDirection": 0,
}
EXTENT_ID = {
    "kDistanceExtent": 0,
    "kToNextExtent": 1,
    "kAngleExtent": 2,
    "kToExtent": 3,
    "kFullSweepExtent": 4,
    "kThroughAllExtent": 5,
    "kFromToExtent": 6,
}

SHELL_DIR_ID = {
    "kBothSidesShellDirection": 0,
    "kInsideShellDirection": 1,
    "kOutsideShellDirection": 2,
}

CHAMFER_TYPE_ID = {
    "kTwoDistances": 0,
    "kDistanceAndAngle": 1,
    "kDistance" : 2,
}

PATTERN_SPACING_TYPE_ID = {
    "kDefault": 0,
    "kFitted":1,
    "kFitToPathLength":2,
}
