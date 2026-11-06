# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\00_overview.md"
t = open(p, encoding="utf-8").read()
add = """

---

# 附录 · 当前交付状态（2026-11-06 15:20）

## 已交付

| 类别 | 文件 |
|---|---|
| 总览/流程 | `docs/00_overview.md`、`docs/01_maintop_pipeline.md`、`docs/maintop_api.md`（T1，57KB） |
| ESC/P2 规范 | `docs/prn_escp2.md`（T2，26KB，含整文件 round-trip 逐字节验证工具）、`docs/02_geometry_escp2.md` |
| PRS/色彩/加网 | `docs/prs_format.md`、`docs/color_pipeline.md`（T3） |
| 板卡机 HSSF | `docs/prn_board.md`、`docs/board_pipeline.md`（T4） |
| 集成方案 | `docs/05_integration.md`（DLL 1:1 替换 mtrip.dll 的 C API 兼容层） |
| 验证报告 | `docs/06_validation.md` |
| C++ 实现 | `src/`：mtr_core（PrsConfig / 图像 / ICC / 加网 / ESC-P2 编码 / HSSF 编码 / 布局 / PRN 反解）、`mtr_cli.exe`、`mtr_rip.dll`（导出 MainTopRip 等 4 函数） |
| 工具 | `tools/oracle/`（oracle 生成/校验/语料）、`tools/prn_tools/`（解析/RLE/round-trip/预览）、`tools/prs_tools/`（prs/ICC/加网分析）、`tools/board_tools/`（HSSF 解析）、`tools/validate/` |
| 语料 | `reference/prn_samples/` 784 个参考 PRN（235MB）+ `reference/jobs/manifest_all.csv`；`reference/profiles/` ICC/LUT；`reference/inputs/` 合成输入图 |
| 构建 | `build.cmd`（一条命令：MSVC+Qt6.8.3+Ninja 构建并自动部署 Qt/ICC/PRS），产物 `build/mtr_cli.exe`、`build/mtr_rip.dll` |

## 验证结论（详见 docs/06_validation.md）

- **oracle 与生产等价**：金样本重放除 TI 时间戳外逐字节相同；语料 784 个 PRN 全部可复现。
- **ESC/P2 结构**：我们的命令区 91 字节与 oracle **逐字节一致**；块数/推进/颜色记录顺序/n/m 一致。
- **整文件字节级**：T2 的 decode→re-encode 对 135 个样本（95.9MB）**逐字节一致（仅 TI）** → 编码器规则（含 RLE ≥3 规则）已完全掌握。
- **HSSF 0x5555**：T4 用 oracle 语料 92 项校验全通过，引擎已实现。
- **加网**：模型 `level=(3v+D)>>8` 精确（256 级探针 0 矛盾），C 通道阈值场已精确提取（384×384），M/Y/K 精确场正在由 T1 补跑数据后生成。
- **未完成/下一步**：① 四通道精确阈值场落盘后直接替换 `build/screen/`；② no-CC 的 RGB→CMYK 精确标定（K 偏低）；③ 大图阈值场覆盖（>384 行需要更大探针或发现 D 场生成规则）；④ 实机打印验收。
"""
if "附录 · 当前交付状态" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("overview updated")
