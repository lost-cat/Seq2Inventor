from typing import Any, Optional

key_context = None


def get_reference_key_str(entity):
    global key_context
    part = entity.Application.ActiveDocument
    reference_manager = part.ReferenceKeyManager
    if key_context is None:
        key_context = reference_manager.CreateKeyContext()
    key = get_reference_key(entity, key_context)
    key_str = get_string_reference_key(key, reference_manager)
    return key_str


def get_entity_by_reference_key(doc, key, key_context):
    entity = None
    context = None
    status, _, entity, context = doc.ReferenceKeyManager.CanBindKeyToObject(
        key, key_context, entity, context
    )
    if status:
        return entity
    else:
        return context


def get_string_reference_key(reference_key, reference_key_manager):
    string, location = reference_key_manager.KeyToString(reference_key)
    return string


def get_reference_key(entity, key_context):
    key = []
    key = entity.GetReferenceKey(key, key_context)
    return key


def get_face_by_transient_key(com_def, key):
    faces = com_def.SurfaceBodies.Item(1).Faces
    for i in range(1, faces.Count + 1):
        face = faces.Item(i)
        if face.TransientKey == key:
            return face
    return None


def get_edge_by_transient_key(com_def, key):
    edges = com_def.SurfaceBodies.Item(1).Edges
    for i in range(1, edges.Count + 1):
        edge = edges.Item(i)
        if edge.TransientKey == key:
            return edge
    return None
