# FANUC M-20iA/35M 逆解（ikfast）

OpenRAVE **ikfast** 自动生成的解析逆解源码，集成在本后端项目中。

## 目录结构

```
m20ia_35m/
├── ikfast.h              # ikfast 公共头（OpenRAVE）
├── M-20iA_35M.cpp        # 逆解/正解实现（勿手改）
├── ikfast_export.cpp     # C 导出层（供 Python ctypes）
├── build.cmd             # Windows 编译脚本
├── lib/                  # 编译输出（git 忽略）
│   └── m20ia_35m_ik.dll
└── README.md
```

## 编译（Windows）

需安装 [MinGW-w64](https://www.mingw-w64.org/) 并将 `g++` 加入 PATH：

```bat
cd backend\app\ikfast\m20ia_35m
build.cmd
```

Linux / macOS：

```bash
g++ -std=c++11 -O2 -DIKFAST_NO_MAIN -shared ikfast_export.cpp M-20iA_35M.cpp -o lib/libm20ia_35m_ik.so
```

## 单位与坐标系

| 量     | 单位   |
|--------|--------|
| 平移   | 米 (m) |
| 关节角 | 弧度 (rad) |
| 旋转   | 行优先 3×3 矩阵 |

末端位姿须与生成该 ik 时的 OpenRAVE 机器人模型一致（DH、工具坐标、零位）。

## 相关 API 文档

见 `backend/docs/IKFAST_API.md`。
