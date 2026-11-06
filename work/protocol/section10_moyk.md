
## 10. M/Y/K 256 级高精度扫描 + 阈值场提取（2026-11-06 15:20 追加）

**A) M/Y/K 各 256 级（t=0..255 step1）**：768 个作业全部 result=0，无失败。
输入 `reference/inputs/probe_scan_{M,Y,K}###_64.tif`，PRN
`reference/prn_samples/probe_scan_{M,Y,K}###_a3dtf1390_m2.prn`；单通道 PRN 大小 264B(t=0)..~51.7KB，
三通道各约 12.2-12.3 MB。清单 `work/protocol/evidence/probe_scan_manifest.json`（1075 条）。

* 量化律验证（A3 mode2）：max |平均点值−3t/255| = M **0.000857**、Y **0.000864**、K **0.000312**。
* 颜色码↔墨：M→`0x12`、Y→`0x11`、K→`0x04`、C→`0x00`。
* **阈值场已导出**：`work/protocol/evidence/probe_scan_thresholds_{M,Y,K}.bin`
  （各 T1[449280] T2[449280] T3[449280]，uint16 LE，布局与 C 版相同；
  只需 T1>0 的约 147,4xx 个页面像素）。
  三通道均 T1∈[1,85]，T2−T1、T3−T2 集中于 84/85/86，与 C 完全同构。
* **D 估计**：`T1 = ceil((256−D)/3)` ⇒ **D ∈ [256−3·T1, 258−3·T1]**。
* **跨通道独立性**：与 C 的 T1 在相同位置相同的比例仅
  M 1,680/138,466（1.2%）、Y 1,761/139,159（1.3%）、K 1,693/140,236（1.2%）
  ⇒ **D 场每通道独立**（确认 Team 模型“每通道独立随机阈值场”）。摘要：
  `work/protocol/evidence/probe_scan_thresholds_MYK_summary.json`。

**B) C=64、720x720（tile 周期探测）**：`probe_scan_C64_720.tif` → PRN **5,494,356 B**；
页面横向 4320 px（n=1080 bytes×4），blocks=63、advance=79，ESC_S.width=4320。
C 覆盖 ink=14,051,353 px / (4320×4320) = **75.29%**（=3·64/255，律成立）。
与 64x64 的 C064 对比：在相同 x=0..383 处，前 433 内容行中 124/173 行内容相同
（差异来自两者微步进行映射不同），供判断 D 场 tile 周期/相位用。

**C) margin 探针（D 场索引坐标判定）**：
`probe_scan_C64_marginT100_64.tif`（margin=[0,100,0,0]）→ 51,535 B；
`probe_scan_C64_marginL100_64.tif`（margin=[100,0,0,0]）→ 108,787 B。

* **纵向 margin 不改变栅格数据**：marginT 与无 margin 的 C64 在全部 433 个内容行的
  96 字节内容**逐字节相同**（垂直偏移由页面定位实现）⇒ D 的垂直索引是内容相对；
* **横向 margin 改变阈值采样**：marginL 内容右移 2832 px（2832/4=708 字节），
  在任何字节对齐下内容都与无 margin 不同 ⇒ D 的横向索引包含左边距（按栅格/绝对 X 采样）。
* 结论供 Team 拟合：D 场很可能是“内容 Y + 绝对/栅格 X”索引的随机场；B 的 720 版可继续验证 tile。

**复现**：`python work/protocol/exp_scan_moyk256.py`（生成 768+3 输入并串行跑，约 6-8 分钟）→
`python work/protocol/rebuild_manifest_moyk.py`（修正/补全 manifest）→
`python work/protocol/extract_moyk_thresholds.py`（提取 M/Y/K 阈值场 + 跨通道对比）。
