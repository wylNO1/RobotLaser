# CAD 接口 — 外部前端调用说明

本仓库**仅提供 HTTP API**，不包含前端页面。任意 Web / 桌面 / 移动端项目通过 REST 调用即可。

- 服务地址（本地开发）：`http://127.0.0.1:8000`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`
- Swagger UI：`http://127.0.0.1:8000/swagger`
- 单位：毫米（`mm`）

---

## 1. 调用流程（推荐：上传一次，反复选面）

**当前推荐工作流**：先用 `/cad/upload` 上传 STEP 一次拿到 `model_id` → 之后每次选面只传 `model_id + face_id`，**无需重复上传文件** → 按类型使用 `feature_groups` 做路径规划。

```
外部前端                          本仓库 FastAPI 后端
    │                                      │
    │  GET /api/v1/cad/status              │
    │ ────────────────────────────────────►│ 检查 pythonOCC 是否可用
    │◄──────────────────────────────────── │
    │  { pythonocc_available: true }       │
    │                                      │
    │  POST /api/v1/cad/upload (file)      │  上传一次，服务端缓存
    │ ────────────────────────────────────►│
    │◄──────────────────────────────────── │  { model_id, filename, size }
    │                                      │
    │  POST /api/v1/stp/convert            │  （可选）STEP → GLB 显示
    │ ────────────────────────────────────►│
    │◄──────────────────────────────────── │  二进制 GLB
    │                                      │
    │  用户在视图中点击选中一个面           │
    │  face_id = "face_3"                  │
    │                                      │
    │  POST /api/v1/cad/analyze/face       │
    │  form: model_id + face_id (无需 file) │
    │ ────────────────────────────────────►│ 只提取该面轮廓/孔/特征
    │◄──────────────────────────────────── │   （隔离子进程，避免 OCC DLL 崩溃）
    │  CadFaceAnalyzeResult                │
    │  + feature_groups（按类型分组）       │
    │                                      │
    │  再点其它面：只改 face_id 重复上一步   │  仍然无需重传 file
    │                                      │
    │  POST /api/v1/cad/path/generate/face │  （可选）基于单面结果生成刀路
    │  或 analyze/face_and_path 一步完成    │
    │ ────────────────────────────────────►│
    │◄──────────────────────────────────── │
    │  { analyze, path }                   │
    │                                      │
    └── 用 polylines / feature_groups 在你自己的 Three.js / Babylon 中绘制
```

> **关于崩溃**：特征提取现在统一在独立子进程中运行（仅加载 pythonOCC，不与 trimesh/cascadio 同进程），
> 避免 Windows 上 OCCT DLL 冲突导致的 `0xC06D007F: Procedure not found` 整进程崩溃；即便单次几何处理
> 触发 OCC 原生异常，也只会让子进程退出并返回 422，而不会杀死服务。

### face_id 约定

| 规则 | 说明 |
|------|------|
| 格式 | `face_0`、`face_12`，或纯数字 `0`、`12` |
| 编号来源 | 与 OCC `TopExp_Explorer(shape, TopAbs_FACE)` 遍历顺序一致，从 0 开始 |
| 与 mesh 对应 | STEP→GLB 每个面为独立节点 `face_{idx}`（`node.extras.cad.face_id`）；`scenes[0].extras.cad.face_ids` 为全量列表 |

前端选面后，把选中面的 `face_id` 传给 `/analyze/face` 即可。

---

## 2. 接口一览

| 方法 | 路径 | Content-Type | 说明 |
|------|------|--------------|------|
| GET | `/api/v1/cad/status` | — | 是否安装 pythonOCC |
| **POST** | **`/api/v1/cad/upload`** | `multipart/form-data` | **上传 STEP 一次 → 返回 `model_id`（推荐）** |
| **POST** | **`/api/v1/cad/analyze/face`** | `multipart/form-data` | **单面特征识别（推荐）** |
| **POST** | **`/api/v1/cad/analyze/face_and_path`** | `multipart/form-data` | **单面分析 + 刀路（推荐）** |
| POST | `/api/v1/cad/path/generate/face` | `multipart/form-data` | 基于单面 analyze JSON 生成刀路 |
| POST | `/api/v1/cad/analyze` | `multipart/form-data` | 全模型特征识别（调试/批量） |
| POST | `/api/v1/cad/path/generate` | `multipart/form-data` | 基于全模型 analyze JSON 生成刀路 |
| POST | `/api/v1/cad/analyze_and_path` | `multipart/form-data` | 全模型分析 + 刀路 |
| POST | `/api/v1/cad/analyze/json` | `multipart/form-data` | 简化表单参数的全模型分析 |

字段详解见 [CAD_RESPONSE_FIELDS.md](./CAD_RESPONSE_FIELDS.md)。

---

## 3. 请求参数

### 3.0 `POST /api/v1/cad/upload`（推荐，先调一次）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | `.stp` / `.step` |

返回：

```json
{ "model_id": "9f1c...", "filename": "part.step", "suffix": ".step", "size": 123456 }
```

- `model_id` 由文件内容哈希得到：**同一文件重复上传会复用同一 id**。
- 拿到 `model_id` 后，下方所有带 `file` 的分析接口都可改用 `model_id` 字段替代 `file`，**无需再次上传**。
- 缓存默认保留约 24 小时；过期后调用会返回 404，重新 `upload` 即可。

### 3.1 `POST /api/v1/cad/analyze/face`（推荐）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 二选一 | `.stp` / `.step`（首次直接上传时用） |
| `model_id` | string | 二选一 | 来自 `/cad/upload`，**复用已上传文件时用（推荐）** |
| `face_id` | string | 是 | 选中面 ID，如 `face_3` |
| `options_json` | string | 否 | `CadAnalyzeOptions` JSON 字符串 |

> `file` 与 `model_id` 二选一：传了 `model_id` 就不必再传 `file`。`/cad/analyze`、
> `/cad/analyze/face_and_path`、`/cad/analyze_and_path` 同样支持 `model_id` 替代 `file`。

`options_json` 示例：

```json
{
  "linear_deflection": 0.1,
  "angular_deflection": 0.5,
  "work_plane": "auto",
  "hole_diameter_min": 0.5,
  "hole_diameter_max": 500,
  "include_cylinder_holes": false
}
```

| 选项 | 说明 |
|------|------|
| `linear_deflection` | 边离散精度 (mm)，越小弧线越密，默认 `0.1` |
| `work_plane` | `auto` \| `xy` \| `yz` \| `xz` |
| `include_cylinder_holes` | 是否从圆柱面合成孔轮廓，默认 `false`（避免圆角/外圆柱误判） |

### 3.2 `POST /api/v1/cad/analyze/face_and_path`

| 字段 | 类型 | 必填 |
|------|------|------|
| `file` | File | 是 |
| `face_id` | string | 是 |
| `analyze_options_json` | string | 否 |
| `path_options_json` | string | 否 |

### 3.3 `POST /api/v1/cad/path/generate/face`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `analyze_json` | string | 是 | `/analyze/face` 返回的**完整** JSON |
| `path_options_json` | string | 否 | `PathPlanOptions` JSON |

`path_options_json` 示例：

```json
{
  "strategy": "combined",
  "tool_diameter": 6,
  "step_over": 3,
  "clearance_z": 5,
  "feed_cut": 800,
  "hole_lead_in": true
}
```

`strategy`：`outer_contour` | `hole_circle` | `zigzag` | `combined`

### 3.4 全模型接口（兼容保留）

`POST /api/v1/cad/analyze`、`/path/generate`、`/analyze_and_path` 参数与旧版相同，返回 **CadAnalyzeResult**（含所有面）。适用于调试或需要一次看全零件特征的场景。

---

## 4. 响应结构（外部前端消费）

### 4.1 `CadFaceAnalyzeResult`（单面 `/analyze/face`）

| 字段 | 用途 |
|------|------|
| `target_face_id` | 本次分析的面 ID |
| `model_bbox` | 零件整体包围盒（相机对准） |
| `face` | 该面元数据（类型、法向、内外环 id） |
| `polylines[]` | `{ id, closed, points:[{x,y,z}] }` 画轮廓线 |
| `contours[]` | 轮廓类型、中心、法向、参数 |
| `holes[]` | 孔特征 |
| `outer_contours[]` | 该面上外轮廓 contour id |
| **`feature_groups`** | **按类型分组，路径规划直接取用** |
| `work_plane` / `work_plane_normal` | 加工坐标系 |

#### feature_groups（按类型存储）

```json
{
  "contours_by_type": {
    "outer": [ /* ContourFeature[] */ ],
    "circle": [ /* ... */ ],
    "slot": [ /* ... */ ],
    "rectangle": [ /* ... */ ],
    "hexagon": [ /* ... */ ],
    "unknown": [ /* ... */ ]
  },
  "holes_by_type": {
    "circle": [ /* HoleFeature[] */ ]
  },
  "wires_by_role": {
    "outer": [ /* 外环 WireFeature[] */ ],
    "inner": [ /* 内环 WireFeature[] */ ]
  }
}
```

前端示例：

```javascript
const outer = data.feature_groups.contours_by_type.outer ?? [];
const circles = data.feature_groups.holes_by_type.circle ?? [];
const innerWires = data.feature_groups.wires_by_role.inner ?? [];
```

### 4.2 `CadAnalyzeResult`（全模型 `/analyze`）

与单面结构类似，但包含 `summary`、全部 `faces[]`，且无 `feature_groups`。详见 [CAD_RESPONSE_FIELDS.md](./CAD_RESPONSE_FIELDS.md)。

### 4.3 `PathPlanResult`（`path`）

| 字段 | 用途 |
|------|------|
| `segments[]` | 刀路段 `{ id, strategy, feed, points[] }` |
| `total_length` | 路径总长度 (mm) |
| `estimated_time_s` | 估算时间 (s) |

### 4.4 错误

| HTTP | 含义 |
|------|------|
| 400 | 空文件、扩展名错误、JSON 无效、`face_id` 不存在或格式错误、未提供 `file`/`model_id` |
| 404 | `model_id` 不存在或缓存已过期（重新 `/cad/upload`） |
| 422 | STEP 解析或几何处理失败（含子进程内 OCC 原生异常） |
| 501 | 未安装 pythonOCC（`detail` 含安装提示） |

错误体示例：`{ "detail": "face_id 不存在: face_999" }`

---

## 5. 外部前端示例代码

### 5.1 上传一次 → 反复选面（推荐，无需重传文件）

```javascript
const API_BASE = "http://127.0.0.1:8000";

// 第一步：上传 STEP 一次，拿到 model_id
async function uploadStep(stepFile) {
  const form = new FormData();
  form.append("file", stepFile);
  const res = await fetch(`${API_BASE}/api/v1/cad/upload`, { method: "POST", body: form });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? res.statusText);
  return body.model_id; // 之后一直复用
}

// 第二步：每次选面只传 model_id + face_id（不再传 file）
async function analyzeFaceById(modelId, faceId, options = {}) {
  const form = new FormData();
  form.append("model_id", modelId);
  form.append("face_id", faceId); // 例如 "face_3"
  form.append("options_json", JSON.stringify({ work_plane: "auto", ...options }));

  const res = await fetch(`${API_BASE}/api/v1/cad/analyze/face`, { method: "POST", body: form });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? res.statusText);
  return body; // CadFaceAnalyzeResult
}

// 用法：
// const modelId = await uploadStep(stepFile);
// const a3 = await analyzeFaceById(modelId, "face_3");
// const a7 = await analyzeFaceById(modelId, "face_7"); // 同一文件，零重传

// 兼容写法：首次也可直接带 file 一步到位
async function analyzeSelectedFace(stepFile, faceId, options = {}) {
  const form = new FormData();
  form.append("file", stepFile);
  form.append("face_id", faceId);
  form.append("options_json", JSON.stringify({
    linear_deflection: 0.1,
    work_plane: "auto",
    ...options,
  }));

  const res = await fetch(`${API_BASE}/api/v1/cad/analyze/face`, {
    method: "POST",
    body: form,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? res.statusText);
  return body; // CadFaceAnalyzeResult
}

// 按类型取特征，供路径规划模块使用
function groupForPathPlanning(analyze) {
  const g = analyze.feature_groups;
  return {
    outerContour: (g.contours_by_type.outer ?? [])[0] ?? null,
    holes: g.holes_by_type.circle ?? [],
    slots: g.contours_by_type.slot ?? [],
    rectangles: g.contours_by_type.rectangle ?? [],
  };
}
```

### 5.2 单面分析 + 刀路（一步）

```javascript
async function analyzeFaceAndPath(stepFile, faceId) {
  const form = new FormData();
  form.append("file", stepFile);
  form.append("face_id", faceId);
  form.append("analyze_options_json", JSON.stringify({ work_plane: "auto" }));
  form.append("path_options_json", JSON.stringify({
    strategy: "combined",
    tool_diameter: 6,
    step_over: 3,
  }));

  const res = await fetch(`${API_BASE}/api/v1/cad/analyze/face_and_path`, {
    method: "POST",
    body: form,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? res.statusText);
  return body; // { analyze, path }
}
```

### 5.3 分步：先单面分析，再生成刀路

```javascript
async function generatePathFromFaceAnalyze(faceAnalyzeResult) {
  const form = new FormData();
  form.append("analyze_json", JSON.stringify(faceAnalyzeResult));
  form.append("path_options_json", JSON.stringify({ strategy: "combined", tool_diameter: 6 }));
  const res = await fetch(`${API_BASE}/api/v1/cad/path/generate/face`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}
```

### 5.4 cURL（联调）

```bash
curl http://127.0.0.1:8000/api/v1/cad/status

# 上传一次拿 model_id
curl -X POST http://127.0.0.1:8000/api/v1/cad/upload -F "file=@part.stp"
# → {"model_id":"9f1c...","filename":"part.stp",...}

# 之后选面只传 model_id（无需重传文件）
curl -X POST http://127.0.0.1:8000/api/v1/cad/analyze/face \
  -F "model_id=9f1c..." \
  -F "face_id=face_0" \
  -F "options_json={\"work_plane\":\"auto\",\"linear_deflection\":0.1}"

# 兼容：首次也可直接传 file
curl -X POST http://127.0.0.1:8000/api/v1/cad/analyze/face \
  -F "file=@part.stp" \
  -F "face_id=face_0" \
  -F "options_json={\"work_plane\":\"auto\",\"linear_deflection\":0.1}"

curl -X POST http://127.0.0.1:8000/api/v1/cad/analyze/face_and_path \
  -F "file=@part.stp" \
  -F "face_id=face_0" \
  -F "path_options_json={\"strategy\":\"combined\",\"tool_diameter\":6}"
```

---

## 6. CORS（跨域）

后端默认允许所有来源（`allow_origins=["*"]`）。生产环境在 `backend/.env` 配置：

```env
CORS_ALLOW_ORIGINS=https://your-frontend.com,http://localhost:5173
CORS_ALLOW_CREDENTIALS=true
```

---

## 7. TypeScript 类型（复制到外部项目）

可从 OpenAPI 生成，或对照 `backend/app/models/cad.py` 手写。核心类型名：

| 类型 | 用途 |
|------|------|
| `CadFaceAnalyzeResult` | 单面分析结果（**推荐**） |
| `FaceFeatureGroups` | `feature_groups` 分组结构 |
| `CadFaceAnalyzeAndPathResponse` | 单面分析 + 刀路 |
| `CadAnalyzeResult` | 全模型分析（兼容） |
| `PathPlanResult` | 刀路结果 |
| `CadAnalyzeOptions` / `PathPlanOptions` | 请求选项 |

---

## 8. STEP → GLB（`/api/v1/stp/convert`）

用于 3D 预览显示（合并为单一 mesh）。**按面提取轮廓/特征**请使用 `/cad/analyze/face`，与 GLB 导出相互独立。

```
GET  /api/v1/stp/status     → { convert_ready, engine, ... }
POST /api/v1/stp/convert    → multipart file → 二进制 GLB
```

Query 参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `linear_deflection` | `0.1` | 网格精度 (mm) |
| `angular_deflection` | `0.5` | 角度偏差 (rad) |

- **conda `occ`（已装 pythonOCC）**：pythonOCC 三角化导出
- **无 pythonOCC**：使用 cascadio

---

## 9. 后端启动（供外部联调）

```bat
cd RobotLaserNew
run_server.cmd
```

需 Conda 环境 `occ`（含 pythonOCC）。算法说明见 [CAD_ALGORITHM.md](./CAD_ALGORITHM.md)，字段说明见 [CAD_RESPONSE_FIELDS.md](./CAD_RESPONSE_FIELDS.md)。
