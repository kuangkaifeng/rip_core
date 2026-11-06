# -*- coding: utf-8 -*-
src = r"D:\work\RIP核心分析\tools\color_tools\fit_gray_calib2.py"
t = open(src, encoding="utf-8").read()
# 替换 PIL ICC 段为“引擎自身 ICC”（调用 mtr_cli gray）
old_start = t.index("# ---- ICC (PIL lcms2) ----")
old_end = t.index("CH_ORDER = [\"C\", \"M\", \"Y\", \"K\"]")
new_icc = '''# ---- 引擎自身 ICC 数值链（mtr_cli gray 输出，避免与 PIL/lcms 版本差异）----
import subprocess
CLI = os.path.join(WS, "build", "mtr_cli.exe")
PRS = os.path.join(WS, "reference", "prs", "A3-DTF-1390.prs").replace("\\\\", "/")
ENGINE_ICC = {}
r = subprocess.run([CLI, "gray", "--prs", PRS, "--mode", "2"],
                   capture_output=True, text=True, cwd=os.path.join(WS, "build"))
assert r.returncode == 0, r.stderr
for line in r.stdout.strip().splitlines():
    parts = [int(x) for x in line.split()]
    ENGINE_ICC[parts[0]] = parts[1:5]
print("engine gray ICC loaded:", len(ENGINE_ICC))


def icc_cmyk(t):
    return tuple(ENGINE_ICC[t])


'''
t = t[:old_start] + new_icc + t[old_end:]
# 输出路径改为 calib_gray_engine.bin
t = t.replace('"calib_gray.bin"', '"calib_gray_engine.bin"')
open(r"D:\work\RIP核心分析\tools\color_tools\fit_gray_calib3.py", "w", encoding="utf-8", newline="").write(t)
print("v3 script written")
