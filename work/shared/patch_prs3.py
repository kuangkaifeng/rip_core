# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t = open(p, encoding="utf-8").read()
start = t.index("void PrsConfig::parseModeTable()")
end = t.index("const PrsMode *PrsConfig::mode(int modeId) const")
new_func = r'''void PrsConfig::parseModeTable()
{
    modes.clear();

    struct EscDef {
        int pageUnit, uA, uV, uH, r, v, h, M, adv;
    };
    // A3-DTF-1390（v3）的 10 个基础模式参数（按 modeId%10；实测见 docs/02_geometry_escp2.md）
    static const EscDef a3[10] = {
        {360, 8, 8, 4, 1440, 16, 2, 245, 71},   // mode0: CMYK      720x360
        {360, 8, 8, 4, 1440, 16, 2, 277, 35},   // mode1: CMYKW1W2  720x360
        {720, 4, 4, 4, 1440, 16, 2, 555, 79},   // mode2: CMYK      720x720
        {720, 4, 4, 4, 1440, 16, 2, 587, 39},   // mode3: CMYKW1W2  720x720
        {720, 4, 4, 2, 1440, 16, 4, 627, 11},   // mode4: CMYK      1440x720
        {720, 4, 4, 2, 1440, 16, 4, 627, 11},   // mode5: CMYKW1W2  1440x720
        {1440, 2, 2, 2, 1440, 16, 4, 1227, 11}, // mode6: CMYK      1440x1440
        {1440, 2, 2, 2, 1440, 16, 4, 1227, 11}, // mode7: CMYKW1W2  1440x1440
        {1440, 2, 2, 1, 1440, 16, 2, 1227, 11}, // mode8: CMYK      2880x1440
        {1440, 2, 2, 1, 1440, 16, 2, 1227, 11}, // mode9: CMYKW1W2  2880x1440
    };

    struct BaseDef {
        int x, y, planes;
        bool cc;
        const char *dpi;
        const char *ink;
    };
    static const BaseDef a3Base[10] = {
        {720, 360, 4, false, "v720x360dpi", "CMYK"},
        {720, 360, 6, false, "v720x360dpi", "CMYKW1W2"},
        {720, 720, 4, false, "v720x720dpi", "CMYK"},
        {720, 720, 6, false, "v720x720dpi", "CMYKW1W2"},
        {1440, 720, 4, false, "v1440x720dpi", "CMYK"},
        {1440, 720, 6, true, "v1440x720dpi", "CMYKW1W2"},
        {1440, 1440, 4, false, "v1440x1440dpi", "CMYK"},
        {1440, 1440, 6, true, "v1440x1440dpi", "CMYKW1W2"},
        {2880, 1440, 4, false, "v2880x1440dpi", "CMYK"},
        {2880, 1440, 6, true, "v2880x1440dpi", "CMYKW1W2"},
    };

    if (version == 3) {
        for (int paper = 0; paper < 3; ++paper) {
            for (int i = 0; i < 10; ++i) {
                PrsMode m;
                m.modeId = paper * 10 + i;
                m.xDPI = a3Base[i].x;
                m.yDPI = a3Base[i].y;
                m.planes = a3Base[i].planes;
                m.colorCorrection = a3Base[i].cc;
                m.dpiText = QString::fromLatin1(a3Base[i].dpi);
                m.inkText = QString::fromLatin1(a3Base[i].ink);
                m.pageUnit = a3[i].pageUnit;
                m.uA = a3[i].uA;
                m.uV = a3[i].uV;
                m.uH = a3[i].uH;
                m.rasterR = a3[i].r;
                m.rasterV = a3[i].v;
                m.rasterH = a3[i].h;
                m.marginM = a3[i].M;
                m.advance = a3[i].adv;
                m.blockRows = 90;
                // rowStep = pageUnit / 图像DPI（运行时按图像内嵌 DPI 计算，120dpi 时为 6/3）
                m.rowStep = m.pageUnit / 120;
                // 内容起点相对首块位置：M + 约 3mm（实测 85@720、43@360 吻合）
                m.p0Offset = m.marginM + static_cast<int>(std::lround(0.11811 * m.pageUnit));
                m.initialAdvance = 0;
                modes.append(m);
            }
        }
    } else {
        // H13 XP600（HSSF 0x5555）：4 个模式全部 CMYKW1 + 校色
        static const int ys[4] = {720, 1080, 1440, 2160};
        static const char *names[4] = {"V720x720 dpi", "V720x1080 dpi",
                                       "V720x1440 dpi", "V720x2160 dpi"};
        for (int i = 0; i < 4; ++i) {
            PrsMode m;
            m.modeId = i;
            m.xDPI = 720;
            m.yDPI = ys[i];
            m.planes = 5;
            m.colorCorrection = true;
            m.dpiText = QString::fromLatin1(names[i]);
            m.inkText = QStringLiteral("CMYKW1");
            m.blockRows = 90;
            modes.append(m);
        }
    }
}

'''
t = t[:start] + new_func + t[end:]
open(p, "w", encoding="utf-8", newline="").write(t)
print("parseModeTable rewritten")
