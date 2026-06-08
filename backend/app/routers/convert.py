"""URDF -> Babylon scene JSON."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.services.skeleton_builder import parse_urdf_to_babylon_scene
from app.services.urdf_parser import MeshResolver

router = APIRouter(prefix="/urdf", tags=["urdf"])


@router.post("/convert")
async def convert_urdf(
    file: UploadFile = File(..., description="robot.urdf 文件或含资源的 .zip"),
    embed_meshes: bool = Form(True, description="是否在 JSON 中内嵌 glb_base64"),
    urdf_path_in_zip: str | None = Form(
        None,
        description="若上传 zip，可指定包内相对路径，如 robots/foo.urdf；留空则自动找第一个 .urdf",
    ),
) -> JSONResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")

    filename = (file.filename or "").lower()
    urdf_xml: str
    resolver: MeshResolver

    if filename.endswith(".zip"):
        zf = zipfile.ZipFile(io.BytesIO(raw))
        names = [n for n in zf.namelist() if not n.endswith("/")]
        urdf_names = [n for n in names if n.lower().endswith(".urdf")]
        if not urdf_names:
            raise HTTPException(400, "zip 中未找到 .urdf 文件")
        if urdf_path_in_zip:
            chosen = urdf_path_in_zip.replace("\\", "/")
            if chosen not in names:
                raise HTTPException(400, f"zip 中不存在路径: {chosen}")
        else:
            chosen = sorted(urdf_names, key=len)[0]
        urdf_xml = zf.read(chosen).decode("utf-8", errors="replace")
        urdf_dir = Path(chosen).parent.as_posix()
        prefix = urdf_dir + "/" if urdf_dir and urdf_dir != "." else ""
        resolver = MeshResolver(Path("."), extra_roots=[], zip_file=zf)
        resolver.urdf_dir = Path(prefix) if prefix else Path(".")
        resolver.zip_file = zf
    elif filename.endswith(".urdf") or "." not in filename:
        urdf_xml = raw.decode("utf-8", errors="replace")
        resolver = MeshResolver(Path("."))
    else:
        raise HTTPException(400, "请上传 .urdf 或 .zip")

    try:
        scene = parse_urdf_to_babylon_scene(urdf_xml, resolver, embed_meshes=embed_meshes)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"URDF 解析失败: {e}") from e

    return JSONResponse(content=scene)


@router.get("/convert_path")
def convert_urdf_from_disk(
    urdf_path: str = Query(..., description="服务器上的 URDF 路径"),
    embed_meshes: bool = Query(True, description="是否内嵌 glb_base64"),
) -> JSONResponse:
    p = Path(urdf_path).expanduser().resolve()
    if not p.is_file():
        raise HTTPException(404, f"文件不存在: {p}")
    urdf_xml = p.read_text(encoding="utf-8", errors="replace")
    resolver = MeshResolver(p.parent)
    scene = parse_urdf_to_babylon_scene(urdf_xml, resolver, embed_meshes=embed_meshes)
    return JSONResponse(content=scene)
