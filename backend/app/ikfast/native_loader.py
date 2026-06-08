"""ctypes 加载 ikfast 编译出的本地共享库。"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

from app.ikfast.m20ia_35m import LIB_DIR, MODEL_ID, NUM_JOINTS, ROBOT_NAME

MAX_IK_SOLUTIONS = 128

_lib: ctypes.CDLL | None = None
_lib_path: Path | None = None


@dataclass(frozen=True)
class RobotModelInfo:
    model_id: str
    name: str
    num_joints: int


def _library_candidates() -> list[Path]:
    if sys.platform == "win32":
        return [LIB_DIR / "m20ia_35m_ik.dll"]
    if sys.platform == "darwin":
        return [LIB_DIR / "libm20ia_35m_ik.dylib", LIB_DIR / "libm20ia_35m_ik.so"]
    return [LIB_DIR / "libm20ia_35m_ik.so"]


def _bind_m20ia_35m(lib: ctypes.CDLL) -> None:
    lib.m20ia35m_get_num_joints.argtypes = []
    lib.m20ia35m_get_num_joints.restype = ctypes.c_int

    lib.m20ia35m_get_kinematics_hash.argtypes = []
    lib.m20ia35m_get_kinematics_hash.restype = ctypes.c_char_p

    lib.m20ia35m_get_ikfast_version.argtypes = []
    lib.m20ia35m_get_ikfast_version.restype = ctypes.c_char_p

    lib.m20ia35m_compute_ik.argtypes = [
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
    ]
    lib.m20ia35m_compute_ik.restype = ctypes.c_int

    lib.m20ia35m_compute_fk.argtypes = [
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.m20ia35m_compute_fk.restype = None


def _load_library() -> ctypes.CDLL:
    global _lib, _lib_path
    if _lib is not None:
        return _lib

    last_err: str | None = None
    for path in _library_candidates():
        if not path.is_file():
            continue
        try:
            _lib = ctypes.CDLL(str(path))
            _lib_path = path
            _bind_m20ia_35m(_lib)
            return _lib
        except OSError as e:
            last_err = str(e)
            _lib = None

    hint = (
        "未找到 ikfast 共享库。请执行: "
        "cd backend\\app\\ikfast\\m20ia_35m && build.cmd"
    )
    if last_err:
        hint += f" （{last_err}）"
    raise OSError(hint)


def ikfast_available() -> bool:
    try:
        _load_library()
        return True
    except OSError:
        return False


def library_path() -> Path | None:
    try:
        _load_library()
        return _lib_path
    except OSError:
        return None


def robot_models() -> list[RobotModelInfo]:
    return [
        RobotModelInfo(model_id=MODEL_ID, name=ROBOT_NAME, num_joints=NUM_JOINTS),
    ]


class M20iA35mIkFast:
    """FANUC M-20iA/35M ikfast 封装。"""

    def __init__(self) -> None:
        self._lib = _load_library()
        self.num_joints = int(self._lib.m20ia35m_get_num_joints())

    @property
    def kinematics_hash(self) -> str:
        raw = self._lib.m20ia35m_get_kinematics_hash()
        return raw.decode("utf-8") if raw else ""

    @property
    def ikfast_version(self) -> str:
        raw = self._lib.m20ia35m_get_ikfast_version()
        return raw.decode("utf-8") if raw else ""

    def compute_ik(self, eetrans: list[float], eerot: list[float]) -> list[list[float]]:
        if len(eetrans) != 3 or len(eerot) != 9:
            raise ValueError("eetrans 需 3 元，eerot 需 9 元（行优先旋转矩阵）")

        trans_arr = (ctypes.c_double * 3)(*eetrans)
        rot_arr = (ctypes.c_double * 9)(*eerot)
        buf_len = MAX_IK_SOLUTIONS * self.num_joints
        joints_buf = (ctypes.c_double * buf_len)()

        n = self._lib.m20ia35m_compute_ik(trans_arr, rot_arr, joints_buf, MAX_IK_SOLUTIONS)
        if n < 0:
            return []

        out: list[list[float]] = []
        for i in range(n):
            start = i * self.num_joints
            out.append([float(joints_buf[start + j]) for j in range(self.num_joints)])
        return out

    def compute_fk(self, joints: list[float]) -> tuple[list[float], list[float]]:
        if len(joints) != self.num_joints:
            raise ValueError(f"joints 需要 {self.num_joints} 个关节角（弧度）")
        j_arr = (ctypes.c_double * self.num_joints)(*joints)
        trans = (ctypes.c_double * 3)()
        rot = (ctypes.c_double * 9)()
        self._lib.m20ia35m_compute_fk(j_arr, trans, rot)
        return [float(trans[i]) for i in range(3)], [float(rot[i]) for i in range(9)]


_solver: M20iA35mIkFast | None = None


def get_m20ia_35m_solver() -> M20iA35mIkFast:
    global _solver
    if _solver is None:
        _solver = M20iA35mIkFast()
    return _solver
