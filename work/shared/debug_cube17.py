import os
WS = r"D:\work\RIP核心分析"
CONTENT = 6817
PLANES = os.path.join(WS, "work", "shared", "cube17_planes")
plane = open(os.path.join(PLANES, "content_0_04.w6817h6817.bin"), "rb").read()
tile = open(os.path.join(WS, "3rdparty", "screen", "thr_K.bin"), "rb").read()

def pred_level(x, y, v):
    ti = ((y % 1024) * 1024 + (x % 1024)) * 3
    t1, t2, t3 = tile[ti], tile[ti+1], tile[ti+2]
    p = (1 if v >= t1 else 0) + (1 if v >= t2 else 0) + (1 if v >= t3 else 0)
    return min(3, p)

# patch 0 (black) center content (48,48)
cx, cy = 48, 48
print("patch0 K plane values around center (x=30..40, y=48):")
print(" actual:", [plane[48*CONTENT + x] for x in range(30,41)])
print(" pred229:", [pred_level(x, 48, 229) for x in range(30,41)])
# 统计窗口 60x60 mean & match for candidates
for v in (228, 229, 230):
    eq = tot = 0
    for y in range(cy-30, cy+30):
        base = y*CONTENT
        for x in range(cx-30, cx+30):
            if pred_level(x,y,v) == plane[base+x]: eq += 1
            tot += 1
    print("v=%d match=%.5f" % (v, eq/tot))
mean = sum(sum(plane[y*CONTENT+cx-30: y*CONTENT+cx+30]) for y in range(cy-30, cy+30)) / 3600.0
print("observed mean level:", round(mean,4), " expected 3v/255 for v229:", round(3*229/255,4))
