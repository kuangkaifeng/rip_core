// ============================================================================
// error_diffusion.h —— 误差扩散抖动（FM 类加网）
// 提供多种核（Floyd-Steinberg / Atkinson / Jarvis / Stucki / Burkes / Sierra 等）
// 与蒙泰 FM 加网做对比实验用。
// ============================================================================
#pragma once

#include <QVector>
#include <cstdint>

namespace mtr {

enum class DiffusionKernel {
    FloydSteinberg = 0,
    Atkinson,
    JarvisNinke,
    Stucki,
    Burkes,
    Sierra3,
    Sierra2,
    SierraLite,
    RandomDither
};

struct DiffusionConfig {
    DiffusionKernel kernel = DiffusionKernel::FloydSteinberg;
    int levels = 4;      // 输出级数（2bit=4）
    int strength = 100;  // 误差扩散强度 %
};

QVector<uint8_t> diffuse(const QVector<uint8_t> &gray, int width, int height,
                         const DiffusionConfig &cfg);

} // namespace mtr
