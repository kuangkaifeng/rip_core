# 板卡机（H13 / 北印 BetterPrinter）打印链路全图

> 目标读者：engine-dev（写 HSSF PRN writer / 打印接头）、Lead。
> 配套文档：`docs/prn_board.md`（PRN 字节格式，已定死）、`docs/maintop_api.md`（蒙泰作业协议）、`docs/01_maintop_pipeline.md`。
> 一句话：**H13 链路 = 蒙泰 MainTop RIP（H13 XP600.prs）→ HSSF 0x5555 PRN → 北印 BetterPrinter.dll（bpPrintSendTask）→ 板卡。** 北印 SDK 不 RIP、不转格式；pass/双向/波形/墨序都是板卡侧配置，不在 PRN 里。

---

## 1. 全链路

```
┌────────────────────────────── PC 侧 ──────────────────────────────┐
│                                                                    │
│  图像/画布                                                          │
│    │                                                               │
│    ▼                                                               │
│  蒙泰 RIP（二选一入口）                                              │
│   a) mtrip.dll C API:  MainTopRip(json) → PRN buffer → 落盘 .prn    │
│   b) mtripNet.exe HTTP :8089 / gRPC :8090  (同一引擎，进程隔离)      │
│      输入: json{ doc, prs, modeId, output.file, inputColorEditor,   │
│                inkIE, rotate, scale, margin, view, range }          │
│      引擎配置: H13 XP600.prs (+ .meta/.wpk) + ICC/曲线/加网           │
│    │                                                               │
│    ▼  xxx.prn  (HSSF 0x5555, 48B 头 + 行交错 2bit, K,C,M,Y,W1)      │
│  北印 BetterPrinter.dll                                            │
│    bpInit → bpOpenAll → bpReadCfgPara                               │
│    → bpPrintSendTask(BP_PRINT_TASK{ cImageFilePath=prn,             │
│                                     stPrnInfo=解析PRN头, ePass,...})│
│    → bpGetPrintImageStatus 轮询；bpPrintPause/bpPrintStop           │
│    │                                                               │
└────┼───────────────────────────────────────────────────────────────┘
     ▼  USB / 网口（板卡 IP 见 DeviceConfig.ini [Device] ip=192.168.0.2 等）
  板卡（主板+小车板+喷头）：
    按板卡配置施加 pass/双向/波形/墨序/白墨次数，把 PRN 光栅转成喷头点火数据
```

**北印自己还有一套 RIP 备选**：`BetterRip.dll` 导出 `bpRipStart/bpRipProgress/bpRipResultCode/bpRipStateCode`，`BetterPrintNetObject.h` 的 `bpRipInterface(handle, LP_RipPathInfo, LP_RipParam)`（`ImageRipDef.h`：`nDpiX/nDpiY/nBit/nPass/stWhiteSpot[]/nLightCount/strPrnOrder/RipEngine(Screen/Screen64M/Screen268M)/rtAngle/MirrorMode...`），引擎文件在 `RIP/` 目录（`Rip.dll`+`SendData.dll`+`ImageRead.dll`+`ImageWhite.dll`+`CachePool.dll`+`Config/ICC Profile/Scheme`）。**但 H13 这条实际链路走的是蒙泰**（证据 §2），我们的替代目标是复刻蒙泰输出。

---

## 2. 链路证据

### 2.1 北印官方软件内嵌蒙泰（不是“蒙泰安装版”外部调用）

官方 `InkSonic Control Software.exe` 内字符串（偏移为文件内偏移）：

* `@0x51a638`：`XP600 | I3200 | G5I | byxp6.prs | byxp6.txt | by3200.prs | by3200.txt | byg5i.prs | byg5i.txt | /MT/bin/`
* `@0x51a6xx`：`MainTopRipManager::setHeadType`（源码路径 `f:\localworkspace\betterprinterapp\betterprinterclassic\maintopripmanager.cpp`）
* `@0x51aaa8`：`PATH ...\MT\bin;`、`mtrip.dll`、`MainTopRip`、`MainTopRipCancel`、`MainTopRipReleaseBuffer`、`MainTopRipManager::ansyRunMainTop`、`RIP result error!`、`Output file error!`、`Prs file error!`、`Incorrect dongle status!`
* `@0x5333a8`：UI 文案 `MainTop Rip / Rip Start / Time / Capacity / Length / Print Dpi / Ink / Paper`
* `@0x51a668` 附近还有 head model 表：`I3200/G5I`，每个头型一个 `by*.prs`（**by = 北印** OEM 的蒙泰打印设置文件）

→ 北印软件把蒙泰引擎放在自己的 `MT\bin` 里，按喷头型号选 `byxp6.prs/by3200.prs/byg5i.prs` 调 `MainTopRip`。我们手上的 `H13 XP600.prs` 就是这种 OEM 蒙泰驱动设置包（同目录 `.meta`=driverShowName、`.wpk`=WPKF 辅助数据）。

### 2.2 rip-studio 的现状（要替代的就是这一段）

* `README.md:121-123`：`RipControl → 蒙泰 mtrip.dll → 生成 PRN 文件`；`PrinterControl → 北印 BetterPrinter.dll → 发送到打印机`。
* `src/service/ripService/ripcontrol.cpp`：
  * `:854-861` 旧 H13 分支被注释：原本 `KaartrekenaarRip.json` + `H13 XP600.prs`，现强制 `GemodifiseerdeMasjienRip.json` + `A3-DTF-1390.prs`（所以当前工程实际只跑改装机 ESC/P2；板卡机分支待我们自研 RIP 接管）。
  * `:594-598` `modeId = (whiteChannelCount==1) ? qualityMode*2+1 : qualityMode` —— H13（白通道数 2）modeId=质量档 0..3。
  * `:492-530` 白墨 JSON：`inputColorEditor[{inkName:"W1"/"W2", mode:"full"|"color", invert:false}]` + `inkIE[{mode:"invaginate"|"expand", index:4, dots:[n,n,n,n]}]`，dots=内缩/外扩 mm（0..10）。
  * `:1503-1512` 默认 `m_prsPath = H13 XP600.prs`；`KaartrekenaarRip.json`（bin\bin）为 H13 作业模板（modeId=1、W1 full）。
 * 历史日志（`bin\bin\log.txt`）：`use MainTopRip, JSON size=...` + `file: .../KaartrekenaarRip.json`（H13 模板）+ `PRN write fished: ... (637 bytes)`（小图/异常档）与 `H13Rip.json` 等；后续 `PrinterWorker::doPrint` 对 `temp/data/<epoch>.prn` 逐张打印。
* `src/service/printService/printerControlH13.cpp`（**北印 SDK 对接全部在这里**）：
  * `:626-729` `readPrnInfo()`：读 48B 头，按魔数分派 YCDZ `0x7A646379` / BYHX `0x58485942` / AT `0x4D435441` / 其它按 HSSF `0x5555`（`PRN_IMAGE_INFO`）解析；`nDotBit=0` 时用 BPL/Width 反推。注释写明“完全复制 Demo 的 GetPrnFileInfo”。
  * `:767-865` `buildPrintTask()`：填 `BP_PRINT_TASK`（nPage/nXPage/nYPage=1、Roi=0,0,W,H、从 `bpReadCfgPara` 取墨序/速度/方向/羽化/白墨次数/边距），`ePass` 简化固定 `PRINT_PASS_1`，`cImageFilePath` = PRN 路径。
  * `:1781-1828` `doPrint()`：`buildPrintTask` → `bpPrintSendTask` → 起进度轮询。
  * 其它：`bpCleanStart/bpAddInkStart/bpXMotor*/bpYMotor*/bpZMotor*` 等维护/电机操作（与 RIP 无关）。
* 旧工程/新工程日志中的成功打印（`bpPrintSendTask returned: 0` + `print task sent OK`）大量出现，对应 `temp/data/*.prn`（H13 尺寸如 3570x4878）——证明“蒙泰 PRN 文件 → bpPrintSendTask → 板卡”这条路是可用的。

### 2.3 H13 实际过的 PRN 尺寸

旧工程 `bin\bin\log.txt` 中 H13 打印任务尺寸（`buildPrintTask task: WxH`）绝大多数是 `3570x4878`（720x1080 档）及其倍数/条带（3570x9756、3570x18668……），与蒙泰 modeId=1（720x1080）一致；`1788919812455.prn` 就是该尺寸的真实文件（C=5、KCMYW、W 满版）。这与 `KaartrekenaarRip.json` 模板（H13 XP600.prs + modeId=1 + W1 full）完全吻合。

---

## 3. 需要复刻的参数（按“是否进 PRN”分类）

### 3.1 进 PRN 光栅的参数（RIP 侧，自研 engine 负责）

| 参数 | H13 值/来源 | 说明 |
|---|---|---|
| 分辨率 | mode0 720x720 / mode1 720x1080 / mode2 720x1440 / mode3 720x2160 | `queryMode` + oracle 实测；x 恒 720，y 随质量档 720/1080/1440/2160 |
| 通道/平面数 | **C=5：K,C,M,Y,W1** | `H13 XP600.prs` 固定；见 prn_board §3.3 单色实验 |
| bit 深 | **2bit**（4 级点 0/1/2/3） | 头 reserved[0]=2（或 0+推断）；数据每像素 2bit |
| 图像几何 | `W_out=in_px*xDPI/view_dpi*scale`，`H_out=W_out*yDPI/xDPI` | `KaartrekenaarRip.json`: view=120dpi, scale=100；MainTop 按 view dpi 解释输入像素 |
| 白墨 W1 | `inputColorEditor[mode:full|color]` + `inkIE{mode:invaginate|expand, index:4, dots:[mm]}` | full=全铺白（p4 满版 3）；color=彩区铺白；invaginate/expand=内缩/外扩 mm |
| 色彩管理 | H13 XP600.prs 内嵌 ICC/线性化/加网（colorCorrection=true） | 属 PRS/色彩管线，见 `docs/prs_format.md`、`docs/color_pipeline.md` |
| 分色/加网 | 蒙泰 ScreenProcess/MtColorIO；板卡机同 prs 的 mode 内置 | 板卡机 prs 与 A3 ESC/P2 的 prs 不同 |
| rotate/scale/margin | 作业 JSON 级：`rotate:0/90/180/270`、`scale:[x,y]`、`margin:[l,t,r,b]` | 决定 PRN 内容方向/大小，格式无标记 |
| 墨量限制 | prs 内 inkLimit/linearization | 见 PRS 文档 |

### 3.2 不进 PRN、但打印必须对的板卡参数（打印侧）

| 参数 | H13 值/来源（证据） | 说明 |
|---|---|---|
| PrintType | `Config.ini [print] PrintType=2` | 北印软件打印类型（2=喷墨板卡?） |
| 波形 | `Config.ini [print] WaveHeadTypeID=260, WaveSel=1`；`DeviceConfig.ini [config] waveDir=xp600-4号机-波形 / waveSel0=0/waveSel1=3`；`SoftConfig\InkSonic-H13-F1080-1H.xml`：`sWaveCfgPathName=wave\tx800lin`、`nWaveSel_0/1=0`、`fWaveVoltage_*`；`wave\TX800LIN\PWV.bat` 生成波形 | 板卡点火波形；`H13 XP600.wpk`（WPKF 容器，内嵌 `mtbyorigin.bin`）是蒙泰 OEM 驱动的辅助数据，**不需要**写进 PRN |
| pass | `BP_PRINT_TASK.ePass`：北印官方 H13 安装 `System\Config.ini [task] ePass=4`、`System\DeviceConfig.ini [task] ePass=4`；rip-studio 里打包的是 XP600-4 头机配置（`bin\bin\DeviceConfig.ini [task] ePass=8`，`waveDir=xp600-4号机-波形`）。`CfDpiDef.ini` 给 (xDPI,yDPI)→可选 pass 列表（如 720x720: 4/8；720x1200: 4/8/2…） | pass 是板卡运动/羽化参数，**不在 PRN 头**；蒙泰 PRN 的 reserved 全 0 也说明它不承载 pass |
| 双向/方向 | `BP_PRINT_TASK.isReverse/isHorizontalMirror/isVerticalMirror`、`nXDirMode`（`bpReadCfgPara` 读板卡配置）；`Config.ini [task] isReverse=0,isHorizontalMirror=0,isVerticalMirror=0`；H13 XML `nPrintColorOrder=1` | 镜像/反向由打印任务决定（RIP 输出不镜像） |
| 墨序 | PRN 平面顺序固定 K,C,M,Y,W1；板卡映射 `nColorShowPrn_0..=0,1,2,3,4,5`（ink 索引 0=k,1=C,2=M,3=Y,4=LC,5=LM…8=White）、`nInkCountColor_*=0,1,2,3,8`（第 5 通道计 White）、`stCutInk.nChlIsOpen[0..3]`、`nSpecialPrintMode=1`（单头白彩）、`nPrintColorOrder=1`、`nMultyWhiteInk=1` | 板卡侧按“通道→喷头”映射；PRN 只管平面顺序 |
| 喷头/板卡 | H13 XML：`nHeadCount=1`、`nColorCount=5`、`nHeadType=261`、`nPrintMode=1`（非标打印）、`nSpecialPrintMode=1`、`nXPrintSpeedMode=2`、`nHeadLinkMode=1`、`nSectionWidth=100`；板卡 IP `DeviceConfig.ini [Device] ip=192.168.0.2` | 机型配置，来自北印 `SoftConfig\*.xml` |
| 边距/布局 | `BP_MARGIN_CONFIG`、`nXMarginMode/nYMarginMode`、任务级 fX/FY/FZMargin；rip-studio 目前 margin 全 0 | |
| 羽化/彩条 | `BP_ECLOSION_CONFIG`（pass 羽化/喷头间羽化）、`BP_COLOR_BAR_CONFIG` | 打印质量参数，PRN 无关 |

> **给 engine-dev 的边界**：自研 RIP 只需产出 §3.1 的 HSSF PRN（§prn_board.md §5 契约）；§3.2 是“打印时传给 BetterPrinter / 板卡配置”的参数，不是 PRN 内容。复刻蒙泰 = 复刻 §3.1 的像素结果（分色/ICC/限墨/线性化/加网/白墨/几何），打印链路仍用北印 SDK。

### 3.3 modeId ↔ pass ↔ 波形 的关系（澄清）

* **modeId ↔ 分辨率**：modeId=质量档 → (720,·) 的 yDPI（720/1080/1440/2160）；`queryMode` 已确认，oracle 文件头实测一致。
* **modeId ↔ pass**：无直接耦合。蒙泰 prs 的 mode 里可能带默认 pass，但 PRN 不携带；北印打印用 `BP_PRINT_TASK.ePass`（板卡配置/UI 选择），`CfDpiDef.ini` 约束每个分辨率可选的 pass（例：720x720→4/8）。历史打印日志里 `pass=1` 是 rip-studio 简化写死的，不代表板卡真实 pass。
* **modeId ↔ 波形**：无关。波形由板卡配置决定（`WaveHeadTypeID/WaveSel/waveDir` + `.wpk`/PWV 波形文件），PRN 不携带。

---

## 4. 与 rip-studio 现有 H13 代码的对接点（替换蒙泰时要动哪里）

现状（`src/service/printService/printerControlH13.cpp` + `include/printerControlH13.h`）：

| 位置 | 现状 | 替换蒙泰后的目标 |
|---|---|---|
| `RipControl::doRip`（ripcontrol.cpp:854-861） | 强制 `GemodifiseerdeMasjienRip.json` + `A3-DTF-1390.prs`（ESC/P2），H13 分支注释 | 增加自研 HSSF writer 分支：`H13/modeId→(720,ydpi)`、`C=5 KCMYW`、输出到 `temp/data/<epoch>.prn` |
| PRN 输出 | `MainTopRip` 返回 buffer 写文件 | 自研 engine 按 `prn_board.md §5` 写 48B 头+行交错数据 |
| `PrinterWorker::readPrnInfo`（:626-729） | 读真实 PRN 头（4 格式分派） | 不用改；自研 PRN 头自洽（`nDotBit=2` 或 0） |
| `PrinterWorker::buildPrintTask`（:767-865） | `ePass` 写死 `PRINT_PASS_1`；其余从 `bpReadCfgPara` 取 | 改为按板卡配置/UI 取真实 `ePass`（如 4/8）；`stPrnInfo` 用解析结果 |
| `PrinterWorker::doPrint`（:1781-1828） | `bpPrintSendTask` + 状态轮询 | 不变（链路通用） |
| `PrinterControlH13::printPrn(prnPath)` | 手动打印任意 PRN（QFileDialog） | 保留，用于实机验收自研 PRN |
| `doRip` 的 prs/白墨 JSON | W1/W2 白墨参数经 `inputColorEditor/inkIE` 传给蒙泰 | 自研 engine 内部实现白墨（full/color/invaginate/expand），不再发 JSON |

**最小对接契约**：自研 RIP 产出“北印能发”的 HSSF PRN（`docs/prn_board.md` §5）；打印侧维持 `readPrnInfo → buildPrintTask → bpPrintSendTask` 不变。建议在 `buildPrintTask` 里对自研文件补 `ePass` 与 `stPrnInfo` 校验（`parse_hssf.py check`）。

---

## 5. 无实机验证 + 实机验收方法

### 5.1 无板卡（PC 侧）

1. **格式自检**：`tools/board_tools/parse_hssf.py check <file>`（sig/大小/bpl 公式/dotBits）；`selftest` 额外校验严格大小、paperWidth、BPL 对齐归类（蒙泰=8 字节对齐，北印 TestFile=4 字节对齐，两者读端都接受）。
2. **与 oracle 对拍**：同一输入图、同一 prs/mode 下，自研 PRN 与蒙泰 PRN 的 **头字段应逐项相等**（除数据区；BPL 用 align8 才与蒙泰一致）；数据区可解码对图像（`parse_hssf.py planes`，与源图/蒙泰解码图对比）。
3. **解码正确性**：`parse_hssf.py planes` 出的平面图若与 `TestFile/*.prn.bmp` 或源图对不上，说明行交错/平面序/位序/对齐有错（本文档已给出唯一正确解）。
4. **北印 SDK 读头（可选）**：北印 demo 的 `GetPrnFileInfo` / `bpGetPrnFileInfo` 应返回 OK 且字段与 PRN 头一致。
5. **北印预览工具（可选）**：`PrinterParamConfigTool.exe` / `PrnFilePreview.dll` / `PreviewPrn.dll` 打开 PRN 预览（GUI）。
6. 断言清单见 `docs/prn_board.md` §5 验收 checklist。

### 5.2 实机（最终验收）

1. 用 `PrinterControlH13::printPrn()`（或北印软件“打印 PRN 文件”）打开自研 PRN；
2. 观察：`bpPrintSendTask` 返回 0、板卡状态 `bpGetPrintImageStatus` 进度变化、实际出墨/图案正确（颜色/白墨/位置/无错位条带）；
3. 对照打印：同一图先打蒙泰 PRN 再打自研 PRN，比较图案；
4. 边界样本：纯黑/纯白/单 C,M,Y 色块→ 验证平面序；100x100 小图（mode0）→ 验证对齐/窄幅；100% 白满版→ 验证 p4 白墨；渐变/线条→ 验证 2bit 4 级点。

---

## 6. 与改装机（ESC/P2）路线的差异（避免做错方向）

| 项 | 板卡机（本文） | 改装机（另一路线） |
|---|---|---|
| 机型 | H13/H13D/VF13… | C13B/E13B/F13/L8A（Epson 1390 改装） |
| .prs | `H13 XP600.prs`（北印 OEM 蒙泰驱动） | `A3-DTF-1390.prs` |
| RIP 输出 | **HSSF 0x5555**（48B 头+行交错 2bit 光栅） | **ESC/P2**（EJL/remote 头+命令区+光栅记录） |
| 消费 | 北印 `BetterPrinter.dll` → 板卡（USB/网口） | Windows 打印后台 spooler/RAW 送 Epson 驱动 |
| 关键代码 | `printerControlH13.cpp`、`BetterPrintNetObject.h` | `printerControlC13B.cpp`、`printToWindowsPrinter(OpenPrinter/WritePrinter RAW)` |
| 复刻落点 | 自研 HSSF writer（本任务） | 自研 ESC/P2 生成器（T2） |

> 两者唯一共享的是“蒙泰 RIP 引擎/作业 JSON/PRS”这一层，PRN 层完全不同，不要混用。

---

## 7. 未解之谜 / TODO

1. **`b.prn` magic `0x74667966`** 的来源（不是北印 4 种 PRN 格式之一、无打印记录；详见 `prn_board.md` §8）。判别实验：`GetPrnFileInfo` 读它 / 北印软件打开打印。
2. **白墨 `invaginate/expand` 的像素规则**（PRN 层 p4=White 已确定；内缩/外扩 mm→像素、彩区/满版语义需 prs/色彩分析）。
3. **H13 双白通道（W1/W2）**：rip-studio 认为 H13 有 2 个白通道（`ripcontrol.cpp:492`），但 H13 XP600.prs 的 oracle 输出固定 5 平面（只有 1 个白平面）。H13D/VF13 是否 6 平面待确认（用对应 prs 跑 oracle，看 `nColorPlane`）。
4. **板卡固件对 reserved/paperWidth 的依赖**：两种写法（蒙泰全 0 / 厂商 (2,pass,1,0)）都被北印软件接受；最终以实机打印为准。
5. **pass 与光栅的关系**：需确认板卡 pass 是对成品光栅做行交错（PRN 与 pass 无关），还是 RIP 时就按 pass 做了 dot 分配（若是后者，PRN 生成还需 pass 参数）。判别法：同一图、同 mode、不同 ePass 打印，若只有“条纹/进度”变化而图案不变→PRN 与 pass 无关；若图案点分布变化→需按 pass 生成。建议实机做一次对比。
6. **.wpk 文件用途**：`WPKF` 容器，H13 版内嵌 `mtbyorigin.bin`（A3 版为 `eps1k4origin.bin`），像是喷头/原点辅助数据；对“生成 PRN 给北印发送”不是必需，若要做完整替代蒙泰驱动再深挖。
