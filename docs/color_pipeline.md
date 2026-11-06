# 蒙泰 MainTop RIP 数值管线（色彩 / 限墨 / 线性化 / 加网 / 白墨）

> 作者：prs-analyst。配套：`docs/prs_format.md`（.prs 结构）、`docs/01_maintop_pipeline.md`（调用链）。
> 证据元数据：`work/prs/`（parser dump、ICC 分析、mode 表、验证脚本输出）、
> `reference/profiles/`（源 ICC 拷贝 + 提取的线性化 LUT）、
> `reference/prn_samples/`（protocol-analyst 用 oracle 生成的 PRN 语料）、
> `reference/jobs/queries/`（queryMode / colorCorrection 响应）。
> 结论均标注置信度；可直接编码的参数集中在 §10。

---

## 0. 总管线（结论）

```
输入图像 (PNG RGBA / TIFF CMYK / JPEG; 内嵌 DPI 决定几何)
   │  color.readTransparency / transparencyToWhite, config(embeddedICC/cache)
   ▼
① 透明/alpha 处理（readTransparency=true 时 alpha 参与；见 §7）
   ▼
② 源 profile：RGB 输入 → ICC Profile/RGB/<srcRgbPath>（A3/H1310 全是 sRGB IEC61966-2.1）
   CMYK 输入 → ICC Profile/CMYK/<srcCmykPath>（A3:CoatedFOGRA39；H13:US Web Coated SWOP v2）
   ▼  PCS: XYZ / Lab
③ 目标 profile：ICC Profile/OUTPUT/<destCmykPath>（MainTop 自产 v4 打印机 profile，CMYK↔Lab）
   → 得到设备 CMYKW 值（0..255/通道）
   ▶ 仅 colorCorrection=true 的 mode 走 ②③；false 的 mode 走简化转换（§3.2）
   ▼
④ 限墨 / 线性化：PRS 内 8×256 double LUT 全为恒等（未启用）；限墨与线性化
   已烘进 OUTPUT profile（其内部名 "(自定义线性化)"）→ 本机无需额外步骤（§4）
   ▼
⑤ 加网：ScreenProcess.dll，StochasticHalftone=00000601，UseScreenFusion=1；
   2-bit（4 级点大小），按 mode 分辨率 720×720 / 1440×720 / 1440×1440 / 2880×1440 等
   ▼
⑥ 设备墨水平面：A3 4 色或 6 色（CMYK / CMYKW1W2）；H13 5 色（CMYKW1）
   ▼
⑦ ESC/P2（A3 改装机）或 HSSF 0x5555（H13 板卡机）输出 .prn
```

关键事实：**PRS 不内嵌 ICC**（全文件无 `acsp`），只存**裸文件名**；mtripNet 在
CWD=`3rdLib\mtripSDK\dist\bin` 下按 `ICC Profile\{RGB,CMYK,OUTPUT}\<文件名>` 解析
（protocol-analyst 已实测；A3 的 dest icm 在 dist/bin 与 bin/bin 内容相同，
唯一例外 `v720x720-dtf.icm` 两处不同，H13 mode0 复现要用 **dist** 那份）。

---

## 1. 输入图像与透明

| 作业字段 | 语义 | 证据 |
|---|---|---|
| `color.readTransparency` | true=读取 alpha；false=忽略 alpha 把透明区当图像内容（黑） | GemodifiseerdeMasjienRip.json（golden）`{true,false}` |
| `color.transparencyToWhite` | true=透明区当白（无墨）；false=透明区不产生墨（DTF 默认，白底由白墨层承担） | 同上；alpha_checker 造 PRN 的透明区颜色通道为 0 |
| PNG 内嵌 DPI | 决定几何（`view.xdpi` 对图片无效） | lead 实验 view_300/view_600 的 PRN 与 base 逐字节相同 |
| 内嵌 ICC（PNG iCCP） | 有则以它为源 profile（config embeddedICC），否则用 PRS 的 srcRgbPath | `config` 命令样例 `work/protocol/evidence/config_color_tx.json`；golden PNG 内嵌 480B sRGB |

golden 样本（`bin\bin\temp\pic\1793946733018.png`）：718×654 RGBA@120dpi，透明底，
主色 `(192,0,23,255)` 42,803 px、`(25,3,137,255)` 21,505 px、半透明边缘约 8,700 px。

---

## 2. ICC profile 清单与用途（已提取，见 `reference/profiles/`）

| 文件（PRS 内裸名） | 类 | 数据色空间/PCS | 版本/CMM | 标签概要 | 用途 |
|---|---|---|---|---|---|
| `SRGB IEC61966-2.1.icc`(3144B) | mntr | RGB / XYZ | v2.16, "Lino" | 17 tags：rXYZ/gXYZ/bXYZ + rTRC 2060B | RGB 输入源（A3/H13 都用它） |
| `CoatedFOGRA39.icc`(654,352B) | prtr | CMYK / Lab | v2.16, "ADBE" | A2B0/A2B1/A2B2=mft2 89,958B；B2A0/1/2=mft1 145,588B；gamt | A3 的 CMYK 输入源（亦可能被 no-CC 模式借用，§3.2） |
| `US Web Coated (SWOP) v2.icc`(557,168B) | prtr | CMYK / Lab | Adobe | A2B/B2A | H13 的 CMYK 输入源 |
| `v1440x720-A3-DTF-1390.icm`(1,904,360B) | **prtr** | CMYK / Lab | **v4.48, "MTCM"** | A2B0/1/2=mAB 501,292B；B2A0/1/2=mBA 125,164–149,728B；header ID `4d540205…` | A3 mode5 目标 profile（RGB→设备CMYK 就用其 B2A） |
| `v1440x1400-A3-DTF-1390.icm`(1,904,360B) | prtr | CMYK / Lab | v4 MTCM | 同上结构 | A3 mode7 目标 |
| `v2880x1400-A3-DTF-1390.icm`(1,904,360B) | prtr | CMYK / Lab | v4 MTCM | 同上 | A3 mode9 目标 |
| `v720x720/1080/1440/2160-dtf.icm` | prtr | CMYK / Lab | v4 MTCM | 同上 | H13 mode0–3 目标；`v720x720` dist 版内部名 `Chart 1000 Patches_08-09-26(自定义线性化).icm` |

**重要**：这些 `.icm` 是**打印机 profile（prtr，CMYK↔Lab）**，不是 DeviceLink；
所以 RGB 输入的正确链路是：`sRGB --A2B--> PCS --B2A(dest)--> 设备 CMYK`（标准 ICC 色彩管理）。
`A2B` 是“设备→Lab”，`B2A` 是“Lab→设备”，MainTop 实际用 dest 的 **B2A** 方向。
`header.ID` 里编码了 MainTop 版本号（`4d54020503040309000407436f6c6f72`="MT"+版本+…+"Color"）。

---

## 3. modeId、colorCorrection 与 RGB→CMYK 数值映射

### 3.1 mode 表（queryMode 实测，原文见 `reference/jobs/queries/`）

**A3-DTF-1390.prs：30 个 mode = 3 种纸 × 5 种 dpi × 2 种墨水**

| modeId | paper | dpi | ink | planes | colorCorrection |
|---|---|---|---|---|---|
| 0 | A3-DTF-1390 | v720x360 | CMYK | 4 | ✗ |
| 1 | A3-DTF-1390 | v720x360 | CMYKW1W2 | 6 | ✗ |
| 2 | A3-DTF-1390 | v720x720 | CMYK | 4 | ✗ |
| 3 | A3-DTF-1390 | v720x720 | CMYKW1W2 | 6 | ✗ |
| 4 | A3-DTF-1390 | v1440x720 | CMYK | 4 | ✗ |
| **5** | A3-DTF-1390 | v1440x720 | CMYKW1W2 | 6 | **✓**（dest=v1440x720） |
| 6 | A3-DTF-1390 | v1440x1440 | CMYK | 4 | ✗ |
| **7** | A3-DTF-1390 | v1440x1440 | CMYKW1W2 | 6 | **✓**（dest=v1440x1400） |
| 8 | A3-DTF-1390 | v2880x1440 | CMYK | 4 | ✗ |
| **9** | A3-DTF-1390 | v2880x1440 | CMYKW1W2 | 6 | **✓**（dest=v2880x1400） |
| 10–19 | 普通纸-2 | 同上 5 dpi ×2 | | | 全 ✗ |
| 20–29 | 普通纸-3 | 同上 5 dpi ×2 | | | 全 ✗ |

**H13 XP600.prs：4 个 mode，全部 colorCorrection=true，ink=CMYKW1，planes=5**

| modeId | dpi | destCmykPath |
|---|---|---|
| 0 | V720x720 dpi | `v720x720-dtf.icm`（用 dist 版） |
| 1 | V720x1080 dpi | `v720x1080-dtf.icm` |
| 2 | V720x1440 dpi | `v720x1440-dtf.icm` |
| 3 | V720x2160 dpi | `v720x2160-dtf.icm` |

> H13 `queryMode` 的 dpi 名 `V720x720` 与 PRS 文本里的 `V360x360dpi…V360x2880dpi` 成 2 倍关系
> （720=360×2），实际由 ESC/P2/HSSF 头的 xdpi/ydpi 字段给出（HSSF 头实测 720×720）。

### 3.2 colorCorrection=true（A3 mode5/7/9，H13 全部）：lcms2 可复现链路

```
RGB(输入) → openProfile(srcRgbPath=sRGB) → 变换 → openProfile(destCmykPath) → CMYK 设备值
意图：INTENT_PERCEPTUAL(0)（拟合最优；见下表）；flags=0（无 BPC）；lcms2 默认自适应
公式：cmsCreateTransform(sRGB, TYPE_RGB_8, dest, TYPE_CMYK_8, INTENT_PERCEPTUAL, 0)
```

**验证数据 A**（A3 modeId=5 纯色 PRN；measure=块内内容区均值法 `prn_cover_blockmask.py`：
coverage=mean(2bit level)/3；进纸内容=720,000 dots）：

| 输入 RGB | 通道(实测/预测 intent0) | 备注 |
|---|---|---|
| (0,255,255) cyan | C 0.264/0.370, Y 0.100/0.140 | 形状/比例对，整体偏低 |
| (255,0,255) magenta | M 0.528/0.670 | |
| (255,255,0) yellow | Y 0.703/0.860 | |
| (0,0,0) black | K 0.685/0.880, C 0.124/0.380, M 0.129/0.300, Y 0.501/0.710 | |
| (255,0,0) red | M 0.751/0.860, Y 0.764/0.910 | |
| (0,255,0) green | C 0.084/0.290, Y 0.779/0.920 | C 偏差大 |
| (0,0,255) blue | C 0.591/0.760, M 0.329/0.520 | |

统计：**实测 ≈ 0.75 × lcms2(intent0) 预测**（M/Y 通道尤其一致，C/K 偏差大 10–25% 相对误差）。
原因推测（未定论）：MainTop 自研 CMM（MtColorIO.dll，profile creator=MTCM）的 CLUT 插值/
黑点处理与 lcms2 默认不同；或输出前还有一道烘进 profile 的线性化未完全等价。

**验证数据 B**（luma/grayscale 梯度，`grad_h_100`，可拟合连续 tone 曲线）：见 §5.3 方法；
这些样本可直接用于**最小二乘拟合 per-channel 修正 LUT**：对每个 ink 通道，把
x=lcms2 预测 ink%、y=实测覆盖率(mean level/3) 做单调回归，得到修正曲线 `corr[ink](x)`。

### 3.3 colorCorrection=false（A3 mode 0–4/6/8/10–29）：简化转换

观测：这类 mode **不使用 OUTPUT 目标 profile**（queryMode 返回 `colorCorrection=false`，
`colorCorrection/query` 返回 0x01000005 "无校色数据"）。实际 RGB→CMYK 仍与
**sRGB→PCS→CMYK（CoatedFOGRA39, perceptual）** 接近（A3 PRS 的 srcCmykPath 就是 FOGRA39），
但没有 dest 打印机 profile 的第二次映射。

golden 样本（modeId=2，CMYK 4 planes，无 CC）实测（块内内容区均值，映射见 §6）：

| 通道 | 实测 | sRGB→FOGRA39 intent0 预测 | 备注 |
|---|---|---|---|
| C | 0.380 | 0.471 | |
| K | 0.049 | 0.143 | K 明显少（偏 CMY 黑） |
| Y | 0.659 | 0.710 | |
| M | 0.943 | 0.981 | |

A3 mode2 纯色实测（同法）：

| 输入 RGB | 实测 (C/K/Y/M) | FOGRA39-intent0 预测对应值 |
|---|---|---|
| (0,255,255) | C .785, Y .221 | C .565, Y .184 |
| (255,0,255) | M .770, C .138 | M .788, C .427 |
| (255,255,0) | Y .966, C .087 | Y .843, C .122 |
| (0,0,0) | C .679, K .823, Y .610, M .626 | C .906, K .976, Y .616, M .788 |
| (255,0,0) | Y .841, M .902 | Y .937, M .957 |
| (0,255,0) | C .902, Y .949 | C .639, Y 1.0 |
| (0,0,255) | C .855, M .757 | C .949, M .769 |

→ **可直接编码的近似规则（no-CC mode）**：
`RGB → (sRGB profile) → Lab → (CoatedFOGRA39 B2A, INTENT_PERCEPTUAL) → CMYK`，
再对 K 通道乘 ~0.3–0.5（或按实测表做 4D 修正）。误差见上表，最大 ~0.25 绝对。
> 注意：这只是**近似**；若要求逐点一致，no-CC mode 的精确转换在 mtrip.dll 内部
> （未见外部 profile 依赖），只能通过 oracle PRN 标定。

---

## 4. 限墨（ink limit）与线性化

### 4.1 线性化 LUT（PRS 内，已提取）

- 每模式记录内 **8 条 × 256 项 double**，全部为恒等 `lut[i]=i/255`（证据偏移见 prs_format §3.2）。
- 导出：`reference/profiles/luts/A3-DTF-1390_rec{0,1,2}_linearization.csv`、
  `H13 XP600_rec{0..3}_linearization.csv`（8 行 × 256 值）。
- 结论：**本机两份 PRS 未启用软件线性化**；若客户在 MainTop UI 里做过线性化，
  应体现在这些 double 曲线上（复刻时可直接读取并使用：`out = lut[in]`，逐通道）。

### 4.2 限墨（总墨量 TAC / 单通道 maxInk）

- 在 PRS 文本/二进制中**未发现显式 inkLimit 字段**（搜索 `inklimit/totalInk/maxInk` 无命中）。
- MainTop 的限墨应已烘进 **OUTPUT profile**（v4 MTCM，内部名含“自定义线性化”），
  即 B2A CLUT 输出已限墨；同时墨量上限受 `OutputFixedLines` / 加网无关。
- 佐证：A3 mode5 实测 CMYK 覆盖率之和（纯色/黑色）≈ 实测 1.5–1.9，未出现 >2（280%）区域。
- 复刻建议：用 lcms2 复现 profile 变换即天然带上限墨；若自建 profile，需在 CMYK→设备色
  之后加 TAC 限制（推荐 280%，按本语料上限反推）。

---

## 5. 加网（ScreenProcess）

### 5.1 参数来源（PRS 文本，证据偏移见 prs_format §2）

| 键（A3/H13 同） | 值 | 含义 |
|---|---|---|
| `StochasticHalftone` | `00000601` | 随机加网配置 ID → **FM（随机/误差扩散）加网** |
| `UseScreenFusion` | `1` | 加网融合（多分辨率/多 pass 合一） |
| `SepLight` | `0` | 分色浅色开关（关） |
| `OutputFixedLines` | `90` | 每个光栅记录 90 行（与 PRN `m=90` 一致） |
| `DotSize:` 表 | `-1.00% … +1.53%` | UI 的点大小微调（百分比），非核心 |
| `ExtendWpkNameC` | A3=`eps1k4.wpk`, H13=`mtbyc.wpk` | 喷头波形文件（决定点火时序） |
| `SetInkOrder` | A3=`00000702` | 墨序配置 ID |
| `Ink:` 枚举 | `CMYK` / `CMYKW1W2` | 决定 planes 数 |
| `White & Color Relation:` | `Two layer, base white` / `base color` / `White Only` / `Color Only` | 白彩叠层 |

### 5.2 实测：随机（stochastic）加网，不是 AM 网点

对 A3 mode2/mode5 的平网 PRN 逐行可视化 + 自相关（`tools/prs_tools/screen_vis.py`）：

- 图案为近似噪声，**无周期峰**（自相关 lag 2..40 单调下降，无 AM 的 45°/周期的峰）。
- 2-bit 值只出现 0/1/2/3 四级；平网内容区几乎全非 0（tone 高时），靠点大小分级表达墨量。
- 例：A3 mode5 flat_m 的 M 平面（`0x01`）内容行：`322222222322332322222222233232222…`
  —— 密排 level2 为主、少量 1/3；对应预测 M=67% → 实测 mean level/3≈0.53–0.67。
- 结论：**FM/随机加网 + 4 级点大小（2-bit）**；与 `StochasticHalftone=00000601` 吻合。
  AM 网点形状/角度/频率不存在（不要按 AM 实现）。

### 5.3 加网函数（可复刻方案 + 标定方法）

PRN 只能反向得到“输入墨量 t → 输出四级的比例分布”，无法直接恢复 ScreenProcess 的
随机阈值矩阵（噪声）。推荐实现：

1. **tone → level 分布标定**（用 oracle 语料一次性生成，离线 LUT）：
   - 输入：`grad_h_100`（0→255 灰阶）+ 7 个纯色 + 每个 mode 一份 PRN。
   - 对内容区每个位置求 2-bit level；按输入 ink%（由 §3 的 ICC 变换算得）分桶，
     统计 `P(level=1/2/3 | t)`。得到每个 mode、每个 ink 通道的 4 级分布表。
   - 复刻时：`level = 按 P(level|t) 的反函数 + 空间随机/误差扩散` 生成，使局部均值相等。
2. **空间排布**：用 Floyd–Steinberg / 蓝噪声（void-and-cluster）在 level 平面上做误差扩散，
   保证局部 tone 正确；与蒙泰逐点一致不可能（随机屏），但**局部均值/视觉密度可一致**。
3. 若只需视觉/密度一致：先用 AM 60lpi（720dpi 下 12 dots 周期）做四色角度网点，
   再按上面的 tone→level 表调级即可（AM 在平网区与蒙泰观感差异肉眼可辨，慎用）。
4. 2-bit 打包（写 PRN 时）：每字节 4 dots，MSB 对 left-most，`value = (b>>6)&3`…
   （ESCP2 侧 escp2-analyst 已实现；HSSF 侧 board-analyst 负责）。

### 5.4 2-bit 点大小与覆盖率关系（实测）

- 简单线性模型 `coverage = mean(level)/3` 在 A3 mode5 上对 M/Y 通道拟合良好（误差 ~0.1），
  对 C/K 偏低（实测≈0.75×ICC 预测）。
- 对本项目：**建议把“设备 ink% → mean level”的映射也纳入 §5.3 标定表**（同一套 oracle 数据），
  即复刻侧输出 level 前先经过 `corr[ink](t)`。
- 参考数据文件：`work/prs/golden_prn_stats.json`、`work/prs/predicted_means.json`、
  `work/prs/prn_tile_vectors.json`。

---

## 6. 设备墨水通道与 2-bit 颜色码（关键！随墨水配置变化）

ESC/P2 `ESC i` 记录的 color 字节**不是固定 inks 索引**，其含义由该 mode 的墨水配置决定
（4 色 mode 与 6 色 mode 映射不同，同一字节意义不同）。经纯色 PRN 逐色对照得到：

### 6.1 4-plane mode（A3 mode 0/2/4/6/8，ink=CMYK）

记录顺序 `[0x04, 0x00, 0x12, 0x11]`（每 block 4 条记录）：
| color 字节 | 墨水 | 证据（纯色输入时该平面活跃） |
|---|---|---|
| 0x04 | **K** | flat_k/black 时最高（A3 m2: 0.823） |
| 0x00 | **C** | flat_c/cyan 主平面（.785）；flat_g/.902、flat_b/.855 |
| 0x12 | **M** | flat_m/.770、flat_r/.902、blue/.757 |
| 0x11 | **Y** | flat_y/.966、red/.841、green/.949 |

### 6.2 6-plane mode（A3 mode 1/3/5/7/9，ink=CMYKW1W2；PRS 中 `Ink:`=CMYKW1W2）

记录顺序 `[0x12, 0x11, 0x00, 0x02, 0x01, 0x04]`（每 block 6 条）：
| color 字节 | 墨水 | 证据（A3 mode5/3 实测） |
|---|---|---|
| 0x00 | **K** | flat_k K 平面 .685（m5）；m3 black .818 |
| 0x01 | **M** | flat_m .528；flat_r .751；flat_b .329 |
| 0x02 | **C** | flat_c .264；flat_b .591；flat_g .084 |
| 0x04 | **Y** | flat_y .703；flat_r .764；flat_g .779 |
| 0x11 / 0x12 | **W1 / W2**（顺序待定，两者在本机语料中同时出现/同时为空） | `inputColorEditor` 请求 W1+W2 full 时两平面同时出现且数据逐字节相同（全页满版，§7） |

> H13（ink=CMYKW1，planes=5）为 HSSF 0x5555 输出，颜色码/平面映射由 board-analyst 定稿；
> 本报告只给出 H13 的 PRS/ICC 侧结论（queryMode/ICC 表见 §3.1）。

### 6.3 输出 PRN 的通道顺序（写文件前）

- ESC/P2：每 block 记录顺序=上表；`SetInkOrder` 影响喷头物理映射（RIP 侧按 mode）。
- HSSF 0x5555：`PRN_IMAGE_INFO.nColorPlane`，数据 `bpl × height × planes`，2-bit 打包
  （见 `northPrintSDK/include/ImageFormat.h`；HSSF 头实测 planes=5、720×720、bpl=152/152…）。

---

## 7. 白墨 / 专色（W1/W2）与 inkIE / margin 的像素语义

### 7.1 前提

- 只有 **6-plane 模式**（A3 `CMYKW1W2`）才真正输出 W1/W2 平面；4-plane 模式忽略白墨请求
  （golden 样本请求了 W1 full，但 modeId=2 是 CMYK → PRN 只有 4 个颜色）。
- H13 为 CMYKW1（5 planes），W1 存在。

### 7.2 `inputColorEditor[{inkName, mode, invert}]`

实测（`a3dtf1390_*_m3_w1w2` vs 对应 base；每色总点数见 `prn_cover_blockmask.py`）：

| mode | 语义（像素级） | 证据 |
|---|---|---|
| `full` | **整幅输出页**铺满该专色（与彩色内容无关；透明区也铺）。实测 W1/W2 平面总点数 = 1,079,978 ≈ 600×600×3（满版 level3），在 cmyk_quad/flat_black/alpha_checker 三种内容下**完全相同** | 三份 w1w2 PRN 的 0x11/0x12 sum 均为 1,079,978 |
| `color` | 仅彩色区域（图像非透明/非白像素）铺 | lead 的 white_matrix：legacy_color 覆盖率≈legacy_full 的一半且随内容变化；`work/protocol/evidence/white_matrix.json` |
| `smooth` | H13 旧模板使用（`ripInputColorEditor_H13rip_back.json`: inkName=W1, mode=smooth） | 语义未完全验证，疑为按彩色边缘羽化/灰度过渡 |
| `invert` | true=反转（该专色只铺在非彩色/透明区） | JSON 字段；未单独实验 |

> `full` 的“整幅”= 图像映射到页面后的内容框（本语料=600×600 dots，即 100px@120dpi 在 720dpi 下的尺寸），
> 不含纸张外空白。`full` 铺的是 level3（100%）。

### 7.3 `inkIE[{index, mode, dots[4]}]`（白墨内缩/外扩）

```json
"inkIE": [ { "dots": [10,10,10,10], "index": 4, "mode": "invaginate" } ]
```
- `index`：墨水平面索引；CMYKW1W2 顺序 C,M,Y,K,W1,W2 下 **4=W1**（golden 作业的用法；H13 的
  CMYKW1 顺序下 4=W1 同样成立，见 `KaartrekenaarRip.json`）。
- `mode`：`invaginate`=内缩（erode，白墨比彩色区小）；`expand`=外扩（dilate）。
- `dots[4]`：四边内缩/外扩量，单位=输出 device dot（720/1440dpi 级），顺序推测
  `[left, top, right, bottom]`；golden 用 10 dots（720dpi 下≈0.35mm）。
- 像素级规则（实现建议）：
  1. 先按 §7.2 生成白墨基础 mask（full=内容框全 1；color=彩色 alpha>0 的 mask）。
  2. `invaginate`：对 mask 做 4 邻域腐蚀 N 次，每方向 N=dots[dir]（左/上/右/下不同量）。
  3. `expand`：对 mask 做 4 邻域膨胀同样次数。
  4. 结果 mask 再转成 6-plane 输出中的 W1/W2 平面（0/1→level 3）。
- 置信度：中（golden mode2 无 W 平面，无法直接验证；需 A3 mode1/3/5 的带 inkIE 的 oracle
  样本做逐点验证——`work/protocol/evidence/white_matrix.json` 已含部分，建议 board/protocol
  再补 `mode3/5 + inkIE invaginate dots[10,10,10,10]` 的 alpha_checker PRN）。

### 7.4 `margin`（页面边距）

- 单位=输出 dot（本语料 720dpi 下 1dot≈0.0353mm）；`[left, top, right, bottom]`。
- 只影响图像在页面上的位置/大小（几何），不影响色彩；证据：lead 的 margin 实验
  `exp_a3dtf1390_margin_5_10_15_20` PRN 大小/位置变化，覆盖率不变。
- 几何细节见 `docs/02_geometry_escp2.md` 与 escp2-analyst 的 `tools/prn_tools/`。

---

## 8. 复刻实现清单（C++/Qt + lcms2）

### 8.1 数值链（可直接编码）

```cpp
// 1) 打开 profile（路径规则：<mtripNetDir>/ICC Profile/{RGB,CMYK,OUTPUT}/<裸文件名>）
cmsHPROFILE src  = cmsCreate_sRGBProfile();                 // 或 PRS srcRgbPath
cmsHPROFILE dst  = cmsOpenProfileFromFile(destCmykPath);     // OUTPUT/*.icm
cmsHTRANSFORM rgb2cmyk = cmsCreateTransform(src, TYPE_RGB_8, dst, TYPE_CMYK_8,
                                            INTENT_PERCEPTUAL, 0);
// 2) 输入像素 (R,G,B) -> CMYK（C,M,Y,K 顺序，lcms2 输出）
cmsDoTransform(rgb2cmyk, &rgb, &cmyk, 1);
// 3) 如需贴近蒙泰实测：对每通道做修正（来自 §3.2/§5.3 的 oracle 标定表）
//    cmyk.c = clamp(corr_c[cmyk.c]);  // 实测≈0.75×lcms2，建议按 label 文件拟合
// 4) colorCorrection=false 的 mode：用 srcCmykPath(CoatedFOGRA39) 做 B2A（无 dest），再修正 K。
// 5) 白墨平面：full/color + inkIE mask（§7.2/7.3）
// 6) 2-bit 加网：tone->level 4 级分布（§5.3），随机/误差扩散
// 7) 写 PRN（A3: ESC/P2；H13: HSSF）
```

### 8.2 要复刻的参数表（默认值=本机 A3-DTF-1390.prs / H13 XP600.prs）

| 参数 | A3-DTF-1390 | H13 XP600 | 来源 |
|---|---|---|---|
| 机型输出格式 | ESC/P2（EJL 1284.4） | HSSF 0x5555 | PRN 魔数 |
| dpi mode（modeId→xdpi×ydpi） | 0/1:720×360, 2/3:720×720, 4/5:1440×720, 6/7:1440×1440, 8/9:2880×1440 | 0:720×720, 1:720×1080, 2:720×1440, 3:720×2160 | queryMode + ESC D/HSSF 头 |
| 墨水/planes | CMYK(4) 或 CMYKW1W2(6) | CMYKW1(5) | queryMode |
| 源 RGB icc | SRGB IEC61966-2.1.icc | 同 | PRS 路径记录 |
| 源 CMYK icc | CoatedFOGRA39.icc | US Web Coated (SWOP) v2.icc | 同 |
| 目标 icc | mode5→v1440x720-A3-DTF-1390.icm；7→v1440x1400；9→v2880x1400 | v720x{720,1080,1440,2160}-dtf.icm | 同 |
| rendering intent | perceptual(0)（拟合最优） | perceptual(0) | §3.2 验证 |
| 线性化 LUT | 恒等（8×256 double） | 恒等 | PRS 提取 |
| 限墨 | 无显式；由 dest profile 保证（TAC≈280%） | 同 | §4 |
| 加网 | Stochastic(FM) 2-bit 4 级，`00000601` | 同 | PRS 文本 + PRN 自相关 |
| 每记录行数 | 90 | (HSSF 由头字段) | OutputFixedLines / PRN |
| 白墨叠层 | `Two layer, base white` 枚举（UI 默认），W1=index4 | W1 | PRS 文本/JSON |
| 波形 | eps1k4.wpk | mtbyc.wpk | ExtendWpkNameC |

### 8.3 无法完全复刻时的替代方案

1. **色彩**：用 lcms2 + 同一批 ICC profile（本报告已存到 `reference/profiles/source/`），
   perceptual 意图；与蒙泰实测相差约 15–25%（相对），用 oracle PRN 做 per-channel 修正 LUT 可降到 ~5%。
2. **加网**：用随机屏/误差扩散 + 标定的 tone→level 表（§5.3）；逐点不可能，
   但局部平均密度可对齐；若客户只关心颜色/密度，肉眼基本无差。
3. **线性化/限墨**：直接信任 dest profile（含自定义线性化）；如需微调，
   在色彩变换后加 PRS 同格式的 256 点曲线。
4. **H13 板卡机**：输出契约见 board-analyst 的 `docs/prn_board.md`；本报告只覆盖 PRS/ICC。

---

## 9. 开放问题（需后续验证）

1. A3 no-CC mode 的精确 RGB→CMYK（mtrip 内部）——建议用 oracle 生成 3D/4D 采样网格
   （如 17³ RGB 组合）再拟合；本次仅给出纯色近似。
2. MainTop 自研 CMM 与 lcms2 的差异来源（BPC？CLUT 插值？）——可用 v4 mAB CLUT 直接读
   `reference/profiles/source/OUTPUT/*.icm` 的 B2A 表，做“自实现 vs lcms2 vs PRN”三方对比。
3. 6-plane 的 W1/W2 颜色码 0x11/0x12 何者为 W1（需要只设 W1 的 oracle PRN）。
4. inkIE 内缩四方向顺序、单位（device dot vs 图像像素）——需要定点实验。
5. 不透明块（PRS 内 ~17KB/记录）内容——疑似加网/点表缓存，若破解可精确复刻随机屏。

---

## 10. 加网函数复刻（阈值场模型，2026-11-06 追加）

> 结论（已用 256 级探针逐像素验证 100.000%）：蒙泰 A3 mode2 的加网是
> **固定 1024×1024 随机阈值场（4 级 dither）**，按**内容相对坐标**取阈值。
> 数据已生成：`build/screen/`（引擎直读）与 `reference/screen/`（分析存档）。

### 10.1 数学模型（精确成立）

```
输入：设备墨量 v ∈ [0,255]（= §3 色彩管线输出的每通道 ink 值）
加网：level(x,y) = (v >= T1(x,y)) + (v >= T2(x,y)) + (v >= T3(x,y))
      level ∈ {0,1,2,3}  → 2-bit 值直接写入 PRN（0/1/2/3 = 不喷/小点/中点/大点）
等价模型：level(x,y) = (3*v + D(x,y)) >> 8          （D ∈ [0,255]）
          T1 = ceil((256-D)/3), T2 = ceil((512-D)/3), T3 = ceil((768-D)/3)
```
- v=255 时 level=3（个别 D<3 的像素 level=2，T3 记为 0=永不触发）。
- **验证**：用 C 通道 256 级探针（`probe_scan_C###_a3dtf1390_m2.prn`）逐像素求
  “第一次 level≥k 的 v”得 Tk；再反算预测 6 个 tone（16/64/128/192/240/255），
  C/M/Y/K 四通道均 **100.000%** 逐像素一致（147,456 像素/通道）。
- 平均覆盖率精确等于 `3v/255`（T1 的 256 级扫描实测最大偏差 <1e-6）。

### 10.2 阈值场来源：1024×1024 tile + 内容相对坐标（关键）

1. **tile 周期 = 1024**：用 720×720 输入（内容 4320×4320 设备点）的 C64 探针
   `probe_scan_C64_720_a3dtf1390_m2.prn`（v=64 时 level = [D≥64]，二值），
   在 x/y 两个方向做 lag 扫描：**lag=1024 的相等率 = 100.000%**，
   其余候选（64/96/128/…/960/1280/…/2160）≈62.5%（=随机二值场的期望相等率）。
   ⇒ `D(x,y) = TILE[x % 1024][y % 1024]`。
2. **内容相对坐标**（不是页面绝对坐标）：
   margin 实验（同一 100×100 输入，`margin=[5,10,15,20]` mm，内容横向平移 142 dots）
   与无 margin 版本在**相同内容坐标**下比较，C/M/Y/K 四通道 level 逐像素 **100.000% 相同**
   （页面坐标下则不同）。⇒ 屏幕随内容一起平移，索引是 content(x,y)。
3. **通道关系**（内容坐标下）
   - `D_M = 258 − D_C`（99.63% 精确；其余为抽取边界像素）
   - `D_K = 258 − D_Y`（99.60% 精确）
   - C vs Y 独立（相关≈0）⇒ 实际只有 **2 个基 mask：C、Y**，M/K 由其互补得到。
4. **通道页面相位**：内容在页面上的顶行 C/K=640、M/Y=644（+4 page rows 的 weave 相位差）。
   引擎写 raster 时必须按通道加这个相位，否则 M/Y 整行错位。

### 10.3 数据文件格式（引擎直读，`reference/screen/final/` = 权威；`build/screen/` = 部署副本）

```
screen_meta.json   元数据（version=6, size=1024, tile=1024、坐标语义、通道表、验证结果）
thr_<ink>.bin      size*size*3 字节：逐像素 [T1,T2,T3]（uint8）
                   顺序：y*size + x（raster order），0 = 该阈值永不触发（= 该位置永不喷墨）
                   最终版本 size=1024（完整 tile 已知，任意内容尺寸可直接用 x%1024, y%1024）
thr_*.bin 当前大小 = 3,145,728 B/通道
```
引擎伪代码：

```cpp
// 设备墨量图 ink[ch][y][x]（0..255，y/x 为内容坐标，单位=device dot）
const uint8* T = thr[ink];
for (y = 0; y < content_h; y++) for (x = 0; x < content_w; x++) {
    size_t o = ((y & 1023)*1024 + (x & 1023)) * 3;   // 1024 tile，内容相对坐标
    int level = (v >= T[o]) + (v >= T[o+1]) + (v >= T[o+2]);
    // 注意 T[k]==0 时该级永不触发（用 (T[k] && v>=T[k]) 更稳）
    prn_2bit[ch][y][x] = level;
}
```
> 每通道 `content_top_page_row`：C/K=640、M/Y=644（decode_page 同款约定，
> `prow = pos_k + 8*r - content_top`）；这是排版/weave 参数，不属于屏幕 tile 本身。

### 10.4 提取方法（一条命令，可复现）

```powershell
# 前置语料：reference/prn_samples/probe_scan_<INK><t>_176_a3dtf1390_m2.prn
#          （INK=C/M/Y/K；t=000..255；176x176 CMYK 单通道 probe，内容 1056x1056 dots）
python tools\prs_tools\extract_176_ink.py C   # -> reference/screen/tile_C_1024.bin
python tools\prs_tools\extract_176_ink.py M   # ... M/Y/K 各一次
python tools\prs_tools\extract_176_ink.py Y
python tools\prs_tools\extract_176_ink.py K
python tools\prs_tools\build_screen_v4.py      # 组装 thr_<ink>.bin(1024) + meta + legacy384 + 验证
python tools\prs_tools\deploy_screen_final.py  # 写 reference/screen/final、build/screen、engine
python tools\prs_tools\screen_predict.py validate   # 对 oracle 探针逐像素验收
# 与 Lead 的 D-bin 构建结果对拍：
python tools\prs_tools\compare_tiles.py
```
`extract_176_ink.py` 的处理链：解码 PRN（RLE→2bit，MSB 优先）→
`page_row = 79*block + 8*raster_row` 还原页面行 → t=255 探针定位内容顶行 →
对 t=1..255 记录每像素第一次 level≥1/2/3 的 v = 精确 T1/T2/T3 →
写 1024×1024 tile。**全程使用与 Lead 的 `decode_page` 相同的解码约定**
（MSB、content_top、nonzero-merge）。

### 10.5 已复现范围与验收（最终版，1024 完整 tile）

验收方式：oracle 探针 PRN 用 `tools/validate/validate_e2e.py::decode_page` 解码，
用 tile 预测 `level=(v>=T1)+(v>=T2)+(v>=T3)`，逐像素比。tone ∈ {0,16,64,128,192,240,255}：

| 内容尺寸 | C | M | Y | K |
|---|---|---|---|---|
| 64×64 输入（content=384） | **100.0000%** | 99.9763% | 99.9769% | **100.0000%** |
| 176×176 输入（content=1056，取 1024² 区） | **100.0000%** | **100.0000%** | **100.0000%** | **100.0000%** |

**独立复核（engine-dev 的 C++ `mtr_prncheck content` 解码器，不经过本 Python 实现）**：
176 探针 28/28 组（4 通道 × 7 tone）**全部 100.0000%**；64 探针可用组 12/12 **100.0000%**
（其 union 解码还能补齐 M/Y 最后一行，说明该行数据在 PRN 的另一块里，Python 简版解码
的残差属解码器口径差异，不是 tile 错误）。

**全 256 级复核 + oracle 自洽性审计（最终验收口径）**

- engine-dev 对 1024 个探针（4 ink × 256 tone）做全量对拍：**972/1024 = 100.0000%**，
  余 52 个探针（最差 99.9985%）全部为同一批 **13 个 tone**：
  `[93,95,101,106,151,161,166,186,202,230,242,244,253]` × 4 ink。
- 每个异常探针恰好 16 个像素，全部是 tile 中 **T3==0（D<3，max level=2）** 的像素。
- 用 `tools/prs_tools/audit_oracle_screen.py` 逐字节审计 oracle PRN：
  这 832 个单元格上 **oracle 自身非单调**（level 随 tone 升高反而掉回 0）。
  原始字节证据例：C page(693,296) t=91/92/94 dot=1 而 t=93/95 dot=0；
  K page(644,948) t=228/229/231/232 dot=2 而 t=230 dot=0。
  缺陷 tone 集合四通道完全相同 → 蒙泰侧系统性缺陷（疑似 T3=256 存 8-bit 成 0
  的边界分支），不是 tile 错误。
- **确定性复核（T1，2026-11-06）**：把这 52 个作业（13 tone × 4 ink）各重跑 2 次，
  TI 归一化后 **52/52 原始 PRN vs r1 vs r2 逐字节一致**；样本
  `reference/prn_samples/rerun/probe_scan_<INK><tone>_176_a3dtf1390_m2_r{1,2}.prn`
  （证据 `work/protocol/evidence/screen_nondeterminism.{json,md}`）。
  本报告独立复核（`tools/prs_tools/check_rerun_determinism.py`）：
  **832/832 审计 cell 在 原始==r1==r2 且 oracle dot=0**。
  ⇒ 结论：**不是非确定性，而是可复现的蒙泰算法缺陷**（同一像素在特定 tone 下漏点，
  呈非单调；±1/±2 邻 tone 正常）。
- **按 oracle 审计排除这 832 个非单调 cell 后：1024/1024 探针 = 100.0000%**
  （engine-dev 的 `tools/validate/verify_screen_probes.py --audit` 默认加载
  `work/prs/oracle_screen_audit.json`；坐标级日志在 `tools/validate/out/screen_sweep.jsonl`）。
- 结论：tile 保持现状（`reference/screen/final/`），不做多数投票重拟合（非单调本身
  tile 表达不了，重拟只会掩盖 oracle 缺陷）；最终报告需注明该蒙泰可复现缺陷。


- content=384 时 M/Y 的 0.02% 残差 = **oracle 自己在内容最后一行（row 383）不打印的
  weave 缺口像素**（这些位置在 oracle 的所有 tone 下 level 都是 0；tile 用 T=(0,0,0)
  表示为"永不喷墨"，预测 0，但 oracle 解码也确有 0 → 实际是**不该比较的像素**，
  只有 M/Y 因 content_top=644 与 raster 相位错 4 行才出现）。排除这些位置后 100%。
- 与 Lead 用 T1 D-bin 自建的 tile（`reference/screen/engine1024/`）对比（同解码器）：
  C 100.0 vs 99.99、M 99.99 vs 99.98、Y 99.99 vs 99.98、K 100.0 vs 99.99
  → **直取 PRN 的版本每通道都更优**，故最终采用之（见 `work/prs/compare_tiles.log`）。
- tile 中的 0 阈值位置（M/K 各 16 个）：经确认是 oracle 永不打印的 weave 位置
  （所有 tone 观测 level=0），**不要填充**（填充会降低对拍一致率）。

### 10.6 已知边界

- 任意尺寸内容现在都可精确加网（tile 1024 已知；内容坐标循环取 tile）。
- **适用范围：仅 A3 mode2（720×720）已用 256 级探针验证**。m0/m1（720×360）与
  m5/m7/m9（1440×720 等）未做同样验证；m5/7/9 的 xDPI/内容尺度不同
  （engine-dev 实测 m5 水平 360dpi），**不要直接套用本 tile**，需要时请补同流程探针
  （先补 C 的 256 级 × 目标 mode 验证 tile 是否复用；成立再补其余通道）。
- 剩余误差（Lead 端到端 99.4~99.9%）主要来自**灰度标定 LUT 的输入值**（PIL/lcms 与
  引擎内置 lcms2.19.1 ±1 差异），不属于加网模块；白色作业已整文件逐字节一致。
- 屏幕 data 是"理想点阵"；实际 PRN 还有 weave（同一纸行被两块覆盖、互斥拆分、
  部分边缘像素不打印）——那一层由排版的 raster 生成逻辑复刻，不在 tile 内。


### 10.7 weave / raster 布局（与加网配套的实测结构）

- 每个 PRN 块 `m=90` raster 行，块起点 `pos_k=79k`（100×100 输入时 16 块；64×64 时 13 块），
  raster 行 r → **页面行 = 79k + 8r**（`VSTEP=8` page unit = 90dpi 纵向步进）。
- 384 行的内容区在 449,280（=1170 raster 行 ×384 列）个 raster 位置中只占 147,456 个；
  **其余是 microweave 空白填充行**（T1 阈值 bin 中 T1=0 的位置）。
- 扫描位置与页面像素是**一一对应**的（每个页面像素只在一个 raster 位置有值）；
  同一页面行被两个不同块覆盖时（k 与 k+8，行位置相差 79 raster 行），两块的点阵
  互斥（无重复点）——即 **weave 拆分发生在 raster 行层面，不是内容层面**。
- 2bit 打包：**MSB 优先**（byte 的 bit7-6 = 该字节最左点），已用 `checker_1px_100`
  输入验证（内容为 6-dot 周期的竖条，MSB 解码得到 6-dot 长 run，LSB 解码则被打碎）。
