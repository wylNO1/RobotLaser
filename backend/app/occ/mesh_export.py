"""Tessellate TopoDS_Shape → GLB (per-face meshes, OCC normals, flat shading)."""

from __future__ import annotations

import numpy as np
import trimesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepLib import BRepLib_ToolTriangulatedShape
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from OCC.Core.gp import gp_Pnt, gp_Vec

from app.utils.glb_export import scene_to_glb_bytes


def _mesh_deflection(shape, linear_deflection: float) -> float:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    diag = ((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2) ** 0.5
    if diag <= 0:
        return linear_deflection
    auto = max(diag * 0.0005, 0.02)
    return min(max(linear_deflection, auto), diag * 0.02)


def _face_outward_normal(face) -> np.ndarray | None:
    try:
        adaptor = BRepAdaptor_Surface(face)
        u0, u1 = adaptor.FirstUParameter(), adaptor.LastUParameter()
        v0, v1 = adaptor.FirstVParameter(), adaptor.LastVParameter()
        um, vm = (u0 + u1) * 0.5, (v0 + v1) * 0.5
        p = gp_Pnt()
        du = gp_Vec()
        dv = gp_Vec()
        adaptor.D1(um, vm, p, du, dv)
        n = du.Crossed(dv)
        if n.Magnitude() < 1e-12:
            return None
        if face.Orientation() == TopAbs_REVERSED:
            n.Reverse()
        return np.array([n.X(), n.Y(), n.Z()], dtype=np.float64)
    except Exception:
        return None


def _winding_indices(face, verts: list, i1: int, i2: int, i3: int) -> list[int]:
    face_n = _face_outward_normal(face)
    if face_n is None:
        return [i1, i3, i2] if face.Orientation() == TopAbs_REVERSED else [i1, i2, i3]
    v0, v1, v2 = verts[i1], verts[i2], verts[i3]
    e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    cx = e1[1] * e2[2] - e1[2] * e2[1]
    cy = e1[2] * e2[0] - e1[0] * e2[2]
    cz = e1[0] * e2[1] - e1[1] * e2[0]
    if cx * face_n[0] + cy * face_n[1] + cz * face_n[2] < 0.0:
        return [i1, i3, i2]
    return [i1, i2, i3]


def _face_to_trimesh(face, loc: TopLoc_Location, triangulation) -> trimesh.Trimesh | None:
    if triangulation is None:
        return None

    try:
        BRepLib_ToolTriangulatedShape.ComputeNormals(face, triangulation)
    except Exception:
        pass

    has_normals = triangulation.HasNormals()
    trsf = loc.Transformation()
    n_nodes = triangulation.NbNodes()
    n_triangles = triangulation.NbTriangles()
    if n_triangles == 0:
        return None

    vertices: list[list[float]] = []
    vnormals: list[list[float]] | None = [] if has_normals else None

    for i in range(1, n_nodes + 1):
        p = triangulation.Node(i)
        if not loc.IsIdentity():
            p = p.Transformed(trsf)
        vertices.append([p.X(), p.Y(), p.Z()])
        if vnormals is not None:
            nn = triangulation.Normal(i)
            if not loc.IsIdentity():
                nn = nn.Transformed(trsf)
            vnormals.append([nn.X(), nn.Y(), nn.Z()])

    faces: list[list[int]] = []
    for i in range(1, n_triangles + 1):
        n1, n2, n3 = triangulation.Triangle(i).Get()
        i1, i2, i3 = n1 - 1, n2 - 1, n3 - 1
        faces.append(_winding_indices(face, vertices, i1, i2, i3))

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    if vnormals is not None and len(vnormals) == len(vertices):
        mesh.vertex_normals = np.asarray(vnormals, dtype=np.float64)
    return mesh


def _mesh_shape(
    shape, linear_deflection: float, angular_deflection: float
) -> None:
    deflection = _mesh_deflection(shape, linear_deflection)
    mesher = BRepMesh_IncrementalMesh(
        shape, deflection, False, angular_deflection, True
    )
    if hasattr(mesher, "IsDone") and not mesher.IsDone():
        raise ValueError("BRepMesh 三角化未完成")


def _iter_face_meshes(shape) -> list[trimesh.Trimesh]:
    meshes: list[trimesh.Trimesh] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = topods.Face(exp.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, loc)
        exp.Next()
        mesh = _face_to_trimesh(face, loc, triangulation)
        if mesh is not None and len(mesh.faces) > 0:
            meshes.append(mesh)
    return meshes


def shape_to_merged_trimesh(
    shape,
    linear_deflection: float = 0.1,
    angular_deflection: float = 0.5,
) -> trimesh.Trimesh:
    """合并所有面为单一网格（减少面间缝隙，法向更平滑）。"""
    _mesh_shape(shape, linear_deflection, angular_deflection)
    parts = _iter_face_meshes(shape)
    if not parts:
        raise ValueError("模型无三角面片，请尝试减小 linear_deflection 或检查 STEP 是否为曲面实体")
    return parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)


def shape_to_scene(shape, linear_deflection: float = 0.1) -> trimesh.Scene:
    """每个 B-Rep 面单独成网格（调试/特殊用途）。"""
    _mesh_shape(shape, linear_deflection, 0.5)
    scene = trimesh.Scene()
    for idx, mesh in enumerate(_iter_face_meshes(shape)):
        scene.add_geometry(mesh, geom_name=f"face_{idx}")
    if not scene.geometry:
        raise ValueError("模型无三角面片")
    return scene


def shape_to_trimesh(shape, linear_deflection: float = 0.1) -> trimesh.Trimesh:
    """合并为单网格（供需要时使用）；GLB 导出请用 shape_to_glb_bytes。"""
    scene = shape_to_scene(shape, linear_deflection=linear_deflection)
    meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.util.concatenate(meshes)


def shape_to_glb_bytes(
    shape,
    linear_deflection: float = 0.1,
    angular_deflection: float = 0.5,
) -> bytes:
    """Export hierarchical per-face GLB (Windows-safe path via mesh_buffers)."""
    from app.occ.mesh_buffers import shape_to_glb_bytes as export_glb

    return export_glb(shape, linear_deflection=linear_deflection, angular_deflection=angular_deflection)
