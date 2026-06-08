#!/usr/bin/env python3
"""FANUC M-20iA/35M 逆解/正解本地调用（不经过 HTTP，仅需 numpy + 已编译 DLL）。

用法（仓库根目录）::

    .venv\\Scripts\\python.exe backend\\scripts\\run_ikfast_m20ia.py status
    .venv\\Scripts\\python.exe backend\\scripts\\run_ikfast_m20ia.py forward 0 0 0 0 0 0
    .venv\\Scripts\\python.exe backend\\scripts\\run_ikfast_m20ia.py inverse --x 0.5 --y 0 --z 0.8

或双击/执行仓库根目录的 run_ikfast_demo.cmd（自动使用 .venv）。

首次使用前: setup_ikfast.cmd
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.ikfast.m20ia_35m import MODEL_ID, ROBOT_NAME, NUM_JOINTS
from app.ikfast.native_loader import get_m20ia_35m_solver, ikfast_available, library_path, robot_models
from app.ikfast.pose import pose_from_xyz_rpy


def _deg(rad: float) -> float:
    return math.degrees(rad)


def _fail_no_dll() -> int:
    print("错误: 未找到 DLL，请先运行 setup_ikfast.cmd", file=sys.stderr)
    print(f"  期望路径: {library_path()}", file=sys.stderr)
    return 1


def cmd_status() -> int:
    ok = ikfast_available()
    print(f"ikfast_available: {ok}")
    print(f"library_path:     {library_path()}")
    if ok:
        s = get_m20ia_35m_solver()
        print(f"model_id:         {MODEL_ID}")
        print(f"robot:            {ROBOT_NAME}")
        print(f"kinematics_hash:  {s.kinematics_hash}")
        print(f"ikfast_version:   {s.ikfast_version}")
    for m in robot_models():
        print(f"  joints: {m.num_joints}")
    if not ok:
        print("提示: 先执行 setup_ikfast.cmd 编译 lib\\m20ia_35m_ik.dll", file=sys.stderr)
    return 0 if ok else 1


def cmd_forward(joints: list[float]) -> int:
    if not ikfast_available():
        return _fail_no_dll()
    solver = get_m20ia_35m_solver()
    trans, rot = solver.compute_fk(joints)
    print("正解结果 (m, rad):")
    print(f"  position: x={trans[0]:.6f} y={trans[1]:.6f} z={trans[2]:.6f}")
    print(
        "  rotation (row-major): "
        f"[{rot[0]:.6f},{rot[1]:.6f},{rot[2]:.6f}; "
        f"{rot[3]:.6f},{rot[4]:.6f},{rot[5]:.6f}; "
        f"{rot[6]:.6f},{rot[7]:.6f},{rot[8]:.6f}]"
    )
    return 0


def cmd_inverse(x: float, y: float, z: float, roll: float, pitch: float, yaw: float) -> int:
    if not ikfast_available():
        return _fail_no_dll()
    solver = get_m20ia_35m_solver()
    eetrans, eerot = pose_from_xyz_rpy([x, y, z], [roll, pitch, yaw])
    solutions = solver.compute_ik(eetrans, eerot)
    print(f"逆解共 {len(solutions)} 组 (关节角: rad, 括号内为度):")
    for i, j in enumerate(solutions):
        deg = ", ".join(f"{v:.4f}({_deg(v):.2f}°)" for v in j)
        print(f"  sol{i}: [{deg}]")
    return 0


def cmd_roundtrip(joints: list[float]) -> int:
    if cmd_forward(joints) != 0:
        return 1
    solver = get_m20ia_35m_solver()
    trans, rot = solver.compute_fk(joints)
    n = len(solver.compute_ik(trans, rot))
    print(f"\n往返逆解得到 {n} 组解")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="M-20iA/35M ikfast 本地调用（直接加载 DLL）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="检查 DLL 是否可用")

    p_fwd = sub.add_parser("forward", help="正解: 6 关节角(弧度)")
    p_fwd.add_argument("joints", type=float, nargs=NUM_JOINTS, metavar="J")

    p_ik = sub.add_parser("inverse", help="逆解: 末端位姿")
    p_ik.add_argument("--x", type=float, required=True)
    p_ik.add_argument("--y", type=float, required=True)
    p_ik.add_argument("--z", type=float, required=True)
    p_ik.add_argument("--roll", type=float, default=0.0)
    p_ik.add_argument("--pitch", type=float, default=0.0)
    p_ik.add_argument("--yaw", type=float, default=0.0)

    p_rt = sub.add_parser("roundtrip", help="正解+逆解自检")
    p_rt.add_argument("joints", type=float, nargs=NUM_JOINTS, metavar="J")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status()
    if args.command == "forward":
        return cmd_forward(list(args.joints))
    if args.command == "inverse":
        return cmd_inverse(args.x, args.y, args.z, args.roll, args.pitch, args.yaw)
    if args.command == "roundtrip":
        return cmd_roundtrip(list(args.joints))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
