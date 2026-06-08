"""
生成 CAD 特征识别测试用 STEP 文件。

用法（conda occ 环境）:
    cd backend
    python tests/fixtures/cad/generate_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCC.Core.IFSelect import IFSelect_RetDone


OUT_DIR = Path(__file__).resolve().parent


def _write_step(shape, path: Path) -> None:
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {path}")


def make_box_shape(w: float = 100.0, h: float = 60.0, d: float = 20.0):
    return BRepPrimAPI_MakeBox(w, h, d).Shape()


def make_plate_with_slot_shape(
    size: float = 100.0,
    thickness: float = 10.0,
    slot_len: float = 40.0,
    slot_w: float = 12.0,
):
    """顶面细长槽（矩形切口，分类为 slot / rectangle）。"""
    box = BRepPrimAPI_MakeBox(size, size, thickness).Shape()
    ax = gp_Ax2(gp_Pnt(size / 2, size / 2, 0), gp_Dir(0, 0, 1))
    cutter = BRepPrimAPI_MakeBox(ax, slot_len, slot_w, thickness).Shape()
    return BRepAlgoAPI_Cut(box, cutter).Shape()


def make_plate_with_rect_pocket_shape(
    size: float = 100.0,
    thickness: float = 10.0,
    rect_l: float = 30.0,
    rect_w: float = 20.0,
):
    box = BRepPrimAPI_MakeBox(size, size, thickness).Shape()
    ax = gp_Ax2(gp_Pnt(size / 2, size / 2, 0), gp_Dir(0, 0, 1))
    cutter = BRepPrimAPI_MakeBox(ax, rect_l, rect_w, thickness).Shape()
    return BRepAlgoAPI_Cut(box, cutter).Shape()


def make_plate_with_hole_shape(
    size: float = 100.0,
    thickness: float = 10.0,
    hole_r: float = 15.0,
):
    box = BRepPrimAPI_MakeBox(size, size, thickness).Shape()
    ax = gp_Ax2(gp_Pnt(size / 2, size / 2, 0), gp_Dir(0, 0, 1))
    cyl = BRepPrimAPI_MakeCylinder(ax, hole_r, thickness).Shape()
    return BRepAlgoAPI_Cut(box, cyl).Shape()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = {
        "box_100x60x20.step": make_box_shape(100, 60, 20),
        "plate_with_hole_100.step": make_plate_with_hole_shape(100, 10, 15),
        "plate_with_slot_100.step": make_plate_with_slot_shape(100, 10, 40, 12),
        "plate_with_rect_100.step": make_plate_with_rect_pocket_shape(100, 10, 30, 20),
    }
    for name, shape in cases.items():
        path = OUT_DIR / name
        _write_step(shape, path)
        print(f"written {path}")


if __name__ == "__main__":
    main()
