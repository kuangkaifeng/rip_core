// ============================================================================
// rgb_cube_lut.h —— RGB 9×9×9 三维 LUT（蒙泰 A3-DTF-1390 mode2 实测反解）
//
// 文件格式（magic "RGB9"）：
//   u8  [4]  magic = "RGB9"
//   u16 [1]  size  = 9（每轴格点数）
//   u8  [1]  channels = 4（C,M,Y,K）
//   u8  [729*4] 数据：索引 = ((rIndex*size + gIndex)*size + bIndex) + channel*729
//                （r-major, g, b-minor；每 ink 顺序 C,M,Y,K）
//
// 轴网格值（非均匀，末端 224→255 间距 31）：
//   GRID = {0,32,64,96,128,160,192,224,255}
//
// 用法：load() 后对任意 8bit RGB 做三线性插值 → 设备墨值 C,M,Y,K（0..255）。
// 资源缺失时 isReady()==false，调用方回退旧的 ICC+灰度标定路径。
// ============================================================================
#pragma once

#include <QByteArray>
#include <QString>

namespace mtr {

class RgbCubeLut {
public:
    static constexpr int kSize = 9;
    static constexpr int kGridPoints = kSize * kSize * kSize;   // 729
    static constexpr int kChannels = 4;

    // 默认路径：resolveResourceDir("color")/rgb_cube9.bin
    static QString defaultPath();

    // 加载；失败返回 false 并给 err（文件缺失/魔数错误/尺寸不符）
    bool load(const QString &path, QString *err = nullptr);
    bool loadFromData(const QByteArray &data, QString *err = nullptr);

    bool isReady() const { return m_ready; }
    int size() const { return m_size; }

    // 三线性插值；out[0..3] = C,M,Y,K（0..255）。未加载时返回 false。
    bool lookup(int r, int g, int b, unsigned char out[kChannels]) const;
    // 四面体插值（3D LUT 常用，非线性区域精度通常优于三线性；实验开关用）
    bool lookupTetrahedral(int r, int g, int b, unsigned char out[kChannels]) const;

    // 轴网格（供测试/调试）
    static const int *grid();

private:
    void buildAxisTables();
    void axis(int v, int *i0, int *i1, float *t) const;

    bool m_ready = false;
    int m_size = 0;
    int m_channels = 0;
    QByteArray m_data;          // kGridPoints*kChannels 字节
    int m_i0[256] = {0};        // 每输入值 -> 低格点
    int m_i1[256] = {0};        // 每输入值 -> 高格点
    float m_t[256] = {0.0f};    // 插值比例
};

} // namespace mtr
