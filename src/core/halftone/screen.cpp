#include "core/halftone/screen.h"

#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <cmath>

namespace mtr {

namespace {

// 确定性 hash（兜底阈值场用）
uint32_t hash32(uint32_t x)
{
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}

QString channelName(int c)
{
    switch (c) {
    case 0: return QStringLiteral("C");
    case 1: return QStringLiteral("M");
    case 2: return QStringLiteral("Y");
    case 3: return QStringLiteral("K");
    default: return QStringLiteral("X");
    }
}

} // namespace

int Screen::toneToLevel(int t)
{
    if (t <= 0) return 0;
    if (t >= 255) return 3;
    return (3 * t) / 255;
}

void Screen::useFallback(int size)
{
    m_channels.clear();
    m_lastError.clear();
    for (int c = 0; c < 4; ++c) {
        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size * 3);
        const uint32_t seed = 0x9E3779B9u * (c + 1);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                const uint32_t h = hash32(static_cast<uint32_t>(x) * 0x1F1F1F1Fu ^
                                          static_cast<uint32_t>(y) * 0x85EBCA6Bu ^ seed);
                const int idx = (y * size + x) * 3;
                ch.threshold[idx + 0] = static_cast<uint8_t>((h >> 24) % 86);
                ch.threshold[idx + 1] = static_cast<uint8_t>(86 + ((h >> 16) % 86));
                ch.threshold[idx + 2] = static_cast<uint8_t>(171 + ((h >> 8) % 85));
            }
        }
        m_channels.append(ch);
    }
    m_loaded = true;
}

bool Screen::load(const QString &dir, QString *err)
{
    m_lastError.clear();
    const QDir d(dir);
    QFile metaFile(d.filePath(QStringLiteral("screen_meta.json")));
    if (!metaFile.exists()) {
        if (err) *err = QStringLiteral("screen_meta.json not found in %1").arg(dir);
        m_lastError = err ? *err : QString();
        return false;
    }
    if (!metaFile.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("cannot open screen_meta.json");
        return false;
    }
    const QJsonDocument doc = QJsonDocument::fromJson(metaFile.readAll());
    metaFile.close();
    if (!doc.isObject()) {
        if (err) *err = QStringLiteral("bad screen_meta.json");
        return false;
    }
    const QJsonObject root = doc.object();
    const int size = root.value(QStringLiteral("size")).toInt(64);
    const QJsonArray channels = root.value(QStringLiteral("channels")).toArray();
    const QStringList names = {QStringLiteral("C"), QStringLiteral("M"),
                               QStringLiteral("Y"), QStringLiteral("K")};
    m_channels.clear();
    for (const QString &name : names) {
        ScreenChannel ch;
        ch.size = size;
        ch.threshold.resize(size * size * 3);
        QString fileName = QStringLiteral("thr_%1.bin").arg(name);
        for (const QJsonValue &v : channels) {
            const QJsonObject o = v.toObject();
            if (o.value(QStringLiteral("ink")).toString().compare(name, Qt::CaseInsensitive) == 0) {
                if (o.contains(QStringLiteral("file")))
                    fileName = o.value(QStringLiteral("file")).toString();
                if (o.contains(QStringLiteral("phaseX")))
                    ch.phaseX = o.value(QStringLiteral("phaseX")).toInt();
                if (o.contains(QStringLiteral("phaseY")))
                    ch.phaseY = o.value(QStringLiteral("phaseY")).toInt();
                break;
            }
        }
        QFile f(d.filePath(fileName));
        if (!f.open(QIODevice::ReadOnly)) {
            if (err) *err = QStringLiteral("cannot open threshold file %1").arg(fileName);
            m_lastError = err ? *err : QString();
            return false;
        }
        const QByteArray raw = f.readAll();
        f.close();
        if (raw.size() < size * size * 3) {
            if (err) *err = QStringLiteral("threshold file too small: %1").arg(fileName);
            return false;
        }
        memcpy(ch.threshold.data(), raw.constData(), static_cast<size_t>(size * size * 3));
        m_channels.append(ch);
    }
    m_loaded = true;
    return true;
}

void Screen::dither(const QVector<uint8_t> &ink, int width, int height, int channel,
                    QVector<uint8_t> *level) const
{
    if (!level) return;
    level->resize(ink.size());
    if (m_channels.isEmpty()) {
        for (int i = 0; i < ink.size(); ++i)
            (*level)[i] = static_cast<uint8_t>(toneToLevel(ink[i]));
        return;
    }
    const ScreenChannel &ch = m_channels.at(qBound(0, channel, m_channels.size() - 1));
    const int size = ch.size;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int idx = y * width + x;
            const int t = ink[idx];
            if (t <= 0) {
                (*level)[idx] = 0;
                continue;
            }
            if (t >= 255) {
                (*level)[idx] = 3;
                continue;
            }
            const int tx = (x + ch.phaseX) % size;
            const int ty = (y + ch.phaseY) % size;
            const int ti = (ty * size + tx) * 3;
            const int t1 = ch.threshold[ti + 0];
            const int t2 = ch.threshold[ti + 1];
            const int t3 = ch.threshold[ti + 2];
            int lvl = (t >= t1) + (t >= t2) + (t >= t3);
            (*level)[idx] = static_cast<uint8_t>(qBound(0, lvl, 3));
        }
    }
}

} // namespace mtr
