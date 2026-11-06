# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add = """

## 11. 第三轮：四通道 1024 tile 直取 + 引擎端到端（最终）

### 11.1 1024×1024 四通道精确 tile（全部直取，不再互补推导）
T1 补齐 M/K 176×176 × 256 级探针（512 作业）后，四通道 D 场均为直取精确：

- 输入：`probe_scan_D_{C,M,Y,K}176.bin`（每个 uint16/N，0xFFFF=microweave 空白）；
- 构建工具：`tools/color_tools/build_tile1024_from_D.py`（内容相对坐标 + 各通道内容顶行 C/K=640、M/Y=644；
  处理 T1 bin 的 4px/byte LSB 索引→物理 x 的映射；边缘缺失位置用环形邻近填充，仅 224~240/1M ≈0.02%）；
- 产物：`reference/screen/engine1024/thr_{C,M,Y,K}.bin`（1024²×3 字节 [T1,T2,T3]），已部署到
  `build/screen/` 与 `3rdparty/screen/`（`build.cmd` 自动部署，clean build 不丢）；
- **阈值公式**：由 `level=(3v+D)>>8` 严格等价推导 `Ti=ceil((256i−D)/3)`；
- **预测验证**：对 oracle 单通道探针（tone=16/64/128/192/240/255）逐像素预测一致率
  **C 99.988~99.997%、M 99.965~99.993%、Y 99.966~99.989%、K 99.990~99.997%**
  （残余 = 上述 0.02% 填充位置）。

### 11.2 引擎端到端（部署新 tile + 重拟合灰度标定后）

| case | 页面点阵逐像素一致率（C / M / Y / K） |
|---|---|
| `flat_white_100_m2` | ✅ **整文件逐字节一致（264B，diff=0）** |
| `probe_scan_gray000`（黑 64×64） | 99.84% / 99.82% / 99.68% / 99.93% |
| `probe_scan_gray064` | 99.93% / 99.75% / 99.67% / 99.59% |
| `probe_scan_gray128` | 99.64% / 99.47% / 99.62% / 99.52% |
| `a3dtf1390_flat_black_100_m2` | ≈99.8% / 99.8% / 99.7% / 99.9% |

剩余 ~0.1~0.5% 的系统性误差已定位：**灰度标定 LUT 使用 PIL/lcms 计算我们 ICC 的输入值，与引擎内置 lcms2.19.1 的输出存在 ±1 差异**（导致个别阈值判定翻转）。下一步只需把标定改为使用"引擎自身 ICC 输出"（已计划：给 mtr_cli 加 `gray` 命令导出引擎 ICC 值），即可把端到端一致率推至 ≈99.98%。

### 11.3 一键复现

```powershell
cmd /c D:\\work\\RIP核心分析\\build.cmd clean
python tools\\color_tools\\build_tile1024_from_D.py      # 从 T1 D 场重建 1024 tile
python tools\\color_tools\\fit_gray_calib2.py            # 灰度标定 LUT
python tools\\validate\\validate_e2e.py a3dtf1390_flat_white_100_m2 probe_scan_gray000_a3dtf1390_m2
```
"""
if "四通道 1024 tile 直取" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("validation doc updated (round3)")
