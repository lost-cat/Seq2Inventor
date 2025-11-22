from typing import Optional, Any

from .metadata import collect_face_metadata, collect_edge_metadata, is_face_meta_similar, is_edge_meta_similar
from .reference import get_reference_key_str
from .sorting import stable_sorted_bodies, stable_sorted_edges, stable_sorted_faces


class EntityIndexHelper:
    def __init__(self, com_def):
        self.com_def = com_def
        self.key_manager = com_def.Application.ActiveDocument.ReferenceKeyManager
        self.key_context = self.key_manager.CreateKeyContext()
        self.cached_face_meta_map = {}
        self.cached_edge_meta_map = {}
        self.type2faceDict = {}
        self.type2EdgeDict = {}

    def update_all(self):
        surface_bodies = self.com_def.SurfaceBodies
        if surface_bodies.Count != 1:
            raise ValueError("Only single body parts are supported for caching")
        body = surface_bodies.Item(1)
        faces = body.Faces
        edges = body.Edges
        self.cached_face_meta_map.clear()
        self.cached_edge_meta_map.clear()
        for i in range(1, faces.Count + 1):
            face = faces.Item(i)
            face_key = self.get_entity_key(face)
            face_meta = collect_face_metadata(face)
            self.cached_face_meta_map[face_key] = {"meta": face_meta, "valid": True, "face": face}

        for i in range(1, edges.Count + 1):
            edge = edges.Item(i)
            edge_key = self.get_entity_key(edge)
            edge_meta = collect_edge_metadata(edge)
            self.cached_edge_meta_map[edge_key] = {"meta": edge_meta, "valid": True, "edge": edge}

        self.build_type_dicts()

    def build_type_dicts(self):
        self.type2faceDict.clear()
        self.type2EdgeDict.clear()
        for key, value in self.cached_face_meta_map.items():
            if not value["valid"]:
                continue
            face_type = value["meta"].get("surfaceType")
            if face_type not in self.type2faceDict:
                self.type2faceDict[face_type] = []
            self.type2faceDict[face_type].append((key, value["meta"]))

        for key, value in self.cached_edge_meta_map.items():
            if not value["valid"]:
                continue
            edge_type = value["meta"].get("geometryType")
            if edge_type not in self.type2EdgeDict:
                self.type2EdgeDict[edge_type] = []
            self.type2EdgeDict[edge_type].append((key, value["meta"]))

    def mark_cache_invalid(self):
        for key in self.cached_face_meta_map:
            self.cached_face_meta_map[key]["valid"] = False
        for key in self.cached_edge_meta_map:
            self.cached_edge_meta_map[key]["valid"] = False

    def select_face_by_meta(self, face_meta):
        target_surface_type = face_meta.get("surfaceType")
        candidates = self.type2faceDict.get(target_surface_type, [])
        selected_key = None
        for key, meta in candidates:
            ok, reason = is_face_meta_similar(face_meta, meta)
            if ok:
                selected_key = key
            else:
                print(f"[debug] Face meta not similar: {reason}")
        if selected_key is None:
            raise ValueError("No matching face found")
        return self.cached_face_meta_map[selected_key]["face"]

    def select_edge_by_meta(self, edge_meta):
        target_edge_type = edge_meta.get("geometryType")
        candidates = self.type2EdgeDict.get(target_edge_type, [])
        selected_key = None
        failed_reasons = []
        for key, meta in candidates:
            ok, reason = is_edge_meta_similar(edge_meta, meta)
            if ok:
                selected_key = key
            else:
                failed_reasons.append(reason)
        if selected_key is None:
            print(f"[debug] Edge meta not similar reasons: {failed_reasons}")
            raise ValueError("No matching edge found")
        return self.cached_edge_meta_map[selected_key]["edge"]

    def get_entity_key(self, entity):
        from .reference import get_reference_key, get_string_reference_key

        key = get_reference_key(entity, self.key_context)
        key_str = get_string_reference_key(key, self.key_manager)
        return key_str

    def get_entity_by_key(self, key_str):
        from .reference import get_entity_by_reference_key

        key = self.key_manager.StringToKey(key_str)
        # return entity


def pick_edge_by_stable_ranks(
    feature,
    stable_body_rank: int,
    stable_edge_rank: int,
    tol: float = 1e-3,
    entity_index_helper: Optional[EntityIndexHelper] = None,
):
    bodies_sorted = stable_sorted_bodies(feature, tol)
    if not bodies_sorted or stable_body_rank < 1 or stable_body_rank > len(bodies_sorted):
        return None
    body = bodies_sorted[stable_body_rank - 1]
    edges_sorted = stable_sorted_edges(body, tol)
    if not edges_sorted or stable_edge_rank < 1 or stable_edge_rank > len(edges_sorted):
        return None
    return edges_sorted[stable_edge_rank - 1]


def pick_face_by_stable_ranks(
    feature,
    stable_body_rank: int,
    stable_face_rank: int,
    tol: float = 1e-3,
    entity_index_helper: Optional[EntityIndexHelper] = None,
):
    bodies_sorted = stable_sorted_bodies(feature, tol)
    if not bodies_sorted or stable_body_rank < 1 or stable_body_rank > len(bodies_sorted):
        return None
    body = bodies_sorted[stable_body_rank - 1]
    faces_sorted = stable_sorted_faces(body, tol)
    if not faces_sorted or stable_face_rank < 1 or stable_face_rank > len(faces_sorted):
        return None
    return faces_sorted[stable_face_rank - 1]


def index_edge(edge, entity_index_helper: Optional[EntityIndexHelper] = None) -> dict:
    surface_body = edge.Parent
    edge_rank = -1
    sorted_edges = stable_sorted_edges(surface_body, 1e-3)
    target_key = edge.TransientKey
    for idx, e in enumerate(sorted_edges, start=1):
        key1 = e.TransientKey
        if key1 == target_key:
            edge_rank = idx
            break

    created_by_feature = surface_body.CreatedByFeature
    surface_body_rank = -1
    sorted_bodies = stable_sorted_bodies(created_by_feature, 1e-3)
    for idx, b in enumerate(sorted_bodies, start=1):
        if get_reference_key_str(b) == get_reference_key_str(surface_body):
            surface_body_rank = idx
            break

    if surface_body_rank == -1 or edge_rank == -1:
        print(
            f"Warning: Could not find edge rank or surface body rank for edge in feature {created_by_feature.Name}"
        )
    return {
        "surfaceBodyRank": surface_body_rank,
        "edgeRank": edge_rank,
        "featureName": created_by_feature.Name,
    }


def index_face(face, entity_index_helper: Optional[EntityIndexHelper] = None) -> dict:
    surface_body = face.Parent
    face_rank = -1
    sorted_faces = stable_sorted_faces(surface_body, 1e-3)
    target_key = face.TransientKey
    for idx, f in enumerate(sorted_faces, start=1):
        key1 = f.TransientKey
        if key1 == target_key:
            face_rank = idx
            break

    surface_body_rank = -1
    created_by_feature = surface_body.CreatedByFeature
    sorted_bodies = stable_sorted_bodies(created_by_feature, 1e-3)
    for idx, b in enumerate(sorted_bodies, start=1):
        if get_reference_key_str(b) == get_reference_key_str(surface_body):
            surface_body_rank = idx
            break

    if surface_body_rank == -1 or face_rank == -1:
        print(
            f"Warning: Could not find face index or surface body index for face in feature {created_by_feature.Name}"
        )
    return {
        "surfaceBodyRank": surface_body_rank,
        "faceRank": face_rank,
        "featureName": created_by_feature.Name,
    }


def get_face_by_index(com_def, face_index, entity_index_helper=None) -> Optional[Any]:
    try:
        feature = get_feature_by_name(com_def, face_index["featureName"])  # noqa: F821
        if not feature:
            return None
        body_rank = face_index["surfaceBodyRank"]
        face_rank = face_index["faceRank"]
        face = pick_face_by_stable_ranks(
            feature,
            stable_body_rank=body_rank,
            stable_face_rank=face_rank,
            entity_index_helper=entity_index_helper,
        )
        return face
    except Exception as e:
        print(f"Error in get_face_by_index: {e}")
        return None


def get_edge_by_index(com_def, edge_index, entity_index_helper=None) -> Optional[Any]:
    try:
        feature = get_feature_by_name(com_def, edge_index["featureName"])  # noqa: F821
        if not feature:
            return None
        body_rank = edge_index["surfaceBodyRank"]
        edge_rank = edge_index["edgeRank"]
        edge = pick_edge_by_stable_ranks(
            feature,
            stable_body_rank=body_rank,
            stable_edge_rank=edge_rank,
            entity_index_helper=entity_index_helper,
        )
        return edge
    except Exception as e:
        print(f"Error in get_edge_by_index: {e}")
        return None


def get_feature_by_name(com_def, feature_name):
    """
    通过feature的名字获取feature对象
    Args:
        com_def: Inventor ComponentDefinition 对象
        feature_name: feature的名字
    Returns:
        feature: Inventor Feature 对象,如果没有找到则返回None
    """
    features = com_def.Features
    for i in range(1, features.Count + 1):
        feature = features.Item(i)
        if feature.Name == feature_name:
            return feature
    return None
