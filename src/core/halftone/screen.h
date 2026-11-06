// ============================================================================
// screen.h —— 蒙泰 stochastic FM 2bit 加网复刻
//
// 由探针语料（T1：单通道恒定墨值 CMYK TIFF → PRN）反推出的模型：
//   设 t = 设备墨值 0..255，
//   base = 3 * t / 255        （0..3 的连续级）
//   frac = base - floor(base)
//   level = floor(base) + (frac > U(x,y) ? 1 : 0)
// 其中 U(x,y) ∈ [0,1) 是固定的 stochastic/FM 阈值场（每通道可带相位偏移）。
// U 的提取：对同一像素用多个 t 的探针 PRN 联立求解（t 步长 1 可把 U 精确到
// 3/255 的量化格）。数据文件格式见 docs/color_pipeline.md 的加网一节。
// ============================================================================
#pragma once

#include <QString>
#include <QVector>
#include <QByteArray>
#include <cstdint>

namespace mtr {

struct ScreenChannel {
    // 阈值场（0..255 映射到 [0,1)），尺寸 size×size，按 (x%size, y%size) 取样
    int size = 64;
    // 每像素 3 字节阈值 [T1,T2,T3]：level = (v>=T1)+(v>=T2)+(v>=T3)
    QVector<uint8_t> threshold;   // size*size*3
    int phaseX = 0;               // 每通道可选的相位偏移（页面点坐标）
    int phaseY = 0;
};

class Screen {
public:
    // 从目录加载（thr_C.bin / thr_M.bin / thr_Y.bin / thr_K.bin + screen.json 元数据）
    bool load(const QString &dir, QString *err = nullptr);
    bool isLoaded() const { return m_loaded; }

    // 内置兜底：确定性蓝噪声（用于未提供阈值场时先跑通管线）
    void useFallback(int size = 64);

    // 单通道连续调墨量（每像素 0..255）→ 2bit level（0..3）
    // channel: 0=C,1=M,2=Y,3=K（对应 ScreenChannel 索引）
    void dither(const QVector<uint8_t> &ink, int width, int height, int channel,
                QVector<uint8_t> *level) const;

    // 逐级 tone→level 映射（不依赖阈值场，用于调试）
    static int toneToLevel(int t);

    QString lastError() const { return m_lastError; }

private:
    QVector<ScreenChannel> m_channels;
    bool m_loaded = false;
    QString m_lastError;
};

} // namespace mtr
