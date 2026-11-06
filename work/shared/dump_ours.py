path = r"D:\work\RIP核心分析\work\shared\ours_black_64_m2.prn"
d = open(path, "rb").read()
print("size", len(d))
for off in range(0, min(len(d), 420), 16):
    chunk = d[off:off+16]
    hx = " ".join("%02x" % c for c in chunk)
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    print("%08x  %-47s  %s" % (off, hx, asc))
