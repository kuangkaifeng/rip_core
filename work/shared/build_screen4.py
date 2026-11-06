# -*- coding: utf-8 -*-
import struct, json, os
WS = r"D:\work\RIP核心分析"
EV = os.path.join(WS, "work", "protocol", "evidence")
OUT = os.path.join(WS, "build", "screen")
os.makedirs(OUT, exist_ok=True)
N = 449280
SIZE = 384
POS = [79 * k for k in range(13)]

def load_bin(path):
    raw = open(path, "rb").read()
    assert len(raw) >= 3 * N * 2, (path, len(raw))
    return [struct.unpack_from("<%dH" % N, raw, c * N * 2) for c in range(3)]

# 通道 -> 源 bin（C 用最早的 probe_scan_thresholds.bin；M/Y/K 用 T1 新导出）
sources = {
    "C": os.path.join(EV, "probe_scan_thresholds.bin"),
    "M": os.path.join(EV, "probe_scan_thresholds_M.bin"),
    "Y": os.path.join(EV, "probe_scan_thresholds_Y.bin"),
    "K": os.path.join(EV, "probe_scan_thresholds_K.bin"),
}
meta = {"size": SIZE, "channels": [], "note": "exact 256-level probe scan (T1) -> 3 thresholds per pixel"}
for name in ["C", "M", "Y", "K"]:
    path = sources[name]
    if not os.path.exists(path):
        print("missing", name, path); continue
    T = load_bin(path)
    field = [[None] * (SIZE * SIZE) for _ in range(3)]
    owner = [False] * (SIZE * SIZE)
    for k in range(13):
        for r in range(90):
            p = POS[k] + 8 * r
            if not (640 <= p <= 1023):
                continue
            prow = p - 640
            base = ((k * 90) + r) * 384
            for x in range(384):
                idx = base + x
                if T[0][idx] == 0:
                    continue
                pidx = prow * 384 + x
                if not owner[pidx]:
                    for c in range(3):
                        field[c][pidx] = T[c][idx]
                    owner[pidx] = True
    owned = sum(owner)
    data = bytearray(SIZE * SIZE * 3)
    for i in range(SIZE * SIZE):
        t1 = field[0][i] if field[0][i] is not None else 1
        t2 = field[1][i] if field[1][i] is not None else 86
        t3 = field[2][i] if field[2][i] is not None else 171
        data[i*3+0] = min(t1, 255); data[i*3+1] = min(t2, 255); data[i*3+2] = min(t3, 255)
    fn = "thr_%s.bin" % name
    open(os.path.join(OUT, fn), "wb").write(bytes(data))
    meta["channels"].append({"ink": name, "file": fn, "approx": False, "phaseX": 0, "phaseY": 0})
    print(name, "owned=", owned, "->", fn)
json.dump(meta, open(os.path.join(OUT, "screen_meta.json"), "w", encoding="utf-8"), indent=1)
print("4-channel exact screen data written")
