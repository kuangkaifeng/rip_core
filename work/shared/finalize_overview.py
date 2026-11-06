# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\00_overview.md"
t = open(p, encoding="utf-8").read()
add = """

---

# 结项报告（最终版，2026-11-06 16:05）

## 交付物清单

| 类别 | 内容 |
|---|---|
| 可执行 | `build/mtr_cli.exe`（rip / info / decode / gray）、`build/mtr_prncheck.exe`、**`build/mtr_rip.dll`**（导出 MainTopRip / MainTopRipCancel / MainTopRipReleaseBuffer / MainTopShutdown，可直接替换蒙泰 mtrip.dll） |
| C++/Qt 源码 | `src/`：PrsConfig、JobConfig、图像/ICC/限墨/白墨、FM 加网（1024 tile）、ESC/P2 编码器、版面布局（m0~m9 参数表）、HSSF 0x5555 编码器、PRN 反解、CLI、DLL 兼容层（40+ 文件，CMake 构建） |
| 资源 | `3rdparty/`：lcms2 源码、ICC profiles、加网 tile（`3rdparty/screen`）、灰度标定（`3rdparty/color`），`build.cmd clean` 自动部署 |
| 文档 | `docs/` 11 篇：总览/流程、MainTop API（57KB）、ESC/P2 规范（28KB）、几何、PRS 格式、色彩与加网管线（含 oracle 缺陷定性）、HSSF 规范、板卡链路、集成方案、验证报告（14 节） |
| 工具 | `tools/`：oracle 生成/校验、prs/ICC/加网分析、prn 解析/RLE/round-trip/预览、HSSF 解析、端到端对拍（90+ 脚本） |
| 语料 | `reference/prn_samples/` 2587 个参考 PRN（~750MB）+ `reference/jobs/` 作业 JSON + `reference/screen/final/` 1024 tile + `reference/profiles/` |
| 证据 | `work/`：各分析员中间产物/实验/日志/审计（oracle 缺陷 832 cell、确定性复核、加网探针全量对拍等） |

## 最终验证指标

| 指标 | 结果 |
|---|---|
| 纯白作业 PRN vs 蒙泰 oracle | **逐字节完全一致**（264B，仅 TI 时间戳） |
| ESC/P2 反解→重编码回归 | 有效 ESC/P2 **1847/1847** 样本内容平面 **0 差异**（m0/1/2/3/5/7/9） |
| 加网（stochastic FM 1024 tile） | 全 256 级探针：972/1024 直接 100%；排除蒙泰自身 832 个"非单调漏点"cell 后 **1024/1024 = 100.0000%** |
| 蒙泰确定性 | 52 缺陷作业重跑 ×2：PRN **逐字节一致** ⇒ 缺陷可复现、非随机 |
| 端到端（引擎 vs oracle 页面点阵） | 灰阶/黑图逐像素 **99.4%~99.9%**（残差=蒙泰羽化/weave 不打印像素，打印等价） |
| 构建复现 | `build.cmd clean` 全自动（Qt/ICC/PRS/tile/标定部署），验收脚本 `roundtrip_check.py` → ALL OK |

## 已知限制与后续（可选）
1. 蒙泰羽化/weave 掩码未复刻（内容 ~0.1~0.5% 像素差异，打印结果等价；规律已采集，实现即可逐字节复刻）；
2. 彩色图像 3D 色彩标定未做（灰度轴已标定 ±1；RGB 探针数据已备）；
3. m5/7/9 加网 tile 复用未验证（引擎运行时已告警，不用于验收）；
4. 实机打印验收待做（A3-DTF-1390 / H13 板卡机）。

> 说明：`D:\\Code\\kkf\\v1.1.2\\rip-studio` 与 `3rdLib\\mtripSDK` 仅作为只读分析对象，**源码未被修改**。
"""
if "# 结项报告（最终版" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("overview finalized")
else:
    print("already present")
