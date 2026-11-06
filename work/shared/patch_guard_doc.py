# -*- coding: utf-8 -*-
# 1) rip_engine: modeId>=4 时警告（加网/色彩标定仅对 mode2 验证）
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old = """    // 2) 图像
    QImage image;"""
new = """    // 1.5) 未验证模式告警：加网 tile 与灰度标定目前仅对 A3 mode2(720x720) 实测验证；
    //      m5/m7/m9（高质量档）未验证，结果仅作"可打印"近似，勿用于验收。
    if (prs.version == 3 && job.modeId >= 4) {
        qWarning("mtr: modeId=%d 的加网 tile/色彩标定尚未验证（仅 mode2 验证通过）；"
                 "输出可用但非逐像素保证。", job.modeId);
    }

    // 2) 图像
    QImage image;"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("rip_engine guard added")

# 2) docs/06_validation.md: 记录 oracle 探针缺陷与验收口径
d = r"D:\work\RIP核心分析\docs\06_validation.md"
t2 = open(d, encoding="utf-8").read()
add = """

## 13. 加网最终对账：oracle 探针语料自身缺陷（重要验收口径）

### 13.1 发现
engine-dev 用独立 C++ 解码器对 **1024 个 tone 探针（4 通道 × 256 级）** 全量核对：
- 972/1024 探针 **100.0000%** 一致；
- 其余 52 个探针（**13 个 tone × 4 ink**，tone 集合 =
  `[93,95,101,106,151,161,166,186,202,230,242,244,253]`）各恰 **16 像素**不一致（最差 99.9985%）。

逐字节审计（T3 独立实现，不经过解码器）确认这 **832 个异常 cell 完全一致（0 未解释/0 遗漏）**：
- 异常像素全部是 tile 中 `T3==0`（D<3，满级=2）的像素；
- 这些 cell 上 **oracle 自身非单调**：同一像素 level 随 tone 升高而"掉回 0"
  （例：C page(693,296) t=91/92/94 dot=1，而 t=93/95 dot=0；K page(644,948) t=228/229/231/232 dot=2，t=230 dot=0）；
- 缺陷 tone 集合四通道完全相同，横跨四套独立作业族 ⇒ 判断为**蒙泰侧系统性缺陷/非确定性**
  （疑似阈值=256 存 8-bit 时回绕成 0 的边界分支），**不是加网 tile 错误**。

### 13.2 最终验收口径
- **排除这 832 个 oracle 非单调 cell 后：1024/1024 探针 = 100.0000%**；
- 因此"对 oracle 全 256 tone 100% 一致"在数学上不可达（oracle 自身违反单调性），
  验收应使用 `tools/validate/verify_screen_probes.py --audit work/prs/oracle_screen_audit.json`；
- tile 保持定稿 `reference/screen/final/`（1024² 四通道直取，meta v6），不做多数投票重拟合（会掩盖 oracle 缺陷）；
- 审计数据：`work/prs/oracle_screen_audit.json`，工具：`tools/prs_tools/audit_oracle_screen.py`。

### 13.3 未验证项标注
- **modeId≥4（m5/m7/m9）**：加网 tile 与灰度标定仅对 mode2 实测验证；引擎已加运行时警告
  （`mtr: modeId>=4 ... 尚未验证`）。待 T1 补 C 通道 256 级 × mode5 探针、T3 验证 tile 复用性后再启用。
- 蒙泰侧确定性复核（52 个作业各重跑 2 次 diff）由 T1 执行、engine-dev 记录（见 engine_status.md §3.5）。
"""
if "oracle 探针语料自身缺陷" not in t2:
    open(d, "w", encoding="utf-8", newline="").write(t2 + add)
    print("validation doc updated (oracle defect)")
