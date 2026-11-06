# -*- coding: utf-8 -*-
import json, os
WS = r"D:\work\RIP核心分析"
job = {
  "command": "rip",
  "doc": {"name": WS.replace("\\","/") + "/reference/inputs/print_debug_test22.jpg"},
  "prs": WS.replace("\\","/") + "/reference/prs/A3-DTF-1390.prs",
  "modeId": 2,
  "range": [[1,1]],
  "output": {"mode":"file","file":{"name": WS.replace("\\","/")+"/work/shared/print_debug/ours_test22_m2.prn","mode":438}},
  "rotate": 0, "scale": [100,100], "margin":[0,0,0,0],
  "view": {"xdpi":120,"ydpi":120},
  "color": {"readTransparency": True, "transparencyToWhite": False},
  "inkIE": [{"index":4,"mode":"invaginate","dots":[10,10,10,10]}],
  "inputColorEditor": [{"inkName":"W1","invert":False,"mode":"full"}],
}
p = os.path.join(WS, "work", "shared", "print_debug", "job_test22_m2.json")
json.dump(job, open(p, "w", encoding="utf-8"), indent=1)
print("job written", p)
