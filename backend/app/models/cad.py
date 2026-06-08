"""CAD feature extraction & toolpath API schemas (frontend-friendly JSON)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkPlane(str, Enum):
    AUTO = "auto"
    XY = "xy"
    YZ = "yz"
    XZ = "xz"


class PathStrategy(str, Enum):
    OUTER_CONTOUR = "outer_contour"
    HOLE_CIRCLE = "hole_circle"
    ZIGZAG = "zigzag"
    COMBINED = "combined"


class ContourType(str, Enum):
    OUTER = "outer"
    CIRCLE = "circle"
    SLOT = "slot"
    RECTANGLE = "rectangle"
    HEXAGON = "hexagon"
    UNKNOWN = "unknown"


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class Vector3D(BaseModel):
    x: float
    y: float
    z: float


class BoundingBox3D(BaseModel):
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float
    center: Point3D


class Polyline3D(BaseModel):
    """Discretized edge or contour for Three.js/Babylon Line geometry."""

    id: str
    closed: bool = False
    points: list[Point3D] = Field(default_factory=list)


class ReferencePoint(BaseModel):
    id: str
    kind: str = Field(
        description="datum | face_center | hole_center | bbox_corner | contour_vertex"
    )
    position: Point3D
    meta: dict[str, Any] = Field(default_factory=dict)


class FaceFeature(BaseModel):
    id: str
    surface_type: str = Field(description="plane | cylinder | cone | sphere | torus | other")
    area: float
    normal: Vector3D | None = None
    axis: Vector3D | None = None
    center: Point3D | None = None
    radius: float | None = None
    bbox: BoundingBox3D | None = None
    outer_wire_id: str | None = None
    inner_wire_ids: list[str] = Field(default_factory=list)


class ContourParameters(BaseModel):
    """特征参数（按 contour_type 填对应字段）。"""

    diameter: float | None = Field(None, description="圆形：Φ直径 (mm)")
    length: float | None = Field(None, description="槽/矩形：L 长 (mm)")
    width: float | None = Field(None, description="槽/矩形：W 宽 (mm)")
    across_flats: float | None = Field(None, description="六边形：对边长 L (mm)")


class ContourFeature(BaseModel):
    """轮廓：线 + 类型 + 中心 + 法向 + 特征参数。"""

    id: str
    contour_type: str = Field(
        description="outer | circle | slot | rectangle | hexagon | unknown"
    )
    center: Point3D
    normal: Vector3D
    polyline_id: str
    wire_id: str | None = None
    face_id: str | None = None
    is_outer: bool = False
    parameters: ContourParameters
    area: float | None = None
    perimeter: float | None = None


class WireFeature(BaseModel):
    id: str
    face_id: str | None = None
    is_outer: bool = True
    length: float
    area: float | None = None
    polyline_id: str | None = None
    contour_id: str | None = None
    contour_type: str | None = None


class HoleFeature(BaseModel):
    id: str
    kind: str = Field(
        description="through | blind | counterbore | slot | rectangle | hexagon | circle | unknown"
    )
    contour_type: str | None = Field(None, description="与 contours.contour_type 一致")
    center: Point3D
    axis: Vector3D
    diameter: float | None = None
    depth: float | None = None
    face_id: str | None = None
    wire_id: str | None = None
    cylindrical_face_ids: list[str] = Field(default_factory=list)
    parameters: ContourParameters | None = Field(
        None, description="与 contours.parameters 相同结构"
    )


class PocketFeature(BaseModel):
    id: str
    bottom_face_id: str
    depth: float
    wire_ids: list[str] = Field(default_factory=list)


class ShapeSummary(BaseModel):
    volume: float | None = None
    surface_area: float | None = None
    bbox: BoundingBox3D
    face_count: int
    edge_count: int
    solid_count: int


class CadAnalyzeOptions(BaseModel):
    linear_deflection: float = Field(0.1, gt=0, description="edge discretization (mm)")
    angular_deflection: float = Field(0.5, gt=0, description="edge discretization (rad)")
    work_plane: WorkPlane = WorkPlane.AUTO
    hole_diameter_min: float = Field(0.5, gt=0, description="min hole diameter (mm)")
    hole_diameter_max: float = Field(500.0, gt=0, description="max hole diameter (mm)")
    include_cylinder_holes: bool = Field(
        False,
        description=(
            "Whether to synthesize hole contours from cylindrical faces. "
            "Disabled by default to avoid treating outer cylinders/fillets as holes."
        ),
    )


class CadAnalyzeResult(BaseModel):
    schema_version: str = "1.1"
    unit: str = "mm"
    summary: ShapeSummary
    reference_points: list[ReferencePoint]
    polylines: list[Polyline3D]
    faces: list[FaceFeature]
    wires: list[WireFeature]
    contours: list[ContourFeature] = Field(
        default_factory=list,
        description="轮廓列表：线、类型、中心、法向、特征参数",
    )
    outer_contours: list[str] = Field(
        default_factory=list, description="外轮廓 contour id 列表"
    )
    holes: list[HoleFeature]
    pockets: list[PocketFeature]
    work_plane: str
    work_plane_normal: Vector3D


class FaceFeatureGroups(BaseModel):
    """按类型索引的特征存储，便于路径规划快速过滤。"""

    contours_by_type: dict[str, list[ContourFeature]] = Field(default_factory=dict)
    holes_by_type: dict[str, list[HoleFeature]] = Field(default_factory=dict)
    wires_by_role: dict[str, list[WireFeature]] = Field(default_factory=dict)


class CadFaceAnalyzeResult(BaseModel):
    """单面提取结果：只包含一个面及其轮廓/孔特征。"""

    schema_version: str = "1.0"
    unit: str = "mm"
    target_face_id: str
    model_bbox: BoundingBox3D
    face: FaceFeature
    reference_points: list[ReferencePoint]
    polylines: list[Polyline3D]
    wires: list[WireFeature]
    contours: list[ContourFeature]
    outer_contours: list[str] = Field(default_factory=list)
    holes: list[HoleFeature]
    pockets: list[PocketFeature]
    feature_groups: FaceFeatureGroups
    work_plane: str
    work_plane_normal: Vector3D


class PathSegment(BaseModel):
    id: str
    strategy: str
    feed: float | None = None
    points: list[Point3D]


class PathPlanOptions(BaseModel):
    strategy: PathStrategy = PathStrategy.COMBINED
    tool_diameter: float = Field(6.0, gt=0)
    step_over: float = Field(3.0, gt=0, description="stepover for zigzag (mm)")
    safe_z: float | None = Field(None, description="rapid plane; default bbox.zmax + clearance")
    clearance_z: float = Field(5.0, ge=0)
    feed_rapid: float = 5000.0
    feed_cut: float = 800.0
    hole_lead_in: bool = True


class PathPlanResult(BaseModel):
    schema_version: str = "1.0"
    unit: str = "mm"
    strategy: str
    segments: list[PathSegment]
    total_length: float
    estimated_time_s: float | None = None


class CadAnalyzeAndPathResponse(BaseModel):
    analyze: CadAnalyzeResult
    path: PathPlanResult


class CadFaceAnalyzeAndPathResponse(BaseModel):
    analyze: CadFaceAnalyzeResult
    path: PathPlanResult
