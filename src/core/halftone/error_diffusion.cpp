#include "core/halftone/error_diffusion.h"

#include <algorithm>
#include <cmath>
#include <random>
#include <vector>

namespace mtr {

namespace {

struct Kernel {
    int dx;
    int dy;
    double w;
};

QVector<Kernel> kernelFor(DiffusionKernel k)
{
    switch (k) {
    case DiffusionKernel::Atkinson:
        return {{1, 0, 1.0 / 8}, {2, 0, 1.0 / 8}, {-1, 1, 1.0 / 8},
                {0, 1, 1.0 / 8}, {1, 1, 1.0 / 8}, {0, 2, 1.0 / 8}};
    case DiffusionKernel::JarvisNinke:
        return {{1, 0, 7.0 / 48}, {2, 0, 5.0 / 48},
                {-2, 1, 3.0 / 48}, {-1, 1, 5.0 / 48}, {0, 1, 7.0 / 48},
                {1, 1, 5.0 / 48}, {2, 1, 3.0 / 48},
                {-2, 2, 1.0 / 48}, {-1, 2, 3.0 / 48}, {0, 2, 5.0 / 48},
                {1, 2, 3.0 / 48}, {2, 2, 1.0 / 48}};
    case DiffusionKernel::Stucki:
        return {{1, 0, 8.0 / 42}, {2, 0, 4.0 / 42},
                {-2, 1, 2.0 / 42}, {-1, 1, 4.0 / 42}, {0, 1, 8.0 / 42},
                {1, 1, 4.0 / 42}, {2, 1, 2.0 / 42},
                {-2, 2, 1.0 / 42}, {-1, 2, 2.0 / 42}, {0, 2, 4.0 / 42},
                {1, 2, 2.0 / 42}, {2, 2, 1.0 / 42}};
    case DiffusionKernel::Burkes:
        return {{1, 0, 8.0 / 32}, {2, 0, 4.0 / 32},
                {-2, 1, 2.0 / 32}, {-1, 1, 4.0 / 32}, {0, 1, 8.0 / 32},
                {1, 1, 4.0 / 32}, {2, 1, 2.0 / 32}};
    case DiffusionKernel::Sierra3:
        return {{1, 0, 5.0 / 32}, {2, 0, 3.0 / 32},
                {-2, 1, 2.0 / 32}, {-1, 1, 4.0 / 32}, {0, 1, 5.0 / 32},
                {1, 1, 4.0 / 32}, {2, 1, 2.0 / 32},
                {-1, 2, 2.0 / 32}, {0, 2, 3.0 / 32}, {1, 2, 2.0 / 32}};
    case DiffusionKernel::Sierra2:
        return {{1, 0, 4.0 / 16}, {2, 0, 3.0 / 16},
                {-2, 1, 1.0 / 16}, {-1, 1, 2.0 / 16}, {0, 1, 3.0 / 16},
                {1, 1, 2.0 / 16}, {2, 1, 1.0 / 16}};
    case DiffusionKernel::SierraLite:
        return {{1, 0, 2.0 / 4}, {-1, 1, 1.0 / 4}, {0, 1, 1.0 / 4}};
    case DiffusionKernel::FloydSteinberg:
    default:
        return {{1, 0, 7.0 / 16}, {-1, 1, 3.0 / 16}, {0, 1, 5.0 / 16}, {1, 1, 1.0 / 16}};
    }
}

} // namespace

QVector<uint8_t> diffuse(const QVector<uint8_t> &gray, int width, int height,
                         const DiffusionConfig &cfg)
{
    QVector<uint8_t> out(gray.size(), 0);
    const int levels = std::max(2, cfg.levels);
    const double strength = std::clamp(cfg.strength, 0, 100) / 100.0;
    const double step = 255.0 / (levels - 1);

    if (cfg.kernel == DiffusionKernel::RandomDither) {
        std::mt19937 rng(0x5A17);
        std::uniform_int_distribution<int> dist(0, 255);
        for (int i = 0; i < gray.size(); ++i) {
            const int t = dist(rng);
            out[i] = gray[i] > t ? static_cast<uint8_t>(levels - 1) : 0;
        }
        return out;
    }

    const QVector<Kernel> kern = kernelFor(cfg.kernel);
    std::vector<double> buf(gray.constData(), gray.constData() + gray.size());

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int idx = y * width + x;
            const double oldv = std::clamp(buf[idx], 0.0, 255.0);
            const int q = static_cast<int>(std::lround(oldv / step));
            const int qc = std::clamp(q, 0, levels - 1);
            out[idx] = static_cast<uint8_t>(qc);
            const double err = (oldv - qc * step) * strength;
            for (const Kernel &k : kern) {
                const int nx = x + k.dx;
                const int ny = y + k.dy;
                if (nx < 0 || nx >= width || ny >= height) continue;
                buf[ny * width + nx] += err * k.w;
            }
        }
    }
    return out;
}

} // namespace mtr
