"""Generate glTF/GLB from URDF primitives and mesh files."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from app.services.urdf_parser import MeshResolver, _find_child, _parse_origin, _text_vec3


def mesh_to_glb(mesh: trimesh.Trimesh) -> bytes:
    from app.utils.glb_export import trimesh_to_glb_bytes

    return trimesh_to_glb_bytes(mesh)


def geometry_to_mesh_bytes(
    geom: ET.Element | None, resolver: MeshResolver
) -> tuple[str, dict[str, Any], bytes | None]:
    """Returns (geometry_kind, params, glb_bytes or None)."""
    if geom is None:
        return "none", {}, None

    box = _find_child(geom, "box")
    if box is not None:
        size = _text_vec3(box.get("size"), [1.0, 1.0, 1.0])
        if len(size) != 3:
            size = [1.0, 1.0, 1.0]
        m = trimesh.creation.box(extents=size)
        glb = mesh_to_glb(m)
        return "box", {"size": size}, glb

    cyl = _find_child(geom, "cylinder")
    if cyl is not None:
        r = float(cyl.get("radius") or 1.0)
        h = float(cyl.get("length") or 1.0)
        m = trimesh.creation.cylinder(radius=r, height=h)
        glb = mesh_to_glb(m)
        return "cylinder", {"radius": r, "length": h}, glb

    sph = _find_child(geom, "sphere")
    if sph is not None:
        r = float(sph.get("radius") or 1.0)
        m = trimesh.creation.icosphere(radius=r)
        glb = mesh_to_glb(m)
        return "sphere", {"radius": r}, glb

    mesh_el = _find_child(geom, "mesh")
    if mesh_el is not None:
        fn = mesh_el.get("filename") or ""
        scale = _text_vec3(mesh_el.get("scale"), [1.0, 1.0, 1.0])
        if len(scale) != 3:
            scale = [1.0, 1.0, 1.0]
        raw = resolver.resolve(fn)
        if raw is None:
            return "mesh", {"filename": fn, "scale": scale, "missing": True}, None
        try:
            loaded = trimesh.load(io.BytesIO(raw), file_type=Path(fn).suffix.lower().lstrip("."))
            meshes: list[trimesh.Trimesh] = []
            if isinstance(loaded, trimesh.Scene):
                for g in loaded.geometry.values():
                    if isinstance(g, trimesh.Trimesh):
                        meshes.append(g)
            elif isinstance(loaded, trimesh.Trimesh):
                meshes.append(loaded)
            if not meshes:
                return "mesh", {"filename": fn, "scale": scale, "error": "empty"}, None
            if len(meshes) == 1:
                m = meshes[0]
            else:
                m = trimesh.util.concatenate(meshes)
            sm = np.diag(scale + [1.0])
            m.apply_transform(sm)
            glb = mesh_to_glb(m)
            return "mesh", {"filename": fn, "scale": scale}, glb
        except Exception as e:  # noqa: BLE001
            return "mesh", {"filename": fn, "scale": scale, "error": str(e)}, None

    return "unknown", {}, None
