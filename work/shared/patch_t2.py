# -*- coding: utf-8 -*-
# 1) RLE: repeat only for runs >=3 (2 bytes as literal), max 128, line reset
c = r"D:\work\RIP核心分析\src\core\encode\escp2_writer.cpp"
t = open(c, encoding="utf-8").read()
old = """            int run = 1;
            while (i + run < le && data[i + run] == data[i] && run < 128) ++run;
            if (run >= 2) {"""
new = """            int run = 1;
            while (i + run < le && data[i + run] == data[i] && run < 128) ++run;
            if (run >= 3) {   // T2 实测：连续 >=3 字节才用重复段（2 字节走字面量）"""
assert old in t
t = t.replace(old, new)
# 字面量段里的“提前截断”也按 >=3 判断
old2 = """                        int nr = 1;
                        while (i + nr < le && data[i + nr] == data[i] && nr < 128) ++nr;
                        if (nr >= 2) break;"""
new2 = """                        int nr = 1;
                        while (i + nr < le && data[i + nr] == data[i] && nr < 128) ++nr;
                        if (nr >= 3) break;"""
assert old2 in t
t = t.replace(old2, new2)
open(c, "w", encoding="utf-8", newline="").write(t)
print("rle patched")

# 2) owner = 最大 k（T2：行分配取满足条件的最大块号）
e = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t2 = open(e, encoding="utf-8").read()
old3 = """    QHash<int, QPair<int, int>> owner;
    for (int k = 0; k < blocks; ++k) {
        for (int r = 0; r < mode.blockRows; ++r) {
            const int p = pos[k] + vstep * r;
            if (!owner.contains(p))
                owner.insert(p, {k, r});
        }
    }"""
new3 = """    // 页面行归属：取满足 pos_k ≡ p (mod vstep)、pos_k<=p、r<blockRows 的【最大 k】（T2 实测规则）
    QHash<int, QPair<int, int>> owner;
    for (int k = blocks - 1; k >= 0; --k) {
        for (int r = 0; r < mode.blockRows; ++r) {
            const int p = pos[k] + vstep * r;
            if (!owner.contains(p))
                owner.insert(p, {k, r});
        }
    }"""
assert old3 in t2
t2 = t2.replace(old3, new3)
# 3) 清理调试 trace 输出
for line in [
    '    fprintf(stderr, "[trace] buildDevicePlanes start\\n");\n',
    '    fprintf(stderr, "[trace] color done, dither start\\n");\n',
    '    fprintf(stderr, "[trace] dither done, result start\\n");\n',
    '    fprintf(stderr, "[trace] writeEscp2 blocks=%d bpl=%d\\n", blocks, bpl);\n',
    '    fprintf(stderr, "[trace] writer finish\\n");\n',
]:
    t2 = t2.replace(line, '')
open(e, "w", encoding="utf-8", newline="").write(t2)
print("owner patched; traces removed")
