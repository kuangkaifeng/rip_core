# -*- coding: utf-8 -*-
# ---- 00_overview: 追加 GUI + 透明修复 ----
p = r"D:\work\RIP核心分析\docs\00_overview.md"
t = open(p, encoding="utf-8").read()
add = """

---

# 附录：GUI 可视化工具（2026-11-06 晚）

- 新增 `mtr_gui.exe`（Qt Widgets）：选图/选 .prs/选 mode/白墨/旋转 → 生成 PRN → 解码显示打印点阵预览（合成/单通道/原图），RIP 在后台线程执行。
- 代码：`src/gui/`（main / mainwindow / previewrenderer），CMake 目标 `mtr_gui`；`build.cmd` 自动部署 Qt6Widgets + platforms/qwindows.dll。
- 自动化：`mtr_gui --selftest <img> <prs> <modeId> <outDir>`（生成 + 预览 PNG），`mtr_gui --screenshot <png> ...`（抓 UI 截图）。
- **顺带修复引擎透明语义**（T3 文档 §1 的 DTF 规则）：`readTransparency=true` 时
  `a==0` 的透明像素应**不产生墨**（此前被当成黑色印出）；`0<a<255` 与白底合成。
  修复后金样本（718×654 RGBA，84% 透明）输出 2,016,094B ≈ 蒙泰 1,734,682B（此前 11MB），
  总墨量 6,287,422 = 蒙泰 6,287,422（完全一致）；蒙泰剩余差异来自块空白带跳跃（49 vs 58 块）。
- 详见 [docs/07_gui.md](07_gui.md)。
"""
if "GUI 可视化工具" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("overview updated")

# ---- 06_validation: 透明修复验证 ----
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add2 = """

## 16. GUI 可视化工具与透明语义修复（收口补充）

### 16.1 `mtr_gui.exe`（Qt Widgets）
同一套 `mtr_core` 引擎的桌面可视化：选图 / 选 `.prs` / 选模式 / 白墨 / 旋转 → 生成 PRN →
后台线程完成后自动解码显示**打印点阵预览**（合成色、原图、单通道 C/M/Y/K/W1），
ESC/P2 与 HSSF 均支持。截图与用法见 [docs/07_gui.md](07_gui.md)。

无界面自检（本报告数字来源）：
```powershell
build\\mtr_gui.exe --selftest <input> <prs> <modeId> <outDir>
# 金样本：RIP OK 2,016,094 B / 预览 OK 4308x3924 / ESC/P2
# 纯白 100：RIP OK 264 B / 预览 OK 600x600（空白页面）
# 黑图 100：RIP OK 256,854 B / 预览 OK 600x600
```

### 16.2 透明语义修复（发现于 GUI 联调）
按 T3 文档 §1 的 DTF 规则修正引擎：
- `readTransparency=true` 且 `a==0`：透明像素**不产生墨**（此前被当成黑色印出）；
- `0<a<255`：按 alpha 与白底合成；`readTransparency=false`：忽略 alpha 按 RGB 处理。

验证（金样本 `1793946733018.png`，718×654 RGBA，84.5% 透明）：
| 指标 | 修复前 | 修复后 | 蒙泰 oracle |
|---|---|---|---|
| PRN 大小 | 11,059,669 B | **2,016,094 B** | 1,734,682 B |
| 总墨量（4 平面 ink 计数） | — | **6,287,422** | **6,287,422（完全一致）** |
| 内容平面像素差异 | — | 7.80%（彩色区域颜色配比+K 分配差异） | — |

块结构差异（蒙泰 49 块含空白带跳跃 150/349 vs 我们 58 块）与色彩 3D 标定是剩余已知项；
不透明图像的既有验证（白图逐字节一致、灰阶/黑图 99.4%~99.9%）**无回归**（本修复只影响 alpha<255 像素）。
"""
if "## 16. GUI 可视化工具与透明语义修复" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add2)
    print("validation updated")
