"""Load mesh / CAD into `trimesh` scenes."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import trimesh

from app.utils.glb_export import trimesh_to_glb_bytes


def load_trimesh_from_bytes(data: bytes, *, filename_hint: str, file_type: str | None = None) -> Any:
    """
    Load geometry using trimesh. `file_type` overrides extension detection
    (e.g. ``'stp'`` for STEP without a filename).
    """
    ext = file_type
    if ext is None:
        ext = Path(filename_hint).suffix.lower().lstrip(".") or None
    if not ext:
        raise ValueError("cannot infer file_type; pass file_type explicitly")
    return trimesh.load(io.BytesIO(data), file_type=ext)


def to_glb_bytes(loaded: Any) -> bytes:
    """Export Trimesh/Scene to GLB with fixed normals and CAD material."""
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("empty scene")
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        mesh = trimesh.Trimesh(loaded)
    return trimesh_to_glb_bytes(mesh)
