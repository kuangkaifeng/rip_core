// ============================================================================
// prs_config.h —— 蒙泰 .prs 打印设置文件解析（C++ 实现）
//
// 结构（逆向自 T3 的 prs_parser.py + oracle 实测）：
//   0x00 u32 magic 0x6E5344D0 (bytes D0 44 53 6E)
//   0x04 u32 format version (3 = A3-DTF-1390 系, 4 = H13 XP600 系)
//   0x14 char[32] 驱动模块名 "MtDummy.pdv"
//   ~0x5540 起：NUL 分隔的文本配置块（键=值：OutputFixedLines/StochasticHalftone/
//              SetInkOrder/v720x360dpi ... 以及驱动选项目录）
//   随后 N 个 mode 记录（A3:3 个 / H13:4 个），每个记录含：
//     [8×256 double 线性化 LUT，条目间 12 字节间隔]
//     [96B mode 配置结构]
//     [4×char[260] ICC 路径组 A: srcRgbPath, srcCmykPath, mcmPath, destCmykPath]
//     [88B 结构]
//     [4×char[260] ICC 路径组 B（同上重复）]
//
// modeId → 记录：仅 colorCorrection=true 的模式（A3 的 5/7/9；H13 全部）在 prs 内
// 带 ICC；其余模式使用缺省 profile。
// ============================================================================
#pragma once

#include <QString>
#include <QByteArray>
#include <QVector>
#include <QTextStream>
#include <QSharedPointer>

namespace mtr {

struct PrsMode {                       // 与 queryMode 返回对齐
    int modeId = 0;
    int xDPI = 720;                    // 水平打印分辨率
    int yDPI = 720;                    // 垂直打印分辨率
    int planes = 4;                    // 墨水通道数（含白墨）
    bool colorCorrection = false;      // 是否使用 prs 内 ICC 校色
    QString dpiText;                   // 例如 "v720x720dpi"
    QString inkText;                   // 例如 "CMYK" / "CMYKW1W2"
    int recordIndex = -1;              // 对应 .prs 内 mode 记录（-1=无，走缺省）

    // ---- ESC/P2（A3-DTF-1390）版面参数（实测/工具推导，见 docs/02_geometry_escp2.md）----
    int pageUnit = 720;                // ESC(U 的 page unit（单位/英寸）
    int uA = 4, uV = 4, uH = 4;        // ESC(U 的三个比值（2880/值 = unit）
    int rasterR = 1440, rasterV = 16, rasterH = 2; // ESC(D)
    int marginM = 555;                 // ESC(c/S 的页边距常数（page unit）
    int advance = 79;                  // 块推进（page unit）
    int rowStep = 6;                   // 图像行 -> 页面行（page unit/图像行）
    int p0Offset = 640;                // 内容起始（K/C 组）相对首块位置的偏移（page unit）
    int colorOffset = 4;               // M/Y/W 组的额外偏移（= vstep/2，page unit）
    int blockRows = 90;                // m
    int initialAdvance = 0;            // 首块前 ESC(v（可为 0 = 不写）
};

struct PrsModeRecord {
    int lutStart = -1;                 // 线性化 LUT 起始偏移
    QVector<QVector<double>> curves;   // 每通道 256 点曲线（8 组）
    QString srcRgbPath;                // 组 A/B: [0]
    QString srcCmykPath;               //          [1]
    QString mcmPath;                   //          [2]
    QString destCmykPath;              //          [3]
};

class PrsConfig {
public:
    bool load(const QString &path, QString *err);
    void dump(QTextStream *out) const;

    const QString &path() const { return m_path; }
    const QByteArray &raw() const { return m_raw; }

    int version = 0;
    QString driverModule;              // "MtDummy.pdv"
    QString machineName;               // 从文本块/路径猜出，例如 "A3-DTF-1390"
    QVector<PrsMode> modes;
    QVector<PrsModeRecord> records;
    QStringList textOptions;           // 文本块中所有可打印字符串

    // ---- 工具 ----
    const PrsMode *mode(int modeId) const;
    // 文本配置键值（例如 "OutputFixedLines" -> "90"）
    QString option(const QString &key) const;
    // 按名字在若干搜索路径下找 ICC 文件并读入
    QByteArray loadIcc(const QString &fileName, QString *err = nullptr) const;
    // 该模式应使用的 ICC 文件名（含缺省回退）
    void colorProfiles(int modeId, QString *srcRgb, QString *srcCmyk, QString *destCmyk) const;

    // ICC 搜索路径（额外追加）
    void addIccSearchDir(const QString &dir) { m_iccDirs.append(dir); }
    static QString bundledIccDir();     // exe 同目录 / ../../3rdparty/icc 等

private:
    void parseModeTable();
    void parseTextBlock();
    bool parseRecords(QString *err);
    void resolveModeRecords();

    QString m_path;
    QByteArray m_raw;
    QStringList m_iccDirs;
};

} // namespace mtr
