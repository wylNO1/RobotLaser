"""Isolated STEP→GLB worker (fresh process, no cascadio / CAD DLL pollution)."""

from __future__ import annotations

import sys
from pathlib import Path


def _convert_file(
    step_path: Path,
    glb_path: Path,
    linear_deflection: float,
    angular_deflection: float,
    pick_level: str = "full",
    filename: str = "model",
) -> None:
    from app.occ.loader import read_step_bytes
    from app.occ.mesh_buffers import (
        shape_to_cad_hierarchical_glb_bytes,
        shape_to_hierarchical_glb_bytes,
    )

    data = step_path.read_bytes()
    shape = read_step_bytes(data, step_path.name)
    if pick_level == "part":
        glb = shape_to_hierarchical_glb_bytes(
            shape,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
        )
    else:
        glb = shape_to_cad_hierarchical_glb_bytes(
            shape,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
            filename=filename,
        )
    glb_path.write_bytes(glb)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) not in (3, 4, 5, 6):
        print(
            "usage: python -m app.services.stp_worker "
            "<input.stp> <output.glb> <linear_deflection> [angular_deflection] [pick_level] [filename]",
            file=sys.stderr,
        )
        return 2

    step_path = Path(args[0])
    glb_path = Path(args[1])
    linear_deflection = float(args[2])
    angular_deflection = float(args[3]) if len(args) > 3 else 0.5
    pick_level = args[4] if len(args) > 4 else "full"
    filename = args[5] if len(args) > 5 else step_path.stem
    _convert_file(step_path, glb_path, linear_deflection, angular_deflection, pick_level, filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
