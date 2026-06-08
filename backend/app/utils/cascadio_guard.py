"""Avoid loading cascadio in the same process as pythonOCC (Windows DLL clash)."""

from __future__ import annotations

import importlib.util


def cascadio_installed() -> bool:
    """Check package presence without importing (importing loads conflicting OCCT DLLs)."""
    return importlib.util.find_spec("cascadio") is not None


def cascadio_usable_with_occ() -> bool:
    from app.occ import occ_available

    return cascadio_installed() and not occ_available()
