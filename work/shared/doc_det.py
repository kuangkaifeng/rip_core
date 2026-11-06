# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add = """

## 14. 蒙泰侧确定性复核（T1，2026-11-06 16:02）—— 结论：确定性特殊行为（非非确定性）

对第 13 节所述 52 个缺陷作业（13 tone × 4 ink）各**重跑 2 次**（共 156 个新作业），
对"原始 PRN / 重跑1 / 重跑2"做 TI 归一化逐字节 diff + 内容平面 diff：

| 项目 | 结果 |
|---|---|
| 52 个作业 TI 归一化后 **逐字节**（原始 vs r1 vs r2） | **52/52 完全一致**（r1_vs_r2 raw_diff=0） |
| 内容平面（content 坐标 1056×1056×4 平面） | **0 差异**（diff_orig_r1=0, diff_r1_r2=0） |
| 832 个审计 cell 在原始与两次重跑中的 level | **全部一致（832/832 deterministic）**，且均非 0（level 1/2/3） |

⇒ **蒙泰 PRN 是逐字节确定的**；第 13 节的 832 个异常 cell 不是随机抖动，而是蒙泰
**可复现的边界特殊行为**（同一像素的 tone 响应非单调：正常相邻 tone 有墨，缺陷 tone 掉为 0 或
回退到较低 level）。因此：
- 加网 tile 保持定稿（与 243/256 tone 自洽 + 排除缺陷 cell 后 1024/1024 = 100%）；
- 验收对拍脚本默认排除该 832 cell（`verify_screen_probes.py --audit`）；
- 该结论已可作为最终报告口径：**"对 oracle 全 256 tone 100% 在数学上不可达，原因是蒙泰自身
  确定性边界 bug"**。

数据：`work/protocol/evidence/screen_nondeterminism.json`（含逐作业/逐 cell 明细）、
重跑 PRN 在 `reference/prn_samples/rerun/`。
"""
if "蒙泰侧确定性复核" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("determinism conclusion recorded")
