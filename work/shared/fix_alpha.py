# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
old = """        for (int x = 0; x < imgW; ++x, dst += 4) {
            const int r = line[x * 4 + 0];
            const int g = line[x * 4 + 1];
            const int b = line[x * 4 + 2];
            const int a = line[x * 4 + 3];
            if (a < 255 && job.readTransparency) {
                // 透明像素：按 transparencyToWhite 决定是否漂白
                if (job.transparencyToWhite) {
                    const int rr = (r * a + 255 * (255 - a)) / 255;
                    const int gg = (g * a + 255 * (255 - a)) / 255;
                    const int bb = (b * a + 255 * (255 - a)) / 255;
                    cmyk[(&*dst - cmyk.data()) + 0] = 0; // placeholder (overwritten below)
                    dst[0] = 0; dst[1] = 0; dst[2] = 0; dst[3] = 0;
                    // 简化：透明=白
                    dst[0] = static_cast<uint8_t>(rr > 254 ? 0 : 255 - rr);
                    dst[1] = static_cast<uint8_t>(gg > 254 ? 0 : 255 - gg);
                    dst[2] = static_cast<uint8_t>(bb > 254 ? 0 : 255 - bb);
                    dst[3] = 0;
                    continue;
                }
            }"""
new = """        for (int x = 0; x < imgW; ++x, dst += 4) {
            int r = line[x * 4 + 0];
            int g = line[x * 4 + 1];
            int b = line[x * 4 + 2];
            const int a = line[x * 4 + 3];
            // 透明语义（T3 实测，docs/color_pipeline.md §1）：
            //   readTransparency=true 时 alpha 参与：
            //     - a==0：透明区**不产生墨**（DTF 默认；白底由白墨层承担）
            //     - 0<a<255：按 alpha 与白底合成（边缘淡出）
            //   readTransparency=false：忽略 alpha，透明区按 RGB 内容处理（若为黑则印黑）
            if (a < 255 && job.readTransparency) {
                if (a == 0) {
                    dst[0] = dst[1] = dst[2] = dst[3] = 0;
                    continue;
                }
                r = (r * a + 255 * (255 - a) + 127) / 255;
                g = (g * a + 255 * (255 - a) + 127) / 255;
                b = (b * a + 255 * (255 - a) + 127) / 255;
            }"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("transparency fixed")
