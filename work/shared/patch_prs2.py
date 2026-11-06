# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t = open(p, encoding="utf-8").read()
old = """void PrsConfig::resolveModeRecords()
{
    if (records.isEmpty()) return;
    // 只给 colorCorrection=true 的模式分配记录；按出现顺序（A3: 5,7,9；H13: 0..3）
    int rec = 0;
    for (PrsMode &m : modes) {
        if (m.colorCorrection && rec < records.size())
            m.recordIndex = rec++;
    }
}"""
new = """void PrsConfig::resolveModeRecords()
{
    if (records.isEmpty()) return;
    // 只给 colorCorrection=true 的模式分配记录。
    // 注意（T3 实测）：A3 的记录顺序不是 modeId 顺序！A3: rec0->mode7(v1440x1400)、
    // rec1->mode5(v1440x720)、rec2->mode9(v2880x1400)。按 dest ICC 文件名匹配。
    QVector<bool> used(records.size(), false);
    for (PrsMode &m : modes) {
        if (!m.colorCorrection) continue;
        int best = -1;
        int bestScore = 1 << 30;
        for (int i = 0; i < records.size(); ++i) {
            if (used[i]) continue;
            const QString &dest = records.at(i).destCmykPath;
            if (dest.isEmpty()) continue;
            // 期望形式 v<yDPI>x<xDPI>...；数值段提取后按 |x-xDPI| 打分
            static const QRegularExpression re(QStringLiteral("v(\\\\d+)x(\\\\d+)"));
            const auto mt = re.match(dest);
            if (!mt.hasMatch()) continue;
            const int vy = mt.captured(1).toInt();
            const int vx = mt.captured(2).toInt();
            if (vy != m.yDPI) continue;
            const int score = qAbs(vx - m.xDPI);
            if (score < bestScore) {
                bestScore = score;
                best = i;
            }
        }
        if (best >= 0) {
            m.recordIndex = best;
            used[best] = true;
        }
    }
}"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched prs mapping")
