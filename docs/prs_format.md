# .prs 打印设置文件格式规范（蒙泰 MainTop / mtripSDK）

> 作者：prs-analyst。目标：让 C++/Qt 实现者能读/写 `.prs`，并知道每个字段对色彩/加网管线的意义。
> 证据文件（只读源）：
> - `D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs`（140,586 B，格式版本 3）
> - `D:\Code\kkf\v1.1.2\rip-studio\bin\bin\H13 XP600.prs`（157,762 B，格式版本 4）
> - `bin\bin\H13 XP600_myicc.prs` / `test_*.prs`（colorCorrection+saveAs 生成，用于对照）
> - 工作区只读副本：`reference\prs\A3-DTF-1390.prs`、`reference\prs\H13 XP600.prs`
> 解析工具：`tools\prs_tools\prs_parser.py`（结构 dump）、`extract.py`（LUT/ICC/mode 表导出）、
> `hexdump.py` / `strings.py` / `diff.py` / `blob_analyze.py`（取证）。
> 结构 dump 输出：`work\prs\prs_dump_*.json`、`work\prs\mode_table.json`、`work\prs\icc_analysis.json`、
> 提取的 LUT：`reference\profiles\luts\*.csv`。

---

## 0. 结论速览（TL;DR）

| 区块 | 偏移（A3 / H13） | 内容 | 置信度 |
|---|---|---|---|
| 魔数 | 0x00 = `D0 44 53 6E`（u32 = 0x6E5344D0） | "MtDS" 容器标识 | 高 |
| 格式版本 | 0x04：`03 00 00 00`=A3，`04 00 00 00`=H13 | 驱动格式版本 | 高 |
| 头长候选 | 0x0C：`60 01 00 00`(352) | 固定头长度/块表偏移 | 中 |
| 解释器模块名 | 0x14：`"MtDummy.pdv"` | 占位文件名字段（NUL 结尾，域宽 ~32B） | 高 |
| 头部其余 | 0x20–0x15F | 标志/机器号/校验/时间戳混合；0x80 处 4B 随内容变（校验?） | 低 |
| 文本配置块 | A3 主块 0x5545 起；H13 主块 0x2CE6 起 | NUL 结尾的 key=value + 驱动选项目录（见 §2） | 高 |
| 模式记录 | A3：3 个 @LUT 0xC090/0x14E18/0x1DB4C；H13：4 个 @0x769B/0x1036F/0x19043/0x21D17 | 每记录 = 不透明块~17KB + 8×线性化 LUT + 96B 配置 + 2 组 ICC 路径 | 高（除不透明块） |
| ICC 路径 | 每记录 2 组 × 4 条 × `char[260]`（stride 0x104） | `[srcRgb, srcCmyk, mcm, destCmyk]`（顺序由对照 queryIccpath 证实） | 高 |
| 线性化 LUT | 每记录 8 条 × 256 项 `double`，间隔 12B | 全部是恒等斜坡 `i/255`（本机文件未做线性化） | 高 |
| 尾块 | A3 0x224F0 `"Manufacturer=inksonic"` + 2×驱动名；H13 尾部同类 | 驱动身份 | 高 |

配色/加网参数在 PRS 中**基本只有文本配置**（wpk 波形名、dpi mode 名、StochasticHalftone、SetInkOrder、DotSize 范围等）；
**没有内嵌 ICC 二进制**（全文件无 `acsp`）——ICC 是外部文件，PRS 只存**裸文件名**，由 mtripNet 相对其
CWD/驱动目录解析。这是复刻时最关键的一点（见 color_pipeline.md §2）。

---

## 1. 容器总体布局（以 A3-DTF-1390.prs 为例，全部 offset 为十进制/十六进制文件偏移）

```
0x00000  固定头（0x160 字节左右；见 §1.1）
...
0x0025C  "SepLight=0\0"           ← 两个散落的小配置键（A3/H13 同一偏移！）
0x0026B  "UseScreenFusion=1\0"
0x00280  二进制小表（u32 小整数数组，如 0x4000/0x0083…，疑似 dpi/pass/表指针）
...
0x08034  [模式记录0 的不透明块开始]（16,476 B）
0x0C090  [记录0 的 8×256 double 恒等 LUT]（16,468 B）
0x100E4  [记录0 的 96 B 配置结构]
0x10144  [记录0 路径组 A：4×char[260]] → SRGB / CoatedFOGRA39 / commnew.mcm / v1440x1400-A3-DTF-1390.icm
0x10554  [88 B 结构]
0x105AC  [记录0 路径组 B：同 4 条路径的副本]
0x109BC  [模式记录1 不透明块开始]（17,500 B；尾部内含 double 斜坡片段）
0x14E18  [记录1 LUT]（16,468 B）
0x18E6C  [116 B VSD/点表：记录1/2 有，记录0 无]
0x18EE0  [记录1 96 B 配置]
0x18F40  [记录1 路径…dest = v1440x720-A3-DTF-1390.icm]
0x197C0  [模式记录2 不透明块开始]（17,292 B）
0x1DB4C  [记录2 LUT]
0x21BA0  [116 B 表]
0x21C14  [记录2 96 B 配置]
0x21C74  [记录2 路径…dest = v2880x1400-A3-DTF-1390.icm]
0x224B4  ← 记录2 路径组 B 结束
0x224F0  "Manufacturer=inksonic\0" + 驱动名记录（两段：A3-DTF-1390 / A3-DTF-1390）
0x2252A  EOF
```

**每模式记录固定组成（A3 验证）**：

| 部分 | 大小 | 证据 |
|---|---|---|
| 不透明块（含义未知，高熵 ~7.4 bits/byte） | A3: 16,476 / 17,500 / 17,292 B；H13: ≈17,320 B | 记录间跨度 − 后续固定部分；`blob_analyze.py` |
| 8×256 double 线性化 LUT + 7×12B 间隔 | 8·2048 + 7·12 = 16,468 B | 8 组 `1/255` double 签名，见 §3 |
| 可选 116 B VSD/点表 | 116 B | 仅 A3 rec1/rec2、H13 记录中；内容见 §3.3 |
| 96 B mode 配置结构 | 96 B | 见 §3.4 |
| 路径组 A：4×`char[260]` | 1,040 B | stride 260=MAX_PATH；`\0` 结尾 |
| 88 B 结构 | 88 B | 两路径组之间固定间距 |
| 路径组 B：4×`char[260]`（A 的副本） | 1,040 B | 两组的 4 个字符串逐字节相同 |

记录跨度（A3）：rec0 0x8034→0x109BC = 35,208 B；rec1 0x109BC→0x197C0 = 36,356 B；rec2 0x197C0→0x224B4 = 36,084 B。
H13 记录跨度恒定 = 0x8CD4 = 36,052 B（4 条记录；rec0 从文本块结束 0x? 到 0x1036F）。

### 1.1 固定头字段表

用 A3 与 H13 对照（`work/prs/prs_dump_*.json` 的 `header`）：

| 偏移 | 类型 | A3-DTF-1390 | H13 XP600 | 解释/证据 |
|---|---|---|---|---|
| 0x00 | u32 | 0x6E5344D0 (`D0 44 53 6E`) | 同 | 魔数 |
| 0x04 | u32 | 3 | 4 | 格式版本（A3 驱动较旧） |
| 0x08 | u32 | 0x00000701 | 0x00000704 | 与版本相关（=版本+0x6FE?）待定 |
| 0x0C | u32 | 0x160 | 0x160 | 头/第一个二级区起点（两文件相同） |
| 0x10 | u32×2 | `00 00 80 01` | 同 | u16(0,0x180) 或 u32 0x01800000；疑似块表个数/尺寸上限 |
| 0x14 | char[32] | `"MtDummy.pdv"` | 同 | 解释器模块名（工具注释：**不决定输出格式**） |
| 0x20 | u32×4 | `0,0x010C0D01,0x00000B00,0` | 同 | 头部标志/机器号 |
| 0x30 | u32[6] | 1, 0x27D, 0x11C, 0x361, 0x351, 0x341 | 不同 | 表指针/长度候选（待验证） |
| 0x48..0x64 | u32[8] | 0,0,0,0x4000,0x4000,0x4000,0x4000,0x267 | 不同 | 混合计数；0x4000=16384 反复出现（16K 块尺寸？） |
| 0x68 | u32 | 0x267(615) | ? | 计数 |
| 0x78 | u32 | 0x499(1177) | ? | 计数 |
| 0x7C | u32 | 0x7C48(31816) | ? | 偏移/长度 |
| 0x80 | 4 B | 随保存内容改变（A3 与 test_* 均不同） | 同 | 疑似内容校验/哈希（改 ICC 路径即变） |
| 0xE8 | u32 | 0x1A8 | ? | |
| 0xEC..0x160 | 随机 96 B+ | 改文件内容后变化 | | 疑似加密/哈希区；另 0x140–0x160 另有一段 |

> 结论：0x00–0x160 的**固定部分仅前 0x20 字节可靠**（魔数/版本/头长/模块名）；
> 其余字段随机化或与保存会话相关，**复刻时可全部写 0/常量**（读文件时忽略）。
> 依据：`test_my/test_bare/test_wrong.prs` 与 `H13 XP600_myicc.prs` 只在 ICC 路径上不同，但这些头部字节
> （0x80、0xEC–0x11C、0x144–0x160、0x295–0x2E5 等）每次都变 → 非语义字段。

---

## 2. 文本配置块（key=value + 驱动选项目录）

每个条目 = NUL 结尾 ASCII 字符串，条目之间为 0–5 个 `00` 填充（**不是**固定 stride，不能按固定记录遍历；
建议做法：在文本区间内扫描 `[\x20-\x7e]{3,}\0`，再按已知键名取值）。
两个文件都有两段文本：头部小段（0x25C 起）+ 主配置块。

### 2.1 头部散落键（A3 与 H13 同偏移，极重要的加网开关）

| 偏移 | 键 | 含义 |
|---|---|---|
| 0x25C | `SepLight=0` | 分色/浅色模式开关（0=关） |
| 0x26B | `UseScreenFusion=1` | 加网融合开关（开） |

### 2.2 A3-DTF-1390.prs 主配置块（起始 0x5545）

| 偏移 | 字符串 | 说明 |
|---|---|---|
| 0x5545 | `A3-DTF-1390` | 驱动显示名 |
| 0x5555 | `ExtendWpkNameC=eps1k4.wpk` | 波形文件（.wpk）名（A3 驱动包内 .wpk=947,709 B） |
| 0x5573 | `OutputFixedLines=90` | **每 raster 记录行数=90**（与 ESC/P2 `m=90` 完全一致） |
| 0x558B | `StochasticHalftone=00000601` | 随机(误差扩散/随机)加网配置 ID `00000601` |
| 0x55AB | `SetInkOrder=00000702` | 墨序配置 ID `00000702` |
| 0x55C4 | `Manufacturer = procolored` | 厂商 |
| 0x55E2 | `SkipUnsupportSpotColor=1` | 忽略不支持的专色 |
| 0x55FF | `common.mcm` | 颜色管理模块配置文件（引用；实际未随包） |
| 0x560E–0x5663 | `v720x360dpi` `v720x720dpi` `v1440x720dpi` `v1440x1440dpi` `v2880x1440dpi` | **5 个 dpi mode 名**（对应 queryMode 里 dpi 字段） |
| 0x5663 | `UseMtCount=0` | |
| 0x5674 | `DotSize:` | 点大小表标题；随后为 `Off/..`? 与 `-1.00%`…`+?%` 的字符串表（0x569E–0x60DA） |
| 0x60E8 | `CMY Dot Replace` … | 边选项目录开始（PrintMedia / Paper Thickness / Ink / BlackInk / Speed / Platen Gap / Duplex / Data Cut / Bottom margin / Media Source / RollMode / Paper Feed Adjust / Feather / White Color Shift / White & Color Relation / Printing Complete state / mode-0..mode-29） |
| 0x62F9 | `Ink:` → `CMYK` / `CMYKW1W2` | **墨水组合枚举**（决定 planes 数与颜色码） |
| 0x67CD | `White Color Shift:` → `up 1.2mm`…`down 1.2mm` | 白墨偏移枚举（±1.2mm 步进 0.02） |
| 0x7932 | `White & Color Relation:` → `Two layer, base white` / `Two layer, base color` / `White Only` / `Color Only` | **白墨/彩墨叠层模式枚举** |
| 0x7A7A | `mode-0` … `mode-29`（每 16B stride） | A3 的 30 个 mode 显示名（与 queryMode 一致） |

### 2.3 H13 XP600.prs 主配置块（起始 0x2CE6）

| 偏移 | 字符串 | 说明 |
|---|---|---|
| 0x2CE6 | `MTF Better Print Ripserver Driver` | 驱动名（queryMode 返回的 name） |
| 0x2D0C | `INKSEQ=1` | 墨序号 |
| 0x2D19 | `NoVDotFlag=0` | 禁用 VSD 点标志 |
| 0x2D2A | `NewDriver=2` | 驱动代次（v4 格式） |
| 0x2D3A | `StochasticHalftone=00000601` | 与 A3 相同随机网 |
| 0x2D5A | `ExtendWpkNameC=mtbyc.wpk` | H13 波形（包内 310,682 B） |
| 0x2D77 | `Reserved2Num = 1` | |
| 0x2D8C | `common.mcm` | |
| 0x2D9B–0x2DFF | `V360x360dpi` … `V360x2880dpi`（6 个） | H13 mode 名（但与 queryMode 的 `V720x720 dpi` 不一致：720=dpi×2 由 pass/交织决定，见 color_pipeline §5） |
| 0x2DFF | `useExtendHeader=1` | v4 扩展头标志 |
| 0x2E15 | `UseMtCount=0` | |
| 0x307B | `LLC` `LLM` `LLY` `LLK` | 浅色墨选项（H13 支持 light ink；A3 无） |

> 文本块尾部是**驱动 UI 选项目录**（所有枚举值/显示名），对本项目主要用于**确认参数语义**，
> 复刻 `.prs` 时可直接用默认值生成（真正影响 RIP 的是 dpi mode 与 ICC 路径）。

---

## 3. 模式记录（Mode Record）

### 3.1 识别方法（可复现）

`extract.py`/`prs_parser.py` 用“**8 组连续 256 项 double 恒等斜坡**”签名定位记录：
在文件中搜索 `double(1/255)` 的 8 字节模式 `10 10 10 10 10 10 70 3f`，回退 8B 若为 `0.0`
则认为是斜坡起点；相邻斜坡间隔恰为 `256*8 + 12 = 2060` 字节，连续 8 组即一个记录。
A3 得到 3 组、H13 得到 4 组（与 queryMode 中含 `colorCorrection=true` 的 mode 数一致，
A3=3（id5/7/9），H13=4（id0..3））。

### 3.2 线性化 LUT（8×256 double，每通道一条）

- 位置：A3 `0xC090 / 0x14E18 / 0x1DB4C`；H13 `0x769B / 0x1036F / 0x19043 / 0x21D17`。
- 结构：`double lut[256]`，`lut[i] = i/255.0`（恒等），第 0 项 0.0、第 255 项 1.0。
- 8 条/记录（`luts[0..7]`），条间 12 字节 `00` 间隔。8 = 最大墨水通道数（CMYKW1W2=6 + 2 备用）。
- **含义假设**：墨量线性化/校正曲线（输入 0..1 → 输出 0..1），加载时按 ink 通道取用。
  本机两份 PRS 全是恒等 → 未启用线性化（与 `inkLimit.before-linearization.json` 中
  "所有通道 linear=[1.0]" 的默认状态一致）。
- 导出：`reference/profiles/luts/<驱动>_rec<N>_linearization.csv`（8 行 × 256 值，`ch0=` 前缀）。

### 3.3 可选 116 B 表（VSD/点大小表，A3 rec1/rec2 有，rec0 无）

A3 rec1 `@0x18E6C`，rec2 `@0x21BA0`（`prs_parser` 定位在 LUT 组之后、96B 配置之前）：

```
rec1: 06 00 0C 00 09 00 00 00 00 00 00 00 | 02 00 00 02 01 00 00 02 00 00 00 00 | (周期12B) ...
      00 03 00 82 00 02 00 82 ...
rec2: 06 00 0C 00 09 00 00 00 00 00 00 00 | ...（同上）...
      00 05 00 82 00 04 00 82 ...
```
- 头 `06 00 0C 00 09 00 00 00`（u16 6,12,9；u32 9）疑似 “6 通道 × 每通道 12B” 表 + 一项 9。
- 表体是 12 字节周期的小整数记录，rec1 与 rec2 仅个别字节（0x0003/0x0002 vs 0x0005/0x0004）不同
  → 与 **mode 分辨率/pass** 相关（rec1=1440x720，rec2=2880x1400），疑似 VSD 点大小表/每 pass 点级别。
- rec0（1440x1400）没有该表 → 可能“加载默认值”。**置信度中**，未用于复刻验证。

### 3.4 96 B mode 配置结构（12 个 u32 左右）

A3 三个记录该结构**完全相同**（逐字节 diff 无差异），偏移：rec0 `0x100E4`、rec1 `0x18EE0`、rec2 `0x21C14`。

```
00 00 00 00 | D0 08 00 00 | 10 00 02 00 | 00 08 00 00 | 00 00 00 00 | 00 08 00 00
00 00 00 00 | 00 00 00 00 | 00 00 10 40 | 00 00 00 00 | 00 00 00 00 | 00 00 00 00
00 00 00 00 | 00 08 00 00 | 01 00 00 00 | 00 00 00 00 | 01 00 00 00 | 00 00 00 00
00 00 00 00 | 00 00 00 00 | 00 00 10 00 | ...
```
- `0x8D0=2256`（rec 间不变）、`0x800=2048`（=256×8，疑似 LUT 字节数/最大通道表大小）、
  `0x40100000`(=float 2.25f)、最终 `0x00100000`。与 dpi 无关（3 记录相同）→
  说明 **dpi/pass 不在该结构**，而在不透明块/116B 表/文本 mode 名中。

### 3.5 ICC 路径记录（4×char[260]，两组）

每个模式记录有 2 组完全相同的路径（“当前/备份”？），每组 4 条，stride = 260 字节（`MAX_PATH`）：

| 序号 | A3 值 | H13 值 | 语义（由 `colorCorrection`/`queryIccpath` 响应证实） |
|---|---|---|---|
| 0 | `SRGB IEC61966-2.1.icc` | 同 | `srcRgbPath`：RGB 输入源 profile |
| 1 | `CoatedFOGRA39.icc` | `US Web Coated (SWOP) v2.icc` | `srcCmykPath`：CMYK 输入源 profile |
| 2 | `commnew.mcm` | 同 | MCM 颜色管理模块配置（文件未随包，疑内置于 `mtrip.dll`） |
| 3 | `v1440x1400-A3-DTF-1390.icm`（rec0）<br>`v1440x720-A3-DTF-1390.icm`（rec1）<br>`v2880x1400-A3-DTF-1390.icm`（rec2） | `v720x720-dtf.icm`<br>`v720x1080-dtf.icm`<br>`v720x1440-dtf.icm`<br>`v720x2160-dtf.icm` | `destCmykPath`：**输出（打印机）profile，CMYK→Lab** |

**路径是裸文件名**：不带目录。mtripNet 运行时 CWD = `3rdLib\mtripSDK\dist\bin`，
其解析目录实测为 `dist\bin\ICC Profile\{RGB,CMYK,OUTPUT}\<文件名>`（见 color_pipeline §2）。

### 3.6 记录 ↔ modeId 映射

由 `queryMode` + `colorCorrection/query` 响应（`reference/jobs/queries/*.json`）确定：

**A3-DTF-1390.prs**（30 个 mode：3 种纸 × 5 dpi × 2 墨水；只有 `colorCorrection=true` 的
mode 5/7/9 在 PRS 中有 ICC 记录）：

| PRS 记录 | destCmykPath | 对应 modeId | mode dpi | ink / planes |
|---|---|---|---|---|
| rec0 | `v1440x1400-A3-DTF-1390.icm` | **7** | v1440x1440dpi | CMYKW1W2 / 6 |
| rec1 | `v1440x720-A3-DTF-1390.icm` | **5** | v1440x720dpi | CMYKW1W2 / 6 |
| rec2 | `v2880x1400-A3-DTF-1390.icm` | **9** | v2880x1440dpi | CMYKW1W2 / 6 |

> ⚠ 记录顺序 **不等于** modeId 顺序（[7,5,9]），且与文本 dpi 名顺序也不一致。
> 实现时请**按 destCmykPath 匹配**，不要按下标猜。

**H13 XP600.prs**（4 个 mode，全部 colorCorrection=true，ink=CMYKW1，planes=5）：

| PRS 记录 | destCmykPath | modeId | dpi |
|---|---|---|---|
| rec0 | `v720x720-dtf.icm` | 0 | V720x720 |
| rec1 | `v720x1080-dtf.icm` | 1 | V720x1080 |
| rec2 | `v720x1440-dtf.icm` | 2 | V720x1440 |
| rec3 | `v720x2160-dtf.icm` | 3 | V720x2160 |

**反向证据（非常有说服力）**：用 `colorCorrection + modify modeId=0 + saveAs` 把 H13 的
`v720x720-dtf.icm` 换成 `my_icc.icm` 后得到 `H13 XP600_myicc.prs`：
记录数 4→3，且 `my_icc.icm` 出现在**最后一条记录的 dest 位置**，`queryIccpath(modeId=0)` 返回
`destCmykPath="my_icc.icm"`。→ (a) modeId 0 对应的是 v720x720 那条记录；
(b) saveAs 后记录顺序会变（不能依赖下标）。

### 3.7 不透明块（~17 KB/记录，高熵）

- 位置：A3 rec0 `0x08034–0x0C090`(16,476B)、rec1 `0x109BC–0x14E18`(17,500B)、
  rec2 `0x197C0–0x1DB4C`(17,292B)；H13 每条 ≈17,320 B。
- 熵 ≈ 7.34–7.43 bits/byte（近似随机/加密/压缩；**未发现 zlib/gzip 头**）。
- 尾部含**double 斜坡片段**（如 rec1 尾部 `10..70 3f, 10..80 3f, …` = 1/255,2/255,…），
  说明该块内部还含有若干 256 项 double 曲线（可能是不同 pass/分辨率的曲线或 per-mode 的
  颜色查找表缓存）。
- 猜测用途（低置信度，待进一步破解）：每 mode 的 **ScreenProcess 加网参数/阈值表 + VSD/点表缓存
  + MCM 缓存**。复刻时可先忽略：ICC 路径 + 身份 LUT + 加网参数（文本）已足以跑通管线。

---

## 4. 校验与差分实验（取证方法）

| 实验 | 结果 | 用途 |
|---|---|---|
| A3 `bin\bin\A3-DTF-1390.prs` vs `3rdLib\mtripSDK\dist\bin\A3-DTF-1390.prs` | MD5 相同 `97875877F51E3DF60639C20D8530E694`，0 差异 | 证明 dist 副本就是运行时使用的文件 |
| `H13 XP600.prs` vs `H13 XP600_myicc.prs`（colorCorrection 改 ICC） | 6 个差异区：0x80(4B)、0xEC–0x11C、0x144–0x160、0x295–0x2E5 + 路径区；记录数 4→3 | 头部随机字段定性 + 记录顺序可变 |
| myicc vs test_bare/test_my/test_wrong | 同 6 区差异；路径区仅文件名不同（`v720x720-dtf.icm`/`my_icc.icm`/`sRGB.icc`） | 确认路径域偏移与 stride 0x104 |
| 路径字符串扫描（`scan_paths.py`） | A3 每记录 8 条路径（2 组×4），组内 stride 0x104 | 结构定位 |

---

## 5. 最小可读写实现（C++/Qt 建议）

读取 `.prs` 所需最小逻辑：

```cpp
// 1) 校验
QByteArray d = file.readAll();
if (d.size() < 0x200 || memcmp(d.constData(), "\xD0\x44\x53\x6E", 4)) return err;
quint32 version = *(const quint32*)(d.constData()+4);   // 3=A3 系列, 4=H13

// 2) 文本配置：在 [0x200, min(0x9000,size)] 扫描 NUL 结尾 ASCII
QHash<QString,QString> kv;  // 按 '=' 拆分；无 '=' 的作为枚举/名称表
// 关键键：SepLight / UseScreenFusion / StochasticHalftone / SetInkOrder /
//         OutputFixedLines / ExtendWpkNameC / <dpi mode 名> / Ink: 后的枚举
// 注意：条目间填充 0~5 个 0x00，必须“扫描”而不是固定 stride 遍历

// 3) 模式记录定位：搜 double(1/255)=10 10 10 10 10 10 70 3f，回退 8B 为 0.0 => LUT 起点
//    每记录 = [不透明块][8x256 double LUT +12B gap][可选116B表][96B cfg]
//              [4x char[260] paths][88B][4x char[260] paths]
//    paths[0]=srcRgb, [1]=srcCmyk, [2]=mcm, [3]=destCmyk（裸文件名）

// 4) modeId -> 记录：按 destCmykPath 文件名匹配 queryMode 表（见 §3.6），不要依赖顺序
```

写入：复刻只需生成**最小 PRS**（甚至可以不写 PRS，直接在自己的 RIP 内硬编码 mode 表 +
ICC 路径——因为 RIP 行为由 mode 参数 + 外部 ICC 决定）。若要兼容蒙泰驱动：
照抄现有文件，仅改 destCmykPath 字符串（260B 域内 NUL 结尾、其余补 0）即可；头部随机区可原样保留。

---

## 6. 未解/待办

1. 不透明块（~17KB/记录）的确切内容（疑似加网/颜色缓存）——需要静态分析 `ScreenProcess.dll`
   或做“同 mode 不同 ICC/不同 dpi”的成对 PRS 差分。
2. 96B/88B 结构、116B 表的字段语义（与 pass/点大小相关）。
3. 头部 0x80 处 4B 校验算法（若想生成原厂可互认的 PRS 才需要）。
4. `.mcm`（common.mcm / commnew.mcm）实际文件不在公开包内，疑似编译进 `mtrip.dll`；
   若坚持“从 prs 完全复刻”，需从 DLL 资源提取（未验证）。
