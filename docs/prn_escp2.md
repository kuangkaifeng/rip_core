# prn_escp2.md · 蒙泰(A3-DTF-1390) ESC/P2 `.prn` 格式与「图像→光栅」几何规范

> 目标读者：engine-dev（C++/Qt 编码器实现）、以及需要复刻字节的验证者。
> 作者：escp2-analyst（T2）。所有结论都带证据（样本名 / 字节偏移 / 统计数字）。
> 状态：格式、RLE、几何模型、颜色码已**逐字节验证**（整文件 decode→re-encode 与厂商文件
> 一致，仅 EJL `TI` 时间戳 7 字节不同）；少数金额级细节列在 §12 TODO。

---

## 0. 一页速览（实现者只需要看这两段）

```
内容层（我们自己的 RIP 产物）：
  pageUnit  = 2880 / ESC(U.a          // mode2/3 = 720 (1/720 inch)
  VSTEP     = ESC(D.v * pageUnit/1440 // mode2/3 = 8  (块内相邻"光栅行"的页面行距)
  hdot      = 1440 / ESC(D.h          // mode2/3 = 720 dpi 水平点距
  content_w_dots = round(imgW * hdot / imgDpi)
  content_h_units= round(imgH * pageUnit / imgDpi)      // 内容高度（页面行数）
  n = ceil(content_w_dots / 4) 补齐到 8 的倍数            // 每行字节数，2bit/像素
  P0 = 640 (mode2/3)                  // 图像第 0 行对应的"纸行"号（见 §7）

光栅化：图像按 (rowStep=pageUnit/imgDpi, colStep=hdot/imgDpi) 最近邻放大到
  (content_w_dots × content_h_units) 的 2bit 点阵（值 0..3 = 不喷/小/中/大点）。

分块（核心！）：
  pos_k = 首发块特殊，之后 = 前面所有 ESC(v) 推进量之和（单位 1/720 inch = page unit）
  块 k 的第 r 行 (r=0..89) 打印在"纸行" paper_row = pos_k + VSTEP*r
  图像纸行 p = P0 + i（i = 图像放大后的行号 0..content_h_units-1）
  → 把 p 分给 k = 满足 pos_k ≡ p (mod VSTEP) 且 pos_k ≤ p 且 r=(p-pos_k)/VSTEP ≤ 89 的
    **最大** k。这样每一纸行只出现在一个块里（无重复喷墨；厂商另做羽化拆分，见 §10）。
  块数 N = 1 + max_p k(p)（p 遍历所有内容纸行；实测见 §8 表）

记录流：每块按颜色顺序写 n 色记录；每条 = ESC ( $ xpos + ESC i color comp=1 bit=2 nL nH mL mH
  + RLE + 0D；块之间写 ESC ( v advance。
```

---

## 1. 文件总体结构（金样本 `1793946733280.prn`，1,734,682 B，modeId=2）

| 偏移 | 内容 |
|---|---|
| `0x000000` | `00 00 00 1B 01` ENTER D4（固定 5 字节） |
| `0x000005` | `"@EJL 1284.4\n"`（13 B） |
| `0x000012` | `"@EJL     \n"`（5 空格 + \n，10 B） |
| `0x00001C` | `1B 28 52 08 00 00 "REMOTE1"`（ESC ( R，payload=00+"REMOTE1"） |
| `0x000029` | remote tags：TI / JS / JH / SN / PP / MI / DP / US / US |
| `0x000083` | `1B 00 00 00` 退出 remote mode |
| `0x000087` | 命令区 12 条（91 B，到 `0x0000E1`） |
| `0x0000E2` | `ESC ( v 04 00 96 00 00 00`（首块前 advance=150，**仅当图像顶部有空白行时才出现**） |
| `0x0000EB` | 块 0 记录开始（`ESC ( $ ...`） |
| … | 49 块 × 4 色 = 196 条记录 |
| 文件尾之前 | `0C`(FF) `1B 40`(ESC @) `1B 28 52 08 00 00 "REMOTE1"` `LD 00 00` `JE 01 00 00` `1B 00 00 00` |

头部字段（remote mode tag 表，全部实测）：

| tag | len | 内容（金样本） | 含义/来源 |
|---|---|---|---|
| TI | 8 | `00 07 EA 0B 06 0E 20 19` | 时间：00 + 年 BE16 + 月+日+时+分+秒（07EA=2026, 0B=11, 06=6, 0E=14, 20=32, 19=25）。**每次作业不同**，是字节级比对唯一需要归一化的字段（实测偏移 45..51）。 |
| JS | 13 | `00 "MAINTOPRINT" 00` | 作业名（固定 MAINTOPRINT） |
| JH | 18 | `00×6 "Maintop Host"` | 主机名（前 6 字节 00，后 12 字节名字） |
| SN | 1 | `00` | 固定 |
| PP | 3 | `00 01 FF` | 固定 |
| MI | 4 | `00 01 00 01` | 固定 |
| DP | 2 | `00 00` | 固定 |
| US | 3 | `00 01 00` | 固定 |
| US | 3 | `00 02 00` | 固定 |

尾部：`0C 1B 40 1B 28 52 08 00 00 "REMOTE1" `LD`(len=0) `JE`(len=1, data=00) `1B 00 00 00`。

---

## 2. 命令区（modeId=2 逐字节；其它 mode 差异见 §9）

`0x87` 起 91 字节，与厂商逐字节一致：

```
1B 40                                ESC @
1B 28 47 01 00 01                    ESC ( G  1     选择图形模式
1B 28 55 05 00 04 04 04 40 0B        ESC ( U  PAGE=4 V=4 H=4 BASE=2880
1B 55 00                             ESC U   0     双向
1B 28 69 01 00 00                    ESC ( i 0     无 MicroWeave
1B 28 4B 02 00 00 02                 ESC ( K 0,2   颜色模式
1B 28 65 02 00 00 21                 ESC ( e 0,33  墨滴大小
1B 28 44 04 00 A0 05 10 02           ESC ( D BASE=1440 VERT=16 HORIZ=2
1B 28 63 08 00 D5 FD FF FF 7F 11 00 00  ESC ( c TOP=-555 LEN=4479
1B 28 53 08 00 D4 10 00 00 29 0D 00 00  ESC ( S W=4308 H=3369
1B 28 6D 01 00 41                    ESC ( m 0x41
1B 28 56 04 00 00 00 00 00           ESC ( V 0     绝对垂直位置=0
```

字段公式（语料实测，见 §9 汇总表）：

- **ESC ( U**：`PAGEUNIT, VUNIT, HUNIT` 三个"每 inch 的分母"，`BASEUNIT=0x0B40=2880`。
  例：`04 04 04` → 2880/4 = **720 dpi 基准**（mode2/3）⇒ 1 page unit = 1/720 inch。
  `08 08 04` → page/v=360，h=720（mode0/1）；`02 02 02` → 1440（mode7）；`02 02 01`（mode9）。
- **ESC ( D**：`BASE=1440, VERTICAL, HORIZONTAL`。
  - **VERTICAL** = 块内相邻光栅行的纸行间距（单位 1/1440 inch）。16 → 1/90 inch。
  - **HORIZONTAL** = 同一行内相邻点(2bit 像素)的水平间距（单位 1/1440 inch）。2 → 1/720 inch
    ⇒ **水平 720 dpi**；4 → 1/360 inch（mode5/7）。
  - 二者换算到 page unit：`VSTEP = VERTICAL * pageUnit / 1440`（mode2/3: 16*720/1440 = 8），
    `colStep_dots = 1440 / HORIZONTAL`（720 dpi for mode2/3）。
- **ESC ( c** = `(int32 TOP, int32 LEN)`，**ESC ( S** = `(u32 W, u32 H)`：
  ```
  M   = 页码边距常数（按 mode 实测，见 §9）
  content_h_units = round(imgH * pageUnit / imgDpi)      // 内容高度（page unit）
  content_w_units = round(imgW * pageUnit / imgDpi)
  ESC ( c = (-M, content_h_units + M)
  ESC ( S = (content_w_units, content_h_units - M)
  ```
  - 负值 / 小于 M 时按 **u32 回绕**原样写（如 64px 图 mode2：`content_h_units-M = 384-555 = -171`
    → 写 `55 FF FF FF`）。逐字节复刻必须照抄，不要 clamp。
  - 例（100×100@120dpi，mode2）：content=600 → ESC(c)=(-555,1155)、ESC(S)=(600,45)；
    720×720：content=4320 → ESC(c)=(-555,4875)、ESC(S)=(4320,3765)。
- **ESC ( $**（每条记录头）= 水平位置，单位 HUNIT；**mode0..3 实测恒 0**。
  （厂商另一款 prs 的 149.8MB 抓包样本里为 `floor(block/16)%4`，见 §12 TODO。）
- **ESC ( v**（块之间）= 垂直推进，单位 VUNIT(page unit)。mode2 通常 **79**；mode0=71,
  mode1=35, mode3=39, mode5/7/9=11（见 §9）。

---

## 3. 光栅记录（ESC i）格式

每块 = 按颜色顺序写 nColor 条记录，块之间先写 `ESC ( v`：

```
1B 28 24 04 00 <xpos u32 LE>            ESC ( $ 绝对水平位置（mode0-3 恒 0）
1B 69 <color> <comp> <bit> <nL nH> <mL mH>
        color = 墨水通道码（§6）
        comp  = 1  (RLE/TIFF 压缩)
        bit   = 2  (每像素 2 bit，值 0..3 = 点大小)
        n     = 每行字节数（= nL+nH*256）
        m     = 行数，块内恒 90
<RLE 数据>                              // 解压后恰好 n*m 字节
0D                                      // 记录结束
```

- `m=90` 恒等于打印头每色喷嘴数（1390 头：90 喷嘴/通道）。
- `n` 规律：`n = ceil(content_w_dots/4)` 再**向上补齐到 8 的倍数**（实测：600→152、4308→1080、
  7200→1800、1000→256：1000/4=250→256）。补齐字节内容 = 0（厂商在行尾补 0 点）。
  注意行尾剩余 dot 的 padding 由驱动自己决定，我们对齐方式照抄 ``align8``。
- 记录之间没有其它命令；`ESC ( v` 只在块边界出现。

---

## 4. RLE（TIFF 压缩，已逐字节验证）

解码（每条记录独立，按行独立：每 n 字节一行）：

```
c = 数据[i]
  c ≤ 127      → 复制后面 (c+1) 字节（字面量，最多 128）
  c ≥ 128      → 下一字节重复 (257-c) 次（复制段，最多 128）
直到解出 n*m 字节
```

编码（**实测厂商规则**，这是 byte-exact 复刻的关键）：

- 复制段只在**连续相同字节 ≥ 3** 时使用（长度 2 的重复走字面量！统计：全语料
  run 长度直方图最小 3，最大 128）；
- 字面量最大 128 字节，遇到「连续 3 个相同字节」即断开；
- **每行（n 字节）重新开始编码**（跨行不合并；证据：全零记录 90 行 × 9 token：`81 00 ×8 + C9 00`）。

验证（`tools/prn_tools/verify_rle.py`）：对 9 个样本（含金样本、SDK `test.prn`、720 全幅
checker）共 **1060 条记录** decode→encode **全部字节一致**。

---

## 5. 2bit 打包 / 位序 / 点大小

- 每字节 4 个像素，**高位在前**：像素 0 = bit7:6，像素 1 = bit5:4，像素 2 = bit3:2，像素 3 = bit1:0。
  即 `v0=(b>>6)&3, v1=(b>>4)&3, v2=(b>>2)&3, v3=b&3`。
  验证：geomv 探针（1px 竖线在 x=61 → dot 610）解出的第一个非零点正好是 dot 610 ✓。
- 值 0 = 不喷，1/2/3 = 小/中/大点（variable dot，`ESC ( e 0x21`）。
- 水平 1 dot = `HORIZONTAL/1440` inch（mode2/3: 1/720）；2bit 打包不改变点距。

---

## 6. 颜色码 → 墨水通道（实测，mode2 语料）

用纯 RGB 色块（`reference/prn_samples/col_*_mode2.prn` 与 `a3dtf1390_flat_*_100_m2`）
统计每个 color 码的点覆盖率（on=% 有点的像素）：

| 输入 | 0x04 | 0x00 | 0x12 | 0x11 | 结论 |
|---|---|---|---|---|---|
| 纯 K (0,0,0) | 0.52 | 0.52 | 0.52 | 0.52 | 黑 = 四通道全参与 |
| 纯 C (0,255,255) | 0.00 | **0.52** | 0.00 | 0.28 | C = 0x00 |
| 纯 M (255,0,255) | 0.00 | 0.17 | **0.52** | 0.00 | M = 0x12 |
| 纯 Y (255,255,0) | 0.00 | 0.11 | 0.00 | **0.52** | Y = 0x11 |
| 纯 R (255,0,0) | 0.00 | 0.00 | 0.52 | 0.52 | M+Y ✓ |
| 纯 G (0,255,0) | 0.00 | 0.52 | 0.00 | 0.52 | C+Y ✓ |
| 纯 B (0,0,255) | 0.00 | 0.52 | 0.52 | 0.00 | C+M ✓ |

**mode2（4 色）**：记录顺序 `[0x04, 0x00, 0x12, 0x11]` = **[K, C, M, Y]**。
**mode0 完全相同**（顺序/映射一致）。纯色输入里 0x00 的小覆盖是 ICC/UCR 结果（T3 复刻）。

**mode1/mode3（6 色）**：顺序 `[0x12, 0x11, 0x00, 0x02, 0x01, 0x04]`，色块统计：

| 输入 | 0x12 | 0x11 | 0x00 | 0x02 | 0x01 | 0x04 |
|---|---|---|---|---|---|---|
| 纯 K | 0 | 0 | **0.20** | 0.20 | 0.20 | 0.20 |
| 纯 C | 0 | 0 | 0 | **0.20** | 0 | 0.14 |
| 纯 M | 0 | 0 | 0 | 0.09 | **0.20** | 0 |
| 纯 Y | 0 | 0 | 0 | 0.05 | 0 | **0.20** |

⇒ 6 色模式：`0x00=K, 0x02=C, 0x01=M, 0x04=Y`，而 **0x12/0x11 是白墨/空通道**
（不透明色块测试下始终 0）。注意这和标准 ESC/P2 颜色码表（0=K,1=M,2=C,4=Y,17=LM,18=LC）
不同 —— 蒙泰 prs 的通道分配是自定义的，**以本表为准**。6 色下 0x12/0x11 对应 W1/W2 的
确切顺序还需白墨专用样本确认（TODO §12）。

---

## 7. 几何模型（本文件核心，已用金样本+全部探针验证）

### 7.1 三个坐标系

1. **纸行坐标 p**：单位 = page unit（mode2/3 为 1/720 inch）。打印机最小可寻址的垂直行。
2. **块行坐标 (k, r)**：k=块序号，r=0..89。
3. **图像坐标 (x, y)**：像素，dpi 由 PNG 内嵌 `pHYs` 决定（**不是**作业 JSON 的 view.xdpi！

   实测：view=120 时，120dpi 的 PNG → colStep=6；而 72dpi 的 PNG（无 pHYs 时默认 72）
   → colStep=10。`view` 参数对输出尺寸无效，T1 亦已实测）

```
rowStep = pageUnit / imgDpi           // 每图像行 = 多少纸行（120dpi, mode2 → 6）
colStep = (1440/ESC_D.HORIZONTAL) / imgDpi   // 每图像列 = 多少 dot（120dpi, mode2 → 6）
content_w_dots = round(imgW * colStep)
content_h_units= round(imgH * rowStep)
```

图像放大是**最近邻/箱式**：图像行 y 覆盖纸行 `[P0+rowStep*y, P0+rowStep*(y+1)-1]`，
图像列 x 覆盖 dot `[colStep*x, colStep*(x+1)-1]`。竖直方向：P0 是图像行 0 的第一条纸行。

### 7.2 P0（内容起点）与 M（页边距常数）——实测

`M`（写入 ESC(c)/ESC(S) 的页边距）与内容起点 P0 都是 **mode 常量**（与图像尺寸无关，
用 64px/100px/720px/金样本 654px 交叉验证）：

| modeId | pageUnit | VSTEP | M | **P0（纸行）** | P0 证据 |
|---|---|---|---|---|---|
| 0 | 360 | 4 | 245 | **288** | flat_black_100_m0 首行=288 |
| 1 | 360 | 4 | 277 | **324** | m1 首行=324 |
| 2 | 720 | 8 | 555 | **640** | m2/golden/geomh/geomv/col_* 首行=640 |
| 3 | 720 | 8 | 587 | **680** | m3 首行=680 |
| 5 | 720 | 8 | 627 | **712** | m5 首行=712 |
| 7 | 1440 | 16 | 1227 | **1413** | m7 首行=1413 |
| 9 | 1440 | 16 | 1227 | **1413** | m9 首行=1413 |

经验关系：`P0 = M + delta`，delta = **85**（m2、m5，pageUnit=720）、**93**（m3）、
**43**（m0）、**47**（m1）、**186**（m7/m9）。delta/ VSTEP ≈ 10.625 或 11.625 —— 精确公式
未知（TODO §12.1）；**生成器直接查表**。

### 7.3 块内行 ↔ 纸行（最关键的公式）

```
paper_row(k, r) = pos_k + VSTEP * r          r = 0 .. 89
pos_k = 首块前的 ESC(v) 值（无则 0） + Σ_{j<k} advance_j
```

验证：`a3dtf1390_flat_black_100_m2.prn`（16 块×90 行，adv=79）解出的所有非空纸行 =
**640..1239 共 600 行，恰好覆盖内容 600 行，无空洞**；且每行的 (k,r) 全部满足
`(p-pos_k) % 8 == 0`（语料 100% 通过，见 `work/escp2/an_paperrows.py`）。

> 重要：**不要**按「每 90dpi 光栅行内容重复 9 次」理解。90 行/块是 90 个喷嘴行，
> 相邻块推进 79 page-unit（≠90），因此后一块的光栅行会落在前一块行距的**中间**
> （720dpi 网格的 8 个相位），8 个块覆盖全部 8 个相位 ⇒ 实际垂直分辨率 720 dpi。
> 我们解出的每个纸行只出现一次（个别重叠行厂商做拆分，见 §10）。

### 7.4 每个纸行分到哪个块（生成算法）

对每个内容纸行 p（= P0 .. P0+content_h_units-1）：

```
k(p) = 满足以下条件的最大整数 k：
         pos_k ≡ p (mod VSTEP)          // 用 advance 的模逆：k ≡ (p-pos0)*inv(adv) mod VSTEP
         pos_k ≤ p
         r = (p - pos_k)/VSTEP ≤ 89
把该行（2bit 点阵）写进块 k 的第 r 行。
```

- 因为每块只有 90 行，`advance < 90*VSTEP`，所以 p 有多个候选块；取**最大** k
  保证 r≤89 且每行只写一次。
  > 注意：6 色模式（adv=35/39，VSTEP=4/8）下同一纸行有 3~5 个候选块，蒙泰自己的
  > 分配是"从最早可用块开始交织铺开"（每块都填满），而"取最大 k"会得到同样的
  > **打印结果**（每纸行仍只印一次、位置一致）和同样的块数 N（已用 m1→18、m3→33 验证），
  > 只是块之间的行分布不同——追求 byte-exact 才需要复刻厂商的交织顺序。
- **块数** `N = 1 + max_p k(p)`（p 遍历内容行）。等价近似
  `N ≈ floor((P0 + content_h_units - 1 - pos0)/advance) + 1`，个别 mode 会差 1，
  用上式精确算。实测对照：

| 样本 | content_h_units | adv | 实测块数 | 公式 |
|---|---|---|---|---|
| 100px@120 m0 | 300 | 71 | 9 | 9 |
| 100px@120 m1 | 300 | 35 | 18 | 18 |
| 100px@120 m2 | 600 | 79 | 16 | 16 |
| 100px@120 m3 | 600 | 39 | 33 | 33 |
| 100px@120 m5 | 600 | 11 | 120 | 120 |
| 100px@120 m7/m9 | 1200 | 11 | 237 | 237 |
| 720px@120 m2 | 4320 | 79 | 63 | 63 |
| 64px@120 m2 | 384 | 79 | 13 | 13 |
| 金样本 718×654 m2 | 3924 | 79 | **49** | 58（含空白跳过，见 §11） |

### 7.5 旋转 / 镜像 / 缩放 / margin（实测语料 exp_a3dtf1390_*）

这四种变换**都不改命令区字段，只改内容尺寸/像素排布**（命令区与基线逐字节相同，
仅 ESC(S)/ESC(c)/内容不同）：

- **rotate 90/180/270**：命令区完全不变（S=(600,45)、c=(-555,1155)、16 块/79 推进同基线），
  旋转作用在**光栅像素**上（等价于先把图像旋转再按 §7.1 光栅化）。实现上在 RIP 输入阶段
  旋转图像即可，PRN 层不需要额外字段。
- **mirror_h / mirror_v / mirror_hv**：同上，命令区不变；内容做水平/垂直/双向翻转
  （镜像位不在 ESC/P2 头里，由驱动在光栅化前完成）。
- **scale**（百分比，可各向异性）：
  ```
  content_w_units = round(imgW * colStep * scaleX/100 * pageUnit/imgDpi)
  content_h_units = round(imgH * rowStep * scaleY/100)
  ```
  实测：100×100 图 scale200 → S=(1200,645), c=(-555,1755), n=304, 24 块；
  scale50 → S=(300, 4294967041=–555+300 回绕), 12 块；scale(100,50) → S=(600,…), n=152,
  高 300；scale(50,100) → S=(300,…), n=80，高 600。均与公式一致。
- **margin**（单位 **mm**，顺序 `[left, top, right, bottom]`）：
  ```
  content_w_units += round((left+right) * pageUnit / 25.4)
  content_h_units += round((top+bottom) * pageUnit / 25.4)
  prologue ESC ( v  =  top 边距（mm→page unit）；图像内容在 raster 行内的 x 起点 =
                       round(left * pageUnit / 25.4) 个 dot（行首补 0）
  ESC ( $ 仍为 0
  ```
  实测 margin=[5,10,15,20]、100×100@120dpi：基线 600×600 → S=(1167,895)（宽 +567=20mm、
  高 +850=30mm）、c=(-555,2005)、prologue ESC(v)=**283**（10mm*720/25.4=283.5 ✓）、
  首内容纸行 = 640+283 = 923 ✓、n=296（1167 dots→292B→补齐 296）。

### 7.6 首块 advance（图像顶部空白）与「空白跳过」

- **首块前的 ESC ( v**：当图像顶部有空白行时厂商会写一个前置 advance = 顶部第一条有内容的
  纸行的相对位置（单位 page unit，相对图像顶）：
  - 金样本：图像最高内容行 y=25/26 → 150/156，实测写 **150**；
  - geomh（720px@72dpi，第一条线 y=61 → 610）：写 **610**；
  - geomv（竖线从 y=60 → 600）：写 **600**；
  - flat_black（内容从 y=0）：**不写**该命令（0）。
  写入后内容恰好落在块 0 的 r≈80 行（因 P0=640=8*80）。
  **我们自己的生成器可以省略**（pos0=0），只是块数略多、文件略大，打印位置不变。
- **块间跳跃**：金样本 advance 序列 = `150, 79×47, 349, 79...`。349 出现在上方文字
  与下方文字之间的空白带（内容纸行 [796..1965] 与 [2950..4215] 之间的 984 行空白）。
  geomh 每两条横线之间用 592 跳过。规律：**空白带用一次大 advance 跳过**，具体取整规则
  未解（TODO §12.2）。生成器可**不用跳跃**（全部 79），只多几个空块，打印结果一致。

---

## 8. modeId → 参数总表（A3-DTF-1390.prs，实测）

| modeId | 通道数 | ESC(U | ESC(D V,H | n(dots/px) | adv | 颜色顺序 | M | P0 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 4 | 08 08 04 | 16,2 | 152 | 71 | 04,00,12,11 | 245 | 288 | 4-pass |
| 1 | 6 | 08 08 04 | 16,2 | 152 | 35 | 12,11,00,02,01,04 | 277 | 324 | 4-pass ×2 |
| 2 | 4 | 04 04 04 | 16,2 | 152 | 79 | 04,00,12,11 | 555 | 640 | 8-pass（金样本） |
| 3 | 6 | 04 04 04 | 16,2 | 152 | 39 | 12,11,00,02,01,04 | 587 | 680 | 8-pass ×2 |
| 5 | 6 | 04 04 02 | 16,4 | 80 | 11 | 12,11,00,02,01,04 | 627 | 712 | 水平 360dpi |
| 7 | 6 | 02 02 02 | 16,4 | 80 | 11 | 12,11,00,02,01,04 | 1227 | 1413 | pageUnit 1440 |
| 9 | 6 | 02 02 01 | 16,2 | 152 | 11 | 12,11,00,02,01,04 | 1227 | 1413 | pageUnit 1440 |

- 4 色/6 色由 modeId 决定；`ESC ( e`（墨滴大小）实测：m0..m3、m9 = **0x21**，m5/m7 = **0x34**；
  `ESC ( m`：m0..m3 = **0x41**，m5/m7 = **0x40**，m9 = **0x51**；`ESC ( K` 恒 `0002`。
- 「6 色 m1/m3 块数翻倍」原因 = **advance 减半**（71→35、79→39），不是别的；输出数据量翻倍。
- mode5/7 水平 360 dpi（HORIZONTAL=4），故 n 减半（80B/100px 图）。

---

## 9. 记录颜色顺序与 `ESC ( $`

- mode0/2：`[0x04(K), 0x00(C), 0x12(M), 0x11(Y)]`
- mode1/3/5/7/9：`[0x12, 0x11, 0x00(K), 0x02(C), 0x01(M), 0x04(Y)]`
- `ESC ( $` 参数：mode0..3 实测 **恒 0**（196/196、100/100 记录）。厂商另一 prs 的 149.8MB
  USB 抓包样本里是 `floor(block/16)%4`（0..3 循环，每 16 块变一次）——见 TODO。

---

## 10. 重叠带与羽化拆分（厂商行为）

- 由于 `8*advance` 与 `VSTEP` 不互素，第 k 与第 k+8 块的窗口重叠 ~80 page-unit：
  某些纸行会同时落在两块的可打印行里（k 的行 r≈79..89 与 k+8 的行 r≈0..10）。
- 厂商做法：把该行的点阵**拆分**成互斥两份（实测 `both=0`，304/304 对；见
  `a3dtf1390_flat_black_100_m2` 纸行 640：块0 r80 与 块8 r1 互斥）。
  这是羽化（避免拼接带），拆分掩码与加网相位相关（T3：stochastic FM），未完全解出。
- **我们不需要拆分**：按 §7.4 的「取最大 k」规则，每行只写进一个块，另一块该行全 0，
  打印结果相同（厂商那种做法的唯一收益是接缝更平滑）。

---

## 11. 生成伪代码（C++/Qt 直接照抄）

```cpp
// ---- 1. 从 modeId 取参数表（§8） ----
struct ModeParams { int pageUnit, vstep, vdpi, hdpi, advance, M, P0;
                    std::vector<uint8_t> colors; };
ModeParams mp = modeTable[job.modeId];       // ESC(U.a=2880/pageUnit, b同, c=2880/x
                                             // ESC(D: VERTICAL=1440/vdpi*?... 见 §9 表)

// ---- 2. 尺寸 ----
double imgDpiX = pngHorizDpi(), imgDpiY = pngVertDpi();   // 来自 PNG pHYs；缺省 72
int colStep = (int)llround(mp.hdpi / imgDpiX);            // mode2 120dpi -> 6
int rowStep = (int)llround(mp.pageUnit / imgDpiY);        // mode2 120dpi -> 6
int content_w_dots = (int)llround(imgW * (double)mp.hdpi / imgDpiX);
int content_h_units= (int)llround(imgH * (double)mp.pageUnit / imgDpiY);
int content_w_units= (int)llround(imgW * (double)mp.pageUnit / imgDpiX);
int n = align8((content_w_dots + 3) / 4);                 // 每行字节数
// ESC(S) = (content_w_units, content_h_units - M)      [u32 回绕]
// ESC(c) = (-M, content_h_units + M)                   [int32]

// ---- 3. 头/命令区/记录 见 §1 §2 模板 ----

// ---- 4. 光栅化到"纸行" ----
//  layers[color][p] = vector<uint8_t>(n)   // p = 纸行号（绝对）
for (int y = 0; y < imgH; ++y) {
    for (int sub = 0; sub < rowStep; ++sub) {
        int p = mp.P0 + rowStep*y + sub;
        // 每色：把图像行 y 的 2bit 点阵水平放大 colStep 倍并按 §5 打包
    }
}

// ---- 5. 分块 ----
long long pos = 0;                       // pos_0 = 0（可选：顶部空白跳过值）
int N = 0; long long lastP = mp.P0 + content_h_units - 1;
// 精确 N：
for (long long p = mp.P0; p <= lastP; ++p) {
    int r; long long k = solveK(p, pos, mp.advance, mp.vstep, /*out*/r);
    N = std::max(N, (int)k + 1);
}
for (int k = 0; k < N; ++k) {
    if (k > 0) pos += mp.advance;        // 写 ESC ( v pos 增量
    for (auto color : mp.colors) {
        // 填 90 行：r -> 纸行 p = pos + vstep*r -> 若 p 在内容区则拷对应图像行
        std::vector<uint8_t> raw(90 * n, 0);
        for (int r = 0; r < 90; ++r) {
            long long p = pos + vstep*r;
            if (p < mp.P0 || p > lastP) continue;
            int i = (int)((p - mp.P0) / rowStep);   // 图像行
            // 水平放大 colStep 倍 + 2bit 打包写入 raw[r*n ...]
        }
        // ESC ( $ 0 ; ESC i color 1 2 n 90 ; RLE(raw) ; 0D
    }
}
```

`solveK(p)`：`k = 满足 (pos0+adv*k) % vstep == p % vstep 且 pos0+adv*k ≤ p 且
(p-pos0-adv*k)/vstep ≤ 89` 的最大 k。因为 `gcd(advance, vstep)==1`（71/35/79/39/11 都是奇数、
vstep 是 2 的幂），用模逆直接算：`k0 = ((p-pos0) * inv(advance mod vstep)) % vstep`，
然后 `k = k0 + vstep * ((p-pos0-adv*k0) / (adv*vstep))` 向下取整。

> **注意**：如果只追求"能打印"，第 4 步的 2bit 点阵用你们自己的加网结果即可；如果追求
> 和蒙泰 byte-exact，还需要 T3 的 halftone（stochastic FM）和它的"每纸行独立抖动相位"。

---

## 12. 已验证结论 & 未解之谜（TODO）

### 12.1 已逐字节验证（证据）

1. **RLE 编码器 byte-exact**：`tools/prn_tools/verify_rle.py`，
   9 个样本 / 1060 条记录 decode→encode 全等。
2. **整文件 round-trip byte-exact**：`tools/prn_tools/reencode_prn.py`
   把解析结果整体重建（头部/prologue/记录/尾部），与厂商文件比较：
   **ESC/P2 语料全部 135 个文件 / 95,978,263 字节 / 0 差异**（TI 8 字节时间戳归一化后），
   包括全幅 720px checker（9.5MB）、金样本 `1793946733280.prn`、SDK `test.prn`(5.4MB)、
   以及 mode0/1/2/3/5/7/9 各模式样本。5 个 HSSF 0x5555 文件（板卡机）不属于本格式，被跳过。
3. **几何模型**：flat_black_100_m2 16 块解出的非空纸行 = 640..1239 连续 600 行、
   每行 (k,r) 满足 pos_k+8r=p（100%）；geomv/geomh 的线条纸行位置与公式完全吻合。
4. **预览重建**：`tools/prn_tools/render_preview.py` 用该模型从金样本 PRN 重建页面，
   "SNS / 10" 字形、位置、比例正确（见 `work/escp2/golden_preview.png`）。

### 12.2 TODO / 未解

| # | 问题 | 现状 / 下一步 |
|---|---|---|
| 1 | **P0 的精确公式**（=M+delta，delta 43/47/85/93/186 的来历） | 已实测各 mode 常量；delta 与 VSTEP/通道数有相关性但公式未定。下一步：用 oracle 生成同 mode 不同 margin 的样本，或反汇编驱动初始化代码。 |
| 2 | **空白跳过的 advance 取整规则**（金样本 150/349、geomh 592） | 规律=跳过空白带，但具体数值来源未定（似乎=下一个内容纸行 - 常数）。生成器可不用跳跃。 |
| 3 | **重叠带羽化拆分掩码** | 厂商把 k/k+8 重叠行的点阵拆成互斥两份；我们不分拆（另一块写 0）效果等价。若要 byte-exact 需 T3 的 FM 加网相位。 |
| 4 | **每纸行的抖动相位** | 同一图像行对应的 rowStep 条纸行（6 条）厂商的 2bit 值不同（FM 抖动逐行变相位）；我们可复制同一份（最近邻放大），打印可接受。 |
| 5 | `ESC ( $` 在 mode0..3 恒 0 | 149.8MB 的厂商样本里是 floor(block/16)%4；不同 prs/机型。对 A3-DTF-1390 直接写 0。 |
| 6 | 6 色模式下 0x12/0x11（白墨 W1/W2）的语义、顺序、inputColorEditor W1 full 的像素规则 | 需白墨专用样本；归 T3。 |
| 7 | mode5/7/9 的完整字段（M/P0 已实测，ESC(D 水平 360dpi、n 减半已实测；`ESC ( e`/`ESC ( m` 变化） | 语料仅 100px 图；建议补 720px 样本验证 content/块数公式。 |
| 8 | 纸张尺寸 5669×4442 等数值的来源 | 就是 (content_w_units, content_h_units-M) 的实测值，不是固定纸张；不同图不同。 |
| 9 | `view.xdpi/ydpi` 的作用 | 实测**无效**；实际 dpi 取 PNG `pHYs`（缺省 72）。 |

---

## 13. 工具（tools/prn_tools/）

| 文件 | 用途 |
|---|---|
| `parse_prn.py` | 主解析器：`info`/`stats`/`json`/`planes` 子命令；header/prologue/blocks/records/RLE/位打包解码；`planes` 把每条记录解码后的 n*m 光栅导出为 `b<块>_c<色>.bin` + index.json；`rle_encode`（byte-exact） |
| `verify_rle.py` | 对语料做 decode→encode 逐记录比较 |
| `reencode_prn.py` | **整文件 round-trip**：重建 .prn 并与厂商文件比较（TI 归一化）。engine-dev 可用它验证编码器 |
| `render_preview.py` | 用几何模型从 .prn 重建页面 PNG（自动识别 mode 参数），人眼比对用 |
| （work/escp2/ 下）`an_paperrows.py` / `model_check.py` / `an_passes.py` | 本文结论的推导脚本与统计 |

用法：
```powershell
# 解析统计
python tools/prn_tools/parse_prn.py stats job.prn
# 整文件重编码比对（exit 0 = 一致）
python tools/prn_tools/reencode_prn.py reference/prn_samples/xxx.prn --out re.prn
# 重建预览
python tools/prn_tools/render_preview.py job.prn --out preview.png --scale 4
```

---

## 14. 与 Lead `docs/02_geometry_escp2.md` 的差异（请更新）

1. §3.2 的 `page_row = pos_k + VSTEP*r` **正确**；但不要用 90dpi 语义理解重复：每个
   纸行只喷一次（见 §7.3 验证），也不需要"每页行 9 份"。
2. §3.2 的 `P0≈644`：精确值模式常量 **640**（mode2），见 §7.2；`P0≈644` 是 8 行量化误差。
3. §3.5「重叠带互斥拆分」正确，但我们**生成时不需要拆分**（§10）。
4. §3.3/§3.4 的块数经验式 `ceil(8N/adv)+8` 可替换为精确式 `N = 1+max_p k(p)`（§7.4）。
5. 颜色映射：mode2 = `0x04=K,0x00=C,0x12=M,0x11=Y` ✓ 与 Lead 一致；
   但 6 色模式实测是 `0x00=K,0x02=C,0x01=M,0x04=Y`，0x12/0x11 才是白墨位（§6）。
```
