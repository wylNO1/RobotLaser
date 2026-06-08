"""Parse URDF XML and resolve mesh paths (disk or zip)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _local_tag(elem: ET.Element) -> str:
    t = elem.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t or ""


def _find_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for c in list(parent):
        if _local_tag(c) == name:
            return c
    return None


def _findall_children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in list(parent) if _local_tag(c) == name]


def _text_vec3(s: str | None, default: list[float]) -> list[float]:
    if not s or not s.strip():
        return list(default)
    parts = re.split(r"[\s,]+", s.strip())
    return [float(x) for x in parts if x]


def _parse_origin(elem: ET.Element | None) -> tuple[list[float], list[float]]:
    if elem is None:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    o = _find_child(elem, "origin")
    if o is None:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    xyz = _text_vec3(o.get("xyz"), [0.0, 0.0, 0.0])
    rpy = _text_vec3(o.get("rpy"), [0.0, 0.0, 0.0])
    if len(xyz) != 3:
        xyz = [0.0, 0.0, 0.0]
    if len(rpy) != 3:
        rpy = [0.0, 0.0, 0.0]
    return xyz, rpy


def _strip_package_uri(uri: str) -> str:
    """Turn package://pkg/path into /path."""
    if uri.startswith("package://"):
        rest = uri[len("package://") :]
        if "/" in rest:
            return "/" + rest.split("/", 1)[1]
        return "/" + rest
    return uri


@dataclass
class MeshResolver:
    """Resolve mesh paths from URDF directory, optional extra roots, or ZIP."""

    urdf_dir: Path
    extra_roots: list[Path] = field(default_factory=list)
    zip_file: zipfile.ZipFile | None = None

    def resolve(self, filename: str) -> bytes | None:
        rel = _strip_package_uri(filename).lstrip("/").replace("\\", "/")
        candidates: list[Path] = []
        if not Path(rel).is_absolute():
            candidates.append(self.urdf_dir / rel)
            for r in self.extra_roots:
                candidates.append(r / rel)
                candidates.append(r / Path(rel).name)
        else:
            candidates.append(Path(rel))

        for p in candidates:
            try:
                if p.is_file():
                    return p.read_bytes()
            except OSError:
                continue

        if self.zip_file is not None:
            names = {n.replace("\\", "/"): n for n in self.zip_file.namelist()}
            ud = self.urdf_dir.as_posix().replace("\\", "/").strip("/")
            keys: list[str] = []
            rel_norm = rel.lstrip("/")
            if ud and ud != ".":
                keys.append(f"{ud}/{rel_norm}".replace("//", "/"))
            keys.extend([rel_norm, rel_norm.lstrip("./")])
            for k in keys:
                if k in names:
                    return self.zip_file.read(names[k])
            base = Path(rel_norm).name
            for zn, orig in names.items():
                if zn == base or zn.endswith("/" + base):
                    return self.zip_file.read(orig)
        return None


@dataclass
class ParsedUrdf:
    robot_name: str
    links: dict[str, ET.Element]
    joints_raw: list[dict[str, Any]]


def parse_urdf_xml(urdf_xml: str) -> ParsedUrdf:
    root = ET.fromstring(urdf_xml)
    robot_name = root.get("name") or "robot"

    links: dict[str, ET.Element] = {}
    for lk in _findall_children(root, "link"):
        n = lk.get("name")
        if n:
            links[n] = lk

    joints_raw: list[dict[str, Any]] = []
    for j in _findall_children(root, "joint"):
        name = j.get("name") or ""
        jtype = (j.get("type") or "fixed").lower()
        parent_el = _find_child(j, "parent")
        child_el = _find_child(j, "child")
        parent = parent_el.get("link") if parent_el is not None else ""
        child = child_el.get("link") if child_el is not None else ""
        xyz, rpy = _parse_origin(j)
        axis_el = _find_child(j, "axis")
        axis = _text_vec3(axis_el.get("xyz") if axis_el is not None else None, [0.0, 0.0, 1.0])
        if len(axis) != 3:
            axis = [0.0, 0.0, 1.0]
        lim: dict[str, float] | None = None
        lim_el = _find_child(j, "limit")
        if lim_el is not None:
            lim = {}
            for k in ("lower", "upper", "effort", "velocity"):
                v = lim_el.get(k)
                if v is not None:
                    try:
                        lim[k] = float(v)
                    except ValueError:
                        pass
        joints_raw.append(
            {
                "name": name,
                "type": jtype,
                "parent": parent,
                "child": child,
                "origin_xyz": xyz,
                "origin_rpy": rpy,
                "axis": axis,
                "limit": lim,
            }
        )

    return ParsedUrdf(robot_name=robot_name, links=links, joints_raw=joints_raw)
