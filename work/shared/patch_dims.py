# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old = """    // ---- 内容点阵尺寸（打印分辨率下的点阵）----
    const int contentWDots = qMax(1, static_cast<int>(std::lround(
        static_cast<double>(imgW) * mode->xDPI / dpi)));
    const int contentHDots = qMax(1, static_cast<int>(std::lround(
        static_cast<double>(imgH) * mode->yDPI / dpi)));"""
new = """    // ---- 内容点阵尺寸（打印分辨率下的点阵）----
    // A3-DTF-1390（ESC/P2）：几何以 escp2ModeParams 实测表为准（m5/m7/m9 与 PrsConfig 的 dpi 字符串不同）
    int contentWDots = 0;
    int contentHDots = 0;
    if (prs.version == 3) {
        const Escp2ModeParams mp = escp2ModeParams(job.modeId);
        const int hdpi = qMax(1, mp.rasterR / qMax(1, mp.rasterH));
        contentWDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgW) * hdpi / dpi)));
        contentHDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgH) * mp.pageUnit / dpi)));
    } else {
        contentWDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgW) * mode->xDPI / dpi)));
        contentHDots = qMax(1, static_cast<int>(std::lround(
            static_cast<double>(imgH) * mode->yDPI / dpi)));
    }"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("content dims patched")
