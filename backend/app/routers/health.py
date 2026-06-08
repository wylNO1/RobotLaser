"""Health check and service discovery."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["health"])


@router.get("/docs", include_in_schema=False)
def legacy_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/swagger")


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "URDF / CAD conversion backend",
        "health": "/health",
        "swagger_ui": "/swagger",
        "redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "urdf_convert": "POST /api/v1/urdf/convert (multipart: file, embed_meshes)",
        "stp_convert": "POST /api/v1/stp/convert (multipart: file)",
        "ikfast_status": "GET /api/v1/ikfast/status",
        "ikfast_inverse": "POST /api/v1/ikfast/m20ia-35m/inverse",
        "ikfast_forward": "POST /api/v1/ikfast/m20ia-35m/forward",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
