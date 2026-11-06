# 05 · 与 rip-studio 的集成方案（用 mtr 替换蒙泰 SDK）

> 目标：让 rip-studio **不改代码或只改 DLL/库引用** 就能用我们的 RIP 生成 `.prn`。
> 前提：我们的引擎先通过 oracle 参考 PRN 的验证（结构/几何；理想情况逐字节一致，允许 TI 时间戳差异）。

## 1. 两种集成方式

### 方式 A：DLL 1:1 替换（推荐）

我们的 `mtr_rip.dll` 导出与蒙泰 `ripModule.h` **完全同签名**的 C API：

```c
const void* MainTopRip(const void *data, size_t *size);
void        MainTopRipCancel();
void        MainTopRipReleaseBuffer(const void *buf);
void        MainTopShutdown();
```

rip-studio 现有代码（`src/service/ripService/ripcontrol.cpp`）已经按此调用：

```cpp
#include "ripModule.h"
MainTopRip(jsonBytes, &size);            // 我们实现：解析 JSON → 生成 PRN
```

替换步骤（生产工程侧，未来执行）：
1. 把 `mtr_rip.dll`（+ Qt6 Core/Gui/lcms2 运行库）放到 `bin\bin\`；
2. 把 `mtrip.lib` 的导入库换成 `mtr_rip.lib`（或用 `LoadLibrary/GetProcAddress` 动态加载，避免改工程）；
3. 工作目录仍设为 `bin\bin`（prs 相对路径解析）；
4. `MainTopShutdown()` 在 worker 线程析构时调用（现有代码已如此）。

优点：rip-studio 的 `RipWorker::doRip` / `buildRipJson` / 进度/取消逻辑全部不用改。

### 方式 B：命令行替换

`mtr_cli.exe rip --job job.json`（接口同 `dist\bin\test.exe`）。
在 `RipWorker` 里把 `MainTopRip(...)` 调用替换为 `QProcess` 调用 `mtr_cli`。
适合先做灰度验证。

## 2. 作业 JSON 兼容性

`buildRipJson()` 产物我们全部解析（`src/core/job_config.cpp`）：

| 字段 | 处理 |
|---|---|
| `command` | 必须 `"rip"`；其它命令返回 `{"result":0}`（`config` 等） |
| `doc.name` | 输入图片（PNG/JPEG/TIFF） |
| `prs` | 决定机型/输出格式/分辨率/通道/ICC/线性化 |
| `modeId` | 打印模式（A3: 0..3 = CMYK/CMYKW1W2 × 720x360/720x720 等，见 `docs/maintop_api.md` §5.1） |
| `rotate` | 0/180（mirror） |
| `scale`/`margin` | 缩放/边距 |
| `color` | 透明处理 |
| `inputColorEditor` | W1/W2 full/color |
| `inkIE` | 白墨内缩/外扩 + dots |
| `output.file.name` | 输出 PRN 路径 |
| `output.file.mode` | 忽略（438） |
| `view` | 忽略（对图片输入无效，已实测） |
| `range` | 忽略（单页） |

## 3. 机型/格式选择

| 机型 | prs | 我们的输出 |
|---|---|---|
| 改装机 A3-DTF-1390（Epson 1390） | `A3-DTF-1390.prs` | ESC/P2（`src/core/encode/escp2_writer`，见 `docs/02_geometry_escp2.md`） |
| 板卡机 H13 等（北印 BetterPrinter） | `H13 XP600.prs` | HSSF 0x5555（`src/core/encode/hssf_writer`，见 `docs/prn_board.md`） |

> 注意：当前 rip-studio 生产代码对所有机型都强制用 `GemodifiseerdeMasjienRip.json + A3-DTF-1390.prs`（H13 分支被注释）。若恢复板卡机分支，我们的引擎同样支持（HSSF）。

## 4. 替换后的数据流

```
rip-studio RipWorker::doRip
  → buildRipJson()（不变）
  → mtr_rip.dll : MainTopRip(json)
       ├─ JobConfig 解析
       ├─ PrsConfig 解析（分辨率/pass/ICC/线性化/加网/白墨/墨序）
       ├─ 图像读取（QImage，PNG/TIFF/JPEG；CMYK TIFF 走 libtiff 扩展）
       ├─ 色彩管线：ICC(RGB→CMYK) → 限墨 → 线性化 → 白墨/专色 → 加网(2bit)
       ├─ 版面布局：内容尺寸/页边距/块推进/重叠带拆分
       └─ 编码：ESC/P2 或 HSSF → 写 output.file.name
  → （不变）PrinterControl 用北印 SDK/Windows Spooler 发送 PRN
```

## 5. 运行依赖与部署

- Qt 6.8.3（Core/Gui）——rip-studio 已自带（bin\bin\Qt6*.dll）；
- lcms2（静态编译进 mtr_rip.dll，无额外依赖）；
- 无需加密锁、无需 mtripSDK/Adobe/driver 目录。

## 6. 验收清单（替换前必须通过）

1. `mtr_cli rip --job <同一个作业 JSON>` 生成的 PRN 与蒙泰 PRN：
   - ESC/P2 头部 91 字节命令区逐字节一致；
   - 块数/推进序列/颜色记录顺序一致；
   - 页面 raster 逐像素差异率 < 1%（halftone 复刻到位后）；
2. 实机打印：A3-DTF-1390（RAW/USB 或 Spooler）正常出图、位置/尺寸正确；
3. 板卡机 H13：生成的 HSSF PRN 能被北印 BetterPrinter.dll 接受并正常打印。


## 7. 资源文件部署（DLL 形态必读）

`mtr_rip.dll` 运行需要三份数据（`build.cmd` 会从 `3rdparty/` 自动复制到 `build/`）：

| 目录 | 内容 | 说明 |
|---|---|---|
| `icc/` | sRGB / CoatedFOGRA39 / SWOP / A3-DTF-1390 输出 ICM / dtf ICM | 颜色转换 |
| `screen/` | `screen_meta.json` + `thr_{C,M,Y,K}.bin`（1024² 加网 tile） | FM 加网复刻 |
| `color/` | `calib_gray.bin`（灰度轴标定 LUT） | RGB→CMYK 数值标定 |

部署：把上述三个目录放到 `mtr_rip.dll` 同目录（或 Qt 宿主 exe 所在目录）即可；
DLL 在首次调用时会自动以自身所在目录作为资源基准。
