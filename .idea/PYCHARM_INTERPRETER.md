# PyCharm 解释器切换为 pythonOCC (conda occ)

当前项目 **不应** 使用根目录 `.venv`（无 OCC）。请使用：

`C:\Users\xuecheng\miniconda3\envs\occ\python.exe`

## 一次性配置

1. **File → Settings → Project: PythonProject2 → Python Interpreter**
2. 右上角齿轮 → **Add Interpreter → Add Local Interpreter**
3. 选 **Conda Environment** → **Existing** → 环境名 `occ`
4. 确认路径为上述 `python.exe`，名称显示为 **Python 3.10 (occ)**
5. Apply / OK

若列表中没有 `Python 3.10 (occ)`，添加后 `.idea/misc.xml` 中的 SDK 名称会自动匹配。

## 安装后端依赖

在项目根目录双击或执行：

```bat
setup_occ_backend.cmd
```

## 验证

```bat
C:\Users\xuecheng\miniconda3\envs\occ\python.exe -c "import OCC; import fastapi; print('ok')"
```
