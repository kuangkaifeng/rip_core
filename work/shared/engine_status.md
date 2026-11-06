# engine_status · ESC/P2 版面布局 + PRN 编码器 + PRN 反解（T5 / engine-dev）

> 更新时间：2026-11-06 15:35 左右（Asia/Shanghai）
> 范围：`src/core/encode/layout_escp2.{h,cpp}`、`src/core/decode/prn_reconstruct.{h,cpp}`、
> `src/tools/mtr_prncheck.cpp`（CMakeLists 追加）、`tools/validate/*.py`。
> 规范依据：`docs/prn_escp2.md`（T2 定稿，已整文件 round-trip 逐字节验证）+ 本人语料实测。

---

## 1. 结论速览

| 项 | 状态 | 证据 |
|---|---|---|
| 纯白作业（m0/m1/m2/m3）| ✅ **逐字节完全一致（264B，0 差异）** | `mtr_prncheck roundtrip` + `compare`，byteDiff=0 |
| flat_black / checker / 64px / 720px / 金样本（m0..m3/5/7/9）| ✅ 内容平面**逐像素差异 0.0000%**、块数一致 | `tools/validate/roundtrip_check.py` |
| 全语料批量回归（集成后 clean build）| ✅ **1847/1847 个有效 ESC/P2 样本内容 0 差异**（1854 中 5 个 HSSF、2 个 0 字节失败作业除外）| bulk 脚本（见 §5.2） |
| 金样本（718×654）| ✅ 几何/内容 0 差异；结构 58 块 vs 厂商 49（空白带跳跃未复刻，打印等价）| 同上 |
| 端到端 `mtr_cli rip`（Lead 管线 + 本模块）| ✅ 白图逐字节一致（仅 TI）；黑图页面 raster 差异 **0.47%**（<1%，残差在 T3 加网）| §5.1 |
| 羽化拆分掩码 | ⚠ 未复刻（不拆分，打印结果等价）；已采集规律（§4.3），需要时可做 byte-exact | work/escp2/*，本文件 |
| 金样本/顶部空白前的首块 ESC(v（150/610/600）与空白带跳跃（349/592）| ⚠ 未复刻（我们 pos0=0，多几个空块，位置不变）| §4.5 |

---

## 2. 已确认的几何公式（实现依据）

### 2.1 内容尺寸（页面单位 = page unit，m2/m3 = 1/720"，m0/m1 = 1/360"）

```
pageUnit   = 2880 / ESC(U.a            # m2/m3=720, m0/m1=360, m7/m9=1440
VSTEP      = pageUnit / (1440/ESC(D.v) # m2/m3=8, m0/m1=4, m7/m9=16
hdpi       = 1440 / ESC(D.h             # m2/m3/9=720, m0/1/5/7=360
content_w_dots = round(imgW * hdpi / imgDpi)         # imgDpi = PNG pHYs（缺省 72！）
content_h_units= round(imgH * pageUnit / imgDpi)     # = 页面行数
content_w_units= round(imgW * pageUnit / imgDpi)     # 只用于 ESC(S) 宽
n = align8(ceil(content_w_dots / 4))                 # 实测 600->152, 1000->256, 4308->1080
m = 90；2bit MSB：v0=(b>>6)&3, v1=(b>>4)&3, v2=(b>>2)&3, v3=b&3
```

注意：**m0/m1 的 widthDots 是 720dpi 点数、heightDots 是 360dpi 行数**（非方形像素）；
m2/m3 二者同比例。

### 2.2 命令区字段（A3-DTF-1390，实测）

```
ESC @
ESC ( G 01 00 01
ESC ( U 05 00 <uA> <uV> <uH> 40 0B      # 2880 = 0x0B40
ESC U 00
ESC ( i 01 00 00
ESC ( K 02 00 00 02
ESC ( e 02 00 00 <dotSize>              # m0..m3/m9=0x21, m5/m7=0x34
ESC ( D 04 00 A0 05 <rasterV> <rasterH> # r=1440；m0..m4/m9: 16,2；m5/m7: 16,4
ESC ( c 08 00 int32(-M) int32(content_h_units + M)
ESC ( S 08 00 u32(content_w_units) u32(content_h_units - M)   # 负值按 u32 回绕，勿 clamp
ESC ( m 01 00 <method>                  # m0..m3=0x41, m5/m7=0x40, m9=0x51
ESC ( V 04 00 00 00 00 00
（可选）ESC ( v 04 00 <initialAdvance>   # 仅图像顶部有空白时厂商才写，生成可省略
```

### 2.3 模式参数表（写入 `escp2ModeParams()`；m0..m9 全实测/文档一致）

| mode | planes | pageUnit | VSTEP | hdpi | adv | M | P0 | 颜色记录顺序 | 每记录纵向偏移 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 4 | 360 | 4 | 720 | 71 | 245 | 288 | 04,00,12,11 = K,C,M,Y | 0,0,2,2 |
| 1 | 6 | 360 | 4 | 720 | 35 | 277 | 324 | 12,11,00,02,01,04 = W1,W2,K,C,M,Y | 2,2,0,0,2,2 |
| 2 | 4 | 720 | 8 | 720 | 79 | 555 | 640 | 04,00,12,11 = K,C,M,Y | 0,0,4,4 |
| 3 | 6 | 720 | 8 | 720 | 39 | 587 | 680 | 12,11,00,02,01,04 | 4,4,0,0,4,4 |
| 5 | 6 | 720 | 8 | 360 | 11 | 627 | 712 | 12,11,00,02,01,04 | 4,4,0,0,4,4 |
| 7 | 6 | 1440 | 16 | 360 | 11 | 1227 | 1413 | 12,11,00,02,01,04 | 8,8,0,0,8,8 |
| 9 | 6 | 1440 | 16 | 720 | 11 | 1227 | 1413 | 12,11,00,02,01,04 | 8,8,0,0,8,8 |

- 6 色模式色义（T2 实测）：`0x00=K, 0x02=C, 0x01=M, 0x04=Y`，`0x12/0x11 = W1/W2`（白墨，顺序待 T3 确证）。
- 每记录纵向偏移 = 物理头色行错位（C/K 一组，M/Y/W 一组，差 1/180"）：**记录坐标 = 物理纸行 + 偏移**。
  T3（prs-analyst）独立结论"通道页面行相位：C/K 内容顶行=640，M/Y=644"与此一致。
- **P0 为模式常量**（与图像尺寸无关，64px/100px/720px/金样本 654px 交叉验证）；"P0≈644"的旧结论
  是没扣除 M/Y 的 +4 记录偏移造成的。P0 = M + delta（delta 43/47/85/93/186，公式未知，直接查表）。

### 2.4 块/纸行归属（生成算法核心）

```
pos_k = initialAdvance + Σ_{j<k} advance_j          # initialAdvance 生成时取 0
块 k 第 r 行 -> 纸行 p = pos_k + VSTEP*r
对每个内容行 i、每个记录 rec：p_i = P0 + i + recordOffset[rec]
  k(i) = max{ k : pos_k ≡ p_i (mod VSTEP) 且 pos_k ≤ p_i 且 r=(p_i-pos_k)/VSTEP ≤ 89 }
  把内容行 i 写进块 k(i) 第 r 行（每个纸行只写一次；其他块该行写 0）
块数 N = 1 + max k(p)，p 只遍历内容行 P0..P0+H-1（不含记录偏移，才与厂商实测块数一致：
       100px: m0=9,m1=18,m2=16,m3=33；64px: 13；720px: 63；m5=120；m7/m9=237）
```
模逆：`gcd(advance, VSTEP)=1`（adv 奇数），`k0 = ((p-pos0) * inv(adv mod VSTEP)) mod VSTEP`。
实现：`src/core/encode/layout_escp2.cpp: solveBlockRow()` / `computeEscp2Layout()`。

### 2.5 RLE（已按 T2 逐字节验证规则实现）

- 每条记录 `n*m` 字节，**按行（n 字节）重新开始编码**；
- 重复段 token：连续相同字节 **≥3** 才用（长度 2 走字面量），单 token 最长 128；
- 字面量 token：最长 128，遇到"连续 3 个相同字节"即断开；
- 解码：c≤127 → 复制 c+1 字节；c≥128 → 下一字节重复 257-c 次。
- 实现：`Escp2Writer::rleEncode()`（已改 ≥3）。

### 2.6 全零（纯白）作业路径

整页无墨时：不写任何光栅块，命令区后写一条 `ESC ( v 04 00 <whiteAdvance>` 再 `0C` 换页。
whiteAdvance 为**模式常量**（实测，与图像尺寸无关，col_W 1000×1000 与 600×600 同为 705）：
m0=353, m1=349, m2=705, m3=697（m5/7/9 未实测，暂 0）。实现已用于 4 个纯白样本 → 逐字节一致。

---

## 3. C++ 交付物 / API

### 3.1 `src/core/encode/layout_escp2.{h,cpp}`
```cpp
Escp2ModeParams mp = escp2ModeParams(modeId);     // 上表全部参数
Escp2PageRaster page;
page.widthDots  = content_w_dots;                 // 见 §2.1
page.heightDots = content_h_units;
page.planes     = { plane_0, plane_1, ... };      // 顺序 = mp.colorCodes；每平面 0..3
Escp2Config cfg;                                  // 作业名/主机名/时间（TI）由调用方给
Escp2LayoutInfo info;
bool ok = writeEscp2Prn(path, mp, page, cfg, &info, &err);
// 或 buildEscp2Prn(mp, page, cfg, &prnBytes, &info, &err) 只拿内存
```
- 自动处理：p0/块数/位置、记录归属（max-k 独占）、每记录偏移、2bit 打包（MSB）、
  align8 行宽、RLE(≥3)、ESC 命令区、白图路径、尾部。

### 3.2 `src/core/decode/prn_reconstruct.{h,cpp}`
```cpp
Escp2JobInfo job;
PrnReconstructor::parse(prnPath, &job, &err);                 // 结构 + 每记录解码数据
PrnPageRaster page; PrnReconstructor::decode(...);            // 页面物理 raster（已扣记录偏移）
QVector<QVector<uint8_t>> planes; int W,H;
PrnReconstructor::extractContentPlanes(prnPath, modeId, &planes, &W, &H, &job, &err);
PrnReconstructor::exportBmps(page, outDir, &err);             // 每色 BMP + ink_union
Escp2Config cfg = PrnReconstructor::jobInfoToConfig(job);     // 从 PRN 头还原 TI/JS/JH
```
- 自动识别 modeId（pageUnit/planes/rasterH）；p0/每记录偏移按同一张表；
- 解析命令区时把"首块前 ESC(v"计入 initialPos（金样本 150）。

### 3.3 `src/tools/mtr_prncheck.cpp`（新可执行 `mtr_prncheck`）
```
mtr_prncheck info <prn>
mtr_prncheck raster <prn> [--out dir]              # 导出每色页面 BMP（8bit 点阵预览）
mtr_prncheck content <prn> [--out dir] [--mode N]  # 导出内容平面原始 .bin（0..3，content 坐标）
mtr_prncheck compare <ref.prn> <gen.prn>           # 结构 + 内容平面逐像素差异率
mtr_prncheck roundtrip <ref.prn> [--out out.prn] [--mode N]
```
- `content` 导出 `content_<rec>_<code>.w<W>h<H>.bin`（每记录一张 0..3 原始平面，内容坐标，
  已扣 recordOffset/P0），供 T3 加网阈值场等逐像素对拍。
- `roundtrip` = 反解内容平面 → layout+encoder 重编码 → 与参考做结构/内容/字节比较；
- `compare` 输出 `blocks ref->gen / contentDiff%`，验收脚本按 `contentDiff < 0.01%` 判 PASS；
- 注意：Release 下**不要在同一进程内嵌套调用 compare**（已验证会触发 MSVC 释放期 AV，
  工具已拆成两次进程调用；`roundtrip` 自身只做字节对比后退出）。
- 当前 `mtr_cli decode --prn x.prn [--out dir] [--mode N]` 已接到本模块
  （`PrnReconstructor::decode` + `exportBmps`，纯白作业也返回内容尺寸信息）。

### 3.4 `tools/validate/`
| 文件 | 用途 |
|---|---|
| `prn_model.py` | Python 独立解析/几何模型（模式表、solve_block_row、extract_content_planes） |
| `compare_prn.py` | **独立于 C++ 的 PRN 比较器**：结构 + 内容平面逐像素 + 可选图像对齐抽查 |
| `roundtrip_check.py` | 验收驱动：13 个验收样本逐个 roundtrip+compare，输出 PASS/FAIL 表 |
| `verify_screen_probes.py` | **T3 加网阈值场独立复核**：`mtr_prncheck content` 解 oracle 探针 → 与 `reference/screen/final/thr_*.bin` 逐像素比（§3.5） |
| `derive_layout.py` | 早期版面反推脚本（块 advance/重叠带统计） |
| `out/` | 生成的对照 PRN/BMP（可删） |

### 3.5 T3 加网阈值场独立复核（用本模块 C++ 解码器）
- 阈值场：`reference/screen/final/thr_<ink>.bin`（1024 tile，[T1,T2,T3]，0=永不触发），
  `level(v,x,y)=(T1&&v>=T1)+(T2&&v>=T2)+(T3&&v>=T3)`，tile 索引 `(x%1024,y%1024)`（内容坐标）。
- 我的解码路径：`mtr_prncheck content` → `content_<rec>_<code>.w1056h1056.bin`，
  不经过 T3 的任何 Python 代码（内容行 = recorded - recordOffset - P0，M/Y 自动补偿 +4）。
- 结果（`tools/validate/verify_screen_probes.py`）：
  - `probe_scan_<ink><tone>_176`（content=1056）× tone∈{0,16,64,128,192,240,255} × C/M/Y/K：
    **28/28 全部 100.0000%**；
  - `_64` 探针（content=384）× tone∈{64,128,192} 可用样本：**12/12 全部 100.0000%**
    （T3 的 Python 解码在该批 M/Y 为 99.976%，差异为最后一行 weave 缺口；我的 union 解码补齐）；
  - **全 256 级 × 4 ink（1024 个探针）**：`verify_screen_probes.py --all-tones C,M,Y,K`
    - 原始：972/1024 探针 100.0000%；52 个探针各 16 个像素不一致（worst 99.9985%）；
    - 定位：52 个探针 = **13 个 tone**（93,95,101,106,151,161,166,186,202,230,242,244,253）
      × 4 ink；每个探针恰有 16 个"tile 预测 level>0 但 oracle 实际 0"的像素；
    - 交叉核对 T3 审计 `work/prs/oracle_screen_audit.json`：我的 832 个异常 cell 与
      审计的 **832 个 cell 完全一致（0 未解释、0 遗漏）**，均为 **oracle 探针自身非单调漏点**
      （直接读 PRN 原始字节可见，如 C tone93 在 (296,53) dot=0 而 t=92/94 dot=1；
      这些点都落在 tile 中 T3==0 的边界像素上）；
    - **排除 oracle 审计 cell 后：1024/1024 探针全部 100.0000%**。
- **确定性复核（protocol-analyst 重跑 + 本人独立交叉验证）**：
  52 个异常探针（13 tone × 4 ink）的原始 + 重跑 r1/r2（`reference/prn_samples/rerun/`）：
  - PRN **逐字节一致（TI 7 字节归一化后）52/52**；
  - 内容平面（`mtr_prncheck content`，C++ 解码器）**0 像素差异 52/52**；
  - 832 个审计 cell 在三份里 level 全为 0：**832/832**。
  复核脚本：`tools/validate/verify_rerun_determinism.py`；
  证据：`work/protocol/evidence/screen_nondeterminism.{json,md}`（T1）、
  `work/prs/oracle_screen_audit.json` + `work/prs/rerun_check.log`（T3）。
  ⇒ **蒙泰侧是"确定性可复现的算法缺陷"**（非随机/竞争）：D<3（T3==0）边界像素在
  13 个特定 tone 上确定性漏点、非单调；±1/±2 邻 tone 正常。tile 无法表达非单调，
  **最终验收口径**：全 256 级原始 972/1024 探针 100%；排除这 832 个 (ink,tone,x,y)
  oracle 非单调 cell 后 **1024/1024 = 100.0000%**（`verify_screen_probes.py --audit`
  默认加载审计 JSON）。tile 保持现状、无需重拟合、无需再重跑作业。
- 结论：**C++ decode 与 T3 阈值场/坐标约定完全一致**（content_top C/K=640、M/Y=644 成立）；
  残差全部来自上述**已知 oracle 偏差**，不是阈值场/解码器错误。
  该偏差已列为「已知 oracle 偏差」写进最终报告口径（T3 的 docs/color_pipeline.md §10.5）。

---

## 4. 未解 / 已知差异

### 4.1 金样本空白带跳跃（不影响打印结果）
厂商 advance 序列 `[150, 79×47, 349, 79...]`（49 块），我们全用 79（58 块）：
顶部空白跳过 initialAdvance 与块间空白带跳跃均未复刻 → 文件略大/块数多，但**内容纸行完全一致**。
公式未解（349/592 取整规则未知；T2 文档 §7.5/§12.2）。

### 4.2 羽化拆分掩码（byte-exact 的最后差距）
厂商把 k/k+8 重叠带同一纸行的点阵按行内 x 掩码拆给两块（实测 both=0）。我们不做拆分
（拥有者块独占，另一块写 0），**打印结果等价**，但字节不同（例如 flat_black m2: ref 321592B / ours 261332B）。
实测规律（`flat_black_100_m2`，K 色，pair(0,8)）：
- 掩码**只与块内行号 r 有关**（同 r 在不同块对间完全相同 → 几何固定，与内容无关）；
- 拆分密度按 r 渐变：r=79..89 → 90.8%, 81.8%, 72.7%, 63.5%, 54.5%, 50%, 50%, 33.3%, 20%, 9%, 0%
  （r=0..10 为其补集）；
- 不同颜色掩码略有 1~2 dot 的横向平移（物理头列错位）。
若后续要 byte-exact：可从 flat_black 探针提取 90×n 掩码表（只 r<11 与 r>78 非平凡），
按颜色施加横向平移；需要更大画幅时验证掩码是否按 x 周期延拓（未完成）。

### 4.3 每纸行 FM 抖动相位（T3/T2 事项，不影响本模块）
同一图像行对应的 rowStep 条纸行厂商 2bit 值不同（stochastic FM 逐行相位）；我们输入的是
已加网内容平面，不负责此层。

### 4.4 m5/m7/m9 记录偏移是推测值（8,8,0,0,8,8 / 4,4,0,0,4,4）
由 1/180" 物理错位换算；语料里这些模式的 flat_black 样本 `0x12/0x11` 无墨，未能实测全部记录。
内容平面回归 0 差异（§5）说明至少 C/K/M/Y 四色正确。

### 4.5 P0/M 的解析公式未知
现为查表常量（表见 §2.3）。新增 prs/机型时需 oracle 标定。

---

## 5. 验证结果（可复现）

### 5.1 验收（`python tools/validate/roundtrip_check.py`，2026-11-06 15:45 全量重建后复跑）

| 样本 | mode | 期望 | 结果 | 备注 |
|---|---|---|---|---|
| flat_white_100 × m0/m1/m2/m3 | 0/1/2/3 | 逐字节一致 | ✅ byteDiff=0（264B） | 全零作业路径 |
| flat_black_100 × m0/m1/m2/m3 | — | 内容一致 | ✅ diff=0.0000%，块数 9/18/16/33 全同 | 羽化差异→字节不同 |
| checker_1px_100_m2 / checker_8px_720_m2 | 2 | 内容一致 | ✅ 0.0000% / 块数 16、63 同 | |
| geom_flat_black_720_m2 | 2 | 内容一致 | ✅ 0.0000%，63 块同 | 13.8MB 文件 |
| probe_black_64_m2_golden | 2 | 内容一致 | ✅ 0.0000%，13 块同 | |
| golden_repro_1793946733280 | 2 | 几何/内容一致 | ✅ 0.0000%；58 vs 49 块（空白跳跃） | 4308×3924 |
| **[端到端] mtr_cli rip flat_white_100 m2** | 2 | 逐字节（仅 TI 允许不同）| ✅ ref=264B gen=264B，**非 TI 字节差异 0** | Lead 的图像→分色→加网→layout 全链路 |
| **[端到端] mtr_cli rip flat_black_100 m2** | 2 | 页面 raster 差异 <1% | ✅ **0.4717%**（Y 1.24%/C 0.17%/W1 0.18%/W2 0.30%，差异来自 T3 加网近似，非几何）| 同上 |

> 注：端到端黑图 0.47% 是本轮实测（T3 阈值场+Lead 管线），几何/版面本身在"反解→重编码"闭环里是 0%。

### 5.2 全语料回归（集成后 clean build 最终确认）
对 `reference/prn_samples/` 全部可识别 mode（0/1/2/3/5/7/9）的样本逐个
`roundtrip + compare`（`roundtrip` 反解→重编码、`compare` 按内容平面逐像素比较）：
**PASS 1847 / 1854**。7 个未通过均不是 ESC/P2 有效样本：
- `geomh_*_m0`（5 个）= H13 XP600 的 **HSSF 0x5555**（`55 55 00 00...`，T4 范围）；
- `exp_a3dtf1390_dpi_300*.prn`（2 个）= **0 字节失败作业**（oracle 未产出）。
⇒ 有效 ESC/P2 样本 **1847/1847 = 100% 内容平面差异 0.0000%**（m0/1/2/3/5/7/9 全模式）。

### 5.3 独立复核（Python）
- `python tools/validate/compare_prn.py <ref> <gen>` 与 C++ 结果一致（golden 0.0000%，
  且能区分"内容一致但结构不同（空白跳跃/羽化）"）。
- `--image` 输入图对齐抽查：golden 与 flat_black 的**行墨迹一致性 100%**（colStep=6、rowStep=6、
  内容尺寸 4308×3924 / 600×600 全对），独立证明 P0=640、M/Y +4 记录偏移、rowStep 换算正确。

---

## 6. 给 Lead 的集成建议

1. **调用路径**（`rip_engine.cpp`）：
   ```
   图像 --(PNG pHYs DPI)--> mode 参数 mp --(T3: ICC/限墨/线性化/白墨/FM 加网)-->
   Escp2PageRaster{widthDots=content_w_dots, heightDots=content_h_units,
                   planes 顺序 = mp.colorCodes}
   --> writeEscp2Prn(job.prnPath, mp, page, cfg, &info, &err)
   ```
   cfg 里作业名/主机名/TI 默认即可（TI=当前时间，与蒙泰唯一允许不同的字段）。
2. **尺寸换算必须用 PNG 内嵌 DPI（pHYs，缺省 72）**，不是 job.view。`content_h_units` 用
   `imgH*pageUnit/imgDpi`；m0/m1 的平面高度是 360dpi 行数，但宽度是 720dpi 点数。
3. **M/Y 记录 +4 行偏移已封装**：T3 只需按"内容坐标"输出 4/6 张平面（C/K 与 M/Y 同坐标），
   layout 内部按 recordOffsets 排到 644 行；不要自己再位移，否则错位。
4. **白墨**：6 色模式 records[0]=0x12(W1)、records[1]=0x11(W2)，顺序待 T3 定；
   m0/m2 4 色模式没有白墨通道（W1 参数对输出逐字节无影响，T1 已实测）。
5. **纯白页**（全部平面为 0）：自动输出"无块+whiteAdvance"模式 → 与蒙泰逐字节一致。
6. **mtr_prncheck** 可直接做 CI：`roundtrip` + `compare` 两次调用（勿嵌套）；`tools/validate/out/` 为产物。
7. 当前 `build.cmd` 全量构建曾被并发/rip_engine.cpp 编译错误打断；我的文件单独编译通过
   （layout_escp2/prn_reconstruct/mtr_prncheck 已链接出过一次）。**全量重建验证需在 Lead 改完
   rip_engine 后执行**：`cmd /c build.cmd` + `python tools/validate/roundtrip_check.py`。
8. ⚠ 集成注意（m5/m7/m9）：`PrsConfig` 的 mode 表对 mode 5 显示 `1440x720`，但 ESC/P2 实测
   m5 是 pageUnit=720、**水平 360dpi**（ESC(D.h=4，n 减半；T2 文档 §8）。m0..m3 两套数据一致，
   但 m5/7/9 的 `content_w_dots` 请用 `escp2ModeParams(modeId).xDPI`（=hdpi）而不是
   `PrsMode::xDPI`，否则 n/ESC(S) 会错。当前 rip_engine 用的是 `mode->xDPI`，m5/7/9 需注意。

---

## 7. 收尾状态（集成后）

- Lead 已把 `layout_escp2` 接入 `src/core/rip_engine.cpp`（ESC/P2 路径：`escp2ModeParams(modeId)`
  + `writeEscp2Prn`，页面点阵按 `mp.colorCodes` 重排），clean build OK。
- 集成后端到端（Lead 实测）：`a3dtf1390_flat_white_100_m2` 与 oracle **逐字节一致（264B, diff=0）**；
  100×100 灰度/黑图页面逐像素一致率 C 99.8% / M 99.8% / Y 99.7% / K 98.9%（残差在 T1/T3 的加网 tile/LUT）。
- `mtr_cli decode --prn <prn> [--out dir] [--mode N]` 已接到 `prn_reconstruct`：
  输出 modeId/content/p0/命令区参数/页面 raster 统计，并导出每色页面 BMP（`plane_XX.bmp`、`ink_union.bmp`）。
- 集成后回归（当前 clean build）：`python tools/validate/roundtrip_check.py` → **13/13 PRN 目标 +
  CLI 白图端到端 ALL OK**；全语料 1854 个样本 → 有效 ESC/P2 **1847/1847 内容 0 差异**（§5.2）。
- 已知环境坑：build.cmd 与其它 agent 并发构建会互相踩 build 目录，验收前确认无并发构建。

---

## 8. task-8：彩色 3D LUT 集成 + 可选羽化（2026-11-06 18:55）

详见 `work/shared/task8_report.md`。摘要：

- **新增 `RgbCubeLut`**（`src/core/color/rgb_cube_lut.{h,cpp}`）：加载
  `color/rgb_cube9.bin`（magic RGB9/u16 9/u8 4/4×729，r-major/g/b-minor，非均匀轴
  `{0,32,64,96,128,160,192,224,255}`），三线性插值 + 可选四面体；资源缺失静默回退 ICC。
- **接入 `rip_engine.cpp`**：A3(mode) 非灰度像素走 3D LUT；灰度像素仍走 ICC+calib_gray；
  透明语义不变（a==0 不产生墨、0<a<255 白底合成）。
- **开关**：`MTR_NO_CUBE_LUT=1` 回退旧路径；`MTR_CUBE_LUT=<path>` 覆盖文件；
  `MTR_CUBE_GRAY=1`（实验，灰度也用 LUT）；`MTR_CUBE_TETRA=1`（实验，四面体插值）；
  `MTR_VERBOSE=1` 打印加载信息。
- **端到端（print_debug_test22，860×564@72dpi → 8600×5640）总差异率**：
  旧路径 **26.589%** → 默认（3D LUT）**3.945%** → 四面体实验 **3.582%**；
  立方体探针自校验 **0.1506%**（网格点 = LUT 数据精度，非接线错误）。
- **可选羽化**：`MTR_FEATHER=1`（仅 m2）按实测密度表（r=79..89，90.8%→0）把重叠带拆给
  k/k+8 两块；验证 both=0、A∪B=整行、内容平面 0 差异；文件 +14%；默认关闭，不影响验收。
- **回归**：`roundtrip_check.py` → **ALL OK**（白图逐字节一致、13 PRN 目标 0 差异、CLI 白图 TI-only）。
