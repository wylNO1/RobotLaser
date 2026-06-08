"""Detect pythonOCC without importing it (import loads OCCT DLLs)."""

from __future__ import annotations

import importlib.util


def occ_installed() -> bool:
    return importlib.util.find_spec("OCC") is not None
