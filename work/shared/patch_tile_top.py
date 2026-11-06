p = r"D:\work\RIP核心分析\tools\color_tools\build_tile1024_from_D.py"
t = open(p, encoding="utf-8").read()
t = t.replace("""CH = {"C": "probe_scan_D_C176.bin", "M": "probe_scan_D_M176.bin",
      "Y": "probe_scan_D_Y176.bin", "K": "probe_scan_D_K176.bin"}""",
"""CH = {"C": "probe_scan_D_C176.bin", "M": "probe_scan_D_M176.bin",
      "Y": "probe_scan_D_Y176.bin", "K": "probe_scan_D_K176.bin"}
# 各通道内容顶行（页面行）：C/K=640，M/Y=644（实测，见 docs/prn_escp2.md）
TOP = {"C": 640, "M": 644, "Y": 644, "K": 640}""")
t = t.replace("def build_tile(fname):", "def build_tile(fname, top):")
t = t.replace("            i = p - P0\n", "            i = p - top\n")
t = t.replace("    tile = build_tile(fname)", "    tile = build_tile(fname, TOP[ink])")
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched per-channel top")
