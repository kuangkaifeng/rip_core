# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
# 1) 白墨：仅当 inputColorEditor 显式指定才启用（H13 无 W 参数时 oracle W1 为空）
old = """            if (!enabled && w == 0)
                enabled = true; // 6-plane 模式默认 W1 full（生产作业总会带 W1）"""
new = """            // 注意：oracle 实测——没有 inputColorEditor(W1) 参数时 W1 平面为全 0
            //（H13 mode0 probe_black_64 样本 W1 ink=0）；因此不要默认启用。"""
assert old in t
t = t.replace(old, new)
# 2) HSSF reserved 与 oracle 样本对齐为 0（T4：两种写法均可，但 0 才逐字节一致）
old2 = """    hc.dotBits = 2;
    hc.passCount = 1;
    hc.rowsPerStore = 1;"""
new2 = """    hc.dotBits = 0;      // 与 oracle 样本对齐：reserved[0..2] = 0（板卡侧 pass 不由此决定）
    hc.passCount = 0;
    hc.rowsPerStore = 0;"""
assert old2 in t
t = t.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("fixed W1 default + HSSF reserved")
