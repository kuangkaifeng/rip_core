#include "core/encode/escp2_writer.h"

#include <QDateTime>

namespace mtr {

Escp2Writer::Escp2Writer(const Escp2Config &cfg)
    : m_cfg(cfg)
{
    if (m_cfg.colors.isEmpty())
        m_cfg.colors = {{0x12, "K"}, {0x11, "C"}, {0x00, "M"},
                        {0x02, "Y"}, {0x01, "W1"}, {0x04, "W2"}};
}

void Escp2Writer::put(const void *p, int n)
{
    if (n <= 0) return;
    m_out.append(static_cast<const char *>(p), n);
}

void Escp2Writer::putByte(uint8_t b) { m_out.push_back(static_cast<char>(b)); }

void Escp2Writer::putU16(uint16_t v)
{
    putByte(static_cast<uint8_t>(v & 0xFF));
    putByte(static_cast<uint8_t>((v >> 8) & 0xFF));
}

void Escp2Writer::putU32(uint32_t v)
{
    putByte(static_cast<uint8_t>(v & 0xFF));
    putByte(static_cast<uint8_t>((v >> 8) & 0xFF));
    putByte(static_cast<uint8_t>((v >> 16) & 0xFF));
    putByte(static_cast<uint8_t>((v >> 24) & 0xFF));
}

void Escp2Writer::putRemote(const char *cmd, const QByteArray &data)
{
    put(cmd, 2);
    putU16(static_cast<uint16_t>(data.size()));
    if (!data.isEmpty())
        put(data.constData(), static_cast<int>(data.size()));
}

void Escp2Writer::writeJobHeader()
{
    // ENTER D4
    static const uint8_t enterD4[5] = {0x00, 0x00, 0x00, 0x1B, 0x01};
    put(enterD4, 5);
    // EJL 声明
    static const char ejl1[] = "@EJL 1284.4\n";
    put(ejl1, sizeof(ejl1) - 1);
    static const char ejl2[] = "@EJL     \n";
    put(ejl2, sizeof(ejl2) - 1);
    // 进入远程模式
    static const uint8_t escR[6] = {0x1B, 0x28, 0x52, 0x08, 0x00, 0x00};
    put(escR, 6);
    put("REMOTE1", 7);

    // TI: 00 + 年(BE) + 月日时分秒
    QDateTime t = m_cfg.time.isValid() ? m_cfg.time : QDateTime::currentDateTime();
    const QDate d = t.date();
    const QTime tm = t.time();
    QByteArray ti;
    ti.append(static_cast<char>(0x00));
    ti.append(static_cast<char>((d.year() >> 8) & 0xFF));
    ti.append(static_cast<char>(d.year() & 0xFF));
    ti.append(static_cast<char>(d.month()));
    ti.append(static_cast<char>(d.day()));
    ti.append(static_cast<char>(tm.hour()));
    ti.append(static_cast<char>(tm.minute()));
    ti.append(static_cast<char>(tm.second()));
    putRemote("TI", ti);

    // JS: 13 字节 = 0x00 + name(<=11) + 0 填充
    QByteArray js(13, '\0');
    {
        QByteArray name = m_cfg.jobName;
        if (name.size() > 11) name = name.left(11);
        js.replace(1, name.size(), name);
    }
    putRemote("JS", js);

    // JH: 18 字节 = 6 个 0 + hostname(12)
    QByteArray jh(18, '\0');
    {
        QByteArray host = m_cfg.hostName;
        if (host.size() > 12) host = host.left(12);
        jh.replace(6, host.size(), host);
    }
    putRemote("JH", jh);

    putRemote("SN", QByteArray(1, '\0'));
    putRemote("PP", QByteArray("\x00\x01\xFF", 3));
    putRemote("MI", QByteArray("\x00\x01\x00\x01", 4));
    putRemote("DP", QByteArray(2, '\0'));
    putRemote("US", QByteArray("\x00\x01\x00", 3));
    putRemote("US", QByteArray("\x00\x02\x00", 3));

    // 退出远程模式
    static const uint8_t exitRemote[4] = {0x1B, 0x00, 0x00, 0x00};
    put(exitRemote, 4);
}

void Escp2Writer::writePreamble()
{
    putByte(0x1B); putByte(0x40); // ESC @

    // ESC ( G 01 00 01
    static const uint8_t g[6] = {0x1B, 0x28, 0x47, 0x01, 0x00, 0x01};
    put(g, 6);

    // ESC ( U 05 00 [uA, uV, uH, unitLo, unitHi]（unit 恒 2880）
    putByte(0x1B); putByte(0x28); putByte(0x55); putByte(0x05); putByte(0x00);
    putByte(static_cast<uint8_t>(m_cfg.uA));
    putByte(static_cast<uint8_t>(m_cfg.uV));
    putByte(static_cast<uint8_t>(m_cfg.uH));
    putU16(static_cast<uint16_t>(2880));

    // ESC U 00 双向
    putByte(0x1B); putByte(0x55); putByte(0x00);

    // ESC ( i 01 00 00 无 MicroWeave
    static const uint8_t iCmd[6] = {0x1B, 0x28, 0x69, 0x01, 0x00, 0x00};
    put(iCmd, 6);

    // ESC ( K 02 00 00 02
    putByte(0x1B); putByte(0x28); putByte(0x4B); putByte(0x02); putByte(0x00);
    putByte(0x00); putByte(static_cast<uint8_t>(m_cfg.colorMode & 0xFF));

    // ESC ( e 02 00 00 34 墨滴大小
    putByte(0x1B); putByte(0x28); putByte(0x65); putByte(0x02); putByte(0x00);
    putByte(0x00); putByte(m_cfg.dotSize);

    // ESC ( D 04 00 rL rH v h 光栅分辨率
    putByte(0x1B); putByte(0x28); putByte(0x44); putByte(0x04); putByte(0x00);
    putU16(static_cast<uint16_t>(m_cfg.rasterR));
    putByte(static_cast<uint8_t>(m_cfg.rasterV));
    putByte(static_cast<uint8_t>(m_cfg.rasterH));

    // ESC ( c 08 00 pageFormat(int32) pageFormat2(int32)
    putByte(0x1B); putByte(0x28); putByte(0x63); putByte(0x08); putByte(0x00);
    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.pageFormatTop)));
    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.pageFormatBottom)));

    // ESC ( S 08 00 width height（单位 1/1440 inch）
    putByte(0x1B); putByte(0x28); putByte(0x53); putByte(0x08); putByte(0x00);
    putU32(static_cast<uint32_t>(m_cfg.paperWidth));
    putU32(static_cast<uint32_t>(static_cast<int32_t>(m_cfg.paperHeight) >= 0
                                     ? m_cfg.paperHeight
                                     : static_cast<int32_t>(m_cfg.paperHeight)));

    // ESC ( m 01 00 <method>（m0..m3=0x41, m5/m7=0x40, m9=0x51）
    putByte(0x1B); putByte(0x28); putByte(0x6D); putByte(0x01); putByte(0x00);
    putByte(m_cfg.method);

    // ESC ( V 04 00 00 00 00 00
    static const uint8_t vCmd[9] = {0x1B, 0x28, 0x56, 0x04, 0x00,
                                    0x00, 0x00, 0x00, 0x00};
    put(vCmd, 9);

    // 首块前的相对垂直定位（金样本 = 150；0 表示不写，与多数语料一致）
    if (m_cfg.initialAdvance > 0) {
        putByte(0x1B); putByte(0x28); putByte(0x76); putByte(0x04); putByte(0x00);
        putU32(static_cast<uint32_t>(m_cfg.initialAdvance));
    }
}

void Escp2Writer::begin()
{
    m_out.clear();
    m_blockIndex = 0;
    writeJobHeader();
    writePreamble();
}

void Escp2Writer::addBlock(const QVector<QByteArray> &perColor)
{
    addBlock(perColor, -1);
}

void Escp2Writer::addBlock(const QVector<QByteArray> &perColor, int advance)
{
    if (m_blockIndex > 0) {
        const uint32_t adv = static_cast<uint32_t>(advance >= 0 ? advance
                                                               : m_cfg.blockAdvance);
        putByte(0x1B); putByte(0x28); putByte(0x76); putByte(0x04); putByte(0x00);
        putU32(adv);
    }

    const int expect = m_cfg.bytesPerLine * m_cfg.blockRows;
    const int colorCount = m_cfg.colors.size();
    for (int c = 0; c < colorCount; ++c) {
        // ESC ( $ 04 00 <u32>：厂商实测 = (blockIndex / 16) % 4
        putByte(0x1B); putByte(0x28); putByte(0x24); putByte(0x04); putByte(0x00);
        putU32(static_cast<uint32_t>(m_cfg.dollarMode == 0
                                         ? 0
                                         : (m_blockIndex / 16) % 4));

        // ESC i <color> <compress=1> <bitDepth> <nL nH> <mL mH>
        putByte(0x1B); putByte(0x69);
        putByte(m_cfg.colors[c].code);
        putByte(0x01);
        putByte(static_cast<uint8_t>(m_cfg.colorDepth));
        putU16(static_cast<uint16_t>(m_cfg.bytesPerLine));
        putU16(static_cast<uint16_t>(m_cfg.blockRows));

        QByteArray raw(expect, '\0');
        if (c < perColor.size() && !perColor[c].isEmpty()) {
            const int n = qMin(raw.size(), perColor[c].size());
            memcpy(raw.data(), perColor[c].constData(), static_cast<size_t>(n));
        }
        const QByteArray enc = rleEncode(reinterpret_cast<const uint8_t *>(raw.constData()),
                                         raw.size(), m_cfg.bytesPerLine);
        put(enc.constData(), static_cast<int>(enc.size()));
        putByte(0x0D);
    }
    ++m_blockIndex;
}

void Escp2Writer::writeTail()
{
    putByte(0x0C);                 // FF 换页
    putByte(0x1B); putByte(0x40);  // ESC @
    static const uint8_t escR[6] = {0x1B, 0x28, 0x52, 0x08, 0x00, 0x00};
    put(escR, 6);
    put("REMOTE1", 7);
    putRemote("LD", QByteArray());
    putRemote("JE", QByteArray(1, '\0'));
    static const uint8_t exitRemote[4] = {0x1B, 0x00, 0x00, 0x00};
    put(exitRemote, 4);
}

QByteArray Escp2Writer::finish()
{
    writeTail();
    return m_out;
}

QByteArray Escp2Writer::rleEncode(const uint8_t *data, int len, int lineBytes)
{
    QByteArray out;
    out.reserve(len / 4 + 16);
    const int line = qMax(1, lineBytes);
    for (int ls = 0; ls < len; ls += line) {
        const int le = qMin(len, ls + line);
        int i = ls;
        while (i < le) {
            int run = 1;
            while (i + run < le && data[i + run] == data[i] && run < 128) ++run;
            if (run >= 3) {   // T2 实测：连续 >=3 字节才用重复段（2 字节走字面量）
                out.append(static_cast<char>(257 - run));
                out.append(static_cast<char>(data[i]));
                i += run;
            } else {
                const int start = i;
                while (i < le) {
                    if (i + 1 < le) {
                        int nr = 1;
                        while (i + nr < le && data[i + nr] == data[i] && nr < 128) ++nr;
                        if (nr >= 3) break;
                    }
                    ++i;
                    if (i - start >= 128) break;
                }
                const int n = i - start;
                if (n > 0) {
                    out.append(static_cast<char>(n - 1));
                    out.append(reinterpret_cast<const char *>(data + start), n);
                }
            }
        }
    }
    return out;
}

QByteArray Escp2Writer::rleDecode(const uint8_t *data, int len, int expected)
{
    QByteArray out;
    out.reserve(expected);
    int i = 0;
    while (i < len && out.size() < expected) {
        const uint8_t c = data[i++];
        if (c <= 127) {
            const int n = c + 1;
            for (int k = 0; k < n && i < len && out.size() < expected; ++k)
                out.append(static_cast<char>(data[i++]));
        } else {
            const int n = 257 - c;
            if (i >= len) break;
            const char v = static_cast<char>(data[i++]);
            for (int k = 0; k < n && out.size() < expected; ++k)
                out.append(v);
        }
    }
    return out;
}

} // namespace mtr
