// ============================================================================
// job_config.h —— 蒙泰兼容的 RIP 作业参数
//
// 目标是让 rip-studio 现有的 buildRipJson() 产物几乎原样可用：
//   { command:"rip", doc:{name}, prs:..., modeId:..., rotate:..., scale:[x,y],
//     margin:[l,t,r,b], view:{xdpi,ydpi}, color:{readTransparency,transparencyToWhite},
//     inputColorEditor:[{inkName,mode,invert}], inkIE:[{index,mode,dots:[4]}],
//     output:{mode:"file", file:{name, mode:438}}, range:[[1,1]] }
// 我们只消费其中的 RIP 子集（output/range 忽略）。
// ============================================================================
#pragma once

#include <QString>
#include <QVector>
#include <QJsonObject>

namespace mtr {

struct WhiteInkSpec {
    QString inkName;        // "W1" / "W2"
    QString mode;           // "full"（整幅全铺）/ "color"（仅彩色区域）
    bool invert = false;
};

struct InkIESpec {          // 白墨/专色形态学处理
    int index = 4;
    QString mode;           // "invaginate"（内缩）/ "expand"（外扩）
    QVector<double> dots;   // 4 个方向的最多像素偏移（mm 或像素，待 T3 定）
};

struct RipJob {
    QString inputPath;      // doc.name
    QString prnPath;        // output.file.name
    QString prsPath;        // prs

    int modeId = 0;         // 0..3 质量档
    double rotate = 0.0;    // 0 / 180（镜像）
    QVector<double> scale;  // [x, y]，单位 %
    QVector<int> margin;    // [l, t, r, b]
    int viewXDPI = 120;     // 预览视图 dpi（只影响 MainTop 内部渲染尺寸，待确认）
    int viewYDPI = 120;

    bool readTransparency = true;
    bool transparencyToWhite = false;

    QVector<WhiteInkSpec> inputColorEditor;
    QVector<InkIESpec> inkIE;

    // 解析作业 JSON 文件；兼容字段缺失（给默认值）。
    static bool loadFromFile(const QString &path, RipJob *job, QString *err);
    static bool fromJson(const QJsonObject &root, RipJob *job, QString *err);

    // 读入图像后才知道的实际输出尺寸（由 job 决定，不含图像）
    int effectiveDPI(int fallback) const;
};

} // namespace mtr
