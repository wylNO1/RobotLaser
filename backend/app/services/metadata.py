"""Joint / link metadata suitable for `robot_meta.json` sidecars."""

from __future__ import annotations

from typing import Any

from app.services.urdf_parser import ParsedUrdf


def extract_robot_meta(parsed: ParsedUrdf) -> dict[str, Any]:
    """Lightweight joint and link inventory (no mesh payloads)."""
    return {
        "format": "robot_meta",
        "format_version": 1,
        "robot_name": parsed.robot_name,
        "links": sorted(parsed.links.keys()),
        "joints": [
            {
                "name": j["name"],
                "type": j["type"],
                "parent": j["parent"],
                "child": j["child"],
                "axis": j["axis"],
                "limit": j["limit"],
            }
            for j in parsed.joints_raw
        ],
    }
