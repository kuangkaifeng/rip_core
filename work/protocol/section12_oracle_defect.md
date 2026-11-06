
## 12. Oracle 侧可复现的加网缺陷（确定性）——最终报告必须注明

结论（T1 + T3 独立复核一致）：**不是非确定性，而是蒙泰侧可复现的算法缺陷**。
1024 个 tone 探针中 972 个 100%；52 个异常探针（13 tone × 4 ink）各 16 个像素，
共 **832 个异常 cell**，全部是 tile 中 T3==0（D<3，max level=2）的像素，
表现为 **oracle 非单调漏点**（level 随 tone 升高反而掉回 0，tone±1/±2 正常）。

| 项 | 内容 |
|---|---|
| 缺陷 tone（四通道相同） | `[93,95,101,106,151,161,166,186,202,230,242,244,253]` |
| 异常 cell | 13 tone × 4 ink × 16 位置 = **832** |
| oracle 行为 | 本 tone level=0（模型期望 1~2），邻域 tone 有 ink（非单调） |
| 确定性验证（T1） | 52 个作业各重跑 2 次：TI 归一化后 **52/52 逐字节一致**；内容平面 **0 像素差异**；**832/832 cell** 原始==r1==r2 且 == 审计 oracle_dot=0；**832/832 为非单调漏点** |
| 独立复核（T3） | `tools/prs_tools/check_rerun_determinism.py`：832/832 deterministic、832/832 oracle dot==0（日志 `work/prs/rerun_check.log`），写入 `docs/color_pipeline.md` §10.5 |
| 典型证据 | C 内容(x=296,y=53) tone93：orig/r1/r2=0/0/0，而 t=91/92/94=1/1/1（t=95 为另一异常 0）；C page(693,296) t=93/95 dot=0 vs t=91/92/94 dot=1 |
| 影响 | 排除 832 个非单调 cell 后 **1024/1024 探针 = 100.0000%**；tile 维持 `reference/screen/final/`，不做重拟合（重拟合会掩盖该缺陷） |
| 引擎实现 | 可把这 832 个 cell 作为**确定性特例**硬编码/白名单处理，无需随机性容错（疑似蒙泰 T3=256 存 8-bit 成 0 的边界分支） |

**证据链（probe PRN → audit.json → rerun 确定性验证）**
1. 探针 PRN：`reference/prn_samples/probe_scan_<INK><tone>_176_a3dtf1390_m2.prn`（4 ink × 256 tone）
2. 审计：`work/prs/oracle_screen_audit.json`（T3，832 cell 的 `<y>,<x>` 与 `[tone, oracle_dot, model_expected]`）
3. 重跑确定性验证：`reference/prn_samples/rerun/probe_scan_<INK><tone>_176_a3dtf1390_m2_r{1,2}.prn`
   + `work/protocol/evidence/screen_nondeterminism.json` / `.md`（52 探针字节/内容 diff、832 cell 明细）
   + `work/prs/rerun_check.log`（T3 独立复核）
