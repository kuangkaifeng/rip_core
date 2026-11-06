# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include <cstring>', '#include <cstring>\n#include <cstdio>')
# trace in buildDevicePlanes
t = t.replace('    const int imgW = image.width();',
              '    fprintf(stderr, "[trace] buildDevicePlanes start\\n");\n    const int imgW = image.width();')
t = t.replace('    // ---- 3) 加网（FM stochastic 2bit）----',
              '    fprintf(stderr, "[trace] color done, dither start\\n");\n    // ---- 3) 加网（FM stochastic 2bit）----')
t = t.replace('    // ---- 4) 结果 ----',
              '    fprintf(stderr, "[trace] dither done, result start\\n");\n    // ---- 4) 结果 ----')
# trace in writeEscp2
t = t.replace('    Escp2Writer writer(cfg);\n    writer.begin();',
              '    fprintf(stderr, "[trace] writeEscp2 blocks=%d bpl=%d\\n", blocks, bpl);\n    Escp2Writer writer(cfg);\n    writer.begin();')
t = t.replace('    const QByteArray prn = writer.finish();',
              '    fprintf(stderr, "[trace] writer finish\\n");\n    const QByteArray prn = writer.finish();')
open(p, "w", encoding="utf-8", newline="").write(t)
print("traces added")
