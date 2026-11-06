# A3-DTF-1390 白墨/打印流程 oracle 复核（T9-B）

> 目的：用户实机打印彩色照片"颜色发黑发闷 + 横向条纹"，确认 A3 改装机的白墨是否进入 PRN、production 模板 mode2+W1 为何 golden PRN 无白墨记录、缺白底对照片外观的影响。
> 环境：oracle = mtripNet HTTP 8089（A3-DTF-1390.prs），全部串行 POST，result=0；证据 JSON：`work/protocol/evidence/whiteink_a3.json`（26 个作业，含 job/PRN 路径与逐颜色码 ink 计数）。
> 复现：`python work/protocol/exp_whiteink_a3.py` + 下文 transparency 追加实验。

## 0. 结论（先看）

1. **A3 的 mode2（4 色 CMYK，planes=4）绝不输出白墨**：无论 `inputColorEditor` 给 W1/W2 full 还是 color，PRN 里只有 4 个颜色码（0x00/0x04/0x11/0x12），与不加白墨逐字节相同。用户真实作业模板 `GemodifiseerdeMasjienRip.json`（14:32 真机作业：modeId=2 + inputColorEditor W1 full + inkIE invaginate index4）产出的 golden PRN（1,734,682 B）就是 4 色码、**无白墨**；我们的 oracle 重放与它逐字节一致 ⇒ **当前 A3 生产作业实际没有白底**。
2. **6 色模式（mode1 / mode3 = CMYKW1W2，planes=6）可以输出白墨，且与彩色在同一个 PRN 内**：W1=`0x12`、W2=`0x11`；`inputColorEditor W1 full` = 整页全铺（alpha 图实测 359,994 px ≈ 全页 360,000），`W1 color` = 只在非透明/有图区域铺（50% alpha 图 179,709 px）；`inkIE index 4 invaginate` 会收缩 W1（10mm 内缩后仅剩中心 1,156 px）。
3. **白墨是否"另一次作业/另份 PRN"**：rip-studio 当前流程每次打印只发 **一个 rip 作业**（doRip→buildRipJson→MainTopRip 一次），白墨只能随同一 PRN 输出；代码里没有第二道白墨 pass 的证据。之前 golden 无白墨不是"分开的第二个 PRN"，而是 **modeId=2 导致白墨被静默丢弃**。
4. 当前源码 `ripcontrol.cpp`（492–598 行）本应为单白墨通道机型选 `modeId = qualityMode*2+1`（即 1/3/5/7，6 色模式）并组 `inputColorEditor W1`——**只有落到 6 色模式，白墨才会进 PRN**；捕获的真机作业是 modeId=2，说明运行路径/设置落到了 4 色模式（或白墨未启用）。**关键不变量：modeId=2 ⇒ 白底必然缺失**。（建议 app 侧核对白墨开关 → modeId 映射。）
5. 用户"颜色发黑发闷"的候选原因：**DTF 缺白底**——CMYK 墨是半透明的，没有 white underbase 时深色承印物/膜会透出，颜色整体变暗、发闷、彩度下降；这与横向条纹是两个独立问题（条纹已归因 DPI/几何对齐）。若目标介质是深色布料，缺白底足以造成该现象。

## 1. 颜色码映射（按模式不同，解码器必须区分！）

| 模式 | 记录数 | K | C | M | Y | W1 | W2 |
|---|---|---|---|---|---|---|---|
| mode0/2（4 色） | 4 | `0x04` | `0x00` | `0x12` | `0x11` | — | — |
| mode1/3（6 色） | 6 | `0x00` | `0x02` | `0x01` | `0x04` | **`0x12`** | **`0x11`** |

依据：mode3 下 CMYK 单通道 TIFF 探针（`cmyk_probe_C/M/Y/K128_64.tif`）分别只有 0x02/0x01/0x04/0x00 有 ink；
mode3 + `inputColorEditor W1 full` 只多出 0x12 满页；+ `W2 full` 只多出 0x11 满页。
（注意与 mode2 的映射不同：mode2 是 K=0x04、C=0x00、M=0x12、Y=0x11。）

## 2. 实验矩阵（A3-DTF-1390，`inputColorEditor`/`whiteInk` 与模式的关系）

图片：`flat_black_100.png`（纯黑满版）、`alpha_checker_100.png`（RGBA，50% 透明棋盘）、`cmyk_quad_100.png`（C/M/Y/K 四象限 RGB）。
`ink` 数是 PRN 解码后该颜色码 2-bit 非零点数；页面全幅 = 360,000（mode2/m3 100px 图）、180,000（mode1）。

| 作业 | 模式 | 白墨 API | PRN B | 有 ink 的颜色码（ink 数） | 说明 |
|---|---|---|---|---|---|
| m2_iceW1full_black | 2 | ICE W1 full | 321,592 | 0x00:360000 0x04:359994 0x11:360000 0x12:359992 | **无白墨通道**（仅 CMYK 4 码） |
| m2_iceW1color_alpha | 2 | ICE W1 color | 134,505 | 0x11:179712 0x12:179707 | 同上，W1 被忽略 |
| m2_golden_quad | 2 | ICE W1 full+inkIE | 244,131 | 0x00:241911 0x04:89997 0x11:241732 0x12:179995 | 与 mode2 base 完全相同（ICE/inkIE 无效） |
| m2_whiteInk_full_quad | 2 | legacy `whiteInk:full` | 274,262 | 0x00:179995 0x02:89997 0x04:241911 0x11:**360000** 0x12:241732 | 旧接口可在 **mode2** 追加白墨记录（整页 360k，色码映射随墨数变化） |
| m3_base_quad | 3 | 无 | 295,941 | 0x00:89997 0x01:179995 0x02:241911 0x04:241732 | 6 色模式，白码 0x11/0x12 空 |
| m3_golden_quad | 3 | ICE W1 full+inkIE(10mm) | 296,214 | 同上 + **0x12:1156** | W1 生效并被 inkIE 内缩到中心 1,156 px |
| m3_iceW1full_black | 3 | ICE W1 full | 398,353 | 0x00:359994 0x01:359992 0x02:360000 0x04:360000 **0x12:359994** | W1 整页全铺 |
| m3_iceW2full_black | 3 | ICE W2 full | 398,539 | 4 色码满页 + **0x11:359994** | W2=`0x11` |
| m1_iceW1full_black | 1 | ICE W1 full | 244,150 | 4 色码 180,000 + **0x12:179997** | 720×360 模式同样支持白墨 |
| m3_base_C/M/Y/K128 | 3 | 无 | ~75,034 | 分别只有 0x02/0x01/0x04/0x00 | 6 色模式 CMYK 码映射 |
| m1_base_C/M/Y/K128 | 1 | 无 | ~41,200 | 分别只有 0x02/0x01/0x04/0x00 | 同 mode3 |

**transparency（全局 `config color`，因为作业内 `color` 字段被忽略；实验后已恢复 rt=0/tw=0）**

| 配置 | 作业 | W1 码 0x12 ink | 结论 |
|---|---|---|---|
| readTransparency=true | m3 + ICE W1 **full**（alpha 50%） | **359,994**（整页） | full = 全铺（不看透明） |
| readTransparency=true | m3 + ICE W1 **color**（alpha 50%） | **179,709**（非透明半页） | color = 只在非透明区域铺 |
| readTransparency=true | m3 base（无 ICE） | 0 | 不会自动产生白墨 |
| readTransparency=true | m2 + ICE W1 full | 0（无 0x12/0x01 码） | mode2 一律忽略 |
| readTransparency=false | m3 + ICE W1 full/color | 359,994 / 359,994 | 不读透明时整图按不透明处理，full==color |
| readTransparency+transparencyToWhite=true | m3/m2 base（无 ICE） | 0 | `transparencyToWhite` 单独不会新增白通道 |

## 3. 为什么 golden PRN 没有白墨记录

真机作业 JSON（`bin/bin/GemodifiseerdeMasjienRip.json`，2026-11-06 14:32，模式/参数与用户 golden 对一致）：

```json
{ "command":"rip", "modeId":2, "prs":"A3-DTF-1390.prs",
  "inputColorEditor":[{"inkName":"W1","invert":false,"mode":"full"}],
  "inkIE":[{"mode":"invaginate","index":4,"dots":[10,10,10,10]}],
  "color":{"readTransparency":true,"transparencyToWhite":false} }
```

* `modeId=2` 在 queryMode 中 = `v720x720dpi / CMYK / planes=4`，没有 W1/W2 输出槽；
* 实测该 JSON 逐字节重放（`golden_repro_1793946733280.prn`，1,734,682 B）与厂商 golden 一致，**只有 4 个颜色码**（0x00/0x04/0x11/0x12）；
* 因此 `inputColorEditor W1` 被驱动静默丢弃；`inkIE index4` 在 4 色模式下同样无对象可作用。
* 6 色模式（1/3/5/7）下同样的 `inputColorEditor W1` 才会生成白墨平面（见 §2）。
* 当前源码 `ripcontrol.cpp` 会为单白墨通道机型选 `modeId = qualityMode*2+1`（1/3/5/7）——说明**白墨能否打印取决于实际运行时的 modeId / 白墨开关；捕获的作业是 mode2，所以没有白底**（需 app 侧确认白墨启用状态与 mode 选择逻辑，属于前端/配置问题，不是蒙泰 RIP 故障）。

## 4. 白墨对照片打印外观的影响（"发黑发闷"候选原因）

* DTF/膜转印工艺中 CMYK 墨层是半透明的。**没有 white underbase** 时，深色承印物（深色布料）或膜的底色会透过墨层，使整体亮度下降、饱和度变低，观感就是"颜色发黑、发闷、脏"；白色区域也无法呈现白色。
* 若印在白膜/浅色介质上，缺白底的影响较小（这也是为什么这类问题常在深色布料上被报告）。
* 横向条纹与白墨无关：那是 PRN 几何/DPI（无有效 DPI 的 JPEG 按 72dpi）与 weave 对齐问题；Lead 已修 DPI 语义，两者需分别验证。
* 其他可能叠加因素：若打印流程用了 6 色模式但白墨量参数（inputColorEditor full/color + inkIE 内缩 10mm）与实际图像透明度不匹配，也会导致白墨区域错误（多为白边/漏白，而非整体发闷）。

## 5. 修复/验证建议（给 Lead/引擎）

1. **先确认白墨是否被启用/模式是否正确**：A3 生产必须落到 `modeId ∈ {1,3,5,7}`（qualityMode*2+1）且带 `inputColorEditor W1 full|color`；若仍用 modeId=2，则白墨必然为 0（本次实验已证）。
2. 若机器/流程确实需要两次打印（先白后彩），则需另外生成一份只含白墨的 PRN（同一 6 色模式下把 CMYK 置 0、W1 全铺），并在打印端分两次发送——当前 rip-studio 代码没有这条路径，需要新增。
3. 建议用本目录实验做 sanity：mode3 + `W1 color` 用于透明图（白墨只在图像区域），不透明照片通常用 `W1 full` + 合适的 inkIE（内缩/外扩），再用实机确认白墨层。
4. 白墨相关 PRN 体积与 RIP 时间会明显上升（6 色 6816×6816 量级 PRN 会大数倍），打印耗时/内存需评估。

## 6. 证据文件

* `work/protocol/evidence/whiteink_a3.json`：26 个作业（含失败=0）、每个 PRN 的颜色码 ink 计数、job/prn 路径；
* `reference/prn_samples/print_debug_white_*.prn`、`reference/jobs/print_debug_white_*.json`；
* 生产模板与 golden：`bin/bin/GemodifiseerdeMasjienRip.json`、`reference/prn_samples/golden_repro_1793946733280.prn`；
* 源码只读参考：`src/service/ripService/ripcontrol.cpp:489-598`（whiteChannelCount / modeId 公式）、`:860`（模板路径）。
