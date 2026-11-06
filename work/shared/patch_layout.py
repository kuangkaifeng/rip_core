# -*- coding: utf-8 -*-
# 1) prs_config.h: add colorOffset field
h = r"D:\work\RIP核心分析\src\core\prs_config.h"
t = open(h, encoding="utf-8").read()
old = "    int p0Offset = 640;                // 内容起始相对首块位置的偏移（page unit）"
new = "    int p0Offset = 640;                // 内容起始（K/C 组）相对首块位置的偏移（page unit）\n    int colorOffset = 4;               // M/Y/W 组的额外偏移（= vstep/2，page unit）"
assert old in t
t = t.replace(old, new)
open(h, "w", encoding="utf-8", newline="").write(t)

# 2) prs_config.cpp: compute p0Offset/colorOffset per engine-dev model
c = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t2 = open(c, encoding="utf-8").read()
old2 = """                // 行Step = pageUnit / 图像DPI（运行时按图像内嵌 DPI 计算，120dpi 时为 6/3）
                m.rowStep = m.pageUnit / 120;
                // 内容起点相对首块位置：M + 约 3mm（实测 85@720、43@360 吻合）
                m.p0Offset = m.marginM + static_cast<int>(std::lround(0.11811 * m.pageUnit));
                m.initialAdvance = 0;"""
new2 = """                // 图像行 -> 页面行（120dpi 图像）
                m.rowStep = m.pageUnit / 120;
                const int vstep = m.pageUnit / (m.rasterR / m.rasterV); // 光栅行步进
                // 内容起点（K/C 组）：M + 约 3mm；6-plane 再 + 一个 vstep（实测 m0=288,m1=324,m2=640,m3=680）
                m.p0Offset = m.marginM + static_cast<int>(std::lround(0.11811 * m.pageUnit));
                if (m.planes == 6)
                    m.p0Offset += vstep;
                m.colorOffset = vstep / 2;   // M/Y/(W) 组额外错位（实测 m2: 640+4=644）
                m.initialAdvance = 0;"""
assert old2 in t2
t2 = t2.replace(old2, new2)
open(c, "w", encoding="utf-8", newline="").write(t2)

# 3) rip_engine.cpp: block formula + per-color offset
e = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t3 = open(e, encoding="utf-8").read()
old3 = """    // 块数（MVP 经验公式；见 docs/02_geometry_escp2.md §3.3）
    int blocks = static_cast<int>(std::ceil((contentHUnits + M) / static_cast<double>(adv) + 1.0));
    if (mode.planes == 6) blocks *= 2;
    blocks = qMax(1, blocks);"""
new3 = """    // 块数：N = floor((P0 + H - 1)/adv) + 1（engine-dev 实测公式，m0..m3 全部吻合）
    int blocks = static_cast<int>(std::floor(
        (static_cast<double>(p0) + contentHUnits - 1) / adv)) + 1;
    blocks = qMax(1, blocks);"""
assert old3 in t3
t3 = t3.replace(old3, new3)
# 内容行映射：按颜色组加 offset（K/C=0，M/Y/W=colorOffset）
old4 = """            int imgRow = -1;
            if (isOwner && p >= p0) {
                imgRow = static_cast<int>(std::lround(static_cast<double>(p - p0) / rowStep));
                if (imgRow < 0 || imgRow >= result.height) imgRow = -1;
            }
            for (int c = 0; c < cols.size(); ++c) {"""
new4 = """            for (int c = 0; c < cols.size(); ++c) {
                const bool groupMY = (cols.at(c).ink == INK_M || cols.at(c).ink == INK_Y ||
                                      cols.at(c).ink == INK_W1 || cols.at(c).ink == INK_W2);
                const int p0c = p0 + (groupMY ? mode.colorOffset : 0);
                int imgRow = -1;
                if (isOwner && p >= p0c) {
                    imgRow = static_cast<int>(std::lround(
                        static_cast<double>(p - p0c) / rowStep));
                    if (imgRow < 0 || imgRow >= result.height) imgRow = -1;
                }"""
assert old4 in t3
t3 = t3.replace(old4, new4)
# 把原来 for(c) 内层的 imgRow 引用改成直接使用（原 new2 块里用 imgRow 变量，现在在循环内定义，OK）
# 删除旧的 imgRow 变量重复定义（已在上面的循环中定义，原代码块里引用的 imgRow 仍可用）
open(e, "w", encoding="utf-8", newline="").write(t3)
print("patched layout formulas")
