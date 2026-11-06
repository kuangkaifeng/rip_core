// ============================================================================
// layout_escp2.cpp —— ESC/P2 版面布局实现（A3-DTF-1390）
//
// 依据 docs/prn_escp2.md（T2 已用整文件 round-trip 逐字节验证的几何模型）。
// 生成算法：
//   1) 由 modeId 取模式参数（P0/M/advance/颜色顺序/每记录纵向偏移）
//   2) 对每条记录的每个内容行 i，算它落在哪个块的哪一行：
//        p = P0 + i + recordOffset[rec]
//        k = max{ k : pos[k] ≡ p (mod VSTEP), pos[k] ≤ p, (p-pos[k])/VSTEP ≤ 89 }
//      块数 N = 1 + max k
//   3) 块 k 的记录 rec 的第 r 行 = 内容行 (pos[k]+VSTEP*r+off-P0) —— 仅当该行
//      的拥有者是这个块（最大 k 规则，厂商羽化拆分被我们简化成独占）
//   4) n = align8(ceil(widthDots/4))，每行独立 RLE，m=90
//
// 与厂商的已知差异（见 docs/prn_escp2.md §10/§12）：重叠带我们不做 x 羽化拆分
// （打印结果等价）；顶部空白跳过 initialAdvance 我们默认 0（多几个空块）；
// 全零作业按实测模式常量 whiteAdvance 复刻。
// ============================================================================
#include "core/encode/layout_escp2.h"

#include <QDebug>
#include <QFile>
#include <QImage>
#include <QPair>
#include <algorithm>
#include <cstring>

#include "core/encode/plane_pack.h"

namespace mtr {

namespace {

// n = align8(ceil(widthDots/4))（实测：600->152, 1000->256, 4308->1080）
int bytesPerLineFor(int widthDots)
{
    const int bpl = (widthDots + 3) / 4;
    return (bpl + 7) & ~7;
}

QString colorName(int code)
{
    switch (code) {
    case 0x00: return QStringLiteral("K");
    case 0x01: return QStringLiteral("M");
    case 0x02: return QStringLiteral("C");
    case 0x04: return QStringLiteral("Y");
    case 0x11: return QStringLiteral("W2");
    case 0x12: return QStringLiteral("W1");
    default:   return QStringLiteral("?");
    }
}

// 整数模逆（vstep 为 2 的幂，adv 为奇数；扩展欧几里得即可）
int modularInverse(int a, int m)
{
    a %= m;
    if (a < 0) a += m;
    for (int x = 1; x < m; ++x) {
        if ((a * x) % m == 1) return x;
    }
    return 0; // 不应发生（gcd(adv,vstep)=1）
}

} // namespace

// ---------------------------------------------------------------------------
// 实测参数表（A3-DTF-1390.prs）
// 证据：reference/prn_samples/ 各 flat_black/geomh/col_* 样本；
//       docs/prn_escp2.md §7.2 §8 §9
// ---------------------------------------------------------------------------
Escp2ModeParams escp2ModeParams(int modeId)
{
    Escp2ModeParams mp;
    mp.modeId = modeId;
    mp.rasterR = 1440;
    mp.blockRows = 90;
    mp.colorCodes.clear();
    mp.recordOffsets.clear();

    switch (modeId) {
    case 0:                          // 4 色 720x360 dpi（4-pass）
        mp.xDPI = 720; mp.yDPI = 360;
        mp.planes = 4;
        mp.pageUnit = 360;
        mp.uA = 8; mp.uV = 8; mp.uH = 4;
        mp.rasterV = 16; mp.rasterH = 2;
        mp.marginM = 245;
        mp.advance = 71;
        mp.rowStep = 4;
        mp.baseP0 = 288;
        mp.whiteAdvance = 353;
        mp.dotSize = 0x21; mp.method = 0x41;
        mp.colorCodes = {0x04, 0x00, 0x12, 0x11};          // K,C,M,Y
        mp.recordOffsets = {0, 0, 2, 2};
        break;
    case 1:                          // 6 色 360x720 dpi（4-pass ×2）
        mp.xDPI = 720; mp.yDPI = 360;
        mp.planes = 6;
        mp.pageUnit = 360;
        mp.uA = 8; mp.uV = 8; mp.uH = 4;
        mp.rasterV = 16; mp.rasterH = 2;
        mp.marginM = 277;
        mp.advance = 35;
        mp.rowStep = 4;
        mp.baseP0 = 324;
        mp.whiteAdvance = 349;
        mp.dotSize = 0x21; mp.method = 0x41;
        mp.colorCodes = {0x12, 0x11, 0x00, 0x02, 0x01, 0x04};
        mp.recordOffsets = {2, 2, 0, 0, 2, 2};
        break;
    case 3:                          // 6 色 720x720 dpi（8-pass ×2）
        mp.xDPI = 720; mp.yDPI = 720;
        mp.planes = 6;
        mp.pageUnit = 720;
        mp.uA = 4; mp.uV = 4; mp.uH = 4;
        mp.rasterV = 16; mp.rasterH = 2;
        mp.marginM = 587;
        mp.advance = 39;
        mp.rowStep = 8;
        mp.baseP0 = 680;
        mp.whiteAdvance = 697;
        mp.dotSize = 0x21; mp.method = 0x41;
        mp.colorCodes = {0x12, 0x11, 0x00, 0x02, 0x01, 0x04};
        mp.recordOffsets = {4, 4, 0, 0, 4, 4};
        break;
    case 5:                          // 6 色 水平 360dpi 高质量档
        mp.xDPI = 360; mp.yDPI = 720;
        mp.planes = 6;
        mp.pageUnit = 720;
        mp.uA = 4; mp.uV = 4; mp.uH = 2;
        mp.rasterV = 16; mp.rasterH = 4;
        mp.marginM = 627;
        mp.advance = 11;
        mp.rowStep = 8;
        mp.baseP0 = 712;
        mp.whiteAdvance = 0;         // 语料无空白样本，未实测
        mp.dotSize = 0x34; mp.method = 0x40;
        mp.colorCodes = {0x12, 0x11, 0x00, 0x02, 0x01, 0x04};
        mp.recordOffsets = {4, 4, 0, 0, 4, 4};   // 推测同 m3
        break;
    case 7:                          // pageUnit=1440，水平 360dpi
        mp.xDPI = 360; mp.yDPI = 1440;
        mp.planes = 6;
        mp.pageUnit = 1440;
        mp.uA = 2; mp.uV = 2; mp.uH = 2;
        mp.rasterV = 16; mp.rasterH = 4;
        mp.marginM = 1227;
        mp.advance = 11;
        mp.rowStep = 16;
        mp.baseP0 = 1413;
        mp.whiteAdvance = 0;
        mp.dotSize = 0x34; mp.method = 0x40;
        mp.colorCodes = {0x12, 0x11, 0x00, 0x02, 0x01, 0x04};
        mp.recordOffsets = {8, 8, 0, 0, 8, 8};   // 1/180in = 8 page unit @1440dpi
        break;
    case 9:                          // pageUnit=1440，水平 720dpi
        mp.xDPI = 720; mp.yDPI = 1440;
        mp.planes = 6;
        mp.pageUnit = 1440;
        mp.uA = 2; mp.uV = 2; mp.uH = 1;
        mp.rasterV = 16; mp.rasterH = 2;
        mp.marginM = 1227;
        mp.advance = 11;
        mp.rowStep = 16;
        mp.baseP0 = 1413;
        mp.whiteAdvance = 0;
        mp.dotSize = 0x21; mp.method = 0x51;
        mp.colorCodes = {0x12, 0x11, 0x00, 0x02, 0x01, 0x04};
        mp.recordOffsets = {8, 8, 0, 0, 8, 8};
        break;
    case 2:                          // 4 色 720x720 dpi（金样本模式，8-pass）
    default:
        mp.modeId = 2;
        mp.xDPI = 720; mp.yDPI = 720;
        mp.planes = 4;
        mp.pageUnit = 720;
        mp.uA = 4; mp.uV = 4; mp.uH = 4;
        mp.rasterV = 16; mp.rasterH = 2;
        mp.marginM = 555;
        mp.advance = 79;
        mp.rowStep = 8;
        mp.baseP0 = 640;
        mp.whiteAdvance = 705;
        mp.dotSize = 0x21; mp.method = 0x41;
        mp.colorCodes = {0x04, 0x00, 0x12, 0x11};
        mp.recordOffsets = {0, 0, 4, 4};
        break;
    }
    return mp;
}

// 纸行 p -> (block,row)：k = 满足 pos0+adv*k ≡ p (mod VSTEP) 且
// pos0+adv*k ≤ p 且 r=(p-pos0-adv*k)/VSTEP ≤ 89 的 k
// maxBlock >= 0 时限制 k <= maxBlock（生成时用 N-1，复刻厂商"块数不因记录偏移增加"）
static bool solveBlockRow(const Escp2ModeParams &mp, int pos0, int p, int maxBlock,
                          int *block, int *row)
{
    const int adv = qMax(1, mp.advance);
    const int vstep = qMax(1, mp.rowStep);
    const int rel = p - pos0;
    if (rel < 0) return false;
    const int inv = modularInverse(adv % vstep, vstep);
    if (inv <= 0) return false;
    int k0 = (rel % vstep) * inv % vstep;
    int kmax = rel / adv;
    if (maxBlock >= 0 && kmax > maxBlock) kmax = maxBlock;
    if (kmax < k0) return false;
    int k = k0 + ((kmax - k0) / vstep) * vstep;
    while (k >= 0) {
        const int r = (rel - adv * k) / vstep;
        if (r >= 0 && r < mp.blockRows) {
            if (block) *block = k;
            if (row) *row = r;
            return true;
        }
        if (r >= mp.blockRows) return false;
        k -= vstep;
    }
    return false;
}

bool escp2SolveBlockRow(const Escp2ModeParams &mp, int pos0, int p, int *block, int *row)
{
    return solveBlockRow(mp, pos0, p, -1, block, row);
}

Escp2LayoutInfo computeEscp2Layout(const Escp2ModeParams &mp, int widthDots, int heightDots)
{
    Escp2LayoutInfo info;
    info.advance = mp.advance;
    info.rowStep = mp.rowStep;
    info.widthDots = widthDots;
    info.heightDots = heightDots;
    info.bytesPerLine = bytesPerLineFor(widthDots);
    info.p0 = mp.baseP0;
    info.positions.clear();
    if (heightDots <= 0 || widthDots <= 0) {
        info.blockCount = 0;
        return info;
    }
    // ESC(S) 宽 = content_w_units = round(content_w_dots * pageUnit / xDPI)
    info.contentWUnits = static_cast<int>(
        (static_cast<qint64>(widthDots) * mp.pageUnit + mp.xDPI / 2) / qMax(1, mp.xDPI));

    // N = 1 + max_p k(p)，p 遍历内容纸行（不含每记录偏移 —— 与厂商实测块数一致）
    int maxK = -1;
    for (int i = 0; i < heightDots; ++i) {
        int k = -1, r = -1;
        if (!escp2SolveBlockRow(mp, mp.initialAdvance, mp.baseP0 + i, &k, &r))
            continue;
        if (k > maxK) maxK = k;
    }
    info.blockCount = maxK + 1;
    info.positions.resize(info.blockCount);
    for (int k = 0; k < info.blockCount; ++k)
        info.positions[k] = mp.initialAdvance + k * mp.advance;
    return info;
}

bool normalizePageForMode(const Escp2ModeParams &mp, Escp2PageRaster *page, QString *err)
{
    if (!page) {
        if (err) *err = QStringLiteral("null page raster");
        return false;
    }
    if (page->widthDots <= 0 || page->heightDots <= 0) {
        if (err) *err = QStringLiteral("empty page raster (%1x%2)")
                            .arg(page->widthDots).arg(page->heightDots);
        return false;
    }
    const int want = mp.colorCodes.size();
    if (page->planes.size() < want) {
        if (err) *err = QStringLiteral("page raster has %1 planes, mode %2 needs %3")
                            .arg(page->planes.size()).arg(mp.modeId).arg(want);
        return false;
    }
    const qsizetype expect = static_cast<qsizetype>(page->widthDots) * page->heightDots;
    for (int i = 0; i < want; ++i) {
        if (page->planes[i].size() != expect) {
            if (err) *err = QStringLiteral("plane %1 size %2 != %3")
                                .arg(i).arg(page->planes[i].size()).arg(expect);
            return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// 可选羽化（feather）—— 复刻蒙泰"重叠带拆分"物理效果（默认关闭）
//
// 背景：块 k 与块 k+8 的纸行窗口重叠时（m2: k 的 r=79..89 与 k+8 的 r=0..10
// 落在同一纸行），蒙泰把该行点阵按行内 x 掩码拆给两块（实测 both=0，
// 即同一像素只由其中一块打印）。我们默认"最大块号独占整行"（打印结果等价，
// 但物理接缝处没有 vendor 的羽化）。设置环境变量 MTR_FEATHER=1 后启用
// vendor 风格的拆分：较早块 k 按密度表 featherDensity(r) 打印部分 x 点，
// 较晚块 k+8 打印其余点。
//
// 密度表来自 flat_black_100_m2 实测（较早块行号 r=79..89，K 色）：
//   90.83%, 81.83%, 72.67%, 63.50%, 54.50%, 50.00%, 50.00%,
//   33.33%, 20.00%, 9.00%, 0.00%
// 掩码用确定性哈希（蓝噪声近似），不同颜色不再做 1~2 dot 平移（未实测完）。
//
// 风险：
//   * 与厂商掩码不同源 → 只能改善接缝观感，不保证逐字节/逐点一致；
//   * 行内拆分使 RLE 数据量增加、文件变大；
//   * 仅支持 m2（adv=79/VSTEP=8，重叠带恰好 2 块覆盖）；其他 mode 自动忽略；
//   * 默认关闭，不影响已验收的默认输出与 roundtrip 验收。
// ---------------------------------------------------------------------------
namespace {

bool envEnabled(const char *name)
{
    const QByteArray v = qgetenv(name).trimmed();
    if (v.isEmpty()) return false;
    if (v == "0") return false;
    if (v.compare("false", Qt::CaseInsensitive) == 0) return false;
    return true;
}

// 较早块行号 r 的拆分密度（r=79..89；其余行无重叠 → 1.0）
float featherDensity(int r)
{
    if (r < 79 || r > 89) return 1.0f;
    static const float t[11] = {0.9083f, 0.8183f, 0.7267f, 0.6350f, 0.5450f,
                                0.5000f, 0.5000f, 0.3333f, 0.2000f, 0.0900f, 0.0f};
    return t[r - 79];
}

// 确定性 x 掩码：keep=true 表示该点由"较早块"打印
bool featherKeep(int x, int r)
{
    const float d = featherDensity(r);
    if (d >= 1.0f) return true;
    if (d <= 0.0f) return false;
    uint32_t h = static_cast<uint32_t>(x) * 2654435761u ^
                 static_cast<uint32_t>(r + 1) * 2246822519u;
    h ^= h >> 13;
    h *= 0x5bd1e995u;
    h ^= h >> 15;
    return (h & 0xFFFFu) < static_cast<uint32_t>(d * 65535.0f + 0.5f);
}

} // namespace

bool buildEscp2Prn(const Escp2ModeParams &mp, const Escp2PageRaster &page,
                   const Escp2Config &cfgJob, QByteArray *out,
                   Escp2LayoutInfo *infoOut, QString *err)
{
    if (!out) return false;
    if (!normalizePageForMode(mp, const_cast<Escp2PageRaster *>(&page), err))
        return false;

    const Escp2LayoutInfo layout = computeEscp2Layout(mp, page.widthDots, page.heightDots);
    if (infoOut) *infoOut = layout;

    const int rs = qMax(1, mp.rowStep);
    const int rows = qMax(1, mp.blockRows);
    const int colors = mp.colorCodes.size();
    const int bpl = layout.bytesPerLine;

    // ---- 作业头/命令区配置 ----
    Escp2Config ec = cfgJob;
    ec.uA = mp.uA;
    ec.uV = mp.uV;
    ec.uH = mp.uH;
    ec.rasterR = mp.rasterR;
    ec.rasterV = mp.rasterV;
    ec.rasterH = mp.rasterH;
    ec.dotSize = mp.dotSize;
    ec.method = mp.method;
    ec.colorMode = 2;
    ec.paperWidth = static_cast<uint32_t>(layout.contentWUnits);
    ec.paperHeight = static_cast<uint32_t>(page.heightDots - mp.marginM);  // 负值按 u32 回绕
    ec.pageFormatTop = -mp.marginM;
    ec.pageFormatBottom = page.heightDots + mp.marginM;
    ec.dollarMode = 0;
    ec.initialAdvance = mp.initialAdvance;
    ec.blockRows = rows;
    ec.blockAdvance = mp.advance;
    ec.bytesPerLine = bpl;
    ec.colorDepth = 2;
    ec.colors.clear();
    ec.colors.reserve(colors);
    for (int c = 0; c < colors; ++c)
        ec.colors.append(Escp2Color{static_cast<uint8_t>(mp.colorCodes[c]),
                                    colorName(mp.colorCodes[c])});

    // ---- 全零作业（纯白）：不发块，只写尾部前的一条 ESC(v（模式常量）----
    bool anyInk = false;
    for (int c = 0; c < colors && !anyInk; ++c) {
        const QVector<uint8_t> &pl = page.planes[c];
        for (int i = 0; i < pl.size(); ++i) {
            if (pl[i]) { anyInk = true; break; }
        }
    }
    if (!anyInk) {
        if (infoOut) {
            infoOut->blockCount = 0;
            infoOut->positions.clear();
        }
        ec.initialAdvance = mp.whiteAdvance;
        Escp2Writer writer(ec);
        writer.begin();
        *out = writer.finish();
        return true;
    }

    Escp2Writer writer(ec);
    writer.begin();

    // ---- 可选羽化：预计算每纸行被哪些 (block,row) 覆盖（仅 MTR_FEATHER=1 且 m2）----
    const bool featherOn = envEnabled("MTR_FEATHER") && mp.modeId == 2;
    if (envEnabled("MTR_FEATHER") && !featherOn)
        qWarning("mtr: MTR_FEATHER 仅对 A3 mode2 实现；当前 modeId=%d 忽略", mp.modeId);
    QVector<QVector<QPair<int, int>>> cover;
    if (featherOn && layout.blockCount > 0) {
        const int maxP = layout.positions.last() + rs * (rows - 1);
        cover.resize(maxP + 1);
        for (int k = 0; k < layout.blockCount; ++k) {
            const int base = layout.positions[k];
            for (int r = 0; r < rows; ++r) {
                const int p = base + rs * r;
                if (p >= 0 && p < cover.size())
                    cover[p].append(qMakePair(k, r));
            }
        }
    }

    // ---- 逐块生成数据 ----
    QVector<uint8_t> line(page.widthDots);
    QVector<uint8_t> featherLine(page.widthDots);
    QVector<QByteArray> perColor(colors);
    for (int k = 0; k < layout.blockCount; ++k) {
        const int base = layout.positions[k];
        for (int c = 0; c < colors; ++c) {
            const int offset = c < mp.recordOffsets.size() ? mp.recordOffsets[c] : 0;
            const QVector<uint8_t> &plane = page.planes[c];
            QByteArray &data = perColor[c];
            data.resize(bpl * rows);
            data.fill('\0');
            uint8_t *dst = reinterpret_cast<uint8_t *>(data.data());
            for (int r = 0; r < rows; ++r) {
                const int p = base + rs * r;
                const int contentRow = p - offset - layout.p0;
                if (contentRow < 0 || contentRow >= page.heightDots)
                    continue;
                const uint8_t *src = plane.constData()
                                     + static_cast<qsizetype>(contentRow) * page.widthDots;
                int n = 0;
                int outBpl = 0;
                QVector<uint8_t> packed;
                if (featherOn && p >= 0 && p < cover.size() && cover[p].size() == 2) {
                    // 重叠带：较早块 kA 打印 mask 为真的点，较晚块 kB 打印其余点
                    const int kA = cover[p].at(0).first;
                    const int rA = cover[p].at(0).second;
                    if (k != kA && k != cover[p].at(1).first)
                        continue;
                    for (int x = 0; x < page.widthDots; ++x) {
                        const bool keep = featherKeep(x, rA);
                        const bool mine = (k == kA) ? keep : !keep;
                        featherLine[x] = mine ? src[x] : 0;
                    }
                    packed = pack2BitRows(featherLine, page.widthDots, 1, &outBpl, 8);
                    n = qMin(bpl, outBpl);
                } else {
                    int owner = -1, ownerRow = -1;
                    if (!solveBlockRow(mp, mp.initialAdvance, p, layout.blockCount - 1,
                                       &owner, &ownerRow))
                        continue;
                    if (owner != k)
                        continue;                   // 该纸行归别的块（默认：不做羽化拆分）
                    packed = pack2BitRows(
                        QVector<uint8_t>(src, src + page.widthDots),
                        page.widthDots, 1, &outBpl, 8);
                    n = qMin(bpl, outBpl);
                }
                std::memcpy(dst + static_cast<qsizetype>(r) * bpl,
                            packed.constData(), static_cast<size_t>(n));
            }
        }
        writer.addBlock(perColor, mp.advance);
    }

    *out = writer.finish();
    return true;
}

bool writeEscp2Prn(const QString &prnPath, const Escp2ModeParams &mp,
                   const Escp2PageRaster &page, const Escp2Config &cfg,
                   Escp2LayoutInfo *info, QString *err)
{
    QByteArray prn;
    if (!buildEscp2Prn(mp, page, cfg, &prn, info, err))
        return false;
    QFile f(prnPath);
    if (!f.open(QIODevice::WriteOnly)) {
        if (err) *err = QStringLiteral("cannot write prn: %1").arg(prnPath);
        return false;
    }
    if (f.write(prn) != prn.size()) {
        if (err) *err = QStringLiteral("short write: %1").arg(prnPath);
        return false;
    }
    f.close();
    return true;
}

QImage escp2PlanePreview(const QVector<uint8_t> &plane, int width, int height)
{
    QImage img(qMax(1, width), qMax(1, height), QImage::Format_RGB888);
    for (int y = 0; y < height; ++y) {
        uint8_t *line = img.scanLine(y);
        const uint8_t *src = plane.constData() + static_cast<qsizetype>(y) * width;
        for (int x = 0; x < width; ++x) {
            const int v = 255 - src[x] * 85;
            line[x * 3 + 0] = static_cast<uint8_t>(v);
            line[x * 3 + 1] = static_cast<uint8_t>(v);
            line[x * 3 + 2] = static_cast<uint8_t>(v);
        }
    }
    return img;
}

} // namespace mtr
