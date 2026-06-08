# pythonOCC CAD 特征识别与刀路规划算法说明

## 1. 系统架构

```
前端 (Vue/React/Three.js)
    │  multipart/form-data 或 fetch
    ▼
FastAPI  `/api/v1/cad/*`
    │
    ├─ routers/cad.py          HTTP 契约、参数校验
    ├─ services/cad_service.py 业务流程编排
    ├─ models/cad.py             Pydantic JSON Schema（前后端共用）
    └─ occ/                      pythonOCC 内核（可选依赖）
         ├─ loader.py            STEP → TopoDS_Shape
         ├─ discretize.py        Edge/Wire → 折线
         ├─ geometry_utils.py    面包围盒、曲面分类、加工坐标系
         ├─ features/extractor.py  点/面/线/孔识别
         └─ path/planner.py      2.5D 刀路生成
```

设计原则：

- **分层**：路由不直接调用 OCC，便于单测与替换内核（如 OCP）。
- **JSON 友好**：所有几何输出为 `Point3D` / `Polyline3D`，前端可直接画线、标点。
- **可选依赖**：未安装 pythonOCC 时 `/cad/status` 仍可用，分析接口返回 `501`。

---

## 2. STEP 载入与拓扑规范化

**输入**：`.stp` / `.step` 字节流。

**步骤**：

1. `STEPControl_Reader.ReadFile` + `TransferRoots` → `OneShape()`。
2. 拓扑规范化 `_normalize_shape`：
   - 优先取第一个 `TopAbs_SOLID`；
   - 否则取第一个 `TopAbs_SHELL`；
   - 否则保留复合体。

**输出**：`TopoDS_Shape`，作为后续 `TopExp_Explorer` 的根。

---

## 3. 特征识别算法

### 3.0 单面提取（推荐 API 路径）

**入口**：`extract_face_features(shape, options, face_id=...)`

```
1. 解析 face_id → 整数索引（face_12 或 12）
2. TopExp_Explorer(shape, FACE) 遍历，取第 index 个面
3. 调用 _extract_face_payload() 只处理该面
4. _build_feature_groups() 按 contour_type / hole kind / wire role 分组
5. 返回 CadFaceAnalyzeResult（含 feature_groups）
```

与全模型 `extract_all_features()` 共用同一套 `_extract_face_payload()`，保证单面与全模型结果一致。

**face_id 与 OCC 遍历顺序一致**，与 per-face mesh 命名 `face_{idx}` 对齐。

### 3.1 面（Face）遍历

```
FOR face IN TopExp_Explorer(shape, TopAbs_FACE):
    adaptor = BRepAdaptor_Surface(face)
    分类: Plane | Cylinder | Cone | Sphere | Torus | other
    area = brepgprop.SurfaceProperties(face)
    wires = face 上所有 TopAbs_WIRE
```

记录字段：`surface_type`, `area`, `normal`/`axis`/`radius`, `outer_wire_id`, `inner_wire_ids`。

### 3.2 边离散与外轮廓线（Wire / Polyline）

对每条 `Wire`：

1. 收集所有 `Edge`，用 `GCPnts_QuasiUniformDeflection` 按 `linear_deflection` 采样为 3D 折线。
2. 边端点连接容差与 `linear_deflection` 自适应（非固定 1e-6），提高弧面/大模型闭合率。
3. 多段链不连通时保留最长连通链，避免伪连接飞线。
4. 首尾相连判断 `closed`（容差与离散精度同量级）。
5. 平面面：投影到**面法向**二维，用鞋带公式算面积；非平面面：PCA 投影 + 非平面度检测。

**平面外轮廓判定**（同一平面 Face）：

- 所有 **closed** _wire 按 `area` 降序排序；
- **面积最大** 者为 `outer_wire`（外轮廓线）；
- 其余 closed 内环 → 孔候选（见 3.3）。

全局外轮廓：在所有平面面中，取面积最大的 `outer_wire_id` 写入 `outer_contours[]`。

全局外轮廓：单面模式下在该面 `contours` 中取最大外轮廓；全模型模式在所有面中取最大。

### 3.3 轮廓分类（contour_classifier）

平面与非平面 wire 均进入 `classify_wire_contour()`：

| contour_type | 判定依据 |
|--------------|----------|
| `outer` | 外环 wire |
| `circle` | 圆度 ≥ 0.88，或兜底圆度 > 0.65 |
| `slot` | 长宽比 ≥ 1.75 且非圆 |
| `hexagon` | 约 6 拐角 + 边长均匀 |
| `rectangle` | 4–6 拐角或 OBB 近似矩形 |
| `unknown` | 非平面度超阈值或无法分类 |

非平面面使用 `prefer_pca_plane=true`，投影基由 PCA 拟合。

### 3.4 孔（Hole）识别

**路径 A — 平面内环（铣削孔、沉头孔口部）**

- 条件：`inner_wire`、closed、`area > 0`；
- 等效直径：`d = 2 * sqrt(area / π)`；
- 过滤：`hole_diameter_min ≤ d ≤ hole_diameter_max`；
- 孔心：折线顶点质心；孔轴：平面法向 `normal`。

**路径 B — 圆柱面（钻孔、镗孔壁）**

- 条件：`surface_type == cylinder` 且 `include_cylinder_holes=true`（默认关闭，避免外圆柱/圆角误判）；
- `diameter = 2 * radius`，同上直径过滤；
- 孔心：圆柱轴上一点；孔轴：圆柱轴线方向。

**去重**：孔心坐标按 0.01mm 网格量化，距离 < 1mm 视为同一孔。

**类型**（可扩展）：`through | blind | counterbore | slot`；当前默认 `through`，盲孔需结合对面圆柱或深度链分析（后续可加 `BRepClass3d_SolidClassifier`）。

### 3.5 参考点（Reference Points）

| kind | 来源 |
|------|------|
| `face_center` | 平面/圆柱轴心 |
| `hole_center` | 孔心 |
| `datum` | 包围盒中心、min、max |
| `contour_vertex` | （预留）轮廓顶点 |

### 3.6 口袋（Pocket）

识别框架已预留 `pockets[]`：可基于「平面底面 + 侧壁面夹角 + 内环面积」规则扩展，当前版本返回空列表。

### 3.7 加工坐标系（Work Plane）

| 模式 | 法向 |
|------|------|
| `xy` | (0,0,1) |
| `yz` | (1,0,0) |
| `xz` | (0,1,0) |
| `auto` | 包围盒最短边方向（典型装夹面） |

---

## 4. 刀路规划算法（2.5D）

**输入**：

- 全模型：`CadAnalyzeResult` + `PathPlanOptions`
- 单面：`CadFaceAnalyzeResult` → `face_analyze_to_path_payload()` 适配后 + `PathPlanOptions`

**公共参数**：

- `safe_z = bbox.zmax + clearance_z`（快移平面）
- `z_cut`：默认取包围盒中间高度（可改为多层切片循环）

### 4.1 外轮廓 (`outer_contour`)

1. 取 `outer_contours[0]` 对应折线；
2. 先在 `safe_z` 走一圈闭合边界；
3. 下到 `z_cut` 再切一圈；
4. 进给 `feed_cut`。

### 4.2 孔加工 (`hole_circle`)

对每个孔：

1. 快移到孔心 `(x,y,safe_z)`；
2. 以 `diameter/2 - tool_offset` 为半径生成 `n` 点圆（`n ∝ 周长/step_over`）；
3. 在 `z_cut` 平面走圆；
4. 抬刀回 `safe_z`。

### 4.3 行切 (`zigzag`)

在包围盒 `[xmin,xmax]×[ymin,ymax]`：

- 行距 `step_over`；
- 奇偶行反向，形成弓字形；
- 每行：快移 → 下刀 → 切削 → 抬刀。

### 4.4 组合策略 (`combined`)

依次生成：外轮廓 → 各孔圆 → 行切；`total_length` 为各段折线长度之和；`estimated_time_s ≈ total_length / feed_cut * 60`。

---

## 5. 外部前端调用

本仓库不含前端实现。推荐流程：

1. `POST /stp/convert` → GLB 显示
2. 用户选面 → `face_id`
3. `POST /cad/analyze/face` → `feature_groups` 按类型取特征
4. `POST /cad/path/generate/face` 或 `/analyze/face_and_path` → 刀路

完整契约与示例见 **[CAD_API_EXTERNAL.md](./CAD_API_EXTERNAL.md)**，字段说明见 **[CAD_RESPONSE_FIELDS.md](./CAD_RESPONSE_FIELDS.md)**。

---

## 6. 安装 pythonOCC

Windows 推荐使用 Conda：

```bash
conda create -n occ python=3.10
conda activate occ
conda install -c conda-forge pythonocc-core
pip install -r backend/requirements.txt
```

可选文件：`backend/requirements-occ.txt`（说明性依赖）。

---

## 7. 扩展建议

1. **多层粗精加工**：对 `z` 从 `zmax` 到 `zmin` 按 `ap` 步距切片，重复 4.1–4.3。
2. **轮廓偏置**：外轮廓 inward offset 使用 `BRepOffsetAPI_MakeOffset`。
3. **孔序优化**：孔心 TSP（最近邻 / 2-opt）减少空行程。
4. **槽识别**：内环长宽比 > 阈值 → `kind: slot`。
5. **装配体**：遍历 `TopAbs_SOLID` 多个零件分别分析并带 `part_id`。
