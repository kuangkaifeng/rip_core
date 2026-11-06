from PIL import Image
import os, json
paths = [r"D:\Code\kkf\v1.1.2\rip-studio\bin\bin\temp\pic\1793946733018.png",
         r"D:\work\RIP核心分析\reference\inputs\golden_1793946733018.png"]
for p in paths:
    if os.path.exists(p):
        im = Image.open(p)
        print(p, "size=", im.size, "dpi=", im.info.get("dpi"), "dpm=", im.info.get("dpi"))
    else:
        print(p, "MISSING")
j = json.load(open(r"D:\work\RIP核心分析\reference\jobs\golden_repro_1793946733280.json", encoding="utf-8"))
print("golden job doc.name:", j["doc"]["name"])
print("golden job keys:", {k: (v if k not in ("inputColorEditor","inkIE","view","color","range") else v) for k,v in j.items() if k in ("modeId","rotate","scale","margin","view")})
print("inputColorEditor:", j.get("inputColorEditor"))
