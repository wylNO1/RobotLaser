"""RPY / homogeneous transforms for URDF (same convention as ROS URDF)."""

from __future__ import annotations

import numpy as np


def rpy_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Intrinsic XYZ fixed angles -> 3x3 rotation (roll about x, pitch y, yaw z)."""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=np.float64)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=np.float64)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=np.float64)
    return rz @ ry @ rx


def xyz_rpy_to_matrix(xyz: list[float], rpy: list[float]) -> np.ndarray:
    """4x4 transform from URDF origin xyz + rpy (radians)."""
    r = rpy_to_matrix(float(rpy[0]), float(rpy[1]), float(rpy[2]))
    t = np.eye(4, dtype=np.float64)
    t[:3, :3] = r
    t[:3, 3] = np.array(xyz, dtype=np.float64)
    return t


def matrix_to_xyz_rpy(m: np.ndarray) -> tuple[list[float], list[float]]:
    """Decompose 4x4 into xyz and rpy (for debugging / round-trip)."""
    xyz = [float(m[0, 3]), float(m[1, 3]), float(m[2, 3])]
    r = m[:3, :3]
    pitch = np.arcsin(-float(r[2, 0]))
    if abs(np.cos(pitch)) > 1e-8:
        roll = np.arctan2(float(r[2, 1]), float(r[2, 2]))
        yaw = np.arctan2(float(r[1, 0]), float(r[0, 0]))
    else:
        roll = np.arctan2(-float(r[1, 2]), float(r[1, 1]))
        yaw = 0.0
    return xyz, [float(roll), float(pitch), float(yaw)]
