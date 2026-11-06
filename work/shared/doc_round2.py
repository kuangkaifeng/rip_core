# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add = """

## 10. 第二轮结果（1024 阈值 tile + 灰度轴标定集成后，2026-11-06 15:5x）

### 10.1 关键数据就绪
- **1024×1024 加网阈值 tile**（内容相对坐标，D(x,y)=TILE[x%1024][y%1024]）：
  `reference/screen/engine/thr_{C,M,Y,K}.bin`（1024²×3 字节 [T1,T2,T3]），已持久化到
  `3rdparty/screen/` 并由 `build.cmd` 自动部署到 `build/screen/`（clean build 也不会丢）。
  - C/Y 来自 176×176 × 256 级探针（T1），T3 验证模型 `level=(3v+D)>>8` 与解码 PRN **逐像素 0 差异**；
  - M/K 目前由互补关系（D_M=258−D_C、D_K=258−D_Y）推导（约 99.6% 精确，T1 正在补 176×176 直取数据）。
- **灰度轴标定 LUT**：`3rdparty/color/calib_gray.bin`（4×256，v_icc→v_oracle，
  由 oracle 的 32 级 RGB 中性灰探针 + 精确 tile 反解整数墨值拟合，见
  `tools/color_tools/fit_gray_calib2.py`），`build.cmd` 自动部署到 `build/color/`。

### 10.2 端到端验证结果（`tools/validate/validate_e2e.py`）

| case | 结果 |
|---|---|
| `a3dtf1390_flat_white_100_m2`（纯白） | ✅ **逐字节完全一致（264B，diff=0）** |
| `probe_scan_gray000`（黑, 64×64） | 页面点阵一致率：C 99.84% / K 98.89% / Y 99.68% / M 99.80% |
| `probe_scan_gray064` | C 99.93% / K 99.58% / Y 99.67% / M 99.76% |
| `probe_scan_gray128` | C 99.65% / K 99.50% / Y 99.63% / M 99.45% |
| `probe_scan_gray192` | C 99.49% / M 99.68% / Y 99.44% / K 100%（K 无墨） |
| `probe_scan_gray248` | C 99.71% / M 99.90% / Y 99.72% / K 100% |
| `a3dtf1390_flat_black_100_m2`（100×100，内容 600×600） | C 99.83% / K 98.88% / Y 99.70% / M 99.82% |

剩余误差来源（已定位）：
1. M/K tile 由互补推导（~99.6%），T1 已开始补 176×176 M/K 直取探针；
2. C/Y tile 的 238/240 个"边缘异常位置"（0xFFFF）需填有效阈值；
3. 标定 LUT 是灰度轴 1D 近似（颜色输入的三维色彩仍需 RGB ramps 标定，数据已备）。

### 10.3 可复现命令

```powershell
cmd /c D:\\work\\RIP核心分析\\build.cmd clean     # 会部署 Qt/ICC/PRS/screen tile/calib
python tools\\validate\\validate_e2e.py a3dtf1390_flat_white_100_m2 probe_scan_gray000_a3dtf1390_m2
python tools\\color_tools\\fit_gray_calib2.py       # 重建灰度标定 LUT
```
"""
if "第二轮结果（1024 阈值 tile" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("validation doc updated with round2")
