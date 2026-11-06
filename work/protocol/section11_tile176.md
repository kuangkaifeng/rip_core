
## 11. 1024 阈值 tile 补测：C/Y 176×176 256 级 + 精确 D 场（2026-11-06 15:35）

背景：D 已确认是 **1024×1024 固定 tile、按内容相对坐标索引**；此前 64×64 探针只覆盖 tile 左上
384×384。本批用 176×176 输入（内容 1056×1056 输出像素 > 1024）一次覆盖整 tile。

* **512 个作业（C、Y 各 256 级）全部 result=0，无失败**；PRN 共 160.54 MB。
* 命名（重要）：为避免覆盖已有 64×64 探针，PRN/job stem 显式加 `_176`：
  * 输入 `reference/inputs/probe_scan_C###_176.tif` / `probe_scan_Y###_176.tif`（###=000..255）
  * PRN `reference/prn_samples/probe_scan_C###_176_a3dtf1390_m2.prn`（Y 同理）
  * 作业 JSON/响应 `reference/jobs/probe_scan_*_176_a3dtf1390_m2.{json,resp.json}`
  * 清单 `work/protocol/evidence/probe_scan_manifest.json` 新增 kind `C176`/`Y176` 512 条。
* 光栅几何：176 px @120 dpi → mode2 下 1056×1056 页面像素；解码后 N=**2,090,880** 个光栅位置
  （n=264 字节×4=1056 px/行，m=90 行/record，blocks=22），其中页面像素 **1,115,136=1056²**，
  其余为微步进空白填充行（T1=0）。
* **阈值导出**（按请求命名）：
  `work/protocol/evidence/probe_scan_thresholds_C176.bin` / `probe_scan_thresholds_Y176.bin`
  ＝ T1[N] T2[N] T3[N]（各 uint16 LE，N=2,090,880，共 11.96 MiB/文件；
  布局与 64×64 版一致：block-major→record-major→row-major、4 px/byte LSB-first）。
* **精确 D 场导出**：`probe_scan_D_C176.bin` / `probe_scan_D_Y176.bin`
  （每个 4,181,760 B：uint16/N；0..255 = D，0xFFFF = 空白填充位置；光栅顺序同 T1 文件）。
  推导：主映射 (T2−T1,T3−T2)=(85,85) ⇒ **D = 258−3·T1**；C/Y 各有 238/240 个边缘异常位置留 0xFFFF。
* **模型 100% 验证**：用 D 重建 `level=(3t+D)>>8`，与解码 PRN 在 24 个 t 值
  （0,1,2,8,16,…,240,254,255）逐像素对比：
  **C：0 差异 / 26,757,552 次比较；Y：0 差异 / 26,757,504 次比较。**
* D 统计：范围 **3..255、步长 3（共 85 级，直方图近似均匀，约 13,100/级）**
  ⇒ 有效阈值分辨率为 3/255（85 级）；（T1=1..85 与 D=3..255 一一对应）。
* 摘要：`work/protocol/evidence/probe_scan_D_176_summary.json`、
  `probe_scan_thresholds_176_summary.json`。
* `probe_scan_C64_720` 的 tile 周期证据继续保留（PRN 5,494,356 B）。

**复现**：
`python work/protocol/exp_scan_tile176.py`（生成 512 输入并串行跑，实测 25 s）
→ `python work/protocol/extract_tile176_thresholds.py`（导出 T1/T2/T3）
→ `python work/protocol/derive_D_tile176.py`（导出 D 并做全量抽样验证；需 numpy）。
