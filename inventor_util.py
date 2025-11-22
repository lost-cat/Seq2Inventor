"""
Backward-compatibility facade for the legacy `inventor_util` module.
It re-exports the public API from the new `inventor_utils` package.
"""

# Re-export everything defined by inventor_utils' public API
from inventor_utils import *  # noqa: F401,F403
from inventor_utils import __all__ as _INVENTOR_UTILS_ALL

__all__ = list(_INVENTOR_UTILS_ALL)
