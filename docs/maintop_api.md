# 蒙泰 MainTop RIP 模块 API 与 mtripNet 作业协议（含 oracle 复现手册）

> 版本/环境：mtrip 模块 **2.55.0**（speciality=`changzhuo`），mtripNet HTTP 服务 **v1.6.0**
> 观测时间：2026-11-06，主机 Windows 10 x64，加密锁在线（SN `A5103200002`）。
> 材料来源：`D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\`（只读）的 SDK 文档
> `sdk\doc\maintop-rip-module-v2.html`（version 2.55.0, 2026.6.2 by 姚诚成）、
> `sdk\examples\test.cpp`、`sdk\include\ripModule.h`、`dist\bin\mtripNet.json`、
> rip-studio 生产代码 `src\service\ripService\ripcontrol.cpp`，以及本文档作者的
> **实测证据**（全部落盘于 `work\protocol\evidence\`、`reference\`）。
>
> 结论先行：**HTTP oracle 已跑通，并与 rip-studio 原生生成逐字节等价**。用生产作业
> `bin\bin\GemodifiseerdeMasjienRip.json` 原样重放（仅改输出路径），得到 1,734,682 B
> 的 PRN，与厂商金样本 `bin\bin\temp\data\1793946733280.prn` 除 EJL 头 TI 时间戳 7 字节外
> **逐字节相同**（见 §9.2）。A3-DTF-1390（改装机）输出 ESC/P2；H13 XP600（板卡机）输出
> HSSF `0x5555`。

---

## 0. 名词与文件位置

| 项 | 值 |
|---|---|
| SDK 根 | `D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK` |
| C 头文件 | `sdk\include\ripModule.h` |
| 导入库 (MSVC x64) | `sdk\lib\Windows\X64\mtrip.lib` |
| 运行时 DLL/EXE | `dist\bin\mtrip.dll`、`mtrip3.dll`、`mtripNet.exe`、`mtripNetProxy.dll`、`mtripNetJobProgress.dll`、`ScreenProcess.dll`、`MtColorIO.dll`、`epspass.dll`、`mtpdf.dll`、`mtpack.dll`、`lcms2.dll` 等 |
| 服务配置 | `dist\bin\mtripNet.json` |
| 依赖目录 | `dist\Adobe\`（PDF/PS 解释器）、`dist\driver\`（驱动包） |
| 示例 | `sdk\examples\test.cpp`、`test.exe`、`rip.json`、`whiteInk.json`、`preview.json`、`queryFile.json`、`queryMode.json`、`inputPlugin.json`、`inkLimit.json`、`*.prs` |
| 本机运行实例 | `dist\bin\mtripNet.exe`（PID 会变），监听 8089/8090；CWD=**dist\bin**（关键，决定相对路径解析） |
| 本次 oracle 工具 | `tools\oracle\mtrip_oracle.py` 等（见 §9） |
| 参考语料 | `reference\prn_samples\`、`reference\jobs\`、`reference\inputs\` |

---

## 1. MainTopRip C API

### 1.1 导出函数（`ripModule.h`）

```c
const void* MainTopRip(const void *data, size_t *size);   // 执行一条 JSON 命令
void        MainTopRipCancel();                          // 取消正在执行的操作
void        MainTopRipReleaseBuffer(const void *buf);    // 释放 MainTopRip 返回的 buffer
void        MainTopShutdown();                           // 进程退出前清理
```

语义（文档 §1 + 实测）：

* `data`：UTF-8 编码、**无 BOM** 的 JSON 字符串（命令 + 参数）。
* `size`：入参=JSON 字节数；出参=响应字节数；返回指针为响应 JSON（UTF-8）。
* 返回值非 `nullptr` 且 `size>0` 时必须调用 `MainTopRipReleaseBuffer(ret)` 释放。
* 同步阻塞：`rip` 命令在输出完毕或被中断后才返回（实测一页 100×100 图约 0.04–1.7 s，
  视 mode/分辨率/缓存而定）。
* `MainTopRipCancel()` 阻塞到操作实际被取消后返回（文档 §1）。
* `MainTopShutdown()` 之后不得再调用任何 API。
* 错误情况：函数仍返回 JSON，用 `result` 字段表示返回码（见 §8），
  配置 `config/errorString` 后附带 `error`/`errorString` 文本。

### 1.2 最小调用流程（`test.cpp` 的行为，可复现）

```cpp
readFile("rip.json")                       // 读 UTF-8 JSON（缓冲上限 1 MiB，足够）
MainTopRip(config_errorString_setting_1)   // 先开错误文本（可选）
MainTopRip(jobJson, &size)                 // 真正执行
MainTopRipReleaseBuffer(ret)
MainTopShutdown()
```

命令行版：`dist\bin\test.exe <jsonFile>`；**工作目录必须是 `dist\bin`**（依赖 DLL、
相对 prs/ICC 路径都在此解析），可用 `cd /d ...\dist\bin && test.exe D:\path\job.json`。
写输出文件请给 `output.file.name` 绝对路径，切勿在只读生产目录落文件。

### 1.3 mtripNetProxy（文档 §4.2）

`mtripNetProxy.dll` 用 HTTP/gRPC 连接 mtripNet，接口与 mtrip 相同，另有：

```c
typedef void (*progressProc)(MainTopJobProgress *p);
void MainTopSetHostPort(const char *hostName, int port, int protocol); // protocol: 0=HTTP, 1=GRPC
int  MainTopSetJobProgressCallback(progressProc callback);             // 0=失败
```

默认 host=`localhost`, port=`8089`, HTTP。开发期可把 `mtripNetProxy.dll` 改名 `mtrip.dll`
以在调试器下运行（原 mtrip.dll 禁调试）。

---

## 2. mtripNet 服务（HTTP 8089 / gRPC 8090）

### 2.1 启动与配置

`dist\bin\mtripNet.json`（本次实际文件）：

```json
{
  "service": {
    "http": { "active": true, "port": 8089 },
    "grpc": { "active": true, "port": 8090 }
  },
  "netjob": { "cache": "./cache" },
  "mtripConfig": [
    { "command": "config", "type": "errorString", "setting": 0 }
  ]
}
```

| 字段 | 说明（文档 §4.1） |
|---|---|
| `service.http.active/port` | 是否启用 HTTP / 端口 |
| `service.grpc.active/port` | 是否启用 gRPC / 端口 |
| `netjob.cache` | 远程作业（§2.5）本地缓冲目录 |
| `mtripConfig` | 启动时依次执行的 config 命令数组；**不打印成功消息**，依赖返回值的配置勿放这里 |

实测：启动后约 **10–13 s** 才就绪（端口监听 ≠ 可用；就绪后 `/version` 立即响应）。
控制台日志（Lead 重定向于 `work/protocol/mtripnet_console.log`）示例：

```
2026-11-06 14:56:33 INFO  MainTop mtrip net interface v1.6.0
2026-11-06 14:56:43 INFO  Register job progress plugin successfully
2026-11-06 14:56:43 INFO  Start to process 1 mtrip config items
2026-11-06 14:56:43 INFO  Service HTTP API port 8089
2026-11-06 14:56:43 INFO  Service GRPC API port 8090
2026-11-06 14:57:41 [HTTP] |  200 |      1.0563ms |  127.0.0.1 | GET  "/mtrip/v1/version"
2026-11-06 14:57:50 [HTTP] |  200 |    1.2431929s |  127.0.0.1 | POST "/mtrip/v1/jobs"
```

> 注意 `mtripConfig` 只在启动时执行，且当前文件里 `errorString.setting=0`（关闭错误文本）。
> 要拿到可读错误必须**进程内**再 POST 一条 `config/errorString`（见 §4.1）。

### 2.2 HTTP 端点（文档 §4.1.1 + 实测）

| Endpoint | 方法 | 说明 | 实测 |
|---|---|---|---|
| `/mtrip/v1/jobs` | POST | 等价 `MainTopRip`：body 就是作业 JSON，响应 JSON | ✅ 阻塞到 RIP 完成后返回 |
| `/mtrip/v1/cancel` | POST | 等价 `MainTopRipCancel`（**全局取消当前作业**，body 可为空，无 ids 参数） | ✅ 返回 `{"result":0}` |
| `/mtrip/v1/version` | GET | 等价 `query.version` 响应 | ✅ |
| `/mtrip/v1/status` | GET | 等价 `query.info` 响应 | ✅ |
| `/mtrip/v1/jobs/progress` | GET | 作业进度 **SSE 流**，每行 `data: <JSON>` | ✅ 见 §7 |

请求细节（实测）：

* Header：`Content-Type: application/json;charset=utf-8`（缺省也能工作，但建议带上）。
* Body：UTF-8 JSON，**字段与 C API 完全一致**；`prs`、`doc.name`、`output.file.name`
  可以是相对 mtripNet CWD 的路径（如 `./A3-DTF-1390.prs`）或绝对路径。
* 响应：HTTP 状态码恒为 **200**（包括业务错误）；业务结果看 JSON `result`。
* 响应 JSON 为 UTF-8（中文 `error` 文本正常 UTF-8，无 BOM）。
* 非法 JSON / 未知命令返回 `{"result":2,...}` 或 `{"result":9,...}`（见 §8）。
* 服务端 HTTP 访问日志会打印到控制台（method/路径/耗时/状态），可用于证明作业确实经过 mtripNet。

**cURL 示例（与 SDK 文档截图一致，实测成功）**

```bat
curl -H "Content-Type: application/json;charset=utf-8" --data-binary "@./rip.json" ^
     http://localhost:8089/mtrip/v1/jobs
```

```json
{ "result": 0 }
```

SSE 示例（文档截图 + 本机实测一致）：

```bat
curl -N http://127.0.0.1:8089/mtrip/v1/jobs/progress
data: {"jobID":1,"state":1}
data: {"jobID":1,"state":2,"process":{"page":0,"progress":0}}
data: {"jobID":1,"state":2,"process":{"page":0,"progress":5000}}
data: {"jobID":1,"state":2,"process":{"page":0,"progress":10000}}
data: {"jobID":1,"state":3,"end":{"end":1793947716}}
```

### 2.3 gRPC（文档 §4.1.2）

`mtripNet` 的 proto：

```proto
syntax = "proto3";
package riprpc;
service Mtrip {
  rpc MaintopRip(MaintopRipRequest) returns (MaintopRipResponse) {}
  rpc MaintopRipCancel(MaintopRipCancelRequest) returns (MaintopRipCancelResponse) {}
  rpc MaintopRipJobProgress(MaintopRipJobProgressRequest) returns (stream MaintopRipJobProgressReponse) {}
}
message MaintopRipRequest { bytes data = 1; }
message MaintopRipResponse { bytes response = 1; string error = 2; }
message MaintopRipCancelRequest {}
message MaintopRipCancelResponse { string error = 1; }
message MaintopRipJobProgressRequest {}
message MaintopRipJobProgressReponse { bytes data = 1; }
```

* `MaintopRipRequest.data` = 作业 JSON；`response` = 响应 JSON。
* `MaintopRipJobProgressReponse.data` = 进度 JSON：`jobID`、`state`、`process.page`、
  `process.progress`（万分比）、`end.end`（unix UTC 秒）。
* 端口 8090；本次分析未使用 gRPC（HTTP 已满足需求），需要时可用同一 JSON 直接调。

### 2.4 远程作业（文档 §4.1.3，mtripNet ≥ v1.1.0）

mtripNet 支持把 `doc` 扩展为网络文件，下载到 `netjob.cache` 后再 RIP，结束后删除缓冲：

| 协议 | doc 扩展 | 关键字段 |
|---|---|---|
| HTTP | `doc.net.http` | `uri`（`doc.name` 失效；未给 `doc.type` 时默认 `auto`） |
| FTP | `doc.net.ftp` | `address`(含 port)、`user`、`password`、`file` |
| SSH | `doc.net.ssh` | `address`、`hostKey`(可缺省)、`user`、`password` 或 `keyFile`、`file` |

（本次未实测远程作业，按文档记录。）

### 2.5 并发/实例限制（文档 §1.2 + 实测约束）

* **PDF/PS/EPS 共用一个解释器实例**：前一作业扫描/RIP 未完成时，后续 PDF 作业返回 `busy`（返回码 8）。
* **图片格式输入**：解析器按作业独立，支持多实例（文档），但这不等于允许无限并发。
* 文档 §1.4：进度通知不保证连续，可能从 5% 直接跳到 99%。
* 本次 oracle 始终**串行** POST（团队约定）；未做并发压测，生产集成建议也先串行 + 单实例。

---

## 3. 作业 JSON schema（`command: "rip"`）

> 来源：文档 §2.3 全字段表 + rip-studio `ripcontrol.cpp` 实际生成 + 本机实测。
> 标 ⚠️ 为实测异常/坑，标 ✅ 为已实测可用，标 ❓ 为文档有但本次未验证。

### 3.1 顶层字段

| 字段 | 类型 | 最低版本 | 实测 | 说明 |
|---|---|---|---|---|
| `command` | string | — | ✅ | 固定 `"rip"` |
| `input` | input | — | ❓ | 输入方式（见 3.2）；与旧式顶层 `doc` 二选一 |
| `doc` | doc / doc[] | — | ✅ | 图片/PDF 输入；也是 input 的快捷写法（文档 §2.3 末：doc 型输入可把 doc 直接写顶级） |
| `prs` | string | — | ✅ | .prs 绝对路径，或相对 mtripNet CWD（=dist\bin）的路径 |
| `modeId` | int | — | ✅ | `queryMode` 返回的 `modes[].id`；无效值 → result 2 |
| `range` | int[2][] | — | ✅ | 页码范围，pdf/ps 有效；图片恒第一页，可缺省 |
| `output` | output | — | ✅ | 输出方式（见 3.6）；`file`/`raw`/`plugin`/`pageFile` 顺序取第一个有效 |
| `scale` | float / float[2] | — | ✅ | 百分比，`100`=原大；`[sx,sy]` 可各向异性；缺省 `[100,100]` |
| `margin` | float[4] | — | ✅ | 左/上/右/下，**毫米**；纸张四周额外留白；缺省全 0 |
| `rotate` | float | v2.7.0 | ✅ | 逆时针旋转角度；0/90/180/270 实测生效 |
| `mirror` | bool[2] | v2.7.0 | ✅⚠️ | `[水平,垂直]` 是否镜像；**必须 JSON 布尔**，传 `[1,0]` 被静默忽略（实测） |
| `view` | inputView | — | ⚠️ | 输入视口/dpi；**对图片输入完全无效**（实测，见 §10.3） |
| `id` | int | v1.8.0 | ✅ | 作业 id（1..2147483647），用于进度/查询；0 或缺省=不用进度 |
| `dpi` | customDpi | v2.18.0 | ❌**致命** | 自定义精度；**本机 mtripNet 2.55 实测会进程内致命错误静默退出**（§10.1） |
| `color` | — | — | ⚠️ | 文档 **rip 表中无此字段**，但 rip-studio 会带 `{readTransparency,transparencyToWhite}`；实测不报错，效果与全局 `config/color` 混淆（§10.5） |
| `whiteInk` | whiteInkChannel[] | v2.4.0 | ✅ | 挂网后**额外添加**白墨/专色通道（§3.7，实测可用） |
| `inputColorEditor` | inputColorEditor[] | v2.14.0 | ✅⚠️ | 校色前添加专色通道；**只在 prs 模式本身拥有该墨通道时才进 PRN**（§10.4） |
| `inkIE` | inkIE[] | v2.22.0 | ✅⚠️ | 通道内缩/外扩；index 指“驱动+inkLimit 定义的墨序”，**对 inputColorEditor 新增通道无效**（实测 mode2 index4 无效果） |
| `inkLimit` | inkLimitChannel[] | v2.12.0 | ❓ | 修改/新增通道的 maxInk、gamma、linear[256] |
| `extraMap` | extraMapChannel[] | v2.11.0 | ❓ | 挂网前新增额外通道（旧接口，建议用 inputColorEditor） |
| `maxInk` | float[] | v2.6.0 | ❓ | 各通道最大墨量 [0,1]（v2.12 起建议用 inkLimit） |
| `inputExtraColorNameMap` | string[] | v2.6.0 | ❓ | 输入 extra 通道（spot/alpha）→ 墨水名映射，如 `["W1","W2"]` |
| `contrastBrightness` | {alpha,beta} | v2.17.0 | ❓ | 亮度/对比度，(0,+∞)，1.0 不变 |
| `curve` | curve[] | v2.17.0 | ❓ | 通道 gamma/linear 曲线（256 元素） |
| `channelCopy` | channelCopy[] | v2.36.0 | ❓ | 通道复制（可改墨序） |
| `combines` | combine[] | v2.44.0 | ❓ | 通道按位合并 and/or/not |
| `density` | colorDensity[] | v1.17.0 | ❓ | 区域浓度调整（C/M/Y/K/LC/LM/… by y 范围，毫米） |
| `contone` | contoneImage | v1.17.0 | ❓ | 输出连续调 tiff/bigtiff（8/16bit），非 PRN；不支持 margin |
| `clip` | ripClip | v1.21.0 | ❓ | 裁切区域 mm（left/top/right/bottom） |
| `colored` | bool | v2.26.0 | ❓ | 输入已完成颜色处理，无需再校色 |
| `mtcount` | bool | v2.38.0 | ❌ | 统计半色调点类型，响应加 `mtcount`；**本机驱动实测拒绝**：带此字段立即返回 `{"result":1,"error":"用户取消"}`（0.02s，不生成 PRN），不可用来取点型统计（改用解码 PRN 的 2-bit 值，见 §12） |
| `linePlugin` | {id,param} | v2.52.0 | ❓ | 挂网后/输出前按行处理插件 |

### 3.2 input / doc 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `input.doc` | doc | 文件输入（可 doc 数组=多文件，此时必须给 `view`，且不支持 pdf/ps/eps） |
| `input.plugin` | {lib,param} | 输入插件 |
| `input.imagePlugin` | {id,param} | 图像输入插件（此时 `view` 无效） |
| `input.autoLayout` | autoLayoutJob[] + paper/intervalX/intervalY/allowFlip/algorithm | 自动排版（v2.41.0，本次未验证） |
| `doc.name` | string | 文件名（含路径）；图片支持 bmp/jpg/png/tif/psd/psb/webp，文档另有 ps/eps/pdf |
| `doc.password` | string | PDF 密码 |
| `doc.type` | string | `auto`/`pdf`/`eps`/`ps`/`tif`/`jpg`/`bmp`/`psd`/`psb`/`png`/`webp`；缺省按扩展名 |
| `doc.colored` | bool | 输入已颜色处理（仅图片格式） |
| `doc.imageBufferSize` | int | 读缓存，默认 4 MiB（本次实测 1 GiB 也正常） |
| `doc.transform` | {a,b,c,d,tx,ty} | 仿射变换 `x'=ax+cy+tx, y'=bx+dy+ty`（v2.24.0） |
| `doc.inputExtraColorNameMap` | string[] | 多文件模式下额外通道映射 |
| `doc.inputColorEditor` | inputColorEditor[] | 多文件模式按文件定义 |
| `doc.contrastBrightness` / `doc.curve` | — | 同上，多文件模式按文件定义 |
| `doc.transformBufferSize` | int | 变换缓存，默认 4 MiB |

**inputView**：`left/top/right/bottom`（取整、可为负）、`xdpi/ydpi`（浮点）。
实测命令虽然接受，但对图片输入**不改变输出**（§10.3）。

### 3.3 output

| 字段 | 类型 | 说明 |
|---|---|---|
| `output.file.name` | string | 输出文件名（**绝对路径更安全**，可含中文，实测 OK） |
| `output.file.mode` | int | Windows 下被忽略；rip-studio/SDK 示例惯用 `438` |
| `output.raw.ip/port/timeout` | string/int/int | 网络 raw 输出，timeout 毫秒默认 1050 |
| `output.plugin.lib/id/param` | string/int/string | 输出插件（每次输出重新加载；v1.12+ 可先 regPlugin 得 id） |
| `output.pageFile.name/mode` | string/int | 分页输出，实际文件名后自动附加 `-n` |

实测：`output.mode` 可省略；`file.mode=438` 与省略结果一致（Windows 忽略）。

### 3.4 scale / margin / rotate / mirror（实测行为）

* `scale`：`[50,50]` → 输出块数减半级别（blocks 16→12），`[200,200]` → blocks 24；
  各向异性 `[100,50]`/`[50,100]` 正常。
* `margin`：`[5,10,15,20]`（mm）→ PRN 尺寸/块位置变化（A3 mode2 cmyk_quad：244,131→256,737 B，blocks 仍 16，advance 79 重复）。
* `rotate`：90/180/270 都改变光栅内容（与基准逐字节不同），4 色覆盖率不变；
  `rotate=180` 与 `mirror=[true,true]` 输出**完全相同**（均为 242,602 B，逐字节一致）
  —— 可据此判定 180° 旋转=水平+垂直镜像。
* `mirror`：必须是 `[true,false]`/`[false,true]`/`[true,true]`；传 `[1,0]` 等整数 **静默忽略**
  （与基准逐字节相同）。

### 3.5 dpi（customDpi，v2.18.0）—— ❌ 本机致命

```json
"dpi": { "xdpi": 300, "ydpi": 300 }
```

字段定义：`xdpi/ydpi`（浮点可缺省，默认用驱动值）、`level`（2/3/4，输出数据级别）。
**实测：A3 mode2 带上该字段后，mtripNet 2.55 进程创建 0 字节输出文件后静默退出**
（连接被重置、无 Application Error/WER 事件、进程消失）。列入“致命坑”，
生产禁用；本次仅保留一条复测记录（§10.1）。⚠️ 未在 H13 上验证，同样不要用。

### 3.6 whiteInk（白墨通道，v2.4.0，实测可用）

```json
"whiteInk": [ { "mode": "full", "density": "normal" } ]
```

| 字段 | 值 | 说明 |
|---|---|---|
| `mode` | `none`/`full`/`color`/`seperate`/`spot` | none 忽略；full 全范围出墨；color 有墨处出白（填充底色）；seperate 反铺（无墨处出白）；spot 按 `spotName` 专色 |
| `spotName` | string | spot 模式的专色名（如 "W1"） |
| `density` | `normal`/`less`/`small`/`more`/`most`/`ownset` | 白墨墨量；ownset 用 `densityValue` |
| `densityValue` | int [0,100] | ownset 时的墨量 |

实测（A3 mode2、alpha_checker_100、全局 readTransparency=true，颜色码覆盖率为 T2 解析器统计）：

| 参数 | PRN B | 颜色码覆盖率 |
|---|---|---|
| full/normal | 164,636 | `0x00:0.205 0x11:0.411 0x12:0.205` |
| color/normal | 158,846 | `0x00:0.205 0x11:0.205 0x12:0.205` |
| seperate/normal | 158,936 | `0x00:0.205 0x11:0.206 0x12:0.205` |

（`0x02/0x04` 在该输入下为 0；透明/白墨的完整语义属于 T3 色彩管线分析。）

### 3.7 inputColorEditor（v2.14.0）

```json
"inputColorEditor": [ { "mode": "full", "invert": false, "inkName": "W1" } ]
```

| 字段 | 值 |
|---|---|
| `mode` | `full` 全铺 / `color` 彩色全铺（透明保持透明）/ `smooth` 彩色平滑（按彩色算灰度）/ `smoothNeg` 平滑取反 / `white` 非透明区域白色 / `whiteNeg` 反白 |
| `invert` | bool，缺省 false |
| `inkName` | 通道名，如 "W1"/"W2"；也接受 "CMYKW1W2"（一次命名多个） |
| `whiteTole` | 白墨容差（white/whiteNeg 有效，8/16bit 时 0-255/0-65535） |

实测关键结论：**只有当 prs 的该 mode 本身就定义了这个墨通道，新增通道才会出现在 PRN 里。**
A3 mode2（plane=4，CMYK）加 `W1 full` 与不加的输出 **逐字节相同**（厂商金样本自身也是如此）；
A3 mode1/3（plane=6，CMYKW1W2）加 `W1 full` 才出现额外通道（m3 alpha 210,250 B、覆盖率 `0x12:0.199`）。
`inputColorEditor` 的 mode（full/color/smooth/…/invert）在 mode2 上均**无字节差异**（因为无槽位）；
有槽位时的具体差异属 T3 研究范围。

### 3.8 inkIE（内缩/外扩，v2.22.0）

```json
"inkIE": [ { "mode": "invaginate", "index": 4, "dots": [10,10,10,10] } ]
```

| 字段 | 说明 |
|---|---|
| `mode` | `invaginate` 内缩 / `expand` 外扩 |
| `index` | 通道索引（0 起，含驱动定义的墨 + inkLimit 新增墨；**不含 inputColorEditor 新增通道**） |
| `dots` | 4 个方向毫米数，顺序 左上右下，范围 [0,10] |

实测（A3 mode3，cmyk_quad_100，W1 golden 模板）：
无 inkIE 296,214 B；`invaginate index4 dots [5,5,5,5]` 304,151 B；`[10,10,10,10]` 320,348 B；
`expand` 同样 320,348 B。A3 mode2 上 `index:4` **无效果**（无第 5 个墨槽）。

### 3.9 旧式 extraMap/inkLimit/其他

* `extraMap`：`{mode: full|color|smooth, invert: bool/string, inkName}`，挂网前新增通道（文档建议改用 inputColorEditor）。
* `inkLimit`：`{mode: edit|new, index, inkName, maxInk(0-100), singleGamma(-3..3), linear[256]}`；`linear` 必须 256 个 [0,1] 浮点。
* `channelCopy`/`combines`/`density`/`contone`/`clip`：字段定义见文档 §2.3，本次未实测。

---

## 4. config 命令族（`command:"config"`）

> 全部为**临时设置**，mtrip 不持久化；DLL 重新加载即恢复默认。mtripNet 实例内全局生效，
> 会影响后续所有作业，实验后应恢复。所有 config 返回 `{"result":0}`。

### 4.1 errorString（v1.22.0，最常用）

```json
{ "command": "config", "type": "errorString", "setting": 1 }
```

| setting | 含义 |
|---|---|
| 0 | 关闭（**mtripNet.json 默认**）——错误只给 `result` 码 |
| 1 | 按运行环境自动语言（本机=简体中文；rip-studio 用 1） |
| 2 | 英语 |
| 3 | 简体中文 |

实测：关闭时 `{"result":6}`；开启后 `{"result":6,"error":"打开输入文件失败"}`（UTF-8 中文）。
注意：配置是进程级的，重启 mtripNet 后需重新 POST。

### 4.2 color（校色/缓存/透明）

```json
{ "command": "config", "type": "color",
  "embeddedICC": true, "cache": true, "transparencyToWhite": false, "readTransparency": false }
```

| 字段 | 默认（文档/全新实例实测） | 说明 |
|---|---|---|
| `embeddedICC` | true | 使用图片内嵌 ICC |
| `cache` | **true**（文档默认；重启后实测 true） | 校色缓存；**大幅加速**：同输入同参数重复作业从 1.0–1.6 s 降到 0.04–0.1 s；做动态校色/颜色调整时必须置 false 才生效（文档） |
| `transparencyToWhite` | false | 图片非透明区域输出白墨专色 |
| `readTransparency` | false | 读取图片透明层数据（queryFile 的 hasTransparency 字段依赖它） |

返回还带 `cacheNum`（当前缓存项数，实测随作业增长）。
> 首次会话曾观测到 `cache=false, readTransparency=true`（前一个使用者的设置）；重启后为上述默认值。
> **不要假设进程状态**，每次会话先 query 一次再决定。

### 4.3 其他 config 类型（文档 §2.5）

| type | 关键字段/用途 |
|---|---|
| `opt` | halftone 线程数（默认 32）、halftoneBufferMaxSize(256MiB)、halftoneBufferMaxLines(256)、interpretation(true)、threadBufferMaxSize/MaxLines、multiImageBlock*、halftoneCache(true)、useImageLocalCache(false)、localCacheDir(v2.49.0) |
| `buffer` | `output`(true)：PRN 是否缓冲发送；`bitsReverseOrder`(false)：byte 内 bit 顺序 0..7 |
| `adobe` | `overprintInPDF`(true)、`cmmCIE`(0/1/2)、`resolution`{type:auto/custom/low/medium/high, xdpi,ydpi}、`ignoreEmbedded*ProfileInPDF`(true)、`tolerance`{c,m,y,k} |
| `regPlugin`/`unregPlugin` | 注册/注销插件，pluginType：jobProgress/output/image/line（line 用 4） |
| `regJobProgressPlugin`/`unregJobProgressPlugin` | 旧版进度插件接口 |
| `driverInstall` | 导入驱动包 `{name, prsOutputDir}` |
| `driverExport` | 导出驱动包 `{prs, output, targetArch, originWpk, password}` |

实测 `query opt` / `query buffer` 默认值（全新实例）：

```json
opt: {"halftone":32,"halftoneBufferMaxSize":268435456,"halftoneBufferMaxLines":256,
      "interpretation":true,"threadBufferMaxSize":268435456,"threadBufferMaxLines":1024,
      "multiImageBlockMaxSize":67108864,"multiImageBlockMaxLines":1024,
      "multiImageBlockThreads":1,"halftoneCache":true,"useImageLocalCache":false,"localCacheDir":""}
buffer: {"output":true,"bitsReverseOrder":false}
```

---

## 5. query 命令族

### 5.1 queryMode（查打印机模式）

请求：

```json
{ "command": "queryMode", "prs": "./A3-DTF-1390.prs" }
```

可选：`allowDuplicationOfName`(bool)、`locale`(auto/enu/chs/cht)、`inks`(bool，返回墨水表)。

响应字段：`result`、`name`（打印机名）、`format`（可缺省，如 TIFF）、`modes[]`、`inks[]`（inks=true 时）。

`mode`：`name`、`id`、`dpi`、`paper`、`ink`、`colorCorrection`(bool)、`planes`。
`inks`：`name`、`id`、`colors`（墨序）、`planes`。

**A3-DTF-1390.prs 实测（30 个 mode，id 0–29）**：

| id | dpi | ink | planes | colorCorrection | paper |
|---|---|---|---|---|---|
| 0 | v720x360dpi | CMYK | 4 | false | A3-DTF-1390 |
| 1 | v720x360dpi | CMYKW1W2 | 6 | false | A3-DTF-1390 |
| 2 | v720x720dpi | CMYK | 4 | false | A3-DTF-1390 |
| 3 | v720x720dpi | CMYKW1W2 | 6 | false | A3-DTF-1390 |
| 4 | v1440x720dpi | CMYK | 4 | false | A3-DTF-1390 |
| 5 | v1440x720dpi | CMYKW1W2 | 6 | **true** | A3-DTF-1390 |
| 6 | v1440x1440dpi | CMYK | 4 | false | A3-DTF-1390 |
| 7 | v1440x1440dpi | CMYKW1W2 | 6 | **true** | A3-DTF-1390 |
| 8 | v2880x1440dpi | CMYK | 4 | false | A3-DTF-1390 |
| 9 | v2880x1440dpi | CMYKW1W2 | 6 | **true** | A3-DTF-1390 |

id 10–19 = 同样的 10 组（dpi/ink 循环）但 paper=`普通纸-2`；id 20–29 = paper=`普通纸-3`。
ink 表：`CMYK`（id 0，colors `["K","C","M","Y"]`，planes 4）、`CMYKW1W2`（id 1，colors `["K","C","M","Y","W1","W2"]`，planes 6）。
**注意：墨序是 K,C,M,Y（K 在最前），不是 C,M,Y,K。**

**H13 XP600.prs 实测（4 个 mode）**：

| id | dpi | ink | planes | colorCorrection | paper |
|---|---|---|---|---|---|
| 0 | V720x720 dpi | CMYKW1 | 5 | true | DTF |
| 1 | V720x1080 dpi | CMYKW1 | 5 | true | DTF |
| 2 | V720x1440 dpi | CMYKW1 | 5 | true | DTF |
| 3 | V720x2160 dpi | CMYKW1 | 5 | true | DTF |

打印机名：A3 = `A3-DTF-1390`；H13 = `MTF Better Print Ripserver Driver`。
H13 所有 mode 均 `colorCorrection=true`（即都有 ICC），A3 只有 5/7/9 有。

### 5.2 queryFile（文件基本信息）

```json
{ "command": "queryFile", "doc": { "name": "D:/.../flat_black_100.png" } }
```

图片响应 `page`：`width`/`height`（毫米）、`xdpi`/`ydpi`、`color`（颜色类型枚举）、
`spot`（专色名数组）、`hasTransparency`（当 readTransparency=true 时返回）、`exif`（有方向时）。
PDF 响应 `pdf[]`（每页 width/height mm）。

实测（PNG 内嵌 120 dpi，100×100 px）：`width=height=21.1685 mm, xdpi=ydpi=119.99, color=4`；
64×64 → 13.5478 mm；alpha PNG `hasTransparency=true`。
颜色枚举数值文档未给；按文档列举顺序推断 `4=rgb`（我们的 RGB PNG）。

### 5.3 query（通用查询）

```json
{ "command": "query", "type": "<type>" }
```

| type | 响应要点（实测/文档） |
|---|---|
| `version` | `version:"2.55.0"`、`os:"Windows10 X64"`、`speciality:"changzhuo"`、`dongle:true` |
| `info` | `busy:false`、`count:0`（正在工作的作业数） |
| `color` | `embeddedICC`、`cache`、`cacheNum`、`transparencyToWhite`、`readTransparency` |
| `opt` | 见 §4.3 |
| `buffer` | `output`、`bitsReverseOrder` |
| `dongle` | `online:true`、`sn:"A5103200002"` |
| `job` | 输入加 `id`；响应 `state` + `process{page,progress}` + `end{time}`（见 §7） |
| `docType` | 输入加 `name`；响应 `type`（unknown/pdf/eps/ps/tif/jpg/bmp/psd/psb/png/webp） |
| `errorString` | 返回当前 errorString setting |
| `driverMtcount` | 输入 `prs`；响应 `maxChannels` |
| `adobe` | PDF 解析参数 |

### 5.4 colorCorrection（校色 ICC 查询/修改）

查询（v2.35 新对象式）：

```json
{ "command": "colorCorrection", "prs": "D:/.../A3-DTF-1390.prs", "modeId": 5,
  "query": { "mcm": { "srcRgbPath": true, "srcCmykPath": true, "destCmykPath": true } } }
```

实测返回（裸文件名，不含目录）：

| prs / modeId | destCmykPath | srcCmykPath | srcRgbPath |
|---|---|---|---|
| A3 m5 | `v1440x720-A3-DTF-1390.icm` | `CoatedFOGRA39.icc` | `SRGB IEC61966-2.1.icc` |
| A3 m7 | `v1440x1400-A3-DTF-1390.icm` | 同上 | 同上 |
| A3 m9 | `v2880x1400-A3-DTF-1390.icm` | 同上 | 同上 |
| H13 m0–3 | `v720x720-dtf.icm` / `v720x1080-dtf.icm` / `v720x1440-dtf.icm` / `v720x2160-dtf.icm` | `US Web Coated (SWOP) v2.icc` | `SRGB IEC61966-2.1.icc` |

A3 非 5/7/9 的 mode 返回 `0x01000005`（当前无校色数据）。
旧式 `"query":["iccPath"]` 也可用；`modify`/`modify2`、`saveAs` 见文档 §2.7。
ICC 实际文件位置：`dist\bin\ICC Profile\OUTPUT\*.icm`、`CMYK\CoatedFOGRA39.icc`、`RGB\SRGB IEC61966-2.1.icc`。

### 5.5 preview

```json
{ "command": "preview", "input": {...}, "resolution": [1280,720],
  "output": {"file": {"name": "./a.tif", "mode":438} } }
```

生成 tiff 预览（取代已废止的 `view` 参数语义）。本次未实测。

### 5.6 job（作业取消命令）

```json
{ "command": "job", "type": "cancel", "ids": [101, 102] }
```

响应 `{result, jobs:[{id, result}]}`（文档 §2.8）。注意与 HTTP 的
`POST /mtrip/v1/cancel`（=MainTopRipCancel 全局取消）不是一回事。

---

## 6. 返回码（result）全表

### 6.1 旧返回码（`<ol start="0">`，文档 §1）

| code | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 用户取消 |
| 2 | 输入参数错误 |
| 3 | 没有找到相应的 prs |
| 4 | 错误的 prs 文件 |
| 5 | 不支持的输入文件格式 |
| 6 | 打开输入文件失败 |
| 7 | 解析输入文件失败 |
| 8 | 模块忙（PDF/PS/EPS 解释器单实例） |
| 9 | 不支持的命令 |
| 10 | 内存不足 |
| 11 | 图像驱动或输入插件加载失败 |
| 12 | 创建输出对象失败（输出文件/插件失败） |
| 13 | 加载输出驱动失败 |
| 14 | 需要的组件加载失败 |
| 15 | 图片数据或输入插件读取错误 |
| 16 | 无 ripServer 加密锁 / 非 ripServer 锁 |
| 17 | 加密锁已过期 |
| 18 | 加密锁计时芯片损坏 |
| 19 | 作业尺寸或精度需求超过加密锁限制 |
| 20 | 颜色模块失败（ICC 找不到等） |
| 21 | 通过 http 访问时，成功启动作业但在处理中 |
| 22 | 输出失败（file/raw/plugin 发送失败） |
| 23 | 作业不存在（v1.8.0） |
| 24 | 插件不存在（v1.8.0） |
| 25 | mtripNet 代理访问错误（响应含 error） |
| 26 | contone 参数目前不支持 |
| 27 | clip 参数错误 |

### 6.2 v2.0.0 起扩展码（0x01000000 段）

| code | 含义 |
|---|---|
| 0x01000001 | 输入失败（file/plugin 数据读取失败） |
| 0x01000002 | 输入插件加载错误 |
| 0x01000003 | 图像变换模块创建失败（v2.7.0） |
| 0x01000004 | 图像变换失败（v2.7.0；**取消作业在变换阶段也会报这个**，见 §7.3） |
| 0x01000005 | 当前无校色数据（v2.20.0） |
| 0x01000006 | 缺少自定义输入范围（v2.24.0） |
| 0x01000007 | 自动排版失败（v2.41.0） |
| 0x01000008 | 加密锁不支持自动排版（v2.41.0） |
| 0x01000009 | 驱动不支持点类型统计（v2.42.0） |

### 6.3 本机实测错误码（`work/protocol/evidence/config_color_tx.json`）

| 触发 | result | error（errorString=1） |
|---|---|---|
| doc.name 不存在 | 6 | 打开输入文件失败 |
| prs 不存在 | 3 | （对应文本未记录） |
| modeId=99 / -1 | 2 | 输入参数错误 |
| output.file 目录不存在 | 12 | （创建输出对象失败） |
| 未知 command | 9 | 不支持的命令 |
| command 类型错误 / 缺 command | 9 | 不支持的命令 |
| 把 .prs 当图片输入 | 5 | 不支持的输入文件格式 |
| doc.type=pdf 但内容是 PNG | 7 | 解析输入文件失败（约 2.4 s 后返回） |
| 非法 JSON body | 2 | 输入参数错误 |
| cancel 打断 transform | 0x01000004 | 图像变换失败, 可能是参数配置有误 |
| cancel 打断 RIP/挂网 | 1 | 用户取消 |

---

## 7. 作业进度、查询与取消

### 7.1 作业 id 与进度查询

* 在 rip JSON 加 `"id": N`（1..2147483647）。作业完成后进度信息约保留 5 分钟。
* `{ "command":"query", "type":"job", "id": N }`：

```json
{ "result": 0, "state": 2, "end": { "time": 1793947716 } }
```

* 快速作业可能直接返回 `state:2`（不再给 process）。`state` 枚举（query.job）：
  `0`=预处理进行中、`1`=RIP 进行中、`2`=成功完成、`3`=失败。
  （文档未给数字映射，此映射由 §7.2 SSE 事件与最终状态对照推定。）
* 作业失败后 `query job` 可能返回 `result:2 输入参数错误`（id 未登记）。

### 7.2 SSE 进度流 `/mtrip/v1/jobs/progress`

* 每行 `data: <JSON>`；不需要 body；`curl -N` 可用。
* 事件序列实测（A3 mode2、100×100 图、id=1001，约 1 s 完成）：

```
data: {"jobID":1001,"state":1}                                  # 作业准备/开始
data: {"jobID":1001,"state":2,"process":{"page":0,"progress":0}} # 输出中
data: {"jobID":1001,"state":2,"process":{"page":0,"progress":200}}
...                                                             # progress 0..10000（万分比）
data: {"jobID":1001,"state":2,"process":{"page":0,"progress":10000}}
data: {"jobID":1001,"state":3,"end":{"end":1793947716}}         # 结束（成功）
```

* SSE `state` 枚举与 query.job 不同：`1`=准备、`2`=输出中（带 process）、`3`=成功结束；
  gRPC 文档描述还有“作业失败”。`end.end` 为 unix UTC 秒（query.job 的 `end.time` 同值）。
* 进度事件可能跳跃（文档 §1.4）；该流是**全局**的，会推送所有带 id 作业的事件。
* 曲线：progress 步进不规则（0,200,300,...)，最多到 10000。

### 7.3 取消（实测）

* `POST /mtrip/v1/cancel`（空 body）→ `{"result":0}`，阻塞到取消完成（实测 0.02–0.31 s）。
  它**不接受 ids**；等价 C API `MainTopRipCancel`（全局取消当前操作）。
* 被取消作业的 `POST /mtrip/v1/jobs` 响应取决于取消时阶段（A3 mode6、720×720 图、POST 侧 1.4 s）：
  * 在**图像变换阶段**取消（开始后 ~0.5 s）→ `{"result":16777220(0x01000004),"error":"图像变换失败, 可能是参数配置有误"}`，不生成 PRN；
  * 在 **RIP/挂网阶段**取消（~0.9 s / 1.2 s）→ `{"result":1,"error":"用户取消"}`，不生成 PRN（0 字节文件会残留）。
  * 空闲时 POST /cancel → `{"result":0}`。
* 若要按 id 取消（多作业），用 `command:"job", type:"cancel", ids:[...]` 走 `/mtrip/v1/jobs`（文档 §2.8）。

---

## 8. oracle：如何在本机复现生成参考 PRN

### 8.1 前置条件

1. `mtripNet.exe` 在运行且已就绪（约 10–13 s）：

```powershell
Get-Process mtripNet
curl.exe -s http://127.0.0.1:8089/mtrip/v1/version
```

2. Python 3.11：`C:\Espressif\tools\python\python.exe`（PIL 13 可用）。
3. **不要占用/重启 8089/8090；串行 POST**。mtripNet 的 CWD 必须是
   `D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin`（相对 prs/ICC 解析依据）。
4. 若进程崩溃需要重启（Lead 授权流程）：

```powershell
Start-Process -FilePath "D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin\mtripNet.exe" `
  -WorkingDirectory "D:\Code\kkf\v1.1.2\rip-studio\3rdLib\mtripSDK\dist\bin" `
  -RedirectStandardOutput "D:\work\RIP核心分析\work\protocol\mtripnet_console.log" `
  -RedirectStandardError  "D:\work\RIP核心分析\work\protocol\mtripnet_console.err.log" `
  -WindowStyle Hidden
# 轮询等待 ~15s，不要用 -Force 杀正在初始化的进程
```

### 8.2 工具（`tools\oracle\`）

| 脚本 | 用途 |
|---|---|
| `mtrip_oracle.py` | 单命令 CLI：`version`/`status`/`query-mode`/`post`/`rip`/`sse`/`cancel`/`prn-info`/`compare` |
| `make_inputs.py` | 生成 `reference/inputs/*.png`（120 dpi 合成图：纯色/棋盘/渐变/alpha/1px 线，64/100/720） |
| `make_inputs_dpi.py` | 同像素、内嵌 72/300 dpi 的 PNG（验证 view vs 内嵌 DPI） |
| `make_corpus.py` | 批量基础语料（2 机型 × modeId0–3 × 18 图 + 白墨 + 720 大图），带断点续跑 |
| `run_batch.py` | 按 JSON spec 串行跑任意作业批（跨分析员样本请求用） |
| `build_manifest.py` | 扫描 `reference/prn_samples` 重建总清单 `reference/jobs/manifest_all.csv` |

示例：

```powershell
# 查版本/状态/模式
python tools\oracle\mtrip_oracle.py version
python tools\oracle\mtrip_oracle.py query-mode --prs ./A3-DTF-1390.prs --inks

# 生成一个参考 PRN（输出必须在 workspace 内）
python tools\oracle\mtrip_oracle.py rip --machine a3dtf1390 --mode 2 ^
  --image reference/inputs/cmyk_quad_100.png ^
  --case a3dtf1390_cmyk_quad_100_m2

# 看 PRN 头/格式/sha256；比较两个 PRN（自动归一化时间戳）
python tools\oracle\mtrip_oracle.py prn-info --file reference\prn_samples\a3dtf1390_cmyk_quad_100_m2.prn
python tools\oracle\mtrip_oracle.py compare 参考a.prn 参考b.prn
```

`rip` 子命令可传 `--rotate/--scale/--margin/--mirror/--white golden|w1w2|color|smooth/
--ice-json/--inkie-json/--dpi/--id/--extra-json`，等价于手工 POST 作业 JSON。
每次运行会把**实际作业 JSON** 写到 `reference\jobs\<case>.json`，响应到 `.resp.json`。

### 8.3 关键坑（复现必读）

1. **编码**：本机 pwsh 是 Windows PowerShell 5.1，`Get-Content/Set-Content` 默认 ANSI，
   读写中文会乱码。用 `read/write` 工具或 Python 写文件；Python 侧统一 UTF-8（无 BOM）。
   控制台显示乱码时加 `$env:PYTHONIOENCODING="utf-8"`（只是显示问题，响应本身是 UTF-8）。
2. **输出路径**：必须给 workspace 内绝对路径（`D:/work/RIP核心分析/...`），
   中文路径实测 OK；**绝不要往 rip-studio 目录写文件**。
3. **确定性**：A3（ESC/P2）同一作业两次运行结果**仅 EJL 头 `TI` 时间戳 7 字节不同**
   （文件偏移 45..51，见 §9.2），其余逐字节相同；H13（HSSF）完全确定。
   比对时用 `sha256_norm`（`mtrip_oracle.py compare/normalize_prn_bytes`）。
4. **错误文本**：默认 `errorString.setting=0`，响应只有 result；先 POST
   `config/errorString setting=1` 再看 `error`。
5. **config 是进程级**：实验会改变 mtripNet 全局状态（cache/readTransparency/…），
   跨分析员共享 oracle 时实验前 query、实验后恢复。
6. **并发**：一次只跑一个作业；`POST /mtrip/v1/jobs` 是同步阻塞接口。
7. **custom dpi 致命**：见 §10.1，不要常规使用。
8. **H13 的 prs 不在 dist\bin**：`H13 XP600.prs` 只在
   `rip-studio\bin\bin\`，必须用绝对路径传；其 ICC 仍按 mtripNet CWD 解析（dist\bin\ICC Profile）。
   **dist 与 bin 两份 `v720x720-dtf.icm` 内容不同**（H13 mode0 的 dest profile），复现时注意。

---

## 9. 参考语料（oracle 输出）规范

### 9.1 目录与命名

```
reference/
  inputs/       合成输入 PNG（120 dpi；另有 _dpi72/_dpi300 变体）
  prn_samples/  <machine>_<case>_m<modeId>[_<variant>].prn
  jobs/         <同名>.json（实际作业 JSON）、<同名>.resp.json（服务端响应）
                manifest.csv（make_corpus 生成）、manifest_all.csv（全量，含 sha256）
  jobs/queries/ colorCorrection/queryMode 等查询证据（prs-analyst 用）
  profiles/     （T3 使用）
```

* `machine`：`a3dtf1390`（A3-DTF-1390.prs，改装机/ESC-P2）或 `h13xp600`（H13 XP600.prs，板卡机/HSSF 0x5555）。
* `case`：输入图片文件名主干，如 `flat_c_100`、`cmyk_quad_100`、`checker_1px_100`、`grad_h_100`、`lines_1px_100`、`alpha_checker_100`、`flat_black_720`。
* `variant`：缺省(基础模板)；`golden` = 金样本式白墨模板（`inputColorEditor:[{W1,full}]` + `inkIE:[{invaginate,index4,dots[10,10,10,10]}]`）；`w1w2` = W1+W2 两个 full 通道。
* 另有 `exp_*`（参数实验）、`geom_*`/`geomh_*`（Lead/T2 请求的几何/颜色对照）、
  `probe_*`/`det_*`/`sse_*`/`golden_repro_*`（验证样本）。

**两种模板（除变体字段外完全相同的固定字段）**：

```jsonc
// 基础模板
{ "command":"rip", "doc":{"name":"<inputs/xxx.png>"}, "prs":"./A3-DTF-1390.prs",
  "modeId":2, "range":[[1,1]],
  "output":{"mode":"file","file":{"name":"<workspace>/reference/prn_samples/xxx.prn","mode":438}},
  "rotate":0, "scale":[100,100], "margin":[0,0,0,0],
  "view":{"xdpi":120,"ydpi":120},
  "color":{"readTransparency":true,"transparencyToWhite":false} }
// golden 变体额外加：
// "inputColorEditor":[{"mode":"full","invert":false,"inkName":"W1"}],
// "inkIE":[{"mode":"invaginate","index":4,"dots":[10,10,10,10]}]
```

### 9.2 金样本级验证（oracle 可信度证明）

* 输入：`bin\bin\temp\pic\1793946733018.png`（1,882,349 B，用户实际 DTF 设计图）
* 作业：`bin\bin\GemodifiseerdeMasjienRip.json`（A3-DTF-1390.prs，modeId=2、rotate0、scale100、
  margin0、view120、inkIE invaginate10、inputColorEditor W1 full、color{readTransparency:true,transparencyToWhite:false}）
* 原厂商输出：`bin\bin\temp\data\1793946733280.prn` = **1,734,682 B**
* 本 oracle 重放（仅把 output 文件名改到 workspace）：**1,734,682 B**
* 逐字节比较：**仅 2 字节不同**，位于 EJL remote `TI` 时间戳（偏移 45..51 内的分/秒）；
  归一化后完全一致（`sha256_norm` 相等，见 `work/protocol/evidence/` 与
  `reference/prn_samples/golden_repro_1793946733280.prn`）。
* 结论：HTTP oracle 与 rip-studio 原生 `MainTopRip` 输出**等价**，可作为 T2/T3/T4 的对照 oracle。
* 重启一致性验证：15:03 按 §8.1 重启 mtripNet（新 PID）后重跑同参数作业，输出与重启前语料
  **归一化后逐字节相同**（`postrestart_sanity.prn` vs `a3dtf1390_flat_black_100_m0.prn`）；
  注意重启会把进程级 config 恢复默认（`errorString=0`、`cache=true`、`readTransparency=false`），
  需重新 POST config。

PRN 确定性细节（A3 ESC/P2）：`TI` tag = `'TI' 08 00 00 00 <年BE16> <月> <日> <时> <分> <秒>`，
时间戳 7 字节位于文件偏移 **45..51**（文件头 3 个 0x00 之后：`00 00 00 1B 01 "@EJL 1284.4\n..."`）。
`normalize_prn_bytes()` 会把它们清零后比较；H13 输出无时间戳，全字节确定。

### 9.3 当前语料规模（2026-11-06 15:45）

* `reference/prn_samples/`：**2,483 个 PRN，约 592.5 MB**；`reference/jobs/manifest_all.csv` 2,481 行
  （不含 0 字节崩溃样本/失败样本）；`reference/jobs/` 下数千个 JSON
  （作业 JSON + 响应 + 查询证据）。
* 基础语料：2 机型 × modeId 0–3 × 18 张 100×100 图 = 144；
  白墨语料 21；720 大图 3；T2 探针 14；prs-analyst 的 mode5/7/9 样本 24；
  Lead 的 geom/geomh 样本 16；参数实验/白墨矩阵/验证样本约 80；
  T6 加网探针：ramp/patch/单值 34 + 阈值场扫描 C 256 / M/Y/K 768 / RGB gray 32 /
  cmykall 16 + 720/margin 3 + **tile176 C/Y/M/K 1,024** = **2,133 个**。

---

## 10. 实测“作业参数 → PRN 特征”对照（关键实验）

> 机器：A3-DTF-1390.prs；除非说明均为 modeId=2（v720x720dpi、CMYK、4 plane）、
> 输入 `reference/inputs/cmyk_quad_100.png`（100×100、120 dpi → 21.17 mm）。
> 特征由 T2 的 `tools/prn_tools/parse_prn.py` 解析：blocks=栅格块数、advance=块推进(79)、
> 覆盖率为各 ESC i 颜色码的 2-bit 非零点占比。
> 证据 JSON：`work/protocol/evidence/exp_features.json`、`exp_params2.json`、
> `white_matrix.json`、`config_color_tx.json`；汇总表 `evidence/tables.md`。

### 10.1 致命坑：`dpi`（customDpi）

* 复现 1（2026-11-06 14:54:14）：A3 mode2 + `"dpi":{"xdpi":300,"ydpi":300}` →
  创建 0 字节输出后 mtripNet **进程静默退出**（连接重置；Windows 事件日志无崩溃记录；无转储）。
* 复现 2（15:02:17，独立重启后的新实例 PID 38924，单发一次）：同样 0.56 s 后连接被重置、
  进程消失、输出 0 字节。→ **可稳定复现**，不是偶发。
* 证据：`reference/jobs/exp_a3dtf1390_dpi_300.json`、`exp_a3dtf1390_dpi_300_retest.json`、
  `reference/prn_samples/exp_a3dtf1390_dpi_300.prn`(0 B)、`work/protocol/evidence/dpi_crash_retest.json`。
* 恢复：按 §8.1 重启 mtripNet（本次实测启动后 **4 s** 即 `/version` 就绪；重启后 oracle 输出与
  重启前逐字节一致，见 §9.2 注）。
* 结论：**该字段不可用于生产/不做常规重试**；任何集成代码里应移除 `dpi` 字段。

### 10.2 modeId → 尺寸/结构（基础语料实测，见附 A）

* A3：mode0/1 = 720×360 dpi，mode2/3 = 720×720 dpi；同图 mode2 比 mode0 大 ~1.5–1.7×，
  mode3（6 plane）比 mode2 大 ~1.2–1.26×。
* W 通道模式（A3 m1/m3、H13 全部）：即使 W 全空，PRN 也比 CMYK 模式多出通道记录。
* **纯白图**：A3 输出仅 **264 B**（没有任何栅格数据，只剩头/尾命令）；H13 仍是定长帧。
* H13（HSSF 0x5555）每个 mode 的 PRN **大小固定**（m0=456,048；m1=684,048；m2=912,048；
  m3=1,368,048 B），与图像内容无关（定长帧格式，T4 解析）。

### 10.3 view / 内嵌 DPI

* 同一 100×100、内嵌 120 dpi 图，`view={xdpi:300}`/`{600}`/`{72}` 与不传 view：
  PRN **逐字节相同**（244,131 B，归一化后一致）。
* 换用内嵌 DPI 不同的同像素图（`cmyk_quad_100_dpi72.png` / `..._dpi300.png`），
  输出随内嵌 DPI 变化，且**仍与 view 无关**：
  * dpi72 → 35.28 mm → blocks=21，651,059 B；
  * dpi300 → 8.47 mm → blocks=12，48,265 B；
  * dpi120 基准 → blocks=16，244,131 B。
* 结论：**图片输入的物理尺寸/输出像素数由 PNG 内嵌 DPI 决定，`view` 对图片输入无效**
  （文档说 view 用于输入视口/dpi、imagePlugin 时无效；实测 doc 图片输入也无效）。
  要控制“图→PRN 几何”，改 PNG 的 pHYs/DPI 或使用 `scale`/`margin`。

### 10.4 rotate / scale / margin / mirror

| 参数 | 值 | PRN B | blocks | 说明 |
|---|---|---|---|---|
| 基准 | — | 244,131 | 16 | rotate0, scale100, margin0 |
| rotate | 90 / 180 / 270 | 243,696 / 242,602 / 242,090 | 16 | 内容不同，覆盖率不变；180° == mirror[true,true] |
| scale | [50,50] | 69,859 | 12 | 物理尺寸减半级 |
| scale | [200,200] | 934,342 | 24 | |
| scale | [100,50] / [50,100] | 128,228 / 133,004 | 12/16 | 各向异性有效 |
| margin | [5,10,15,20] mm | 256,737 | 16 | 四周留白；覆盖率下降 |
| mirror | [true,false] / [false,true] / [true,true] | 242,378 / 244,126 / 242,602 | 16 | 布尔生效 |
| mirror | [1,0]/[0,1]/[1,1] | 244,131（=基准） | 16 | **整数被静默忽略** |

### 10.5 color / transparency / inputColorEditor / whiteInk

* 作业内 `"color"` 对象：4 种组合（`readTransparency`×`transparencyToWhite`）输出**全部相同**
  → 该字段不改变图片输入行为；透明处理需全局 `config/color`（§4.2），且只有存在 W 通道时才可见。
* A3 mode2（无 W 槽）：`inputColorEditor W1 full` 与不加 → 逐字节相同（厂商金样本亦然，
  见 §9.2），说明**新增专色只在 prs 模式拥有该通道时进入 PRN**。
* A3 mode3（CMYKW1W2）：`inputColorEditor W1 full` 生效（alpha 图 210,250 B，`0x12:0.199`）。
* `whiteInk` 旧接口在 mode2 上**能**新增白墨通道（full/color/seperate 均生效，见 §3.6 表）。
* inkIE：仅对 prs/inkLimit 中存在的墨通道有效（mode3 index4/5 生效，mode2 index4 无效）。

### 10.6 可选/无副作用字段

`doc.type=auto` + `doc.imageBufferSize=1GiB`、缺省 `range`、缺省 `color`、缺省 `view`：
输出与标准模板逐字节相同（244,131 B）→ 这些字段可安全省略。

### 10.7 H13（板卡机）差异

* 输出 HSSF `0x5555`（文件头 `55 55 00 00 d0 02 00 00 ...`），非 ESC/P2；T4 负责格式解析。
* PRN 大小为 mode 定长（见 10.2）；`rotate=180`/`inputColorEditor`/`inkIE` 不改变文件大小；
  `scale=[50,50]` 改变（456,048→120,048，mode0）。
* 其 mode 均 `colorCorrection=true`，ICC 见 §5.4；H13 m0 的 dest icm 在两份环境不同（§8.3-8）。

---

## 11. 未解/待验证清单（交给 T2/T3/T4）

1. ESC i 颜色码（0x00/0x01/0x02/0x04/0x11/0x12）→ 实际墨通道 + 点大小的精确映射（T2 进行中；
   本文只提供颜色码覆盖率统计）。
2. `color` 全局配置对 alpha 图 → W 通道的像素级规则（readTransparency/transparencyToWhite 与
   whiteInk/inputColorEditor 的交互；本次观测到部分组合字节相同，需 T3 用解码器逐点验证）。
3. H13 HSSF 帧头/数据区（T4）；H13 m0 dest icm 采用 dist/bin 哪一份（同名文件内容不同）。
4. gRPC 8090 未实测；PDF/PS 输入未实测（需要 Adobe 解释器与 dongle，PDF 单实例 busy 语义待验）。
5. `custom dpi` 崩溃根因（是否特定 mode/分辨率，是否 H13 同样崩）——**不做常规复测**。
6. 多作业并发行为未压测（文档：PDF 单实例；图片多实例）。

---

## 附 A：基础语料 case×modeId PRN 大小表

| case (100x100, base template) | A3 m0 | A3 m1 | A3 m2 | A3 m3 | H13 m0 | H13 m1 | H13 m2 | H13 m3 |
|---|---|---|---|---|---|---|---|---|
| alpha_checker_100 | 74,784 | 102,701 | 134,505 | 185,843 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| alpha_grad_100 | 116,802 | 145,113 | 209,732 | 261,124 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| checker_1px_100 | 233,455 | 263,031 | 424,757 | 478,869 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| checker_8px_100 | 127,972 | 156,619 | 220,786 | 272,820 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| cmyk_quad_100 | 138,422 | 167,141 | 244,131 | 295,941 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_b_100 | 125,511 | 153,863 | 226,252 | 277,666 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_black_100 | 191,242 | 220,620 | 321,592 | 373,946 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_c_100 | 124,975 | 153,326 | 225,837 | 277,469 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_g_100 | 90,963 | 119,488 | 146,327 | 197,977 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_k_100 | 191,242 | 220,620 | 321,592 | 373,946 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_m_100 | 123,681 | 151,922 | 224,694 | 276,380 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_r_100 | 124,750 | 153,016 | 224,296 | 275,802 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_white_100 | 264 | 264 | 264 | 264 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| flat_y_100 | 111,048 | 139,251 | 197,990 | 249,668 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| grad_h_100 | 187,493 | 216,721 | 333,549 | 385,578 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| grad_v_100 | 189,173 | 218,453 | 336,189 | 388,210 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| lines_1px_100 | 70,463 | 98,197 | 126,438 | 178,276 | 456,048 | 684,048 | 912,048 | 1,368,048 |
| rgb_quad_100 | 133,881 | 162,654 | 231,377 | 283,124 | 456,048 | 684,048 | 912,048 | 1,368,048 |

## 附 B：参数实验（A3 mode2，基准 cmyk_quad_100 244,131 B / 16 blocks / advance 79）

| 实验 | 关键参数 | PRN B | blocks | 说明/结论 |
|---|---|---|---|---|
| exp_a3dtf1390_rot90 | rotate=90 | 243,696 | 16 | 内容变、覆盖率不变 |
| exp_a3dtf1390_rot180 | rotate=180 | 242,602 | 16 | == mirror[true,true] |
| exp_a3dtf1390_rot270 | rotate=270 | 242,090 | 16 | |
| exp_a3dtf1390_scale50 | scale=[50,50] | 69,859 | 12 | |
| exp_a3dtf1390_scale200 | scale=[200,200] | 934,342 | 24 | |
| exp_a3dtf1390_scale_100x50 | scale=[100,50] | 128,228 | 12 | 各向异性有效 |
| exp_a3dtf1390_scale_50x100 | scale=[50,100] | 133,004 | 16 | |
| exp_a3dtf1390_margin_5_10_15_20 | margin=[5,10,15,20]mm | 256,737 | 16 | 留白生效 |
| exp_a3dtf1390_m2_mirror_h_bool | mirror=[true,false] | 242,378 | 16 | 布尔生效 |
| exp_a3dtf1390_m2_mirror_v_bool | mirror=[false,true] | 244,126 | 16 | |
| exp_a3dtf1390_m2_mirror_hv_bool | mirror=[true,true] | 242,602 | 16 | == rot180 |
| exp_a3dtf1390_mirror_h/v/hv | mirror=[1,0] 等 | 244,131 | 16 | 整数被忽略 |
| exp_a3dtf1390_view_300 / _600 | view xdpi=300/600 | 244,131 | 16 | view 对图片无效 |
| exp_a3dtf1390_dpi72img_* | PNG 内嵌 72dpi | 651,059 | 21 | 几何由内嵌 DPI 决定 |
| exp_a3dtf1390_dpi300img_* | PNG 内嵌 300dpi | 48,265 | 12 | |
| exp_a3dtf1390_m3_golden | mode3 golden | 296,214 | 33 | 6 通道 |
| exp_a3dtf1390_m3_golden_inkIE_inv5 | mode3 + invaginate4 5mm | 304,151 | 33 | inkIE 生效 |
| exp_a3dtf1390_m3_golden_inkIE_exp10 | mode3 + expand4 10mm | 320,348 | 33 | |
| exp_a3dtf1390_m2_golden | mode2 + W1 full | 244,131 | 16 | 与不加 W1 相同 |
| exp_a3dtf1390_m2_golden_inkIE_inv10 | mode2 + inkIE index4 | 244,131 | 16 | 无该通道→无效 |
| exp_a3dtf1390_whiteInk_full_normal | whiteInk full | 274,262 | 16 | 白墨通道出现 |
| exp_a3dtf1390_whiteInk_sep_ownset90 | whiteInk seperate 90 | 250,195 | 16 | |
| exp_a3dtf1390_whiteInk_color_more | whiteInk color more | 274,268 | 16 | |
| exp_a3dtf1390_doctype_auto | doc.type=auto+1GiB buffer | 244,131 | 16 | 与基准相同 |
| exp_a3dtf1390_no_range_no_color_no_view | 去掉 range/color/view | 244,131 | 16 | 可省略 |
| exp_h13xp600_h13_golden | H13 m0 golden | 456,048 | — | 定长 |
| exp_h13xp600_h13_scale50 | H13 m0 scale50 | 120,048 | — | 仅缩放改变大小 |

## 附 C：白墨/透明矩阵（alpha_checker_100，A3）

| stem | mode | 方式 | PRN B | 颜色码覆盖率 |
|---|---|---|---|---|
| exp_a3_white_matrix_legacy_full_rt1_tw0 | 2 | whiteInk full | 164,636 | `0x00:0.205 0x11:0.411 0x12:0.205` |
| exp_a3_white_matrix_legacy_color_rt1_tw0 | 2 | whiteInk color | 158,846 | `0x00:0.205 0x11:0.205 0x12:0.205` |
| exp_a3_white_matrix_legacy_seperate_rt1_tw0 | 2 | whiteInk seperate | 158,936 | `0x00:0.205 0x11:0.206 0x12:0.205` |
| exp_a3_white_matrix_legacy_*_rt1_tw1 | 2 | whiteInk *_tw1 | 同上三种 | 与 tw0 相同（本输入下） |
| exp_a3_white_matrix_ice_m1_alpha_rt1_tw0 | 1 | inputColorEditor W1 | 126,231 | `0x01:0.091 0x04:0.091 0x12:0.183` |
| exp_a3_white_matrix_ice_m3_alpha_rt1_tw0 | 3 | inputColorEditor W1 | 210,250 | `0x01:0.1 0x04:0.1 0x12:0.199` |
| exp_a3_white_matrix_ice_m3_alpha_rt1_tw1 | 3 | inputColorEditor W1, tw=1 | 210,250 | 同上（本输入下 tw 无差异） |
| exp_a3_white_matrix_ice_m1_cmykquad_rt1_tw0 | 1 | inputColorEditor W1 | 190,671 | `0x01:0.091 0x02:0.123 0x04:0.123 0x12:0.183` |
| exp_a3_white_matrix_ice_m3_cmykquad_rt1_tw0 | 3 | inputColorEditor W1 | 320,348 | `0x01:0.1 0x02:0.134 0x04:0.134 0x12:0.199` |

## 附 D：证据文件索引（work/protocol/evidence/）

| 文件 | 内容 |
|---|---|
| `queryMode.json` / `queryFile.json` | queryMode（含 inks）/queryFile 原始响应 |
| `config.json` / `config_color_tx.json` | config 往返、全局 color/透明矩阵、错误码探针 |
| `determinism.json` | 4 组重复生成对比（A3 仅时间戳 1 字节差异；H13 0 差异） |
| `jobid.json` / `cancel.json` / `cancel_delays.json` | 作业 id/进度查询、取消语义两阶段 |
| `exp_features.json` / `exp_params2.json` | 参数实验特征（大小/blocks/覆盖率/sha） |
| `white_matrix.json` | 白墨/透明矩阵 |
| `tables.md` / `protocol_summary.json` | 汇总表与早期协议摘要 |
| `reference/jobs/queries/*` | prs-analyst 用 queryMode/ICC 原始 JSON |
| `reference/jobs/manifest_all.csv` | 全部 PRN 的清单（sha256/sha256_norm/参数） |

---

## 附 E：与 rip-studio 生产代码的对应（只读参考）

`src\service\ripService\ripcontrol.cpp`：

* `buildRipJson()` 生成作业：`command=rip`、`color{transparencyToWhite:false,readTransparency:true}`、
  `doc.name`、`inputColorEditor`（按 SplotColor：`buildWayId==0?full:color`）、`inkIE`（内缩/外扩）、
  `margin`、`modeId`、`output.file.name/mode=438`、`prs`、`range=[[1,1]]`、`rotate`、`scale`、
  `view{xdpi:120,ydpi:120}`；模板文件 `GemodifiseerdeMasjienRip.json`（改装机）/`KaartrekenaarRip.json`（板卡机）。
* `doSetting()` 先发两条 config：`errorString setting=1`、`color{...}`，然后再 `MainTopRip(job)`。
* 注意：生产模板写死 `modeId=2`（Gemodifiseerde）与 `inputColorEditor W1`，而 A3 mode2 是 4-plane
  CMYK —— 按本文实测，该组合输出中**不会出现 W1 通道**（与厂商金样本一致）；若目标是产出真实
  白墨 PRN，应改用 mode1/mode3，或使用 `whiteInk` 旧接口/T3 的结论确认。
  （此点建议 T3/T4 与 Lead 复核，可能是用户当前生产流程的一个实际缺陷点。）

---

## 12. T6 补充：modeId→ICC 映射表与加网/线性化探针

> 原始数据：`work/protocol/icc_mode_map.json`（完整 query 响应，含每 mode 的
> `remapTbl` 256×N 线性化曲线、`channelMax`、`kcmyGamma`、`dotGain`、`sepLightType`、`pure`、ICC 路径、
> ICC 文件清单+sha256）；可读展开表：`work/protocol/icc_table.md`。
> 加网探针报告：`work/protocol/screen_probe.md`；证据：`work/protocol/evidence/screen_probe_*.json`。

### 12.1 查询方式（本机实测）

```json
// 旧式：只查 ICC 路径
{ "command":"colorCorrection", "prs":"D:/Code/kkf/v1.1.2/rip-studio/bin/bin/A3-DTF-1390.prs",
  "modeId":5, "query":["iccPath"] }

// 旧式：校色头字段（返回 colorCorrection[inkName/channelMax]、dotGain、pure）
{ "command":"colorCorrection", "prs":"...", "modeId":5,
  "query":["channelMax","sepLightType","kcmyGamma","dotGain","remapTbl","pure"] }

// v2.35 对象式（推荐，一次拿全；remapTbl 为 256 double/通道）
{ "command":"colorCorrection", "prs":"...", "modeId":5,
  "query":{ "header":{"channelMax":true,"sepLightType":true,"kcmyGamma":true,
                      "dotGain":true,"remapTbl":true},
            "mcm":{"pure":true,"srcCmykPath":true,"srcRgbPath":true,"destCmykPath":true} } }
```

* A3-DTF-1390.prs：仅 **modeId 5/7/9（colorCorrection=true）** 返回 `result:0`；
  其余 27 个 mode 全部返回 **`0x01000005`「无校色数据」**（旧式/新式查询一致）。
* H13 XP600.prs：modeId 0–3 全部返回 `result:0`。
* `mcm` 返回的是**裸文件名**（无目录），实际解析目录由 mtripNet 进程 CWD（=dist\bin）决定。

### 12.2 A3-DTF-1390（改装机，ESC/P2）（`A3-DTF-1390.prs`）

| modeId | dpi | planes | ink | colorCorrection | 输出 destCmyk ICC | srcCmyk ICC | srcRgb ICC | channelMax(K,C,M,Y[,W1,W2]) | dotGain | sepLightType |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | v720x360dpi | 4 | CMYK | False | —（0x01000005） | — | — | — | — | — |
| 1 | v720x360dpi | 6 | CMYKW1W2 | False | —（0x01000005） | — | — | — | — | — |
| 2 | v720x720dpi | 4 | CMYK | False | —（0x01000005） | — | — | — | — | — |
| 3 | v720x720dpi | 6 | CMYKW1W2 | False | —（0x01000005） | — | — | — | — | — |
| 4 | v1440x720dpi | 4 | CMYK | False | —（0x01000005） | — | — | — | — | — |
| 5 | v1440x720dpi | 6 | CMYKW1W2 | True | `v1440x720-A3-DTF-1390.icm` | `CoatedFOGRA39.icc` | `SRGB IEC61966-2.1.icc` | [95, 100, 100, 100, 100, 100] | 2.4 | 3 |
| 6 | v1440x1440dpi | 4 | CMYK | False | —（0x01000005） | — | — | — | — | — |
| 7 | v1440x1440dpi | 6 | CMYKW1W2 | True | `v1440x1400-A3-DTF-1390.icm` | `CoatedFOGRA39.icc` | `SRGB IEC61966-2.1.icc` | [85, 90, 90, 90, 100, 100] | 3.36 | 3 |
| 8 | v2880x1440dpi | 4 | CMYK | False | —（0x01000005） | — | — | — | — | — |
| 9 | v2880x1440dpi | 6 | CMYKW1W2 | True | `v2880x1400-A3-DTF-1390.icm` | `CoatedFOGRA39.icc` | `SRGB IEC61966-2.1.icc` | [26, 40, 40, 40, 55, 55] | 4.8 | 3 |

（id 10–19 为 `普通纸-2`、20–29 为 `普通纸-3`，dpi/ink 组合与 0–9 一一对应，均无校色数据。）

### 12.3 H13 XP600（板卡机，HSSF）（`H13 XP600.prs`）

| modeId | dpi | planes | ink | colorCorrection | 输出 destCmyk ICC | srcCmyk ICC | srcRgb ICC | channelMax(K,C,M,Y,W1) | dotGain | sepLightType |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | V720x720 dpi | 5 | CMYKW1 | True | `v720x720-dtf.icm` | `US Web Coated (SWOP) v2.icc` | `SRGB IEC61966-2.1.icc` | [100, 100, 100, 100, 100] | 2.8 | 3 |
| 1 | V720x1080 dpi | 5 | CMYKW1 | True | `v720x1080-dtf.icm` | `US Web Coated (SWOP) v2.icc` | `SRGB IEC61966-2.1.icc` | [95, 100, 100, 100, 100] | 3.6 | 3 |
| 2 | V720x1440 dpi | 5 | CMYKW1 | True | `v720x1440-dtf.icm` | `US Web Coated (SWOP) v2.icc` | `SRGB IEC61966-2.1.icc` | [86, 100, 100, 100, 100] | 4 | 3 |
| 3 | V720x2160 dpi | 5 | CMYKW1 | True | `v720x2160-dtf.icm` | `US Web Coated (SWOP) v2.icc` | `SRGB IEC61966-2.1.icc` | [70, 94, 94, 94, 100] | 4.8 | 3 |

### 12.4 线性化曲线 `remapTbl`（每通道 256 个 double，0..1）

A3 m5 抽样（实测墨序 K,C,M,Y,W1,W2，与 queryMode/inks 的 `colors` 一致）：

| 通道 | 0% | 10% | 25% | 50% | 75% | 90% | 100% |
|---|---|---|---|---|---|---|---|
| ch0(K) | 0 | 0.0501 | 0.1415 | 0.3998 | 0.6891 | 0.8338 | 1 |
| ch1(C) | 0 | 0.0283 | 0.0834 | 0.2576 | 0.6519 | 0.8532 | 1 |
| ch2(M) | 0 | 0.0395 | 0.12 | 0.3611 | 0.7021 | 0.8699 | 1 |
| ch3(Y) | 0 | 0.0371 | 0.1159 | 0.3456 | 0.6448 | 0.8225 | 1 |
| ch4(W1) | 0 | 0.098 | 0.251 | 0.502 | 0.7529 | 0.902 | 1 |
| ch5(W2) | 0 | 0.098 | 0.251 | 0.502 | 0.7529 | 0.902 | 1 |

> 全部 mode 的完整曲线在 `work/protocol/icc_mode_map.json` 的
> `modes.<prs>.<modeId>.queries.full_object.response.header.remapTbl`；
> `kcmyGamma` 在所有实测 mode 均为 0。

### 12.5 ICC 文件实际位置（供直接嵌入/复现）

mtripNet CWD=`…\mtripSDK\dist\bin`，ICC 相对文件名解析到 `dist\bin\ICC Profile\` 下
（源参照在 `CMYK\`/`RGB\`，输出参照在 `OUTPUT\`，默认参照在 `DEFAULT\`）：

| 相对 `dist/bin/ICC Profile/` | 大小 | sha256 前 12 | 对应 |
|---|---|---|---|
| `OUTPUT/v1440x720-A3-DTF-1390.icm` | 1,904,360 | d239eae42630 | A3 m5 destCmyk |
| `OUTPUT/v1440x1400-A3-DTF-1390.icm` | 1,904,360 | b9e70da14827 | A3 m7 destCmyk |
| `OUTPUT/v2880x1400-A3-DTF-1390.icm` | 1,904,360 | d96837eaa0fb | A3 m9 destCmyk |
| `OUTPUT/v720x720-dtf.icm` | 3,633,852 | 990b5d352491 | H13 m0 destCmyk（**bin 副本 sha 不同**） |
| `OUTPUT/v720x1080-dtf.icm` | 1,904,344 | 70ed86877204 | H13 m1 destCmyk |
| `OUTPUT/v720x1440-dtf.icm` | 1,904,344 | 43526ee64220 | H13 m2 destCmyk |
| `OUTPUT/v720x2160-dtf.icm` | 1,904,344 | efcce7ac0ad5 | H13 m3 destCmyk |
| `CMYK/CoatedFOGRA39.icc` | 654,352 | da2b9b593e27 | A3 srcCmyk |
| `CMYK/US Web Coated (SWOP) v2.icc` | 557,168 | 35f401731df1 | H13 srcCmyk |
| `RGB/SRGB IEC61966-2.1.icc` | 3,144 | 2b3aa1645779 | srcRgb（共用） |
| `DEFAULT/Default_cmyk.icc` | 557,168 | 842bd0543ab1 | 默认 CMYK 参照 |
| `DEFAULT/Default_rgb.icc` / `Default_gray.icc` | 3,144 / 348 | 2b3aa1645779 / 02774ffbab0b | 默认 RGB/灰度 |

> `bin\bin\ICC Profile\` 有同一套文件名；**除 `v720x720-dtf.icm` 外**同名文件 sha256 相同。
> 完整清单（33 个文件含 sha256）见 `icc_mode_map.json::icc_files` 或 `work/protocol/icc_table.md`。

### 12.6 加网/线性化探针（T6-B，详见 `work/protocol/screen_probe.md`）

* **CMYK TIFF 被接受**：`queryFile` 返回 `color=6`(cmyk)；A3 m2/m0、H13 m0 全部 result=0。
  （输入图：`reference/inputs/cmyk_ramp16_160.tif`、`cmyk_patch20_100.tif`、`cmyk_white_100.tif`、
  `cmyk_full_100.tif`、`cmyk_full4_100.tif`、20 张 `cmyk_probe_<ink><val>_64.tif`；
  PRN：`reference/prn_samples/probe_screen_*.prn`；另 RGB 阶梯：`rgb_gray16_160.png`、`rgb_ramps16_160.png`。）
* **颜色码↔墨实测**（A3 mode2/m0，CMYK 单通道 TIFF 输入）：`C→0x00`、`K→0x04`、`Y→0x11`、`M→0x12`。
* **2-bit 多值加网量化律（核心可实现结论）**：整幅平均 2-bit 点值 = `3·v/255`（v=16..240 误差<1e-4）；
  `v<85`：只用小点(1)且非零覆盖率=3v/255；`85≤v<170`：覆盖率 100%，小点↔中点混合；
  `v≥170`：覆盖率 100%，中点↔大点混合；点型空间排布呈伪随机（误差扩散/蓝噪声类）。
* `mtcount:true` 参数**不可用**：立即 `{"result":1,"error":"用户取消"}`；点型统计靠解码 PRN。
* 720×360（m0）与 720×720（m2）加网量化律一致，仅纵向行数不同。

### 12.7 高精度阈值场扫描（最终任务，2026-11-06 15:10 完成）

用 400 个单值探针（A3-DTF-1390.prs modeId=2，串行，全部 result=0，PRN 共 22.43 MB）
对加网阈值场 U 做密集采样：

| 家族 | 级数 | 输入命名 | PRN 命名 |
|---|---|---|---|
| C | 256（t=0..255） | `reference/inputs/probe_scan_C###_64.tif` | `reference/prn_samples/probe_scan_C###_a3dtf1390_m2.prn` |
| M / Y / K | 各 32（t=0,8,..,248） | `probe_scan_{M,Y,K}###_64.tif` | 同理 |
| gray（RGB 中性） | 32 | `probe_scan_gray###_64.png` | 同理 |
| cmykall（四通道同值） | 16（t=0,17,..,255） | `probe_scan_cmykall###_64.tif` | 同理 |

* 清单+逐作业解码统计：`work/protocol/evidence/probe_scan_manifest.json`。
* **模型验证**：C 通道 256 级全部满足 `平均点值 = 3t/255`，最大偏差 **0.000247**。
* **阈值场**：`work/protocol/evidence/probe_scan_thresholds.bin`
  = `T1[449280] T2[449280] T3[449280]`（uint16 LE，光栅顺序：block-major→record-major→
  row-major，4px/byte LSB-first）；`T1 = min{t : 3t/255 > U}`
  ⇒ **U ∈ ((T1−1)·3/255, T1·3/255]**。
  449,280 个位置中仅 147,456 = 384×384 是页面像素（`T1>0`），其余为微步进空白填充行；
  页面像素的 T1 在 1..85 均匀分布（每级 ≈1,735 个）⇒ 阈值场 U 在 (0,1] 近似均匀（FM/随机）。
* **周期律**：`T2−T1`、`T3−T2` 均集中在 85/86（255/3=85）⇒ 同一阈值场按墨量周期复现，
  与 Team 的加网模型 `level = floor(3t/255) + (frac > U(x,y))` 一致。
* 复现：`python work/protocol/exp_scan_highres.py`（约 3-4 分钟）+
  `python work/protocol/analyze_scan_highres.py`（验证/提取/追加报告）。
  详细说明见 `work/protocol/screen_probe.md` §9。

### 12.8 追加：M/Y/K 256 级扫描与每通道阈值场（2026-11-06 15:20）

* M/Y/K 各 256 级（t=0..255）探针共 768 作业，全部 result=0：
  `reference/prn_samples/probe_scan_{M,Y,K}###_a3dtf1390_m2.prn`，
  清单 `work/protocol/evidence/probe_scan_manifest.json`（1075 条）。
* 量化律验证：max |平均点值−3t/255| = M 0.000857 / Y 0.000864 / K 0.000312；
  颜色码：M→`0x12`、Y→`0x11`、K→`0x04`、C→`0x00`。
* **每通道阈值场**：`work/protocol/evidence/probe_scan_thresholds_{M,Y,K}.bin`
  （T1/T2/T3 各 449,280 uint16 LE，布局同 C 版；`D ∈ [256−3·T1, 258−3·T1]`）。
  摘要 `probe_scan_thresholds_MYK_summary.json`；与 C 的同位置阈值相同率仅 ~1.2%
  ⇒ **D 场每通道独立**。
* 附加探针：C64 720×720（`probe_scan_C64_720`，5.49 MB，印面 4320px 宽，blocks 63）用于
  tile 周期判定；margin 探针 marginT100=51,535 B / marginL100=108,787 B。
  **纵向 margin 不改变栅格内容（433/433 行逐字节相同），横向 margin 改变阈值采样**
  ——供 Team 判定 D 场索引坐标系。详见 `work/protocol/screen_probe.md` §10。

### 12.9 最终补测：1024×1024 阈值 tile 的 C/Y 高精度 D 场（2026-11-06 15:35）

* 背景：D 为 **1024×1024 固定 tile、内容相对索引**；64×64 探针只覆盖 tile 左上 384²。
* C/Y 各 256 级 × **176×176** CMYK TIFF（内容 1056×1056 输出像素 > 1024）：**512 作业全部 result=0**，
  PRN 160.54 MB。命名加 `_176` 以保留旧探针：
  `reference/prn_samples/probe_scan_{C,Y}###_176_a3dtf1390_m2.prn`，
  输入 `reference/inputs/probe_scan_{C,Y}###_176.tif`。
* 阈值导出：`work/protocol/evidence/probe_scan_thresholds_{C,Y}176.bin`
  （T1/T2/T3 各 2,090,880 uint16 LE，N=2,090,880，页面像素 1,115,136=1056²；布局同 64 版）。
* **精确 D 场导出**：`probe_scan_D_{C,Y}176.bin`（uint16/N，0..255=D，0xFFFF=空白填充），
  推导 `D = 258−3·T1`；**C/Y 各 238/240 个边缘异常留空**。
* **模型 100% 验证**：`level=(3t+D)>>8` 重建 vs 解码 PRN，24 个 t 值逐像素对比：
  C **0/26,757,552**、Y **0/26,757,504** 差异。
* D 统计：**3..255 步长 3（85 级，约 13,100/级近均匀）**；摘要
  `work/protocol/evidence/probe_scan_D_176_summary.json`。
* `probe_scan_C64_720` tile 周期证据保留；详细说明 `work/protocol/screen_probe.md` §11。
* 复现：`exp_scan_tile176.py` → `extract_tile176_thresholds.py` → `derive_D_tile176.py`。

### 12.10 最终补齐：M/K 176×176 256 级（四通道全部“直取精确”，2026-11-06 15:45）

* M/K 各 256 级 × 176×176：**512 作业全部 result=0**，PRN 160.59 MB；
  `reference/prn_samples/probe_scan_{M,K}###_176_a3dtf1390_m2.prn`。
* 阈值导出：`probe_scan_thresholds_{M,K}176.bin`（T1/T2/T3 各 2,090,880 uint16 LE，11.96 MiB）；
  **精确 D 导出**：`probe_scan_D_{M,K}176.bin`（uint16/N，0..255=D，0xFFFF=空白），D=258−3·T1。
* **模型 100% 验证（各通道）**：M 0 差异/26,757,216；K 0 差异/26,757,144（24 个 t 逐像素）。
* D 统计同 C/Y：3..255 步长 3、85 级、近均匀。摘要 `probe_scan_D_MK176_summary.json`。
* ⚠ **互补关系注意**：原始光栅位置直接比较 `D_M vs 258−D_C`/`D_K vs 258−D_Y` 一致率仅 0.18%，
  因为同一图像不同墨通道的 **microweave 光栅行排布不同**（page mask 交集仅 ~95%），
  扁平索引≠同一页面像素；互补关系需在内容/1024 tile 坐标下验证（T3 用映射）。
  本批给出各通道直取的精确 D，**不再依赖互补推导**。
* 至此 1024 tile 四通道（K/C/M/Y 对应颜色码 0x04/0x00/0x12/0x11）全部可直取。

### 12.11 ⚠ 最终报告须注明：oracle 侧可复现的加网缺陷（确定性，非非确定性）

* 现象：1024 个 tone 探针中 972 个 100%；**52 个异常探针**（缺陷 tone
  `[93,95,101,106,151,161,166,186,202,230,242,244,253]` × C/M/Y/K 四通道）各 16 像素，
  共 **832 个异常 cell**；全部位于 tile 中 **T3==0（D<3，max level=2）** 的像素，
  oracle 自身**非单调漏点**（level 随 tone 升高掉回 0，tone±1/±2 邻域正常）。
* **确定性验证（T1）**：52 个作业各重跑 2 次 → TI 归一化后 **52/52 逐字节一致**、
  内容平面 **0 像素差异**；**832/832 cell** 原始==r1==r2 且 == 审计 oracle_dot=0；
  **832/832 为非单调漏点**。T3 独立复核（`tools/prs_tools/check_rerun_determinism.py`，
  `work/prs/rerun_check.log`）= 832/832 deterministic、832/832 dot==0。
* **结论**：**可复现的蒙泰算法缺陷**（疑似 T3=256 存 8-bit 成 0 的边界分支），
  不是运行间非确定性。排除这 832 个 cell 后 **1024/1024 探针 = 100.0000%**；
  tile 维持 `reference/screen/final/` 不重拟合；引擎可把这 832 cell 作确定性特例处理。
* 证据链：`reference/prn_samples/probe_scan_<INK><tone>_176_a3dtf1390_m2.prn`
  → `work/prs/oracle_screen_audit.json` →
  `reference/prn_samples/rerun/probe_scan_<INK><tone>_176_a3dtf1390_m2_r{1,2}.prn`
  + `work/protocol/evidence/screen_nondeterminism.{json,md}`
  （详见 `work/protocol/screen_probe.md` §12、`docs/color_pipeline.md` §10.5）。
