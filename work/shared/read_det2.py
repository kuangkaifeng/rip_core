import json
p = r"D:\work\RIP核心分析\work\protocol\evidence\screen_nondeterminism.json"
d = json.load(open(p, encoding="utf-8"))
print(json.dumps(d["summary"], indent=1, ensure_ascii=False))
