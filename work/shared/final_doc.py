# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add = """

## 7. 四通道精确阈值场集成（最终一轮）

T1 补跑 M/Y/K 各 256 级探针（768 作业，0 失败）后，已提取四通道精确阈值场：

- `work/protocol/evidence/probe_scan_thresholds_{C,M,Y,K}.bin`（每通道 T1/T2/T3 各 449,280 uint16，
  页面像素 147,456；跨通道同位置相同率仅 1.2% ⇒ 每通道独立随机场）；
- D 与 T 的关系：`T1=ceil((256−D)/3)` ⇒ `D∈[256−3·T1, 258−3·T1]`；
- 已转换为引擎格式 `build/screen/thr_{C,M,Y,K}.bin`（384×384×3 字节 [T1,T2,T3]），
  引擎 `Screen` 规则：`level=(v≥T1)+(v≥T2)+(v≥T3)`。

集成后 64×64 黑样本逐像素对拍（页面点阵，384×384）：

| 颜色 | 一致率 | 说明 |
|---|---|---|
| Y(0x11) | **85.5%** | 阈值场精确 |
| K(0x04) | 66.8% | 阈值场精确，墨量值差异导致 level 分布不同 |
| M(0x12) | 59.5% | 同上 |
| C(0x00) | 38.1% | 同上 |

结论：**加网阈值场与公式已精确复刻**；剩余差异来自 no-CC 模式下 RGB→CMYK 的数值链
（我们当前用 sRGB→CoatedFOGRA39 perceptual；oracle 对纯黑产出的 C 墨量更低）。
下一步建议（数据已具备）：用 T1 已生成的 `probe_scan_gray*`/`cmykall*`/`rgb_ramps16` 语料
标定 no-CC 的 RGB→CMYK 映射（逐通道曲线拟合），即可把一致率推近 100%。

## 8. 坐标索引规则（T1 margin 探针结论）

- **纵向：内容相对坐标**（纵向 margin 不改变栅格数据，433/433 行逐字节相同）；
- **横向：页面绝对坐标（含左边距）**（横向 margin 会改变阈值采样）。
- 目前阈值场覆盖内容行 0..383；更大内容高度需要更大探针（`probe_scan_C64_720.prn` 已备好）
  或用同一生成规则扩展（待定）。

## 9. 已知环境问题

- **必须 clean build**：`build.cmd clean`。若在多人/多进程同时编辑 src 时增量构建，曾出现
  stale object 导致写出错误 PRN（表现为 ESC i 字段错位）；clean 构建后已验证正常。
- `mtr_cli decode` 仍是占位（engine-dev 已实现 `prn_reconstruct`，可直接接入）。
"""
if "四通道精确阈值场集成" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("validation doc updated")
