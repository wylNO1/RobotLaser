"""ikfast 逆解/正解 API 数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Position3(BaseModel):
    x: float = Field(..., description="末端 X，米")
    y: float = Field(..., description="末端 Y，米")
    z: float = Field(..., description="末端 Z，米")


class Rpy3(BaseModel):
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class RotationMatrix3x3(BaseModel):
    """行优先 3x3，与 ikfast eerot 一致。"""

    r00: float
    r01: float
    r02: float
    r10: float
    r11: float
    r12: float
    r20: float
    r21: float
    r22: float

    def to_row_major(self) -> list[float]:
        return [
            self.r00, self.r01, self.r02,
            self.r10, self.r11, self.r12,
            self.r20, self.r21, self.r22,
        ]


class IkInverseRequest(BaseModel):
    position: Position3
    rpy: Rpy3 | None = Field(default=None, description="RPY 弧度，与 rotation 二选一")
    rotation: RotationMatrix3x3 | None = Field(default=None, description="旋转矩阵，与 rpy 二选一")


class IkForwardRequest(BaseModel):
    joints: list[float] = Field(..., min_length=6, max_length=6, description="6 轴关节角，弧度")


class JointSolution(BaseModel):
    index: int
    joints: list[float]


class IkInverseResponse(BaseModel):
    model_id: str
    num_solutions: int
    solutions: list[JointSolution]
    units: dict[str, str] = Field(default_factory=lambda: {"length": "m", "angle": "rad"})


class IkForwardResponse(BaseModel):
    model_id: str
    position: Position3
    rotation: RotationMatrix3x3
    units: dict[str, str] = Field(default_factory=lambda: {"length": "m", "angle": "rad"})


class IkFastStatusResponse(BaseModel):
    ikfast_available: bool
    library_path: str | None
    kinematics_hash: str | None = None
    ikfast_version: str | None = None
    models: list[dict[str, str | int]]
    hint: str
