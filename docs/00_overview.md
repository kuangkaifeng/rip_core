# 00 · 项目总览：摆脱蒙泰 SDK 的 RIP / PRN 生成（mtr）

> 工作目录：`D:\work\RIP核心分析`（本仓库）
> 生产工程（只读参考）：`D:\Code\kkf\v1.1.2\rip-studio`
> 蒙泰 SDK（只读参考）：`D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK`

## 1. 目标

rip-studio 目前通过 `MainTopRip(JSON)`（`mtrip.dll` → `mtripNet.exe`，需加密锁）生成打印用 `.prn`。
本项目要：

1. 解析清楚蒙泰从「图像 + 作业 JSON + .prs」生成 `.prn` 的完整机制；
2. 在 **不依赖蒙泰 SDK / 加密锁** 的前提下，用 **C++/Qt** 实现等效的 RIP 与 PRN 生成器；
3. 用蒙泰 oracle（本机加密锁 + 运行中的 `mtripNet.exe`）产出的参考 PRN 做逐字节/逐像素验证。

## 2. 关键结论（速览）

| 项 | 结论 | 证据 |
|---|---|---|
| 机型/格式 | **A3-DTF-1390.prs（改装机，Epson 1390）→ ESC/P2**（文件头 `00 00 00 1B 01 ... @EJL 1284.4`）；**H13 XP600.prs（板卡机）→ 汉森 HSSF 0x5555**（文件头 `55 55`） | oracle 实测 + `northPrintSDK/include/ImageFormat.h` |
| 作业入口 | JSON 作业（`command:"rip"`, `doc.name`, `prs`, `modeId`, `rotate`, `scale`, `margin`, `view`, `color`, `inputColorEditor`, `inkIE`, `output.file.name`） | `src/service/ripService/ripcontrol.cpp` |
| oracle | `mtripNet.exe` 正在运行（HTTP 8089 / gRPC 8090）；POST `/mtrip/v1/jobs` 可生成与 rip-studio **除 TI 时间戳外逐字节一致**的 PRN | `tools/oracle/mtrip_oracle.py` |
| 几何 | 图像按 PNG 内嵌 DPI（约 120）→ 打印 DPI 缩放；`view.xdpi/ydpi` 对图片输入无效 | 参数实验（同图 view 120/300/600 输出逐字节相同） |
| 颜色码 | `0x00=C, 0x04=K, 0x11=Y, 0x12=M, 0x01=W1, 0x02=W2`（由纯色图对照得出） | `a3dtf1390_flat_*_100_m2.prn` |
| 白墨 | `inputColorEditor` 的 W1/W2 仅当 prs 模式本身含 W 通道（如 m1/m3，6 planes）才进入 PRN；mode2（4 planes）下加 W1 输出与不加**逐字节相同** | 参数实验 + 金样本 |
| 迁移 | 当前 rip-studio 的 `RipWorker::doRip` 实际对**所有机型**都用 `GemodifiseerdeMasjienRip.json + A3-DTF-1390.prs`（H13 分支被注释） | `ripcontrol.cpp` |

## 3. 目录结构

```
docs/        分析文档（本目录）
reference/   蒙泰 oracle 参考语料（inputs/ 合成输入图, jobs/ 作业JSON+响应, prn_samples/ 参考PRN）
tools/       oracle 脚本、prs 解析、prn 解析/校验工具
src/         我们的 C++/Qt 实现（mtr_core + mtr_cli）
  3rdparty/  lcms2 源码
  build/     构建产物（build/mtr_cli.exe）
work/        各分析员中间产物（protocol/escp2/prs/board/shared）
build.cmd    一键构建脚本（MSVC + Qt6.8.3 + Ninja）
```

## 4. 构建与使用

环境：Qt 6.8.3 MSVC2022 x64（`D:\software\qt6\6.8.3\msvc2022_64`）、VS2022/2026（`D:\Microsoft Visual Studio\18\Community`）、CMake 3.30、Ninja。

```powershell
cmd /c D:\work\RIP核心分析\build.cmd          # 构建 -> build\mtr_cli.exe
build\mtr_cli.exe info --prs ...\A3-DTF-1390.prs
build\mtr_cli.exe rip  --job reference\jobs\xxx.json
build\mtr_cli.exe decode --prn reference\prn_samples\xxx.prn --out outdir
```

## 5. 验证思路

1. **结构/字节级**：同一作业 JSON，`mtr_cli` 生成的 PRN 与 oracle PRN 比较（PSNR/差异率/逐段字节）。
2. **页面级**：把双方 PRN 反解为“页面点阵”（每色 8bit 点大小图），逐像素比较差异率。
3. **实机打印**：把生成的 PRN 通过 RAW 方式发给 Epson 1390（或北印 SDK 发给板卡机）验证。

## 6. 进度与文档索引

| 文档 | 内容 | 负责人 |
|---|---|---|
| `docs/01_maintop_pipeline.md` | 蒙泰 SDK/服务/作业协议/双格式/坑 | protocol-analyst |
| `docs/02_geometry_escp2.md` | ESC/P2 作业结构 + 图像→光栅块几何（本项目核心公式） | Lead（持续更新） |
| `docs/prn_escp2.md` | ESC/P2 完整规范（字段级） | escp2-analyst |
| `docs/prs_format.md` / `docs/color_pipeline.md` | .prs 结构、ICC/线性化/加网/白墨管线 | prs-analyst |
| `docs/prn_board.md` / `docs/board_pipeline.md` | HSSF 0x5555 格式与板卡链路 | board-analyst |
| `docs/06_validation.md` | 验证结果报告 | Lead |


---

# 附录 · 当前交付状态（2026-11-06 15:20）

## 已交付

| 类别 | 文件 |
|---|---|
| 总览/流程 | `docs/00_overview.md`、`docs/01_maintop_pipeline.md`、`docs/maintop_api.md`（T1，57KB） |
| ESC/P2 规范 | `docs/prn_escp2.md`（T2，26KB，含整文件 round-trip 逐字节验证工具）、`docs/02_geometry_escp2.md` |
| PRS/色彩/加网 | `docs/prs_format.md`、`docs/color_pipeline.md`（T3） |
| 板卡机 HSSF | `docs/prn_board.md`、`docs/board_pipeline.md`（T4） |
| 集成方案 | `docs/05_integration.md`（DLL 1:1 替换 mtrip.dll 的 C API 兼容层） |
| 验证报告 | `docs/06_validation.md` |
| C++ 实现 | `src/`：mtr_core（PrsConfig / 图像 / ICC / 加网 / ESC-P2 编码 / HSSF 编码 / 布局 / PRN 反解）、`mtr_cli.exe`、`mtr_rip.dll`（导出 MainTopRip 等 4 函数） |
| 工具 | `tools/oracle/`（oracle 生成/校验/语料）、`tools/prn_tools/`（解析/RLE/round-trip/预览）、`tools/prs_tools/`（prs/ICC/加网分析）、`tools/board_tools/`（HSSF 解析）、`tools/validate/` |
| 语料 | `reference/prn_samples/` 784 个参考 PRN（235MB）+ `reference/jobs/manifest_all.csv`；`reference/profiles/` ICC/LUT；`reference/inputs/` 合成输入图 |
| 构建 | `build.cmd`（一条命令：MSVC+Qt6.8.3+Ninja 构建并自动部署 Qt/ICC/PRS），产物 `build/mtr_cli.exe`、`build/mtr_rip.dll` |

## 验证结论（详见 docs/06_validation.md）

- **oracle 与生产等价**：金样本重放除 TI 时间戳外逐字节相同；语料 784 个 PRN 全部可复现。
- **ESC/P2 结构**：我们的命令区 91 字节与 oracle **逐字节一致**；块数/推进/颜色记录顺序/n/m 一致。
- **整文件字节级**：T2 的 decode→re-encode 对 135 个样本（95.9MB）**逐字节一致（仅 TI）** → 编码器规则（含 RLE ≥3 规则）已完全掌握。
- **HSSF 0x5555**：T4 用 oracle 语料 92 项校验全通过，引擎已实现。
- **加网**：模型 `level=(3v+D)>>8` 精确（256 级探针 0 矛盾），C 通道阈值场已精确提取（384×384），M/Y/K 精确场正在由 T1 补跑数据后生成。
- **未完成/下一步**：① 四通道精确阈值场落盘后直接替换 `build/screen/`；② no-CC 的 RGB→CMYK 精确标定（K 偏低）；③ 大图阈值场覆盖（>384 行需要更大探针或发现 D 场生成规则）；④ 实机打印验收。


---

# 结项报告（最终版，2026-11-06 16:05）

## 交付物清单

| 类别 | 内容 |
|---|---|
| 可执行 | `build/mtr_cli.exe`（rip / info / decode / gray）、`build/mtr_prncheck.exe`、**`build/mtr_rip.dll`**（导出 MainTopRip / MainTopRipCancel / MainTopRipReleaseBuffer / MainTopShutdown，可直接替换蒙泰 mtrip.dll） |
| C++/Qt 源码 | `src/`：PrsConfig、JobConfig、图像/ICC/限墨/白墨、FM 加网（1024 tile）、ESC/P2 编码器、版面布局（m0~m9 参数表）、HSSF 0x5555 编码器、PRN 反解、CLI、DLL 兼容层（40+ 文件，CMake 构建） |
| 资源 | `3rdparty/`：lcms2 源码、ICC profiles、加网 tile（`3rdparty/screen`）、灰度标定（`3rdparty/color`），`build.cmd clean` 自动部署 |
| 文档 | `docs/` 11 篇：总览/流程、MainTop API（57KB）、ESC/P2 规范（28KB）、几何、PRS 格式、色彩与加网管线（含 oracle 缺陷定性）、HSSF 规范、板卡链路、集成方案、验证报告（14 节） |
| 工具 | `tools/`：oracle 生成/校验、prs/ICC/加网分析、prn 解析/RLE/round-trip/预览、HSSF 解析、端到端对拍（90+ 脚本） |
| 语料 | `reference/prn_samples/` 2587 个参考 PRN（~750MB）+ `reference/jobs/` 作业 JSON + `reference/screen/final/` 1024 tile + `reference/profiles/` |
| 证据 | `work/`：各分析员中间产物/实验/日志/审计（oracle 缺陷 832 cell、确定性复核、加网探针全量对拍等） |

## 最终验证指标

| 指标 | 结果 |
|---|---|
| 纯白作业 PRN vs 蒙泰 oracle | **逐字节完全一致**（264B，仅 TI 时间戳） |
| ESC/P2 反解→重编码回归 | 有效 ESC/P2 **1847/1847** 样本内容平面 **0 差异**（m0/1/2/3/5/7/9） |
| 加网（stochastic FM 1024 tile） | 全 256 级探针：972/1024 直接 100%；排除蒙泰自身 832 个"非单调漏点"cell 后 **1024/1024 = 100.0000%** |
| 蒙泰确定性 | 52 缺陷作业重跑 ×2：PRN **逐字节一致** ⇒ 缺陷可复现、非随机 |
| 端到端（引擎 vs oracle 页面点阵） | 灰阶/黑图逐像素 **99.4%~99.9%**（残差=蒙泰羽化/weave 不打印像素，打印等价） |
| 构建复现 | `build.cmd clean` 全自动（Qt/ICC/PRS/tile/标定部署），验收脚本 `roundtrip_check.py` → ALL OK |

## 已知限制与后续（可选）
1. 蒙泰羽化/weave 掩码未复刻（内容 ~0.1~0.5% 像素差异，打印结果等价；规律已采集，实现即可逐字节复刻）；
2. 彩色图像 3D 色彩标定未做（灰度轴已标定 ±1；RGB 探针数据已备）；
3. m5/7/9 加网 tile 复用未验证（引擎运行时已告警，不用于验收）；
4. 实机打印验收待做（A3-DTF-1390 / H13 板卡机）。

> 说明：`D:\Code\kkf\v1.1.2\rip-studio` 与 `3rdLib\mtripSDK` 仅作为只读分析对象，**源码未被修改**。


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
