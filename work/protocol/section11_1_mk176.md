
### 11.1 M/K 176×176 256 级补齐（2026-11-06 15:45，task 最后一块）

按与 C176/Y176 完全相同的规范补齐 M、K：

* **512 作业（M、K 各 256 级）全部 result=0，无失败**；PRN 共 160.59 MB。
* 输入 `reference/inputs/probe_scan_{M,K}###_176.tif`（176×176 CMYK TIFF，120dpi，单通道值=t）
  → PRN `reference/prn_samples/probe_scan_{M,K}###_176_a3dtf1390_m2.prn`（A3 mode2）。
* 光栅 N=2,090,880；页面像素 M=1,115,120、K=1,115,119（=1056² 附近）。
* **阈值导出**：`work/protocol/evidence/probe_scan_thresholds_M176.bin` / `_K176.bin`
  （T1[N] T2[N] T3[N] uint16 LE，各 11.96 MiB，布局同 C176/Y176）。
* **精确 D 导出**：`work/protocol/evidence/probe_scan_D_M176.bin` / `probe_scan_D_K176.bin`
  （uint16/N，0..255=D，0xFFFF=空白填充；各 4,181,760 B）。D=258−3·T1。
* **模型验证（各自通道）**：24 个 t 值逐像素对拍 **M：0 差异/26,757,216；K：0 差异/26,757,144**。
* D 统计：范围 3..255、步长 3（85 级，近均匀 ~13,100/级），与 C/Y 一致。
* 摘要：`work/protocol/evidence/probe_scan_D_MK176_summary.json`。

**⚠ 关于互补关系的注意**：在**原始光栅位置**上直接比较
`D_M` vs `258−D_C`、`D_K` vs `258−D_Y`，一致率只有 **0.18%**。原因不是数据错误：
同一图像的 C/M/K/Y 各通道 PRN 微步进（microweave）的**光栅行/记录排布并不相同**
（t=255 时 page mask 交集仅 ~95%，见 `probe_scan_{C,M,K,Y}255_176` PRN），
因此跨通道的“同一扁平索引”并不是同一页面像素。**互补关系必须在内容坐标/1024 tile 坐标下验证**
（T3 侧已有 raster→content 映射）；本批给出的是各通道**直取**的精确 D，不再依赖互补推导。
