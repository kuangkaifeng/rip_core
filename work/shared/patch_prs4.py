# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t = open(p, encoding="utf-8").read()
assert "PrsConfig::parseRecords" not in t
insert = r'''
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

'''
marker = "const PrsMode *PrsConfig::mode(int modeId) const"
t = t.replace(marker, insert + marker, 1)
open(p, "w", encoding="utf-8", newline="").write(t)
print("re-added functions")
