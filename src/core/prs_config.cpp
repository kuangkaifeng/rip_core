#include "core/prs_config.h"

#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QCoreApplication>

#include "core/resources.h"
#include <QRegularExpression>
#include <cstring>
#include <cmath>

namespace mtr {

namespace {

constexpr uint32_t kMagic = 0x6E5344D0u;

uint32_t rdU32(const QByteArray &b, int off)
{
    if (off < 0 || off + 4 > b.size()) return 0;
    return static_cast<uint32_t>(static_cast<unsigned char>(b[off])) |
           (static_cast<uint32_t>(static_cast<unsigned char>(b[off + 1])) << 8) |
           (static_cast<uint32_t>(static_cast<unsigned char>(b[off + 2])) << 16) |
           (static_cast<uint32_t>(static_cast<unsigned char>(b[off + 3])) << 24);
}

double rdF64(const QByteArray &b, int off)
{
    double v = 0.0;
    if (off < 0 || off + 8 > b.size()) return v;
    std::memcpy(&v, b.constData() + off, 8);
    return v;
}

QString cstr(const QByteArray &b, int off, int maxLen)
{
    if (off < 0 || off >= b.size()) return QString();
    int end = off;
    const int limit = qMin(b.size(), off + maxLen);
    while (end < limit && b[end] != '\0') ++end;
    return QString::fromLatin1(b.constData() + off, end - off);
}

// 从 icc/icm 路径记录的特征串
bool looksLikeIccRecord(const QString &s)
{
    static const QStringList suffixes = {
        QStringLiteral(".icc"), QStringLiteral(".icm"), QStringLiteral(".mcm"),
        QStringLiteral(".pdv"), QStringLiteral(".wpk")};
    for (const QString &suf : suffixes)
        if (s.endsWith(suf, Qt::CaseInsensitive)) return true;
    return false;
}

} // namespace

QString PrsConfig::bundledIccDir()
{
    const QString base = resourceBaseDir();
    QStringList candidates;
    if (!base.isEmpty())
        candidates << QDir(base).filePath(QStringLiteral("icc"))
                   << QDir(base).filePath(QStringLiteral("3rdparty/icc"));
    if (QCoreApplication::instance()) {
        const QString appDir = QCoreApplication::applicationDirPath();
        if (!appDir.isEmpty()) {
            candidates << QDir(appDir).filePath(QStringLiteral("icc"))
                       << QDir(appDir).filePath(QStringLiteral("3rdparty/icc"))
                       << QDir(appDir).absoluteFilePath(QStringLiteral("../../3rdparty/icc"))
                       << QDir(appDir).absoluteFilePath(QStringLiteral("../3rdparty/icc"));
        }
    }
    for (const QString &c : candidates)
        if (QDir(c).exists()) return QDir::cleanPath(c);
    return QString();
}

bool PrsConfig::load(const QString &path, QString *err)
{
    m_path = path;
    m_raw.clear();
    m_iccDirs.clear();
    QFile f(path);
    if (!f.exists()) {
        if (err) *err = QStringLiteral("prs not found: %1").arg(path);
        return false;
    }
    if (!f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("cannot open prs: %1").arg(path);
        return false;
    }
    m_raw = f.readAll();
    f.close();
    if (m_raw.size() < 0x400) {
        if (err) *err = QStringLiteral("prs too small");
        return false;
    }
    if (rdU32(m_raw, 0) != kMagic) {
        if (err) *err = QStringLiteral("prs bad magic (expect D0 44 53 6E)");
        return false;
    }
    version = static_cast<int>(rdU32(m_raw, 4));
    driverModule = cstr(m_raw, 0x14, 32);

    // ICC 搜索目录
    const QString prsDir = QFileInfo(path).absolutePath();
    m_iccDirs << prsDir
              << QDir(prsDir).filePath(QStringLiteral("ICC Profile/CMYK"))
              << QDir(prsDir).filePath(QStringLiteral("ICC Profile/RGB"))
              << QDir(prsDir).filePath(QStringLiteral("ICC Profile/OUTPUT"))
              << QDir(prsDir).filePath(QStringLiteral("ICC Profile/DEFAULT"))
              << QDir(prsDir).absoluteFilePath(QStringLiteral("../ICC Profile/CMYK"))
              << QDir(prsDir).absoluteFilePath(QStringLiteral("../ICC Profile/RGB"))
              << QDir(prsDir).absoluteFilePath(QStringLiteral("../ICC Profile/OUTPUT"))
              << QDir(prsDir).absoluteFilePath(QStringLiteral("../ICC Profile/DEFAULT"))
              << bundledIccDir();

    parseTextBlock();
    parseModeTable();
    if (!parseRecords(err))
        return false;
    resolveModeRecords();

    // 猜机型名
    for (const QString &s : textOptions) {
        if (s.contains(QLatin1String("DTF")) && s.size() < 64 && !s.contains(QLatin1Char('='))) {
            machineName = s;
            break;
        }
    }
    if (machineName.isEmpty())
        machineName = QFileInfo(path).completeBaseName();
    return true;
}

void PrsConfig::parseTextBlock()
{
    // 前 0x9000 字节内提取可打印串
    const int limit = qMin(m_raw.size(), 0x9000);
    int i = 0;
    while (i < limit) {
        if (static_cast<unsigned char>(m_raw[i]) >= 0x20 && static_cast<unsigned char>(m_raw[i]) < 0x7f) {
            int j = i;
            while (j < limit && static_cast<unsigned char>(m_raw[j]) >= 0x20 &&
                   static_cast<unsigned char>(m_raw[j]) < 0x7f)
                ++j;
            if (j - i >= 3)
                textOptions.append(QString::fromLatin1(m_raw.constData() + i, j - i));
            i = j;
        } else {
            ++i;
        }
    }
}

void PrsConfig::parseModeTable()
{
    modes.clear();

    struct EscDef {
        int pageUnit, uA, uV, uH, r, v, h, M, adv;
    };
    // A3-DTF-1390（v3）的 10 个基础模式参数（按 modeId%10；实测见 docs/02_geometry_escp2.md）
    static const EscDef a3[10] = {
        {360, 8, 8, 4, 1440, 16, 2, 245, 71},   // mode0: CMYK      720x360
        {360, 8, 8, 4, 1440, 16, 2, 277, 35},   // mode1: CMYKW1W2  720x360
        {720, 4, 4, 4, 1440, 16, 2, 555, 79},   // mode2: CMYK      720x720
        {720, 4, 4, 4, 1440, 16, 2, 587, 39},   // mode3: CMYKW1W2  720x720
        {720, 4, 4, 2, 1440, 16, 4, 627, 11},   // mode4: CMYK      1440x720
        {720, 4, 4, 2, 1440, 16, 4, 627, 11},   // mode5: CMYKW1W2  1440x720
        {1440, 2, 2, 2, 1440, 16, 4, 1227, 11}, // mode6: CMYK      1440x1440
        {1440, 2, 2, 2, 1440, 16, 4, 1227, 11}, // mode7: CMYKW1W2  1440x1440
        {1440, 2, 2, 1, 1440, 16, 2, 1227, 11}, // mode8: CMYK      2880x1440
        {1440, 2, 2, 1, 1440, 16, 2, 1227, 11}, // mode9: CMYKW1W2  2880x1440
    };

    struct BaseDef {
        int x, y, planes;
        bool cc;
        const char *dpi;
        const char *ink;
    };
    static const BaseDef a3Base[10] = {
        {720, 360, 4, false, "v720x360dpi", "CMYK"},
        {720, 360, 6, false, "v720x360dpi", "CMYKW1W2"},
        {720, 720, 4, false, "v720x720dpi", "CMYK"},
        {720, 720, 6, false, "v720x720dpi", "CMYKW1W2"},
        {1440, 720, 4, false, "v1440x720dpi", "CMYK"},
        {1440, 720, 6, true, "v1440x720dpi", "CMYKW1W2"},
        {1440, 1440, 4, false, "v1440x1440dpi", "CMYK"},
        {1440, 1440, 6, true, "v1440x1440dpi", "CMYKW1W2"},
        {2880, 1440, 4, false, "v2880x1440dpi", "CMYK"},
        {2880, 1440, 6, true, "v2880x1440dpi", "CMYKW1W2"},
    };

    if (version == 3) {
        for (int paper = 0; paper < 3; ++paper) {
            for (int i = 0; i < 10; ++i) {
                PrsMode m;
                m.modeId = paper * 10 + i;
                m.xDPI = a3Base[i].x;
                m.yDPI = a3Base[i].y;
                m.planes = a3Base[i].planes;
                m.colorCorrection = a3Base[i].cc;
                m.dpiText = QString::fromLatin1(a3Base[i].dpi);
                m.inkText = QString::fromLatin1(a3Base[i].ink);
                m.pageUnit = a3[i].pageUnit;
                m.uA = a3[i].uA;
                m.uV = a3[i].uV;
                m.uH = a3[i].uH;
                m.rasterR = a3[i].r;
                m.rasterV = a3[i].v;
                m.rasterH = a3[i].h;
                m.marginM = a3[i].M;
                m.advance = a3[i].adv;
                m.blockRows = 90;
                // 图像行 -> 页面行（120dpi 图像）
                m.rowStep = m.pageUnit / 120;
                const int vstep = m.pageUnit / (m.rasterR / m.rasterV);
                // 内容起点（K/C 组）：M + 约 3mm；6-plane 再 + 一个 vstep（实测 m0=288,m1=324,m2=640,m3=680）
                m.p0Offset = m.marginM + static_cast<int>(std::lround(0.11811 * m.pageUnit));
                if (m.planes == 6) m.p0Offset += vstep;
                m.colorOffset = vstep / 2;   // M/Y/(W) 组额外错位（实测 m2: 640+4=644）
                m.initialAdvance = 0;
                modes.append(m);
            }
        }
    } else {
        // H13 XP600（HSSF 0x5555）：4 个模式全部 CMYKW1 + 校色
        static const int ys[4] = {720, 1080, 1440, 2160};
        static const char *names[4] = {"V720x720 dpi", "V720x1080 dpi",
                                       "V720x1440 dpi", "V720x2160 dpi"};
        for (int i = 0; i < 4; ++i) {
            PrsMode m;
            m.modeId = i;
            m.xDPI = 720;
            m.yDPI = ys[i];
            m.planes = 5;
            m.colorCorrection = true;
            m.dpiText = QString::fromLatin1(names[i]);
            m.inkText = QStringLiteral("CMYKW1");
            m.blockRows = 90;
            modes.append(m);
        }
    }
}


bool PrsConfig::parseRecords(QString *err)
{
    records.clear();
    QVector<int> groupStarts;
    const int n = m_raw.size();
    for (int off = 0; off + 16 <= n; off += 8) {
        if (rdF64(m_raw, off) != 0.0) continue;
        if (std::abs(rdF64(m_raw, off + 8) - (1.0 / 255.0)) > 1e-12) continue;
        int cnt = 0;
        int p = off;
        while (p + 16 <= n) {
            if (rdF64(m_raw, p) == 0.0 &&
                std::abs(rdF64(m_raw, p + 8) - (1.0 / 255.0)) < 1e-12) {
                ++cnt;
                p += 256 * 8;
                if (cnt < 8) p += 12;
            } else {
                break;
            }
        }
        if (cnt >= 4) {
            groupStarts.append(off);
            off = p - 8;
        }
    }

    for (int g = 0; g < groupStarts.size(); ++g) {
        PrsModeRecord rec;
        rec.lutStart = groupStarts[g];
        int p = rec.lutStart;
        for (int c = 0; c < 8; ++c) {
            if (p + 256 * 8 > n) break;
            if (rdF64(m_raw, p) != 0.0) break;
            QVector<double> curve(256);
            for (int k = 0; k < 256; ++k)
                curve[k] = rdF64(m_raw, p + k * 8);
            rec.curves.append(curve);
            p += 256 * 8;
            if (c < 7) p += 12;
        }
        const int searchEnd = qMin(n, p + 16384);
        QVector<QPair<int, QString>> found;
        for (int off = p; off + 4 <= searchEnd; ++off) {
            const int c = static_cast<unsigned char>(m_raw[off]);
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                  (c >= '0' && c <= '9')))
                continue;
            if (off > 0) {
                const unsigned char prev = static_cast<unsigned char>(m_raw[off - 1]);
                if (prev >= 0x20 && prev < 0x7f) continue; // 字符串中间
            }
            QString s = cstr(m_raw, off, 260);
            if (s.size() >= 4 && looksLikeIccRecord(s))
                found.append({off, s});
        }
        QStringList paths;
        for (const auto &pr : found) {
            if (paths.contains(pr.second)) continue;
            bool isSuffix = false;
            for (QString &e : paths) {
                if (e.endsWith(pr.second)) { isSuffix = true; break; }
                if (pr.second.endsWith(e)) { e = pr.second; isSuffix = true; break; }
            }
            if (isSuffix) continue;
            paths.append(pr.second);
            if (paths.size() >= 4) break;
        }
        if (paths.size() >= 4) {
            rec.srcRgbPath = paths.at(0);
            rec.srcCmykPath = paths.at(1);
            rec.mcmPath = paths.at(2);
            rec.destCmykPath = paths.at(3);
        }
        records.append(rec);
    }
    if (err && records.isEmpty())
        *err = QStringLiteral("prs: no mode records found");
    return true;
}

void PrsConfig::resolveModeRecords()
{
    if (records.isEmpty()) return;
    QVector<bool> used(records.size(), false);
    for (PrsMode &m : modes) {
        if (!m.colorCorrection) continue;
        int best = -1;
        int bestScore = 1 << 30;
        for (int i = 0; i < records.size(); ++i) {
            if (used[i]) continue;
            const QString &dest = records.at(i).destCmykPath;
            if (dest.isEmpty()) continue;
            static const QRegularExpression re(QStringLiteral("v(\\d+)x(\\d+)"));
            const auto mt = re.match(dest);
            if (!mt.hasMatch()) continue;
            const int vy = mt.captured(1).toInt();
            const int vx = mt.captured(2).toInt();
            if (vy != m.yDPI) continue;
            const int score = qAbs(vx - m.xDPI);
            if (score < bestScore) { bestScore = score; best = i; }
        }
        if (best >= 0) { m.recordIndex = best; used[best] = true; }
    }
}

const PrsMode *PrsConfig::mode(int modeId) const
{
    for (const PrsMode &m : modes)
        if (m.modeId == modeId) return &m;
    return nullptr;
}

QString PrsConfig::option(const QString &key) const
{
    const QString prefix = key + QLatin1Char('=');
    for (const QString &s : textOptions)
        if (s.startsWith(prefix, Qt::CaseInsensitive))
            return s.mid(prefix.size()).trimmed();
    return QString();
}

QByteArray PrsConfig::loadIcc(const QString &fileName, QString *err) const
{
    if (fileName.isEmpty()) return QByteArray();
    for (const QString &dir : m_iccDirs) {
        const QString p = QDir(dir).filePath(fileName);
        QFile f(p);
        if (f.exists()) {
            if (!f.open(QIODevice::ReadOnly)) continue;
            const QByteArray data = f.readAll();
            f.close();
            if (data.size() > 100) return data;
        }
    }
    if (err) *err = QStringLiteral("icc not found: %1").arg(fileName);
    return QByteArray();
}

void PrsConfig::colorProfiles(int modeId, QString *srcRgb, QString *srcCmyk,
                              QString *destCmyk) const
{
    if (srcRgb) *srcRgb = QStringLiteral("SRGB IEC61966-2.1.icc");
    if (srcCmyk)
        *srcCmyk = version == 3 ? QStringLiteral("CoatedFOGRA39.icc")
                                : QStringLiteral("US Web Coated (SWOP) v2.icc");
    if (destCmyk) destCmyk->clear();

    const PrsMode *m = mode(modeId);
    if (!m) return;
    if (m->recordIndex >= 0 && m->recordIndex < records.size()) {
        const PrsModeRecord &r = records.at(m->recordIndex);
        if (!r.srcRgbPath.isEmpty() && srcRgb) *srcRgb = r.srcRgbPath;
        if (!r.srcCmykPath.isEmpty() && srcCmyk) *srcCmyk = r.srcCmykPath;
        if (!r.destCmykPath.isEmpty() && destCmyk) *destCmyk = r.destCmykPath;
    }
    // 非校色模式：dest 留空（表示不做 CMYK→设备 二次转换）
}

void PrsConfig::dump(QTextStream *out) const
{
    if (!out) return;
    *out << "prs: " << m_path << "\n";
    *out << "  size=" << m_raw.size() << " version=" << version
         << " driver=" << driverModule << " machine=" << machineName << "\n";
    *out << "  modes=" << modes.size() << " records=" << records.size() << "\n";
    for (const PrsMode &m : modes) {
        *out << QStringLiteral("  mode %1: %2x%3 dpi planes=%4 cc=%5 ink=%6 rec=%7\n")
                    .arg(m.modeId).arg(m.xDPI).arg(m.yDPI).arg(m.planes)
                    .arg(m.colorCorrection ? 1 : 0).arg(m.inkText).arg(m.recordIndex);
    }
    for (int i = 0; i < records.size(); ++i) {
        const PrsModeRecord &r = records.at(i);
        *out << QStringLiteral("  record %1: lut@0x%2 curves=%3\n")
                    .arg(i).arg(r.lutStart, 0, 16).arg(r.curves.size());
        *out << "    srcRgb  = " << r.srcRgbPath << "\n"
             << "    srcCmyk = " << r.srcCmykPath << "\n"
             << "    mcm     = " << r.mcmPath << "\n"
             << "    destCmyk= " << r.destCmykPath << "\n";
    }
    const QStringList keys = {QStringLiteral("OutputFixedLines"),
                              QStringLiteral("StochasticHalftone"),
                              QStringLiteral("SetInkOrder"),
                              QStringLiteral("Manufacturer")};
    for (const QString &k : keys) {
        const QString v = option(k);
        if (!v.isEmpty()) *out << "  option " << k << " = " << v << "\n";
    }
}

} // namespace mtr
