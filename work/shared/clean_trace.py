# 清理调试 trace
import re
for p in [r"D:\work\RIP核心分析\src\main.cpp", r"D:\work\RIP核心分析\src\core\rip_engine.cpp"]:
    t = open(p, encoding="utf-8").read()
    lines = [ln for ln in t.split("\n") if "[trace]" not in ln]
    t2 = "\n".join(lines)
    if t2 != t:
        open(p, "w", encoding="utf-8", newline="").write(t2)
        print("cleaned", p)
