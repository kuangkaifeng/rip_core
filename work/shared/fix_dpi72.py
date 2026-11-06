# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old = """int imageDpi(const QImage &img)
{
    const int dpm = img.dotsPerMeterX();
    if (dpm <= 0) return 120;
    return static_cast<int>(std::lround(dpm * 0.0254));
}"""
new = """int imageDpi(const QImage &img)
{
    const int dpm = img.dotsPerMeterX();
    // 无内嵌 DPI 时蒙泰按 72dpi 处理（oracle 实测：860x564 无 DPI JPEG -> 内容 8600x5640）
    if (dpm <= 0) return 72;
    return static_cast<int>(std::lround(dpm * 0.0254));
}"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("default dpi -> 72")
