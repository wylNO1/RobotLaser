# Backend (FastAPI)

## Run locally

**CAD 特征接口需要 pythonOCC**，请使用 Conda 环境 `occ`，不要用根目录 `.venv`：

| 解释器 | pythonOCC | 用途 |
|--------|-----------|------|
| `miniconda3\envs\occ\python.exe` | 有 | 后端 + CAD（推荐） |
| 项目根 `.venv` | 无 | 仅 URDF / 部分 STP |

从仓库根目录：

```bat
setup_occ_backend.cmd
run_server.cmd
```

或手动：

```bat
conda activate occ
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

PyCharm：见 `.idea/PYCHARM_INTERPRETER.md`。Cursor/VSCode：已配置 `.vscode/settings.json` 指向 `occ`。

Tests: `pytest tests -q` (needs `requirements-dev.txt`).

CAD 特征识别专项测试（需 conda `occ`）:

```bat
cd backend
python tests/fixtures/cad/generate_fixtures.py
pytest tests/test_cad_features.py -v
```

## API

- `GET /health` — liveness
- `POST /api/v1/urdf/convert` — URDF or ZIP → Babylon scene JSON
- `GET /api/v1/urdf/convert_path` — URDF from server path (dev only)
- `GET /api/v1/stp/status` — STEP→GLB 引擎是否就绪
- `POST /api/v1/stp/convert` — STEP/STP → GLB（cascadio 优先，失败时用 pythonOCC 三角化）
- `GET /api/v1/cad/status` — pythonOCC availability
- `POST /api/v1/cad/analyze` — feature extraction (points, contours, faces, holes)
- `POST /api/v1/cad/analyze/face` — extract contours/features for one selected face (`face_id=face_12`)
- `POST /api/v1/cad/analyze/face_and_path` — single-face analyze + toolpath
- `POST /api/v1/cad/path/generate` — toolpath from analyze JSON
- `POST /api/v1/cad/path/generate/face` — toolpath from single-face analyze JSON
- `POST /api/v1/cad/analyze_and_path` — analyze + path in one call
- `GET /api/v1/ikfast/status` — ikfast 本地库是否可用
- `POST /api/v1/ikfast/m20ia-35m/inverse` — FANUC M-20iA/35M 逆解
- `POST /api/v1/ikfast/m20ia-35m/forward` — FANUC M-20iA/35M 正解

**ikfast 编译**（首次使用逆解前，需 MinGW `g++`）:

```bat
setup_ikfast.cmd
```

MinGW 可通过 `winget install BrechtSanders.WinLibs.POSIX.UCRT` 安装。

**本地脚本调用**（不经过 HTTP）:

```bat
python backend\scripts\run_ikfast_m20ia.py status
python backend\scripts\run_ikfast_m20ia.py forward 0 -0.5 0.3 0 1.0 0
python backend\scripts\run_ikfast_m20ia.py inverse --x 0.5 --y 0 --z 0.8
```

详见 [app/ikfast/m20ia_35m/README.md](app/ikfast/m20ia_35m/README.md) 与 [docs/IKFAST_API.md](docs/IKFAST_API.md)。

Algorithm: [docs/CAD_ALGORITHM.md](docs/CAD_ALGORITHM.md)  
**External frontend API**: [docs/CAD_API_EXTERNAL.md](docs/CAD_API_EXTERNAL.md)  
**返回字段说明**: [docs/CAD_RESPONSE_FIELDS.md](docs/CAD_RESPONSE_FIELDS.md)

pythonOCC (optional): `conda install -c conda-forge pythonocc-core`

Swagger UI: `/swagger`

## Docker

```bash
docker build -t urdf-backend .
docker run -p 8000:8000 urdf-backend
```
