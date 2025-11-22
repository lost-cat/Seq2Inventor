from functools import lru_cache
from typing import Optional
from win32com.client import constants


@lru_cache(maxsize=1)
def _constants_reverse_index():
    def _collect():
        idx_local = {}
        try:
            dicts = getattr(constants, "__dicts__")
        except Exception:
            dicts = []
        for d in dicts or []:
            try:
                items = d.items()
            except Exception:
                continue
            for name, val in items:
                if not isinstance(name, str) or not name.startswith("k"):
                    continue
                if isinstance(val, bool):
                    continue
                if not isinstance(val, int):
                    try:
                        import numbers

                        if not isinstance(val, numbers.Integral):
                            continue
                    except Exception:
                        continue
                idx_local.setdefault(val, set()).add(name)
        return idx_local

    idx = _collect()
    if not idx:
        try:
            from win32com.client import gencache

            try:
                gencache.EnsureDispatch("Inventor.Application")
            except Exception:
                pass
        except Exception:
            pass
        idx = _collect()
    return {k: sorted(v) for k, v in idx.items()}


def enum_names(value, prefix=None, suffix=None, contains=None):
    names = _constants_reverse_index().get(value, [])
    if prefix:
        names = [n for n in names if n.startswith(prefix)]
    if suffix:
        names = [n for n in names if n.endswith(suffix)]
    if contains:
        names = [n for n in names if contains in n]
    return names


def enum_name(value, prefix=None, suffix=None, contains=None, default=None):
    names = enum_names(value, prefix=prefix, suffix=suffix, contains=contains)
    if names:
        return names[0]
    return default


def object_type_name(value):
    return enum_name(value, suffix="Object")


def operation_name(value):
    return enum_name(value, suffix="Operation")


def extent_direction_name(value):
    return enum_name(value, suffix="ExtentDirection")


def extent_type_name(value):
    return enum_name(value, suffix="Extent") or enum_name(value, suffix="ExtentType")


def map_values_to_names(values, *, prefix=None, suffix=None, contains=None):
    return {v: enum_name(v, prefix=prefix, suffix=suffix, contains=contains) for v in values}


def is_type_of(entity, class_name: str) -> bool:
    """Check if the given COM object is of the specified class."""
    try:
        obj_class_name = entity.Type 
        class_name = 'k' + class_name + 'Object'
        return enum_name(obj_class_name) == class_name
    except Exception:
        raise ValueError("Failed to get the Type of the entity.")
        return False
    

def _const(name: Optional[str], fallback: Optional[int] = None) -> Optional[int]:
    if not name:
        print(f"[const] Missing name; returning fallback {fallback}")
        return fallback
    return getattr(constants, name, fallback)