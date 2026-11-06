# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
# 1) 在 RGB->CMYK 循环前加载标定 LUT
old = """    QVector<uint8_t> cmyk(static_cast<qsizetype>(imgW) * imgH * 4, 0);"""
new = """    // ---- 1.5) 灰度轴标定 LUT（由 oracle RGB 中性灰探针拟合，见 tools/color_tools/fit_gray_calib.py）----
    QVector<uint8_t> calibGray;   // 4*256: C,M,Y,K 的 v_icc -> v_oracle
    {
        const QString calibPath =
            QCoreApplication::applicationDirPath() + QStringLiteral("/color/calib_gray.bin");
        QFile cf(calibPath);
        if (cf.exists() && cf.open(QIODevice::ReadOnly)) {
            const QByteArray d = cf.readAll();
            cf.close();
            if (d.size() >= 1024)
                calibGray = QByteArray(d.constData(), 1024);
        }
    }
    QVector<uint8_t> cmyk(static_cast<qsizetype>(imgW) * imgH * 4, 0);"""
assert old in t
t = t.replace(old, new)
# 2) ICC 结果应用标定
old2 = """                dst[0] = out[0]; dst[1] = out[1]; dst[2] = out[2]; dst[3] = out[3];"""
new2 = """                dst[0] = out[0]; dst[1] = out[1]; dst[2] = out[2]; dst[3] = out[3];
                if (calibGray.size() >= 1024) {
                    for (int ci = 0; ci < 4; ++ci)
                        dst[ci] = static_cast<uint8_t>(calibGray[ci * 256 + dst[ci]]);
                }"""
assert old2 in t
t = t.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="").write(t)
print("engine calib applied")
