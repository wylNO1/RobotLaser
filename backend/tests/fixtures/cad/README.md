# CAD 特征识别测试用例

本目录存放 STEP 测试零件及生成脚本。

| 文件 | 说明 | 预期特征 |
|------|------|----------|
| `box_100x60x20.step` | 长方体 | 6 平面、12 边、外轮廓、参考点 |
| `plate_with_hole_100.step` | 带通孔板 | 平面 + 内环、至少 1 个孔 |

## 生成 STEP

```bat
conda activate occ
cd backend
python tests/fixtures/cad/generate_fixtures.py
```

## 运行测试

```bat
cd backend
pytest tests/test_cad_features.py -v
```
