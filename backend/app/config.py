"""Load configuration from environment variables and optional `.env` file."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BACKEND_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BACKEND_ROOT / "uploads"))).resolve()
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BACKEND_ROOT / "outputs"))).resolve()


def cors_allow_origins_raw() -> str:
    return os.getenv("CORS_ALLOW_ORIGINS", "").strip()


def cors_allow_credentials() -> bool:
    return os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("1", "true", "yes")


def ensure_runtime_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
