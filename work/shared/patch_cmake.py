# -*- coding: utf-8 -*-
# 1) CMake: add screen.cpp
p = r"D:\work\RIP核心分析\src\CMakeLists.txt"
t = open(p, encoding="utf-8").read()
if "halftone/screen.cpp" not in t:
    t = t.replace("    core/halftone/error_diffusion.cpp\n",
                  "    core/halftone/error_diffusion.cpp\n    core/halftone/screen.cpp\n")
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("cmake: screen.cpp added")

# 2) prs_config.h: add ESC/P2 mode params fields
p2 = r"D:\work\RIP核心分析\src\core\prs_config.h"
t2 = open(p2, encoding="utf-8").read()
old = """    QString dpiText;                   // 例如 "v720x720dpi"
    QString inkText;                   // 例如 "CMYK" / "CMYKW1W2"
    int recordIndex = -1;              // 对应 .prs 内 mode 记录（-1=无，走缺省）
};"""
new = """    QString dpiText;                   // 例如 "v720x720dpi"
    QString inkText;                   // 例如 "CMYK" / "CMYKW1W2"
    int recordIndex = -1;              // 对应 .prs 内 mode 记录（-1=无，走缺省）

    // ---- ESC/P2（A3-DTF-1390）版面参数（实测/工具推导，见 docs/02_geometry_escp2.md）----
    int pageUnit = 720;                // ESC(U 的 page unit（单位/英寸）
    int uA = 4, uV = 4, uH = 4;        // ESC(U 的三个比值（2880/值 = unit）
    int rasterR = 1440, rasterV = 16, rasterH = 2; // ESC(D)
    int marginM = 555;                 // ESC(c/S 的页边距常数（page unit）
    int advance = 79;                  // 块推进（page unit）
    int rowStep = 6;                   // 图像行 -> 页面行（page unit/图像行）
    int p0Offset = 640;                // 内容起始相对首块位置的偏移（page unit）
    int blockRows = 90;                // m
    int initialAdvance = 0;            // 首块前 ESC(v（可为 0 = 不写）
};"""
assert old in t2
t2 = t2.replace(old, new)
open(p2, "w", encoding="utf-8", newline="").write(t2)
print("prs_config.h: esc params added")
