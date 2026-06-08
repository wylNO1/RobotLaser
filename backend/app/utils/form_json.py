"""Parse optional JSON fields from Swagger multipart forms."""

from __future__ import annotations

import json
from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Swagger UI 常把可选字段预填为 "string"，不能当作 JSON 解析
_SWAGGER_PLACEHOLDERS = frozenset({"string", "null", "undefined", "none"})


def parse_optional_json_form(raw: str | None, model: type[T], *, field_name: str) -> T:
    """Return default model instance when form field is empty or a Swagger placeholder."""
    if raw is None:
        return model()
    text = raw.strip()
    if not text or text.lower() in _SWAGGER_PLACEHOLDERS:
        return model()
    try:
        return model.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 不是合法 JSON: {e}",
        ) from e


def parse_required_json_form(raw: str, model: type[T], *, field_name: str) -> T:
    text = (raw or "").strip()
    if not text or text.lower() in _SWAGGER_PLACEHOLDERS:
        raise HTTPException(status_code=400, detail=f"{field_name} 不能为空")
    try:
        return model.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 不是合法 JSON: {e}",
        ) from e
