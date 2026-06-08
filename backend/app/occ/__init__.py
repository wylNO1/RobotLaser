"""pythonOCC-based CAD topology utilities (optional dependency)."""

from __future__ import annotations


def occ_available() -> bool:
    try:
        import OCC  # noqa: F401

        return True
    except ImportError:
        return False
