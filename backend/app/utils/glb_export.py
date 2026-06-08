"""GLB export tuned for CAD: flat normals, double-sided, no erroneous vertex merging."""

from __future__ import annotations

import json
import struct
from typing import Any

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial


_CAD_PBR = PBRMaterial(
    baseColorFactor=[0.75, 0.78, 0.82, 1.0],
    metallicFactor=0.12,
    roughnessFactor=0.45,
    doubleSided=True,
)


def flat_shade_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    每个三角形独立顶点 + 面法向，避免共享边法线平均导致背面剔除异常。
    """
    if mesh.faces is None or len(mesh.faces) == 0:
        raise ValueError("empty mesh")

    verts = np.asarray(mesh.vertices[mesh.faces], dtype=np.float64).reshape(-1, 3)
    faces = np.arange(len(verts), dtype=np.int64).reshape(-1, 3)

    fn = np.asarray(mesh.face_normals, dtype=np.float64)
    norms = np.repeat(fn, 3, axis=0)

    out = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    out.vertex_normals = norms
    out.visual.material = _CAD_PBR
    return out


def _force_glb_double_sided(glb_bytes: bytes) -> bytes:
    """确保所有 material 的 doubleSided=true（部分查看器依赖此字段）。"""
    if len(glb_bytes) < 20 or glb_bytes[:4] != b"glTF":
        return glb_bytes
    try:
        from app.utils.raw_glb import pack_glb

        json_len = struct.unpack("<I", glb_bytes[12:16])[0]
        json_chunk = glb_bytes[20 : 20 + json_len]
        bin_off = 20 + json_len
        if bin_off + 8 > len(glb_bytes) or glb_bytes[bin_off + 4 : bin_off + 8] != b"BIN\x00":
            return glb_bytes
        bin_len = struct.unpack("<I", glb_bytes[bin_off : bin_off + 4])[0]
        bin_data = glb_bytes[bin_off + 8 : bin_off + 8 + bin_len]
        doc = json.loads(json_chunk.rstrip(b" \x00"))
        for mat in doc.get("materials", []):
            mat["doubleSided"] = True
        new_json = json.dumps(doc, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return pack_glb(new_json, bin_data)
    except Exception:
        return glb_bytes


def _assign_vertex_normals(mesh: trimesh.Trimesh) -> None:
    """不依赖 scipy 的法向赋值（trimesh.fix_normals 需要 scipy）。"""
    if mesh.vertex_normals is not None and len(mesh.vertex_normals) == len(mesh.vertices):
        return
    fn = np.asarray(mesh.face_normals, dtype=np.float64)
    vn = np.zeros((len(mesh.vertices), 3), dtype=np.float64)
    counts = np.zeros(len(mesh.vertices), dtype=np.float64)
    for i, (a, b, c) in enumerate(mesh.faces):
        n = fn[i]
        for idx in (a, b, c):
            vn[idx] += n
            counts[idx] += 1.0
    mask = counts > 0
    vn[mask] /= counts[mask][:, None]
    for i in range(len(vn)):
        L = float((vn[i, 0] ** 2 + vn[i, 1] ** 2 + vn[i, 2] ** 2) ** 0.5)
        if L > 1e-12:
            vn[i] /= L
    mesh.vertex_normals = vn


def mesh_to_glb_bytes_cad(mesh: trimesh.Trimesh) -> bytes:
    """CAD 导出：平滑法向 + 双面材质（不拆三角面，避免面缝）。"""
    if mesh.faces is None or len(mesh.faces) == 0:
        raise ValueError("empty mesh")
    out = mesh.copy()
    _assign_vertex_normals(out)
    out.visual.material = _CAD_PBR
    return _force_glb_double_sided(trimesh.Scene(out).export(file_type="glb"))


def trimesh_to_glb_bytes(mesh: trimesh.Trimesh) -> bytes:
    flat = flat_shade_mesh(mesh)
    return _force_glb_double_sided(trimesh.Scene(flat).export(file_type="glb"))


def scene_to_glb_bytes(scene: trimesh.Scene) -> bytes:
    """多几何体场景（按面拆分）导出 GLB。"""
    out = trimesh.Scene()
    for name, geom in scene.geometry.items():
        if isinstance(geom, trimesh.Trimesh) and len(geom.faces) > 0:
            out.add_geometry(flat_shade_mesh(geom), geom_name=name)
    if not out.geometry:
        raise ValueError("empty scene")
    return _force_glb_double_sided(out.export(file_type="glb"))
