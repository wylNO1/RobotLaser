"""ikfast 机器人逆解/正解 HTTP 接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.ikfast import (
    IkFastStatusResponse,
    IkForwardRequest,
    IkForwardResponse,
    IkInverseRequest,
    IkInverseResponse,
)
from app.services import ikfast_service

router = APIRouter(prefix="/ikfast", tags=["ikfast"])


@router.get("/status", response_model=IkFastStatusResponse)
def ikfast_status() -> IkFastStatusResponse:
    """检查本地 ikfast 库是否已编译并可加载。"""
    return ikfast_service.get_status()


@router.post("/m20ia-35m/inverse", response_model=IkInverseResponse)
def m20ia_35m_inverse(body: IkInverseRequest) -> IkInverseResponse:
    """FANUC M-20iA/35M 逆解：末端位姿 -> 关节角（可能多组解）。"""
    try:
        return ikfast_service.inverse_kinematics(body)
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/m20ia-35m/forward", response_model=IkForwardResponse)
def m20ia_35m_forward(body: IkForwardRequest) -> IkForwardResponse:
    """FANUC M-20iA/35M 正解：关节角 -> 末端位姿。"""
    try:
        return ikfast_service.forward_kinematics(body)
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
