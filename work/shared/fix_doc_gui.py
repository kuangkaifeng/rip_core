p = r"D:\work\RIP核心分析\docs\07_gui.md"
t = open(p, encoding="utf-8").read()
t = t.replace("![GUI 截图](work/shared/gui_shot2.png)", "![GUI 截图](../work/shared/gui_shot2.png)")
open(p, "w", encoding="utf-8", newline="").write(t)
print("doc image path fixed")
