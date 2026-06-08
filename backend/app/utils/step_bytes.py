"""STEP file sniffing (upload validation without relying on filename)."""

from __future__ import annotations


def is_step_bytes(data: bytes) -> bool:
    if not data or len(data) < 32:
        return False
    sample = data[:16384]
    return (
        b"ISO-10303" in sample
        or sample.lstrip().startswith(b"ISO-10303")
        or (b"HEADER;" in sample and b"ENDSEC;" in sample)
    )


def step_filename_hint(name: str | None) -> str:
    n = (name or "").strip()
    lower = n.lower()
    if lower.endswith(".step"):
        return n
    if lower.endswith(".stp"):
        return n
    return "model.stp" if n else "upload.stp"
