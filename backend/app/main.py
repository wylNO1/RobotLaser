"""FastAPI application entry."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_allow_credentials, cors_allow_origins_raw, ensure_runtime_dirs
from app.routers import cad, convert, health, ikfast, stp

ensure_runtime_dirs()

app = FastAPI(
    title="URDF / CAD conversion backend",
    version="1.0.0",
    description=(
        "URDF（或含 mesh 的 zip）转 Babylon `babylon_robot_scene` JSON；"
        "STEP/STP 转 GLB（需安装 cascadio）；"
        "CAD 特征提取与刀路规划（需安装 pythonOCC）；"
        "FANUC M-20iA/35M 解析逆解（需编译 ikfast 本地库）。"
    ),
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

_cors_raw = cors_allow_origins_raw()
if _cors_raw:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    _cors_credentials = cors_allow_credentials()
else:
    _cors_origins = ["*"]
    _cors_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(convert.router, prefix="/api/v1")
app.include_router(stp.router, prefix="/api/v1")
app.include_router(cad.router, prefix="/api/v1")
app.include_router(ikfast.router, prefix="/api/v1")
