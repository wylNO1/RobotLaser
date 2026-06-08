"""末端位姿与 ikfast 旋转矩阵格式转换。"""

from __future__ import annotations

import numpy as np

from app.utils.transforms import rpy_to_matrix


def rotation_matrix_to_row_major(rot: np.ndarray) -> list[float]:
    """3x3 矩阵 -> ikfast 行优先 9 元 [r00,r01,r02, r10,...]。"""
    r = np.asarray(rot, dtype=np.float64).reshape(3, 3)
    return [float(r[i, j]) for i in range(3) for j in range(3)]


def row_major_to_rotation_matrix(flat9: list[float]) -> np.ndarray:
    if len(flat9) != 9:
        raise ValueError("rotation 需要 9 个元素（行优先 3x3）")
    return np.array(flat9, dtype=np.float64).reshape(3, 3)


def pose_from_xyz_rpy(xyz: list[float], rpy: list[float]) -> tuple[list[float], list[float]]:
    """平移 + RPY(弧度) -> (eetrans[3], eerot[9])。"""
    if len(xyz) != 3:
        raise ValueError("position 需要 [x,y,z]")
    if len(rpy) != 3:
        raise ValueError("rpy 需要 [roll,pitch,yaw]（弧度）")
    rot = rpy_to_matrix(float(rpy[0]), float(rpy[1]), float(rpy[2]))
    return [float(x) for x in xyz], rotation_matrix_to_row_major(rot)
