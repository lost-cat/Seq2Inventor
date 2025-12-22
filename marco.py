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
    # sketch entities
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
    "SketchEnd": 5,
    "Extrude": 10,
    "Revolve": 11,
    "Chamfer": 12,
    "Fillet": 13,
    "Hole": 14,
    "Selection": 15,
    "Extent": 16,
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
