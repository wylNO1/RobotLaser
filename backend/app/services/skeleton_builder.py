"""Assemble Babylon-friendly robot scene JSON from parsed URDF."""

from __future__ import annotations

import base64
from typing import Any

from app.services.gltf_writer import geometry_to_mesh_bytes
from app.services.urdf_parser import MeshResolver, ParsedUrdf, _find_child, _findall_children, _parse_origin, parse_urdf_xml
from app.utils.transforms import xyz_rpy_to_matrix


def parse_urdf_to_babylon_scene(
    urdf_xml: str,
    resolver: MeshResolver,
    *,
    embed_meshes: bool = True,
) -> dict[str, Any]:
    parsed: ParsedUrdf = parse_urdf_xml(urdf_xml)

    child_links = {j["child"] for j in parsed.joints_raw if j["child"]}
    roots = [ln for ln in parsed.links if ln not in child_links]
    root_link = roots[0] if roots else (next(iter(parsed.links)) if parsed.links else "")

    joint_by_child = {j["child"]: j for j in parsed.joints_raw if j.get("child")}

    out_links: list[dict[str, Any]] = []
    for link_name, lk in parsed.links.items():
        jinfo = joint_by_child.get(link_name)
        parent_joint = jinfo["name"] if jinfo else None
        parent_link = jinfo["parent"] if jinfo else None

        visuals_out: list[dict[str, Any]] = []
        for vis in _findall_children(lk, "visual"):
            v_xyz, v_rpy = _parse_origin(vis)
            geom = _find_child(vis, "geometry")
            gtype, gparams, glb = geometry_to_mesh_bytes(geom, resolver)
            entry: dict[str, Any] = {
                "origin": {"xyz": v_xyz, "rpy": v_rpy},
                "geometry": {"type": gtype, **gparams},
            }
            if embed_meshes and glb is not None:
                entry["glb_base64"] = base64.standard_b64encode(glb).decode("ascii")
            elif glb is not None:
                entry["glb_size_bytes"] = len(glb)
            visuals_out.append(entry)

        out_links.append(
            {
                "name": link_name,
                "parent_link": parent_link,
                "parent_joint": parent_joint,
                "visuals": visuals_out,
            }
        )

    joints_out: list[dict[str, Any]] = []
    for j in parsed.joints_raw:
        joints_out.append(
            {
                "name": j["name"],
                "type": j["type"],
                "parent": j["parent"],
                "child": j["child"],
                "origin": {"xyz": j["origin_xyz"], "rpy": j["origin_rpy"]},
                "axis": j["axis"],
                "limit": j["limit"],
            }
        )

    link_index = {l["name"]: i for i, l in enumerate(out_links)}
    fixed_transforms: list[dict[str, Any]] = []
    for j in parsed.joints_raw:
        parent = j["parent"]
        child = j["child"]
        if parent not in link_index or child not in link_index:
            continue
        t_joint_parent = xyz_rpy_to_matrix(j["origin_xyz"], j["origin_rpy"])
        fixed_transforms.append(
            {
                "joint": j["name"],
                "parent_link": parent,
                "child_link": child,
                "joint_in_parent": t_joint_parent.tolist(),
            }
        )

    return {
        "format": "babylon_robot_scene",
        "format_version": 1,
        "robot_name": parsed.robot_name,
        "root_link": root_link,
        "links": out_links,
        "joints": joints_out,
        "kinematics_hints": {
            "rpy_unit": "radians",
            "revolute_prismatic": (
                "Drive animation by applying rotation (revolute) or translation (prismatic) "
                "about `axis` in the joint frame (after joint origin w.r.t. parent link). "
                "Use `joint_in_parent` 4x4 row-major matrix to place the joint frame in parent link space."
            ),
            "joint_frames": fixed_transforms,
        },
    }
