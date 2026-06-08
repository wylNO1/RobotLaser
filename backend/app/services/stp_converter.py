"""STEP/STP (ISO-10303) to GLB.

Windows + conda occ: 仅使用 pythonOCC；在独立子进程中转换，避免与 cascadio / 主进程 DLL 冲突。
无 pythonOCC 时单独使用 cascadio。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.occ import occ_available
from app.utils.mesh_loader import load_trimesh_from_bytes, to_glb_bytes
from app.utils.occ_guard import occ_installed
from app.utils.step_bytes import is_step_bytes, step_filename_hint

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OCC_PYTHON = Path.home() / "miniconda3" / "envs" / "occ" / "python.exe"


def stp_bytes_to_glb(
    data: bytes,
    filename: str,
    *,
    linear_deflection: float = 0.1,
    angular_deflection: float = 0.5,
    pick_level: str = "full",
) -> bytes:
    if not data or len(data) < 32:
        raise ValueError("文件为空或过小，请确认已选择有效的 .stp/.step 文件")

    if not is_step_bytes(data):
        raise ValueError(
            "不是有效的 STEP 文件（未检测到 ISO-10303 / HEADER 段）。"
            "请确认文件未损坏，或在 CAD 中另存为 STEP AP214/AP203。"
        )

    hint = step_filename_hint(filename)

    # pythonOCC：Windows 一律子进程 + 无 trimesh/numpy 导出，避免 0xC06D007F DLL 崩溃
    if occ_installed():
        if sys.platform == "win32":
            return _via_pythonocc_subprocess(
                data,
                hint,
                linear_deflection=linear_deflection,
                angular_deflection=angular_deflection,
                pick_level=pick_level,
            )
        return _via_pythonocc(
            data,
            hint,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
            pick_level=pick_level,
        )

    try:
        return _via_cascadio(data, filename)
    except ImportError as e:
        raise ValueError(
            "未安装 pythonOCC 或 cascadio。conda occ 环境请: "
            "conda install -c conda-forge pythonocc-core"
        ) from e
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"cascadio 转换失败: {e}") from e


def _via_cascadio(data: bytes, filename: str) -> bytes:
    try:
        import cascadio  # noqa: F401
    except ImportError as e:
        raise ImportError("cascadio 未安装: pip install cascadio") from e

    lower = (filename or "").lower()
    if lower.endswith(".step"):
        file_type = "step"
        hint = filename or "model.step"
    else:
        file_type = "stp"
        hint = filename if lower.endswith(".stp") else (filename or "model.stp")
    loaded = load_trimesh_from_bytes(data, filename_hint=hint, file_type=file_type)
    return to_glb_bytes(loaded)


def _occ_python() -> str:
    """Prefer conda occ interpreter set by run_server.cmd / PyCharm env."""
    env_py = os.environ.get("OCC_PYTHON", "").strip()
    if env_py:
        return env_py
    if occ_available():
        return sys.executable
    if _DEFAULT_OCC_PYTHON.is_file():
        return str(_DEFAULT_OCC_PYTHON)
    return sys.executable


def _via_pythonocc_subprocess(
    data: bytes,
    filename: str,
    *,
    linear_deflection: float,
    angular_deflection: float,
    pick_level: str,
) -> bytes:
    suffix = ".step" if filename.lower().endswith(".step") else ".stp"
    with tempfile.TemporaryDirectory() as td:
        step_path = Path(td) / f"input{suffix}"
        glb_path = Path(td) / "output.glb"
        step_path.write_bytes(data)
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONPATH"] = str(_BACKEND_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        # Normalize filename to bare stem (e.g. "arm_part.step" → "arm_part")
        part_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        proc = subprocess.run(
            [
                _occ_python(),
                "-m",
                "app.services.stp_worker",
                str(step_path),
                str(glb_path),
                str(linear_deflection),
                str(angular_deflection),
                pick_level,
                part_name,
            ],
            cwd=str(_BACKEND_ROOT),
            capture_output=True,
            env=env,
            timeout=600,
            creationflags=creationflags,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
            raise ValueError(
                err or f"STEP 转 GLB 子进程失败 (code {proc.returncode})"
            )
        if not glb_path.is_file():
            raise ValueError("STEP 转 GLB 子进程未生成输出文件")
        return glb_path.read_bytes()


def _via_pythonocc(
    data: bytes,
    filename: str,
    *,
    linear_deflection: float,
    angular_deflection: float,
    pick_level: str,
) -> bytes:
    from app.occ.loader import read_step_bytes
    from app.occ.mesh_buffers import (
        shape_to_cad_hierarchical_glb_bytes,
        shape_to_hierarchical_glb_bytes,
    )

    shape = read_step_bytes(data, filename)
    if pick_level == "part":
        return shape_to_hierarchical_glb_bytes(
            shape,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
        )
    return shape_to_cad_hierarchical_glb_bytes(
        shape,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
        filename=filename,
    )
