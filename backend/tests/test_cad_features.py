"""点 / 线(轮廓) / 面 / 孔 — CAD 特征识别算法测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.cad import CadAnalyzeOptions, CadAnalyzeResult, CadFaceAnalyzeResult
from app.occ import occ_available
from app.utils.form_json import parse_optional_json_form


def test_swagger_string_placeholder_ignored():
    opts = parse_optional_json_form("string", CadAnalyzeOptions, field_name="options_json")
    assert opts.work_plane.value == "auto"

from app.occ.features.extractor import extract_all_features, extract_face_features
from app.occ.loader import read_step_bytes

from tests.fixtures.cad.generate_fixtures import (
    make_box_shape,
    make_plate_with_hole_shape,
)

pytestmark = pytest.mark.skipif(
    not occ_available(),
    reason="pythonOCC not installed (use conda env occ)",
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cad"


def _analyze_shape(shape, **opts) -> dict:
    options = CadAnalyzeOptions(**opts)
    return extract_all_features(shape, options)


def _analyze_step_path(path: Path) -> dict:
    data = path.read_bytes()
    shape = read_step_bytes(data, path.name)
    return _analyze_shape(shape)


# ---------------------------------------------------------------------------
# 长方体：面、线、参考点、外轮廓
# ---------------------------------------------------------------------------


class TestWireWorldCoordinates:
  def test_translated_solid_polylines_match_world_frame(self):
      from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
      from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
      from OCC.Core.gp import gp_Trsf, gp_Vec

      box = BRepPrimAPI_MakeBox(50.0, 30.0, 10.0).Shape()
      trsf = gp_Trsf()
      trsf.SetTranslation(gp_Vec(100.0, 200.0, 300.0))
      moved = BRepBuilderAPI_Transform(box, trsf, True).Shape()
      result = _analyze_shape(moved)
      pts = []
      for pl in result["polylines"]:
          pts.extend((p["x"], p["y"], p["z"]) for p in pl["points"])
      assert pts
      xs = [p[0] for p in pts]
      ys = [p[1] for p in pts]
      zs = [p[2] for p in pts]
      assert min(xs) == pytest.approx(100.0, abs=2.0)
      assert min(ys) == pytest.approx(200.0, abs=2.0)
      assert min(zs) == pytest.approx(300.0, abs=2.0)


class TestBoxFeatureExtraction:
  def test_face_count_and_types(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      assert result["summary"]["face_count"] == 6
      assert all(f["surface_type"] == "plane" for f in result["faces"])
      assert result["summary"]["solid_count"] >= 1

  def test_polylines_and_wires(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      assert len(result["polylines"]) >= 6
      assert len(result["wires"]) >= 6
      closed_polys = [p for p in result["polylines"] if p["closed"]]
      assert len(closed_polys) >= 6
      for pl in result["polylines"]:
          assert len(pl["points"]) >= 3
          for pt in pl["points"]:
              assert {"x", "y", "z"} <= set(pt.keys())

  def test_reference_points(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      kinds = {p["kind"] for p in result["reference_points"]}
      assert "datum" in kinds
      assert "face_center" in kinds
      assert any(p["kind"] == "datum" and p["id"] == "pt_bbox_center" for p in result["reference_points"])

  def test_contours_populated(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      assert len(result["contours"]) >= 6
      types = {c["contour_type"] for c in result["contours"]}
      assert "outer" in types
      for c in result["contours"]:
          assert c["center"] and "x" in c["center"]
          assert c["normal"] and "z" in c["normal"]
          assert "parameters" in c

  def test_outer_contour_on_largest_planar_face(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      assert len(result["outer_contours"]) >= 1
      cid = result["outer_contours"][0]
      contour = next(c for c in result["contours"] if c["id"] == cid)
      assert contour["contour_type"] == "outer"
      assert contour["is_outer"] is True

  def test_bbox_summary(self):
      result = _analyze_shape(make_box_shape(100, 60, 20))
      bb = result["summary"]["bbox"]
      assert bb["xmax"] - bb["xmin"] == pytest.approx(100, rel=0.02)
      assert bb["ymax"] - bb["ymin"] == pytest.approx(60, rel=0.02)
      assert bb["zmax"] - bb["zmin"] == pytest.approx(20, rel=0.02)

  def test_pydantic_roundtrip(self):
      raw = _analyze_shape(make_box_shape(100, 60, 20))
      model = CadAnalyzeResult(**raw)
      assert model.schema_version == "1.1"
      assert len(model.contours) >= 6


# ---------------------------------------------------------------------------
# 单面提取：前端选面 → 只提取该面轮廓/特征
# ---------------------------------------------------------------------------


class TestFaceFeatureExtraction:
  def test_extract_single_face(self):
      shape = make_box_shape(100, 60, 20)
      raw = extract_face_features(shape, CadAnalyzeOptions(), face_id="face_0")
      model = CadFaceAnalyzeResult(**raw)
      assert model.target_face_id == "face_0"
      assert model.face.id == "face_0"
      assert len(model.contours) >= 1
      assert len(model.polylines) >= 1
      assert model.feature_groups.contours_by_type
      assert "outer" in model.feature_groups.contours_by_type

  def test_extract_plate_hole_face(self):
      shape = make_plate_with_hole_shape(100, 10, 15)
      full = _analyze_shape(shape)
      top_face = next(f for f in full["faces"] if f["inner_wire_ids"])
      raw = extract_face_features(shape, CadAnalyzeOptions(), face_id=top_face["id"])
      model = CadFaceAnalyzeResult(**raw)
      assert model.target_face_id == top_face["id"]
      assert len(model.holes) >= 1
      assert "circle" in model.feature_groups.holes_by_type
      assert len(model.feature_groups.wires_by_role["inner"]) >= 1

  def test_invalid_face_id_raises(self):
      shape = make_box_shape(100, 60, 20)
      with pytest.raises(ValueError, match="不存在"):
          extract_face_features(shape, CadAnalyzeOptions(), face_id="face_999")


# ---------------------------------------------------------------------------
# 带孔板：孔识别、内环
# ---------------------------------------------------------------------------


  def test_nonplanar_face_inner_circle_still_emits_hole(self):
      result = extract_face_features(
          make_plate_with_hole_shape(100, 10, 15),
          CadAnalyzeOptions(),
          face_id="face_4",
      )
      circle_contours = [c for c in result["contours"] if c["contour_type"] == "circle" and not c["is_outer"]]
      assert len(circle_contours) >= 1
      assert len(result["holes"]) >= 1
      assert result["holes"][0]["contour_type"] == "circle"

      result = _analyze_shape(make_plate_with_hole_shape(100, 10, 15))
      assert len(result["holes"]) >= 1
      hole = result["holes"][0]
      assert hole.get("contour_type") == "circle" or hole.get("kind") == "circle"
      assert hole.get("diameter") is not None
      assert 25 <= hole["diameter"] <= 35  # 2 * r ≈ 30
      circle_contours = [c for c in result["contours"] if c["contour_type"] == "circle"]
      assert len(circle_contours) >= 1
      assert circle_contours[0]["parameters"]["diameter"] is not None

  def test_hole_reference_point(self):
      result = _analyze_shape(make_plate_with_hole_shape(100, 10, 15))
      hole_pts = [p for p in result["reference_points"] if p["kind"] == "hole_center"]
      assert len(hole_pts) >= 1

  def test_planar_face_has_inner_wire_or_hole(self):
      result = _analyze_shape(make_plate_with_hole_shape(100, 10, 15))
      faces_with_inner = [f for f in result["faces"] if f["inner_wire_ids"]]
      # 布尔减孔可能表现为圆柱面 + 孔特征，不一定有平面内环
      assert len(faces_with_inner) >= 1 or len(result["holes"]) >= 1


# ---------------------------------------------------------------------------
# STEP 文件往返（fixtures 目录）
# ---------------------------------------------------------------------------


class TestContourTypesOnFixtures:
  def test_plate_slot_or_rect(self):
      from tests.fixtures.cad.generate_fixtures import make_plate_with_slot_shape

      result = _analyze_shape(make_plate_with_slot_shape(100, 10, 40, 12))
      inner = [c for c in result["contours"] if not c["is_outer"]]
      assert len(inner) >= 1
      assert inner[0]["contour_type"] in ("slot", "rectangle")
      assert inner[0]["parameters"]["length"] is not None


class TestStepFixtures:
  @pytest.fixture(scope="class", autouse=True)
  def _ensure_fixtures(self):
      if not (FIXTURES / "box_100x60x20.step").exists():
          from tests.fixtures.cad import generate_fixtures

          generate_fixtures.main()

  def test_box_step_file(self):
      result = _analyze_step_path(FIXTURES / "box_100x60x20.step")
      assert result["summary"]["face_count"] == 6
      assert len(result["outer_contours"]) >= 1

  def test_plate_hole_step_file(self):
      result = _analyze_step_path(FIXTURES / "plate_with_hole_100.step")
      assert len(result["holes"]) >= 1


# ---------------------------------------------------------------------------
# HTTP API（可选）
# ---------------------------------------------------------------------------


class TestCadAnalyzeApi:
  def test_analyze_upload_box_step(self):
      pytest.importorskip("httpx")
      from fastapi.testclient import TestClient

      from app.main import app

      step_path = FIXTURES / "box_100x60x20.step"
      if not step_path.exists():
          from tests.fixtures.cad import generate_fixtures

          generate_fixtures.main()

      client = TestClient(app)
      data = step_path.read_bytes()
      r = client.post(
          "/api/v1/cad/analyze",
          files={"file": ("box_100x60x20.step", data, "application/octet-stream")},
      )
      assert r.status_code == 200, r.text
      body = r.json()
      assert body["summary"]["face_count"] == 6
      assert len(body["polylines"]) >= 6

  def test_analyze_face_upload_box_step(self):
      pytest.importorskip("httpx")
      from fastapi.testclient import TestClient

      from app.main import app

      step_path = FIXTURES / "box_100x60x20.step"
      if not step_path.exists():
          from tests.fixtures.cad import generate_fixtures

          generate_fixtures.main()

      client = TestClient(app)
      data = step_path.read_bytes()
      r = client.post(
          "/api/v1/cad/analyze/face",
          data={"face_id": "face_0"},
          files={"file": ("box_100x60x20.step", data, "application/octet-stream")},
      )
      assert r.status_code == 200, r.text
      body = r.json()
      assert body["target_face_id"] == "face_0"
      assert body["face"]["id"] == "face_0"
      assert len(body["contours"]) >= 1
      assert "outer" in body["feature_groups"]["contours_by_type"]
