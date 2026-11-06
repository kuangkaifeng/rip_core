# 01 · 蒙泰 MainTop RIP 调用链与作业协议

> 状态：初稿（Lead 汇总，protocol-analyst 的 `docs/maintop_api.md` 为最终版）

## 1. 生产调用链（rip-studio，只读参考）

```
QML 打印按钮
  └─ RipControl (主线程门面, include/ripcontrol.h)
       └─ RipWorker::doRip(imagePath, prnOutputPath, colors, mirrored, mode, ...)
            ├─ 选择作业模板：
            │   改装机 / 当前代码实际固定使用：bin/bin/GemodifiseerdeMasjienRip.json (prs=A3-DTF-1390.prs, modeId=2)
            │   板卡机（旧分支，已注释）：bin/bin/KaartrekenaarRip.json (prs=H13 XP600.prs, modeId=1)
            ├─ buildRipJson() → 写 JSON 文件
            ├─ CoInitializeEx(STA) + 切换工作目录到 mtripSDK\dist\bin
            ├─ doSetting(): 两条 config 命令（errorString / color）
            └─ MainTopRip(jsonBuffer) → mtrip.dll
                 └─（转发）→ mtripNet.exe HTTP POST /mtrip/v1/jobs  ← 实际 RIP 引擎
                       ScreenProcess.dll / MtColorIO.dll / mtrip3.dll + dist\Adobe（PS/PDF 解释器）
                       → 输出 .prn（ESC/P2 或 HSSF，取决于 .prs）
```

说明：`MainTopRip` 是 `ripModule.h` 的 C API：

```c
const void* MainTopRip(const void *data, size_t *size);  // data=作业JSON
void MainTopRipCancel();
void MainTopRipReleaseBuffer(const void *buf);
void MainTopShutdown();
```

## 2. mtripNet 服务（oracle）

- 启动：工作目录必须是 `D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin`（依赖同目录 DLL 与 `..\Adobe`、`..\driver`），运行 `mtripNet.exe`，需插入加密锁。
- 启动到就绪约 10–13 秒（日志：`Service HTTP API port 8089` / `Service GRPC API port 8090`）。
- 端点（实测）：
  - `POST /mtrip/v1/jobs`：body = 作业 JSON，返回 `{"result":0}`；
  - `GET /version`、`GET /status`；
  - `POST /cancel`；
  - `GET /jobs/progress`（SSE）。
- 服务串行处理作业；**不要并发 POST**；自定义 `"dpi":{"xdpi":300,"ydpi":300}` 字段曾导致进程内致命错误静默退出（列入禁用字段）。
- 日志：stdout 重定向到 `work/protocol/mtripnet_console.log`。

## 3. 作业 JSON 字段（当前已知）

```json
{
  "command": "rip",
  "doc": { "name": "输入图像路径" },              // PNG/TIFF/JPEG；几何由图像内嵌 DPI 决定
  "prs": "A3-DTF-1390.prs 路径",                 // 决定机型/分辨率/通道数/输出格式
  "modeId": 2,                                   // 打印模式（见 queryMode 表）
  "rotate": 0,                                   // 0 / 180（镜像）；实测镜像用布尔字段 mirror:[true,false]
  "scale": [100, 100],                           // 百分比
  "margin": [0, 0, 0, 0],                        // 左 上 右 下
  "view": { "xdpi": 120, "ydpi": 120 },          // 对图片输入无效（实测）
  "color": { "readTransparency": true, "transparencyToWhite": false },
  "inputColorEditor": [ { "inkName": "W1", "invert": false, "mode": "full" } ],  // full=整幅 / color=仅彩色区域
  "inkIE": [ { "index": 4, "mode": "invaginate", "dots": [10,10,10,10] } ],      // 白墨内外缩(像素)
  "output": { "mode": "file", "file": { "name": "输出.prn", "mode": 438 } },
  "range": [ [1, 1] ]
}
```

## 4. 查询/配置命令（同一入口，`command` 不同）

| command | 作用 | 示例 |
|---|---|---|
| `rip` | 生成 PRN | 主流程 |
| `config` | 设置 errorString / color(embeddedICC/cache/transparency) | ripcontrol.cpp 的 doSetting |
| `queryMode` | 列出 prs 支持的模式（dpi/ink/planes/colorCorrection） | `bin/bin/queryMode.json` |
| `queryFile` | 查询文档文件信息 | `sdk/examples/queryFile.json` |
| `colorCorrection` + `query:["iccPath"]` | 查询模式实际使用的 ICC | `bin/bin/queryIccpath.json` |
| `colorCorrection` + `modify` + `saveAs` | 修改 prs 内 ICC 并另存 | `bin/bin/buildPrs.json` |
| `preview` / `whiteInk` / `inkLimit` / `inputPlugin` | 预览/白墨/限墨/输入插件 | `sdk/examples/*.json` |

## 5. 两种输出格式

| 机型 | prs 示例 | PRN 头 | 说明 |
|---|---|---|---|
| 改装机 A3-DTF-1390（Epson Stylus Photo 1390） | `A3-DTF-1390.prs` | `00 00 00 1B 01 40 45 4A 4C ...`（EJL 1284.4 + ESC/P2） | 详见 `docs/02_geometry_escp2.md` |
| 板卡机 H13（XP600 喷头 + 北印 BetterPrinter 板卡） | `H13 XP600.prs` | `55 55 00 00 ...`（HSSF `PRN_IMAGE_INFO`） | 详见 `docs/prn_board.md` |

## 6. 已知坑

1. `view.xdpi/ydpi` 对图片输入无效（几何由 PNG 内嵌 DPI 决定）。
2. `mirror` 必须发 JSON 布尔数组 `[true,false]`；发 `[1,0]` 会被静默忽略。
3. `inputColorEditor` 新增 W1/W2 只在 prs 模式本身含 W 通道（6 planes）时生效。
4. 自定义 `dpi` 字段会崩 mtripNet（禁用）。
5. `.prs` 中的 `MtDummy.pdv` 是解释器占位，不决定输出格式；输出格式由 prs 的设备/驱动配置决定。
6. 服务崩溃后重启需 ~13s；生产环境不要频繁切换自定义参数。
