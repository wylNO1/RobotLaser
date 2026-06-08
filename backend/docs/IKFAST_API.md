# ikfast 逆解 API

FANUC **M-20iA/35M** 六轴机器人解析逆解，基于 OpenRAVE ikfast。

## 前置条件

1. 源码位于 `backend/app/ikfast/m20ia_35m/`
2. 安装 MinGW（推荐）并编译 DLL：

```bat
winget install BrechtSanders.WinLibs.POSIX.UCRT
setup_ikfast.cmd
```

3. 调用 `GET /api/v1/ikfast/status`，`ikfast_available` 为 `true`

## 本地 Python 脚本（不经 HTTP）

**请使用项目 `.venv`，不要用系统自带的 `python`**（否则会报 `No module named 'pydantic'` 等错误）。

```bat
cd 仓库根目录

REM 推荐：一键脚本（自动用 .venv）
run_ikfast_demo.cmd status
run_ikfast_demo.cmd forward 0 -0.5 0.3 0 1.0 0
run_ikfast_demo.cmd inverse --x 0.5 --y 0 --z 0.8

REM 或手动指定解释器
.venv\Scripts\python.exe backend\scripts\run_ikfast_m20ia.py status
```

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/ikfast/status` | 库是否可用、机型列表 |
| POST | `/api/v1/ikfast/m20ia-35m/inverse` | 逆解 |
| POST | `/api/v1/ikfast/m20ia-35m/forward` | 正解 |

## 逆解

**POST** `/api/v1/ikfast/m20ia-35m/inverse`

```json
{
  "position": { "x": 0.5, "y": 0.0, "z": 0.8 },
  "rpy": { "roll": 0.0, "pitch": 0.0, "yaw": 0.0 }
}
```

也可用 `rotation`（行优先 3×3）代替 `rpy`，二者不可同时传。

**响应示例：**

```json
{
  "model_id": "m20ia_35m",
  "num_solutions": 2,
  "solutions": [
    { "index": 0, "joints": [0.1, -0.5, 0.3, 0.0, 1.2, 0.0] },
    { "index": 1, "joints": [2.4, -1.1, -0.2, 3.1, -0.5, 1.0] }
  ],
  "units": { "length": "m", "angle": "rad" }
}
```

- `joints` 为 6 个关节角（弧度），多解时需按限位、连续性等自行筛选。

## 正解

**POST** `/api/v1/ikfast/m20ia-35m/forward`

```json
{
  "joints": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
}
```

返回 `position` 与 `rotation`（行优先矩阵元素 `r00`…`r22`）。

## 错误码

| HTTP | 含义 |
|------|------|
| 501 | 未编译或未找到本地 DLL |
| 422 | 请求参数不合法 |

## 项目内模块说明

| 模块 | 职责 |
|------|------|
| `app/ikfast/m20ia_35m/` | C++ 源码与编译脚本 |
| `app/ikfast/native_loader.py` | ctypes 加载 DLL |
| `app/ikfast/pose.py` | RPY ↔ 旋转矩阵 |
| `app/services/ikfast_service.py` | 业务逻辑 |
| `app/routers/ikfast.py` | HTTP 路由 |
