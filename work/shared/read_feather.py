t = open(r"D:\work\RIP核心分析\work\shared\engine_status.md", encoding="utf-8").read()
i = t.find("### 4.3")
if i < 0: i = t.find("4.3")
print(t[max(0,i-200): i+2600] if i>=0 else "not found")
