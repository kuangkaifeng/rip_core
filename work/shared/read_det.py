import json, os
p = r"D:\work\RIP核心分析\work\protocol\evidence\screen_nondeterminism.json"
d = json.load(open(p, encoding="utf-8"))
print("top keys:", list(d.keys())[:10])
for k, v in d.items():
    if isinstance(v, dict):
        print("\n==", k, "keys:", list(v.keys())[:8])
    elif isinstance(v, list):
        print("\n==", k, "list len", len(v), "sample:", v[:2])
    else:
        print("\n==", k, "=", v)
