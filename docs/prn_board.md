# 板卡机（H13 / XP600）`.prn` 格式规范 — HSSF `0x5555`

> 适用链路：`板卡机 H13/H13D/VF13...` + 北印 `BetterPrinter.dll`。
> 结论一句话：**最终 .prn 由蒙泰 MainTop RIP 直接生成，格式是 HSSF `0x5555`（48 字节头 + 行交错 2bit 光栅），北印 SDK 只是读文件、填 `BP_PRINT_TASK` 后把数据发给板卡，不做二次 RIP / 不做格式转换。**
> 对照路线：改装机（Epson 1390/A3-DTF-1390.prs）走 ESC/P2，见 `docs/prn_escp2.md`，与本文无关。

本文所有结论带证据（文件 + 行号/偏移/日志行）。验证脚本：`tools/board_tools/parse_hssf.py`。

---

## 0. 证据链总表（先看这个）

| # | 结论 | 证据 |
|---|------|------|
| E1 | 板卡机 PRN 头结构 = 北印 SDK `HSSF_PRN`（`_PRN_IMAGE_INFO`，48B，`nSignature=0x5555`） | `D:\Code\kkf\v1.1.2\rip-studio\3rdLib\northPrintSDK\include\ImageFormat.h:22-34` |
| E2 | 蒙泰用 `H13 XP600.prs` 也能 RIP，并且输出 HSSF `0x5555` | oracle 语料 `reference/prn_samples/h13xp600_*.prn` 全部 `55 55 00 00` 开头；7 族 mode0-3 文件头见 §2 |
| E3 | H13 实际打印用过的 PRN 就是 HSSF `0x5555`，尺寸 720x1080、5 通道、2bit | `D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn`（21,853,488B，头 `55 55 00 00`，W=3570 H=4878，C=5，BPL=896，720x1080）；同尺寸 PRN 在旧工程日志中被连续打印成功 |
| E4 | 北印侧“打印 PRN”= 读文件头 + `bpPrintSendTask(path)`，不重新生成图像 | `src/service/printService/printerControlH13.cpp:632-729`（readPrnInfo，注释“完全复制 Demo 的 GetPrnFileInfo”）、`:767-865`（buildPrintTask）、`:1781-1828`（doPrint→bpPrintSendTask）；日志 `bin\bin\log.txt` 命中 `readPrnInfo failed` / `bpPrintSendTask returned: 0` |
| E5 | 北印官方控制软件内嵌 `MainTopRipManager`，按喷头型号调用 `byxp6.prs/by3200.prs/byg5i.prs` + `\MT\bin\mtrip.dll` 生成 PRN | 官方 exe 字符串（`D:\work\RIP和北印资料\InkSonic Control Software\...\InkSonic Control Software.exe` @0x51a638 起：`XP600 I3200 G5I byxp6.prs ... /MT/bin/`，@0x51a6xx `MainTopRipManager::setHeadType`，@0x51aaa8 `mtrip.dll MainTopRip MainTopRipCancel MainTopRipReleaseBuffer ... MainTopRipManager::ansyRunMainTop`） |
| E6 | 北印软件“上次打印文件”就是 HSSF `0x5555` 的 TestFile | `...\InkSonic Control Software\System\LPI.ini`：`strLastFilePath=.../TestFile/xp600_4C/720x720_4C+WO.prn`（该文件头 `0x5555`） |
| E7 | 厂商 TestFile（`HeadLeftDistance.prn` 等）同为 HSSF 0x5555，且其数据区排布与格式假设完全自洽（size 公式逐字节吻合、预览图可复原） | `...\northPrintSDK\x64\Release\TestFile\*.prn`；用 `parse_hssf.py` 解码后与同目录 `.prn.bmp` 预览图内容一致（颜色块/圆/照片全部对位） |
| E8 | rip-studio 的设计就是“蒙泰 RIP 出 PRN → 北印 BetterPrinter 发板卡” | `README.md:121-123`；`src/service/ripService/ripcontrol.cpp:854-861`（H13 分支被注释，当前强制 A3）、`:594-598`（modeId 映射） |
| E9 | 板卡机历史打印任务 `stPrnInfo` 由 PRN 头解析得到（W/H/dpi/通道/dotbit），任务里 `ePass` 由板卡配置决定，不在 PRN 头里 | 旧工程 `bin\bin\log.txt` 大量 `[PrinterWorker::buildPrintTask] task: 3570x4878 pass=1 file=...prn`；PRN 头 reserved 全 0（见 §2） |
| E10 | `b.prn`（magic `0x74667966 "fyft"`）**不是**板卡机目标格式（见 §8 未解之谜） | `...\northPrintSDK\x64\Release\RIP\out\b.prn`（12,298,768B，360x1200、C=7），不在北印 4 种受支持魔数（YCDZ/HSSF/BYHX/AT）之列，也无任何日志/配置表明它被打印过 |
| E11 | **BPL 8 字节对齐**（蒙泰写法；北印 TestFile 才是 4 字节对齐） | `exp_h13xp600_h13_scale50.prn`：W=300、2bit、ceil=75、align4=76、align8=80 → 文件 BPL=**80**；`RIP\out\a.prn` W=5008 → 1256（align8；align4=1252）；对照 TestFile W=5670 → 1420（align4） |

---

## 1. 结论与“谁生成、谁消费”

```
图像 ──► 蒙泰 MainTop RIP（mtrip.dll + H13 XP600.prs + ICC/曲线/加网）──► xxx.prn (HSSF 0x5555)
                                                                              │
                                       北印 BetterPrinter.dll ◄── BP_PRINT_TASK(path, stPrnInfo, ePass...)
                                                                              │
                                                                         板卡（USB/网络）
```

* **生成者**：蒙泰（MainTop）RIP。rip-studio 的 `RipControl` / 北印官方软件的 `MainTopRipManager` 都是调蒙泰 C API（`MainTopRip`）或 `mtripNet` HTTP 服务，把图像按 `.prs` 设置 RIP 成 `.prn`。
* **格式**：HSSF（北印 SDK 枚举 `PIIV_HSSF_VERSION=2`），魔数 `0x5555`。
* **消费者**：北印 `BetterPrinter.dll`。`bpPrintSendTask()` 使用 `BP_PRINT_TASK`：`cImageFilePath` 指向 .prn 文件、`stPrnInfo` 由 PRN 头解析（`BP_PRN_IMAGE_INFO`），文件字节原样分块送板卡。
* **北印自己的 RIP 是另一条备选路径**（`BetterRip.dll` / `bpRipStart` / `RIP/Rip.dll`，参数见 `ImageRipDef.h::RipParam`），但 H13 这条线实际用的是蒙泰（E5/E8），我们的替代目标是**复刻蒙泰的输出**，即 HSSF 0x5555。

---

## 2. 文件头（48 字节，Little-Endian）

结构同 `ImageFormat.h:22-34` 的 `PRN_IMAGE_INFO`（HSSF）：

| 偏移 | 类型 | 字段 | 含义 / 生成公式（H13，2bit） |
|------|------|------|------------------------------|
| 0x00 | u32 | nSignature | **`0x00005555`**（磁盘字节序 `55 55 00 00`） |
| 0x04 | u32 | nXDPI | 水平 DPI。H13 恒 **720** |
| 0x08 | u32 | nYDPI | 垂直 DPI。由 modeId 决定：`mode0→720, mode1→1080, mode2→1440, mode3→2160` |
| 0x0C | u32 | nBytesPerLine | **每行每通道字节数**。蒙泰写法：`align8(ceil(nWidth*dotBits/8))`（**8 字节对齐**，dotBits=2）。例：W=600→152；W=300→80（align4 是 76，蒙泰实测 80）；W=3570→896；W=5008→1256。注意：北印自家 TestFile 用的是 **4 字节对齐**（W=5670→1420，align8 会 1424），两套都被读端接受（BPL 以头字段为准），我们复刻蒙泰 → 用 align8 |
| 0x10 | u32 | nHeight | 图像高（像素），= 输出行数 |
| 0x14 | u32 | nWidth | 图像宽（像素） |
| 0x18 | **f32 位模式** | nPaperWidth | 可着墨物理宽度，**float32 米**，公式 `f32(nWidth / nXDPI * 0.0254)`。实测全部样本吻合到 float 精度（如 W=600,720dpi → 0.02116667；W=3570,720dpi → 0.12594166）。注意 SDK 头里声明为 `UINT`，但内容是 float 位模式，生成时按 float 写 |
| 0x1C | u32 | nColorPlane | 通道/平面数。H13 XP600 = **5**（K,C,M,Y,W1）。MainTop 写实际通道数（不是 1/4/6/8 的特殊枚举） |
| 0x20 | u32×4 | nReserved[4] | 见 §2.2 |
| 0x30 | — | 数据区开始 | 紧接 48 字节头 |

### 2.1 头字段实测（oracle 语料，全部来自 蒙泰+H13 XP600.prs）

| 样本 | xDPI | yDPI | W | H | C | BPL | 头 reserved | nPaperWidth(float) | 文件大小 |
|---|---|---|---|---|---|---|---|---|---|
| `h13xp600_flat_k_100_m0.prn` | 720 | 720 | 600 | 600 | 5 | 152 | 0,0,0,0 | 0.02116667 | 456,048 |
| `..._m1.prn` | 720 | 1080 | 600 | 900 | 5 | 152 | 0,0,0,0 | 0.02116667 | 684,048 |
| `..._m2.prn` | 720 | 1440 | 600 | 1200 | 5 | 152 | 0,0,0,0 | 0.02116667 | 912,048 |
| `..._m3.prn` | 720 | 2160 | 600 | 1800 | 5 | 152 | 0,0,0,0 | 0.02116667 | 1,368,048 |
| `probe_black_64_h13_m0.prn`（64x64 输入） | 720 | 720 | 384 | 384 | 5 | 96 | 0,0,0,0 | 0.013547 | 184,368 |
| `exp_h13xp600_h13_scale50.prn`（50% 缩放，**对齐判别关键样本**） | 720 | 720 | 300 | 300 | 5 | **80**（align8；align4=76） | 0,0,0,0 | 0.01058 | 120,048 |
| `h13xp600_cmyk_quad_720_m0.prn`（720px 输入） | 720 | 720 | 4320 | 4320 | 5 | 1080 | 0,0,0,0 | 0.1524 | 23,328,048 |
| 真机历史样本 `1788919812455.prn` | 720 | 1080 | 3570 | 4878 | 5 | 896 | 0,0,0,0 | 0.12594166 | 21,853,488 |
| 蒙泰其它机型实验 `RIP\out\a.prn`（8 通道） | 720 | 2160 | 5008 | 10008 | 8 | **1256**（align8；align4=1252） | 0,0,0,0 | 0.17667112 | 100,560,432 |
| 厂商 TestFile `720x720_4C+WO.prn` | 720 | 720 | 5670 | 5670 | 6 | 1420（align4；align8=1424） | **2,4,1,0** | 0.20002501 | 48,308,448 |
| 厂商 TestFile `HeadLeftDistance.prn` | 720 | 600 | 1905 | 3597 | 5 | 480（a4/a8 同值） | **2,0,1,0** | 0.06720417 | 8,632,848 |

**所有样本都满足** `文件大小 == 48 + nHeight * nColorPlane * nBytesPerLine`（无分块头、无尾部、无压缩）。这是判断一个 .prn 是否 HSSF 的最快办法。

### 2.2 reserved[4] 语义（两种已被接受的写法）

* **蒙泰写法（H13 实际链路）**：`nReserved[0..3] = 0,0,0,0`。dotBits 不写，由消费端从 `BPL/Width` 推断。
* **北印 TestFile 写法（厂商测试图，实际被北印软件打印过，见 E6）**：`[0]=dotBits(2), [1]=pass数(0 或 4), [2]=1, [3]=0`。
* 北印 demo `GetPrnFileInfo` / rip-studio `readPrnInfo`（`printerControlH13.cpp:697-725`）的规则：先取 `nReserved[0]` 为 dotBits；若为 0 或越界则用 BPL/Width 反推（`bpl<=W/8+32→1bit; <=W/4+32→2bit; ...`）。
* **建议**：写 `[0]=2,[1]=pass(默认与 BP_PRINT_TASK.ePass 一致), [2]=1,[3]=0`（厂商 TestFile 写法，语义明确且已被接受）。若要与蒙泰逐字节对齐，写全 0 也可（已证明能被北印软件接受），但注意宽 W≤256 的极小图会被反推规则误判为 1bit，故不推荐全 0。
* dotBits 只有 1 和 2 在本项目出现；H13 一律 2bit（4 级点：0=空、1=小点、2=中点、3=大点；实测 flat_y 平面值分布为 {1,2,3}，黑块平面为 3 占 99%）。

---

## 3. 数据区布局（已用 oracle+真机样本逐像素验证）

### 3.1 行交错（row-interleaved，不是 plane-major）

```
offset = 48
for y in 0 .. nHeight-1:                 # 从上到下
    for c in 0 .. nColorPlane-1:         # 平面顺序 K,C,M,Y,W1
        write(pack_row(plane[c], y), nBytesPerLine)
```

* 验证 1：`1788919812455.prn` 按行交错解码，p2(M)/p3(Y)/p1(C) 分别只在红色"SNS"/蓝色"10"字形上出现，p4 全幅 100%、值全 3（白色满版），与源图 `...\temp\pic\1788919812307.png`（上红 "SNS"、下蓝 "10"、透明底）一致；按 plane-major 解码则全黑，错误。
* 验证 2：厂商 TestFile `720x720_4C+WO.prn` 按行交错解码出的 CMYK 分离图 / 合成图与同目录 `.prn.bmp` 预览内容一致（色块、圆、照片对位）。
* 验证 3：oracle `h13xp600_cmyk_quad_100_m0.prn`（输入 2x2 色块：青/品/黄/黑）按行交错解码，四象限位置/颜色全部对位，无镜像、无旋转（row0 = 源图上边）。
* 验证 4：`exp_h13xp600_h13_scale50.prn`（W=300）用 `BPL=80`（align8）解码图像正常；若用 align4=76 解则逐行错位成斜纹。

### 3.2 2bit 打包（MSB-first）

```
pixel x 的值(0..3) → byte[x/4] 的 bit(6-2*(x%4))
例：像素 0 → bit7..6，像素 1 → bit5..4，像素 2 → bit3..2，像素 3 → bit1..0
行尾不足 1 字节的补 0；每行补到 nBytesPerLine（4 字节对齐）
```

1bit 时为 `bit(7-(x%8))`（本路线不使用）。
行对齐实测（**蒙泰 = 8 字节对齐**，`BPL = align8(ceil(W*2/8))`）：

| 来源 | W | ceil(W*2/8) | align4 | align8 | 实际 BPL |
|---|---|---|---|---|---|
| 蒙泰 H13 (scale 50%) | 300 | 75 | 76 | **80** | **80 → align8** |
| 蒙泰 H13 | 600 | 150 | 152 | 152 | 152 |
| 蒙泰 H13 | 3570 | 893 | 896 | 896 | 896 |
| 蒙泰 其它驱动 a.prn | 5008 | 1252 | 1252 | **1256** | **1256 → align8** |
| 北印 TestFile | 5670 | 1418 | **1420** | 1424 | **1420 → align4**（厂商自己另一套写法，读端 OK） |

→ **自研 writer 用 align8（逐字节对齐蒙泰输出）**；读取/校验端两种都要能接受（BPL 以头字段为准）。

### 3.3 颜色平面顺序（H13 = K,C,M,Y,W1）

oracle 单色块实验（同一 prs/mode，由蒙泰 RIP 出 PRN，脚本统计每平面墨量）：

| 输入 | p0 | p1 | p2 | p3 | p4 | 结论 |
|---|---|---|---|---|---|---|
| flat_y（纯黄） | 0 | 0.02 | 0 | **1.0（值 2/3）** | 0 | p3 = Y |
| flat_m（品红） | 0 | 0.27 | **0.90** | 0 | 0 | p2 = M |
| flat_c（青） | 0 | 0.23 | 0 | 0.15 | 0 | p1 = C（经 ICC 后仍有少量 M/Y 串色） |
| flat_r（红） | 0 | 0 | **1.0** | **1.0** | 0 | M+Y |
| flat_g（绿） | 0 | 0.63 | 0 | **1.0** | 0 | C+Y |
| flat_b（蓝） | 0.12 | **1.0** | **1.0** | 0 | 0 | C+M（+少量 K） |
| flat_black / flat_k | **1.0（值 3 占 99%）** | 1.0 | 1.0 | 1.0 | 0 | p0 = K，ICC 下黑色也带 CMY 墨 |
| flat_black_100_m0_w1w2（请求 W1/W2 full） | 1.0 | 1.0 | 1.0 | 1.0 | **1.0（值全 3）** | p4 = White（白墨满版=值 3） |
| flat_white（纯白） | 0 | 0 | 0 | 0 | 0 | 白色不出墨 |

→ **平面顺序 = K, C, M, Y, W1**（与北印 `RipSavePara`/`PrnOrder=KCMY`、`nColorShowPrn` 默认 0→k,1→C,2→M,3→Y 一致；白墨在最后）。MT H13 XP600.prs 固定 5 通道，modeId 不改变通道数。
注意：rip-studio 内部认为 H13 有 W1/W2 两个白通道（`ripcontrol.cpp:492-530`），但该 prs 产出的 PRN 只有 1 个白平面（p4）。W2 在 H13 XP600.prs 下无独立平面。

### 3.4 没有的东西（容易走弯路，特意列出）

* **没有** pass 分段头/块头/页头；pass 数不在 PRN 里（蒙泰写 reserved=0；北印任务用 `BP_PRINT_TASK.ePass`）。
* **没有** 压缩、没有 RLE、没有 ESC/P2 命令流、没有 EJL 头。
* **没有** 波形/双向/墨序信息（这些是板卡配置，见 `docs/board_pipeline.md`）。
* **没有** 每平面独立高度/不同 BPL；所有平面尺寸相同。
* 文件行序 = 打印图像的“上→下”，镜像/旋转由 RIP 请求的 `rotate/scale/mirror` 或打印任务字段决定，不在 PRN 内标记。

---

## 4. H13 的 modeId 与输出几何

| modeId | (xDPI, yDPI) | 5 通道 | 说明 |
|---|---|---|---|
| 0 | 720 x 720 | K,C,M,Y,W1 | 质量档 0 |
| 1 | 720 x 1080 | 同 | 质量档 1（真机历史样本 1788919812455.prn 即此档） |
| 2 | 720 x 1440 | 同 | 质量档 2 |
| 3 | 720 x 2160 | 同 | 质量档 3 |

* 来源：`ripcontrol.cpp:594-598`：`modeId = (whiteChannelCount==1) ? qualityMode*2+1 : qualityMode`；H13 有 2 个白通道 → **modeId = qualityMode ∈ 0..3**；其它机型（1 个白通道）= 1,3,5,7。与 oracle 实测（mode0-3 的 yDPI 为 720/1080/1440/2160）一致，`queryMode` 也已确认。
* 输出像素几何（RIP 请求 `view.xdpi=ydpi=120`, `scale=100` 时，MainTop 约定按 view dpi 解释输入像素）：
  * `W_out = in_px * xDPI / view_xdpi * scaleX%`
  * `H_out = W_out * yDPI / xDPI`（物理长宽比与输入一致；oracle 100x100 输入：mode0→600x600，mode1→600x900，mode2→600x1200，mode3→600x1800）
* **pass 不在 modeId/PRN 内**：pass 是打印（板卡运动/羽化）参数，来源 `BP_PRINT_TASK.ePass`（H13 的 `Config.ini [task] ePass=4`、`DeviceConfig.ini [task] ePass=8`，`CfDpiDef.ini` 给出各 dpi 组合的可选 pass 列表）。wave/双向同理（见 pipeline 文档）。

---

## 5. 最小可打印 HSSF PRN 契约（writer 必读）

给定：图像尺寸 `W x H`（像素，RIP 后）、`xDPI/yDPI`（= modeId 表）、平面数 `C=5`、dotBits=2：

```python
import struct
def align8(n): return (n + 7) & ~7

def write_hssf(path, W, H, xDPI, yDPI, rows_by_plane):
    """rows_by_plane: 5 个平面, 每个是 H 行、每行 W 个 0..3 的点值"""
    C = 5
    bpl = align8((W*2 + 7)//8)                      # 蒙泰 8 字节对齐；W=300→80, W=600→152
    pw  = struct.unpack('<I', struct.pack('<f', W / xDPI * 0.0254))[0]  # float32 位模式
    hdr = struct.pack('<12I',
        0x5555, xDPI, yDPI, bpl, H, W, pw, C,
        2,      # reserved[0] = dotBits（厂商 TestFile 写法；蒙泰写 0 也可被接受）
        0,      # reserved[1] = pass 数（可选，北印任务实际用 BP_PRINT_TASK.ePass）
        1, 0)   # reserved[2]=1, [3]=0（厂商写法；蒙泰写全 0）
    with open(path, 'wb') as f:
        f.write(hdr)                                 # 必须 48 字节
        for y in range(H):
            for c in range(C):                       # 顺序固定 K,C,M,Y,W1
                row = bytearray(bpl)
                pixels = rows_by_plane[c][y]         # 每像素 0..3
                for x in range(W):
                    row[x >> 2] |= (pixels[x] & 3) << (6 - 2*(x & 3))
                f.write(row)                         # 每行恰好 bpl 字节
```

**验收 checklist（缺一不可）**
1. 文件头 48B，偏移 0 处 `55 55 00 00`；
2. `size == 48 + H * C * bpl`（严格相等）；
3. `bpl == align8(ceil(W*2/8))`（复刻蒙泰；W=300 必须 80 而不是 76）；
4. `nPaperWidth` 的 float 位 ≈ `W/xDPI*0.0254`（误差 < 1e-6）；
5. 数据区行交错、平面序 K,C,M,Y,W1、MSB-first 2bit、每行补到 bpl；
6. `nColorPlane == 5`；`nReserved[0] ∈ {0,2}`（推荐 2）。
7. 打印前 app 侧 `BP_PRINT_TASK.stPrnInfo` 填对：`nWidth/nHeight/nBytesPerLine/nXDPI/nYDPI/nColorChannelNum=5/nDotBit=2/nSignature=0x5555`（见 §6）。

**Python 工具**（`tools/board_tools/parse_hssf.py`，纯标准库）：
```
python parse_hssf.py info   <file.prn>            # 打印头字段+尺寸校验+推断 dotBits
python parse_hssf.py check  <files...>            # 批量校验：sig/size/bpl 公式
python parse_hssf.py planes <file.prn> --out dir --scale 8   # 解码每平面 PNG(+合成图)
python parse_hssf.py make   --out t.prn --width 600 --height 600 --xdpi 720 --ydpi 720 --planes 5 --fill 0,0,0,0,3
```
`planes` 解码时若平面顺序/行交错/位序错，图像会明显花掉——可直接与同目录 `.prn.bmp` 或源图对照，作为“无板卡验证”。

---

## 6. 与北印 `BetterPrinter.dll` 的对接契约

`BP_PRINT_TASK`（`northPrintSDK/include/printparam.h:99-166`）关键字段：

| 字段 | 填什么 |
|---|---|
| `cImageFilePath` | **完整 .prn 文件路径**（北印 demo/rip-studio 就是这样用；文件由 SDK 自己读） |
| `cImageFileName` | 文件名 |
| `stPrnInfo` | 由 PRN 头解析（北印 demo `GetPrnFileInfo` / rip-studio `readPrnInfo`）：`nSignature,nXDPI,nYDPI,nBytesPerLine,nHeight,nWidth,nColorChannelNum,nDotBit,nPassNum` |
| `Roi` | `0,0,W,H` |
| `ePass` | 板卡配置的 pass（如 4/8），不是从 PRN 头取 |
| `bColorInk/bWhiteInk/bOilInk/bSpotInk` | 由板卡通道配置 `stCutInk.nChlIsOpen[0..3]` 决定 |
| `nMultyWhiteInk` 等 | 板卡配置（白墨打印次数） |
| `bRegionalPrint/nPage/nXPage/nYPage/fXSpace/fYSpace` | 常规为 false/1/1/1/0/0 |
| `nPrintColorOrder/nSectionWidth/stMargin/stEclosion/...` | 板卡配置透传 |

打印调用序列（rip-studio H13）：`bpInit()` → `bpOpenAll()` → `bpReadCfgPara()` → `bpPrintSendTask(handle, task)` → 轮询 `bpGetPrintImageStatus()`；暂停 `bpPrintPause`、停止 `bpPrintStop`。
**注意**：`bpPrintSendTask` 只在有板卡在线时才可能返回 `STATUS_OK(0)`；无实机不能验证“发送成功”，只能验证文件格式/头解析。日志里 `readPrnInfo failed` 表示文件根本不是 4 种受支持格式/头不完整（历史上有 3 个失败样本 1783997742676.prn 等）。

---

## 7. 与自研旧原型 `src/rip/prngenerator.cpp` 的逐条对比

旧原型已经抓到大部分要点，但有 3 处会直接导致板卡不认/白墨异常：

| 项 | 旧原型（prngenerator.cpp / riptypes.h） | 实际（本文） | 结论 |
|---|---|---|---|
| 48B 头字段布局 | `uint32 sig,xDPI,yDPI,bpl,height,width; float paperWidth; uint32 colorPlane; uint32 reserved[4]`（riptypes.h `PRN_IMAGE_INFO`） | 同（paperWidth 在偏移 0x18 的 float） | ✅ 正确 |
| `paperWidth` | 写 `0.0f`（`prngenerator.cpp:109,283`） | 必须写 `f32(W/xDPI*0.0254)` | ❌ 修正 |
| `reserved` | `[0]=dotBits, [1]=pass, [2]=vsdMode, [3]=0`（`:112-115`） | 厂商写法 `[0]=2,[1]=pass,[2]=1,[3]=0`；蒙泰写全 0 | ⚠️ 建议改成 `[0]=2,[1]=pass,[2]=1,[3]=0` |
| 数据区排布 | **行交错**（line-interleaved，`:212-247`：`for y: for c: write row`） | 行交错 | ✅ 正确（这一点原型猜对了，不是 plane-major） |
| 平面数/颜色 | 由调用方 `colorPlanes` 决定；`Hello.prn` 是 4 平面（无白） | H13 固定 5 平面 K,C,M,Y,W1 | ❌ H13 必须输出白平面（p4） |
| 平面顺序 | 未定义（调用方给） | K,C,M,Y,W1 | ⚠️ 明确固定 |
| 2bit 打包 | MSB-first，`bitPos=(pxPerByte-1-x%4)*2`（`:144-147`） | 同 | ✅ 正确 |
| 行对齐 | `align4(ceil(W*2/8))`（`:195-197`） | **align8**（蒙泰实测：W=300→80；align4 会得 76） | ⚠️ 改成 8 字节对齐 |
| 文件大小 | header+行交错数据 | `48+H*C*BPL` | ✅ |
| dot 值语义 | 0/1/2/3 四级（DOT_EMPTY/SMALL/MIDDLE/BIG） | 蒙泰确实用 0..3 四级（flat_y 平面出现 1/2/3） | ✅ 语义对；生成端要按 4 级加网 |
| `Hello.prn`（63MB）本身 | 头为 0x5555，但 BPL=6024=W（1 字节/像素）、paperWidth=0，不满足 2bit 公式；`parse_hssf.py selftest` 判 FAIL | 不是可用的 H13 PRN，只能当“头部字段大致长这样”的参考 | ❌ 不可作为格式基准 |

---

## 8. 未解问题 / 待判别实验（如实记录，避免误导）

1. **`b.prn`（magic `0x74667966`，ASCII "fyft"）是什么？**
   * 位置：`...\northPrintSDK\x64\Release\RIP\out\b.prn`（及 `dist\bin\out\b.prn`、`out\test.prn` 同内容，12,298,768B，时间 2026/6/12）。
   * 头：`0x74667966, 360, 1200, BPL=316, H=5560, W=2504, paperWidthFloat=0.17668, C=7, r0=2, 0,0,0`。BPL=316 对应的其实是 **1bit** 宽度 2504（`ceil(2504/8)=313→316`），与 r0=2 矛盾；说明它不是标准 HSSF 语义。
   * 已排除：蒙泰 4 种受支持 PRN 魔数（YCDZ/HSSF/BYHX/AT）里没有它；没有日志/配置/li 表明它被打印过；同目录 `a.prn`（100MB，`0x5555`，720x2160，C=8）是另一次实验（8 通道，非 H13 的 5 通道/720x1080 档）。
   * 判断：这是**用别的 driver/.prs（非 H13 XP600）做 MainTop 输出实验的产物**，不是 H13 板卡格式。判别实验（若需要）：用北印 `BetterPrintAppDemo` 的 `GetPrnFileInfo` 或 `bpGetPrnFileInfo` 读它，应该会落到“generic 0x5555”错误分支；或把它放进北印软件打印，观测是否报格式错误。
2. **白墨 `invaginate/expand` 的像素级规则**：oracle 里 `inputColorEditor W1 full + inkIE invaginate index=4 dots=10` 的白平面 p4 只有 ~0.3% 墨（`h13xp600_flat_black_100_m0_golden.prn`），而不带 inkIE 的 `_w1w2` 变体 p4 满版 100%。白墨生成逻辑的精确语义属色彩/PRS 分析范围（见 prs 文档），PRN 格式层面只需知道 **p4 = White，值 0..3**。
3. **板卡固件是否使用 `nPaperWidth`/`reserved[0]`**：目前只能证明“蒙泰写 0、厂商 TestFile 写 (2,pass,1,0)”两种文件都被北印软件接受。建议 writer 先按厂商写法，再进行实机验证。
4. **实机验收**：本文所有格式结论都能离线验证；但“板卡真正接受我们的 PRN”需要一次实机打印（用北印软件打开/打印我们的 PRN，或 rip-studio `printPrn()`，观察 `bpPrintSendTask` 返回 0 与板卡动作）。测试图建议：纯黑/纯白/青品黄单色块、100x100、mode0（720x720），与 oracle 同名样本对照。

---

## 9. 复现命令与样本清单

```powershell
# 校验一批样本（头/大小公式/推断 dotBits/对齐方式）
& C:\Espressif\tools\python\python.exe D:\work\RIP核心分析\tools\board_tools\parse_hssf.py check `
  D:\work\RIP核心分析\reference\prn_samples\h13xp600_flat_y_100_m0.prn `
  D:\work\RIP核心分析\reference\prn_samples\exp_h13xp600_h13_scale50.prn `
  D:\work\RIP核心分析\reference\prn_samples\h13xp600_cmyk_quad_100_m0.prn `
  D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn `
  D:\Code\kkf\v1.1.2\rip-studio\3rdLib\northPrintSDK\x64\Release\TestFile\xp600_4c\720x720_4C+WO.prn

# 强校验（bpl 公式/严格大小/paperWidth/对齐归类），无 FAIL 即 corpus 自洽
& C:\Espressif\tools\python\python.exe ...\parse_hssf.py selftest ...（见 work/board/validation_report.txt）

# 生成一个最小 H13 样本（300x300, mode0, 白满版），与 oracle scale50 同尺寸：120,048B
& C:\Espressif\tools\python\python.exe ...\parse_hssf.py make --out minimal.prn --width 300 --height 300 --xdpi 720 --ydpi 720 --planes 5 --fill 0,0,0,0,3

# 解码平面并可视化（无板卡时最直观的格式验证）
& C:\Espressif\tools\python\python.exe D:\work\RIP核心分析\tools\board_tools\parse_hssf.py planes `
  D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn --out D:\work\RIP核心分析\work\board\out\gold --scale 8
```
样本：
* 蒙泰+H13 XP600.prs oracle：`D:\work\RIP核心分析\reference\prn_samples\h13xp600_*.prn`（mode0-3、flat/quad/grad/checker/lines/alpha、带/不带 W1）
* 真机历史样本：`D:\Code\kkf\ripstudio\bin\bin\temp\data\1788919812455.prn` + 源图 `...\temp\pic\1788919812307.png`
* 厂商 TestFile：`D:\Code\kkf\v1.1.2\rip-studio\3rdLib\northPrintSDK\x64\Release\TestFile\*.prn`（含 `.prn.bmp` 预览）
* 反例（不要当目标格式）：`...\RIP\out\b.prn`（`0x74667966`）、`...\RIP\out\test.prn`（ESC/P2 `0x1B000000`）、`...\SpecialPRN\SpecialPRN.prn`（BMP）。
