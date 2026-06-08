"""Server-side STEP cache.

Lets the frontend upload a STEP/STP file once (→ ``model_id``) and then run
feature extraction on any number of faces without re-uploading the file. The
cache is keyed by content hash, so re-uploading the same file is deduped.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from app.config import BACKEND_ROOT

CACHE_DIR = Path(BACKEND_ROOT, "uploads", "cad_cache").resolve()

# model_id is a truncated sha256 hex digest; restrict strictly to avoid traversal.
_MODEL_ID_RE = re.compile(r"^[0-9a-f]{8,64}$")
# Default cache lifetime; entries older than this may be pruned on access.
_DEFAULT_TTL_SECONDS = 24 * 3600


def _ensure_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def compute_model_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def _validate_model_id(model_id: str) -> str:
    mid = (model_id or "").strip().lower()
    if not _MODEL_ID_RE.match(mid):
        raise ValueError(f"model_id 格式无效: {model_id!r}")
    return mid


def store_step(data: bytes, filename: str) -> dict:
    """Persist STEP bytes and return cache metadata (includes ``model_id``)."""
    _ensure_dir()
    model_id = compute_model_id(data)
    suffix = ".step" if (filename or "").lower().endswith(".step") else ".stp"
    step_path = CACHE_DIR / f"{model_id}{suffix}"
    if not step_path.exists():
        step_path.write_bytes(data)
    meta = {
        "model_id": model_id,
        "filename": filename or f"model{suffix}",
        "suffix": suffix,
        "size": len(data),
        "updated_at": time.time(),
    }
    (CACHE_DIR / f"{model_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return meta


def get_step_path(model_id: str) -> Path:
    """Return the cached STEP file path, or raise ``KeyError`` if missing."""
    mid = _validate_model_id(model_id)
    for suffix in (".step", ".stp"):
        candidate = CACHE_DIR / f"{mid}{suffix}"
        if candidate.is_file():
            return candidate
    raise KeyError(model_id)


def get_meta(model_id: str) -> dict:
    mid = _validate_model_id(model_id)
    meta_path = CACHE_DIR / f"{mid}.json"
    if not meta_path.is_file():
        raise KeyError(model_id)
    return json.loads(meta_path.read_text(encoding="utf-8"))


def prune_expired(ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> int:
    """Delete cache entries older than ``ttl_seconds``. Returns count removed."""
    if not CACHE_DIR.is_dir():
        return 0
    cutoff = time.time() - ttl_seconds
    removed = 0
    for step_path in list(CACHE_DIR.glob("*.st*p")):
        try:
            if step_path.stat().st_mtime < cutoff:
                step_path.unlink(missing_ok=True)
                (CACHE_DIR / f"{step_path.stem}.json").unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    return removed
