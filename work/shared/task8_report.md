# task-8 报告：引擎集成 RGB 3D LUT（彩色复刻）+ 羽化掩码（可选）

> 负责人：engine-dev；时间：2026-11-06 18:55（Asia/Shanghai）
> 任务：用户实机打印彩色照片"发黑/发闷 + 横向条纹"。Lead 已修 DPI 语义（JPEG 无有效 DPI → 72）；
> 本报告涵盖 ① RGB 9³ 3D LUT 集成 ② 可选羽化 ③ 端到端对比与回归。

---

## 1. 端到端结果（`print_debug_test22.jpg` 860×564 @72dpi → 内容 8600×5640，80 块）

命令：`build/mtr_cli.exe rip --input reference/inputs/print_debug_test22.jpg --prn <out> --prs reference/prs/A3-DTF-1390.prs --mode 2`
对比：`build/mtr_prncheck.exe compare reference/prn_samples/print_debug_test22_m2.prn <out>`
（内容平面：C/M/Y/K 逐像素 2bit level 差异率）

| 变体 | K | C | M | Y | **TOTAL** | 说明 |
|---|---|---|---|---|---|---|
| 旧路径 `MTR_NO_CUBE_LUT=1` | 11.40% | 49.48% | 13.17% | 32.31% | **26.589%** | 基线（与 Lead 报的 26.59% 一致）；自适应开关验证有效 |
| **默认（3D LUT + 灰度 ICC）** | 2.217% | 3.121% | 4.383% | 6.059% | **3.945%** | 本次集成默认路径 |
| `MTR_CUBE_GRAY=1`（灰度也用 LUT） | 2.217% | 3.124% | 4.385% | 6.062% | 3.947% | 略差 → 证实"灰度保留 ICC+calib"是正确的 |
| `MTR_CUBE_TETRA=1`（四面体插值） | 2.026% | 2.943% | 3.803% | 5.555% | **3.582%** | 更优（9% 相对降低），见 §2.4 |

- 结构完全一致：blocks 80/80、content 8600×5640、p0=640、记录顺序 K,C,M,Y、320 条记录 color/n/m 全同。
- 28.6pp 的下降来自 3D LUT；剩余 3.58~3.95% 主要是 **9³ 网格三线性/四面体插值误差**（见 §2.3 的自校验）。
- 输出文件：`work/shared/print_debug/ours_test22_m2.prn`（默认）、`ours_test22_m2_tetra.prn`、`ours_test22_m2_feather.prn`、`ours_test22_m2_nocube.prn`。

## 2. RGB 9×9×9 3D LUT 集成

### 2.1 新增文件
- `src/core/color/rgb_cube_lut.{h,cpp}`：`RgbCubeLut` 加载 + 三线性/四面体插值。
  - 格式：magic `"RGB9"` + u16 size(=9) + u8 channels(=4) + 4×729 u8；
  - 索引：`((rIdx*9 + gIdx)*9 + bIdx) + channel*729`（r-major/g/b-minor；ink 顺序 C,M,Y,K）；
  - 轴网格非均匀 `{0,32,64,96,128,160,192,224,255}`，用 256 项预计算查表做分段坐标映射；
  - 资源路径：`resolveResourceDir("color")/rgb_cube9.bin`（build.cmd 部署 `3rdparty/color/*` → `build/color/`）。
- `src/core/rip_engine.cpp`：RGB→CMYK 阶段接入（见 §2.2）；CMakeLists 追加 `core/color/rgb_cube_lut.cpp`。

### 2.2 转换规则（优先级）
```
透明像素（readTransparency）：
  a==0      -> 不产生墨（全 0）              【语义不变】
  0<a<255   -> 先与白底合成 RGB，再走下面规则  【语义不变】
非透明像素：
  A3 (prs.version==3) 且 LUT 可用 且 !(灰度 && ICC 可用)  -> 3D LUT
  否则 ICC + calib_gray（旧路径，灰度优先走此路径）        -> 旧路径
  否则朴素互补兜底
```
- **灰度像素（r==g==b）默认仍走 ICC+calib_gray**（Lead 要求；A/B 显示灰度用 LUT 略差，见上表）。
- `MTR_NO_CUBE_LUT=1`：强制回退旧路径（已验证 = 26.589% 基线）。
- `MTR_CUBE_LUT=<path>`：覆盖 LUT 文件路径（A/B 实验用）。
- `MTR_CUBE_GRAY=1`：灰度也用 LUT（实验，默认关）。
- `MTR_CUBE_TETRA=1`：四面体插值替代三线性（实验，默认关）。
- `MTR_VERBOSE=1`：打印 LUT 是否加载成功/路径。
- 资源缺失时**静默回退** ICC 路径（不影响可编译/可运行）。

### 2.3 LUT 自校验（RGB 立方体探针）
`reference/inputs/probe_rgbcube9_540.png`（729 个 9³ 格点色块）→ 我们生成 PRN vs oracle `probe_rgbcube9_540_m2.prn`：
**TOTAL 0.1506%**（K 0.084%/C 0.206%/M 0.175%/Y 0.137%）。
- 此场景所有像素都正好在 LUT 网格点上 → 说明"LUT 加载/索引/插值/加网链路"正确；
- 0.15% 残差 ≈ LUT 数据本身的栅格反解精度（Lead 报 max 0.0059 level；整数化+边界阈值翻转导致少量像素差 1 级），属 T3 校验范围；
- 而照片（颜色在网格点之间）默认 3.95% / 四面体 3.58%，说明剩余误差主要来自 9³ 网格插值近似，而不是引擎接线错误。
- 建议：T3 用 `probe_screen_rgb_ramps16` 独立量化插值误差；若明显，可考虑把 `MTR_CUBE_TETRA` 设为默认（接口不变，只需改一处布尔）。

### 2.4 四面体 vs 三线性
- 默认仍为 **三线性**（Lead 指定接口）；`MTR_CUBE_TETRA=1` 实测照片 TOTAL 3.945% → **3.582%**，
  立方体探针结果完全不变（0.1506%）。3D LUT 业界通常用四面体（对角方向更准），
  建议 Lead/T3 评估后决定是否改默认（一行改动）。

## 3. 可选羽化（feather，默认关闭）

### 3.1 背景与设计
- 厂商在块 k 与块 k+8 的重叠带（k 的 r=79..89 与 k+8 的 r=0..10 同纸行）把该行点阵按行内 x 掩码拆给两块（both=0，每点只打一次）。
- 我们默认"最大块号独占整行"（打印结果等价、已验证），接缝处没有厂商的羽化 → 用户报告横向条纹的可能原因之一。
- `layout_escp2.cpp` 已实现 **MTR_FEATHER=1**（仅 m2）：
  - 预计算每纸行覆盖它的 (block,row) 列表；恰好 2 块覆盖时：
    较早块 k 按密度表 `featherDensity(r)`（r=79..89 实测：90.83%→0）用确定性哈希掩码打印部分 x 点，
    较晚块 k+8 打印其余点；
  - 非重叠行/其他模式保持原行为；默认关闭，不影响默认输出与验收。

### 3.2 验证
- `flat_black_100_m2`：feather PRN 解码内容平面与厂商 **0% 差异**（未丢墨/未重复喷）；
  重叠行检查：`both=0`、`A∪B=600`（完整行），A 占比与密度表同量级（r=80: 85% vs 81.8% 目标，r=84: 47% vs 50%，r=88: 7.8% vs 9%）。
- `print_debug`：feather 输出内容平面与默认输出 **0 像素差异**（只是把同一些点分给两块）；
  文件 35.36MB → **40.39MB**（+14%；行内拆分使 RLE 变长；厂商同张照片 PRN 36.06MB）。
- 性能：print_debug 生成 2.7s（默认 3.4s 含 LUT），可接受。

### 3.3 风险（供用户实机 A/B）
1. 掩码是"同密度、不同源"的自研哈希，**不是厂商原掩码**：目的是改善接缝观感，不保证逐点/逐字节一致；不用于验收。
2. 颜色间 1~2 dot 的横向平移（物理头列错位）未复刻；m3/m0/m1 等多覆盖模式未实现（自动忽略）。
3. 文件变大 +14%；RLE 边界与默认不同。
4. **默认关闭**：`MTR_FEATHER=1` 时才生效；roundtrip/白图验收不受影响。
5. 若实机条纹仍在，需再查其他原因（如加网 tile 的行相位、平台步进等）。

## 4. 回归（默认路径，无环境变量）
- `python tools/validate/roundtrip_check.py` → **ALL OK**：
  - 4 个纯白样本逐字节一致（264B，byteDiff=0）；
  - 13 个 PRN 目标内容平面 0.0000%、块数一致；
  - CLI 白图端到端 TI-normalized byte-exact。
- 说明：LUT 只作用于 `rip_engine` 的 RGB→CMYK 阶段；`mtr_prncheck` 的反解/重编码与 layout/encoder 未变。

## 5. 交付文件清单
- 代码：`src/core/color/rgb_cube_lut.{h,cpp}`（新）、`src/core/rip_engine.cpp`（接入 + 开关）、
  `src/core/encode/layout_escp2.{h,cpp}`（feather 可选 + 注释）、`src/CMakeLists.txt`（追加源文件）。
- 产物/对比：`work/shared/print_debug/{ours_test22_m2.prn, ours_test22_m2_tetra.prn,
  ours_test22_m2_feather.prn, ours_test22_m2_nocube.prn, ours_rgbcube9_m2.prn,
  compare_default.txt, compare_cubegray.txt, compare_nocube.txt}`。
- 本报告：`work/shared/task8_report.md`。
