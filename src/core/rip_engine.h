// ============================================================================
// rip_engine.h —— RIP 主引擎
//
// 数据流（与蒙泰语义对齐，细节由 docs/color_pipeline.md 定）：
//   QImage(RGBA) --ICC--> CMYK --inkLimit--> 线性化 --> 白墨生成
//        --> 加网(AM/FM, 2bit) --> 设备通道平面 --> PRN 编码器(ESC/P2 或 HSSF)
// ============================================================================
#pragma once

#include <QString>
#include <QImage>
#include <QVector>
#include <cstdint>

#include "core/job_config.h"
#include "core/prs_config.h"

namespace mtr {

// 单个设备墨水通道的 2bit 点阵（每像素 1 字节，值 0..3；编码阶段再打包）
struct DevicePlane {
    QString name;                 // "K"/"C"/"M"/"Y"/"W1"/"W2" ...
    int width = 0;
    int height = 0;
    QVector<uint8_t> data;        // width*height，值 0..3
};

struct RipResult {
    int width = 0;
    int height = 0;
    int xDPI = 0;
    int yDPI = 0;
    QVector<DevicePlane> planes;  // 顺序 = 设备墨序
};

class RipEngine {
public:
    void setPlaneDumpDir(const QString &dir) { m_planeDumpDir = dir; }

    bool run(const RipJob &job, QString *err);

private:
    bool buildDevicePlanes(const RipJob &job, const PrsConfig &prs,
                           const QImage &image, RipResult *result, QString *err);
    QString m_planeDumpDir;
};

} // namespace mtr
