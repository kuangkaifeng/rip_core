# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old = """        // W1/W2
        for (int w = 0; w < 2; ++w) {
            const int ink = (w == 0) ? INK_W1 : INK_W2;"""
new = """        // W1/W2（白墨通道数 = planes - 4：H13 5-plane 只有 W1；A3 6-plane 有 W1/W2）
        const int whiteCount = qBound(0, mode->planes - 4, 2);
        for (int w = 0; w < whiteCount; ++w) {
            const int ink = (w == 0) ? INK_W1 : INK_W2;"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("5-plane fix applied")
