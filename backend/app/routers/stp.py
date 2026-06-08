"""STEP/STP -> GLB."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.utils.cascadio_guard import cascadio_installed, cascadio_usable_with_occ
from app.utils.occ_guard import occ_installed
from app.utils.file_handler import (
    content_disposition_attachment,
    read_upload_file,
    require_extension,
)
from app.utils.step_bytes import is_step_bytes, step_filename_hint


router = APIRouter(prefix="/stp", tags=["stp"])


@router.get("/status")
def stp_status() -> dict:
    """检查 STEP→GLB 可用引擎（外部前端可先调此接口）。"""
    occ = occ_installed()
    cascadio_pkg = cascadio_installed()
    return {
        "cascadio_available": cascadio_pkg,
        "cascadio_usable": cascadio_usable_with_occ(),
        "cascadio_blocked_by_pythonocc": occ and cascadio_pkg,
        "pythonocc_available": occ,
        "convert_ready": occ or cascadio_usable_with_occ(),
        "engine": "pythonocc" if occ else ("cascadio" if cascadio_pkg else "none"),
        "hint": (
            "已装 pythonOCC：仅使用 pythonOCC 转 GLB；勿在本进程 import cascadio（"
            "Windows 会 DLL 冲突 0xC06D007F）。建议在 occ 环境执行: pip uninstall cascadio -y"
            if occ
            else "需安装 pythonOCC 或 cascadio 之一"
        ),
    }


@router.post("/convert")
async def convert_stp_to_glb(
    file: UploadFile = File(..., description="STEP/STP 零件或装配文件 (.stp / .step)"),
    linear_deflection: float = Query(
        0.1,
        gt=0,
        description="线性偏差 (mm)，越小网格越细。大模型可试 0.2~0.5",
    ),
    angular_deflection: float = Query(
        0.5,
        gt=0,
        le=1.5,
        description="角度偏差 (rad)，默认 0.5",
    ),
    pick_level: str = Query(
        "full",
        description="GLB 层级：full=零件+面+轮廓(默认)，part=仅零件部件(与 PythonProject2 一致)",
    ),
) -> Response:
    raw, name = await read_upload_file(file)
    if name:
        lower = name.lower()
        if not (lower.endswith(".stp") or lower.endswith(".step")):
            if not is_step_bytes(raw):
                raise HTTPException(
                    status_code=400,
                    detail=f"需要 .stp/.step 扩展名，当前文件名: {name!r}",
                )
    elif not is_step_bytes(raw):
        raise HTTPException(status_code=400, detail="文件不是有效的 STEP 内容")
    name = step_filename_hint(name)

    # 必须先判断 OCC，切勿调用 import cascadio（会与 pythonOCC 争用 OCCT DLL）
    if not occ_installed() and not cascadio_installed():
        raise HTTPException(
            status_code=501,
            detail=(
                "STEP 转 GLB 需要 pythonOCC 或 cascadio。conda occ 环境请: "
                "conda install -c conda-forge pythonocc-core"
            ),
        )

    if pick_level not in ("full", "part"):
        raise HTTPException(status_code=400, detail="pick_level 须为 full 或 part")

    try:
        from app.services.stp_converter import stp_bytes_to_glb

        glb = stp_bytes_to_glb(
            raw,
            name,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
            pick_level=pick_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"STEP 转 GLB 失败: {e}") from e

    out_name = name or "model.stp"
    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": content_disposition_attachment(out_name)},
    )
