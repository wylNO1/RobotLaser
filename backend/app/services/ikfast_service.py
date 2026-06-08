"""ikfast 逆解/正解业务层。"""

from __future__ import annotations

from app.ikfast.m20ia_35m import MODEL_ID
from app.ikfast.native_loader import (
    get_m20ia_35m_solver,
    ikfast_available,
    library_path,
    robot_models,
)
from app.ikfast.pose import pose_from_xyz_rpy, row_major_to_rotation_matrix
from app.models.ikfast import (
    IkFastStatusResponse,
    IkForwardRequest,
    IkForwardResponse,
    IkInverseRequest,
    IkInverseResponse,
    JointSolution,
    Position3,
    RotationMatrix3x3,
)


def get_status() -> IkFastStatusResponse:
    available = ikfast_available()
    kin_hash: str | None = None
    version: str | None = None
    if available:
        try:
            s = get_m20ia_35m_solver()
            kin_hash = s.kinematics_hash
            version = s.ikfast_version
        except OSError:
            available = False

    models = [
        {"model_id": m.model_id, "name": m.name, "num_joints": m.num_joints}
        for m in robot_models()
    ]
    path = library_path()
    hint = (
        "ikfast 已就绪，可调用 /api/v1/ikfast/m20ia-35m/inverse 与 forward。"
        if available
        else "请先编译: cd backend\\app\\ikfast\\m20ia_35m && build.cmd（需 g++）"
    )
    return IkFastStatusResponse(
        ikfast_available=available,
        library_path=str(path) if path else None,
        kinematics_hash=kin_hash,
        ikfast_version=version,
        models=models,
        hint=hint,
    )


def _solver():
    if not ikfast_available():
        raise RuntimeError(get_status().hint)
    return get_m20ia_35m_solver()


def _pose_from_request(req: IkInverseRequest) -> tuple[list[float], list[float]]:
    xyz = [req.position.x, req.position.y, req.position.z]
    if req.rotation is not None and req.rpy is not None:
        raise ValueError("rotation 与 rpy 只能指定其一")
    if req.rotation is not None:
        return xyz, req.rotation.to_row_major()
    if req.rpy is not None:
        return pose_from_xyz_rpy(xyz, [req.rpy.roll, req.rpy.pitch, req.rpy.yaw])
    return xyz, [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def inverse_kinematics(req: IkInverseRequest) -> IkInverseResponse:
    solver = _solver()
    eetrans, eerot = _pose_from_request(req)
    raw = solver.compute_ik(eetrans, eerot)
    solutions = [JointSolution(index=i, joints=j) for i, j in enumerate(raw)]
    return IkInverseResponse(
        model_id=MODEL_ID,
        num_solutions=len(solutions),
        solutions=solutions,
    )


def forward_kinematics(req: IkForwardRequest) -> IkForwardResponse:
    solver = _solver()
    trans, rot_flat = solver.compute_fk(list(req.joints))
    rot = row_major_to_rotation_matrix(rot_flat)
    return IkForwardResponse(
        model_id=MODEL_ID,
        position=Position3(x=trans[0], y=trans[1], z=trans[2]),
        rotation=RotationMatrix3x3(
            r00=float(rot[0, 0]), r01=float(rot[0, 1]), r02=float(rot[0, 2]),
            r10=float(rot[1, 0]), r11=float(rot[1, 1]), r12=float(rot[1, 2]),
            r20=float(rot[2, 0]), r21=float(rot[2, 1]), r22=float(rot[2, 2]),
        ),
    )
