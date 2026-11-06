# -*- coding: utf-8 -*-
# ---------- previewrenderer: 裁剪到内容区 + 白页处理 ----------
p = r"D:\work\RIP核心分析\src\gui\previewrenderer.cpp"
t = open(p, encoding="utf-8").read()
old = """        const int planesCount = info.planes > 0 ? info.planes : int(page.colors.size());
        for (auto it = page.planes.constBegin(); it != page.planes.constEnd(); ++it) {
            const QString ink = codeToInk(it.key(), planesCount);
            if (!ink.isEmpty())
                planes.insert(ink, it.value());
        }
        w = page.widthDots;
        h = page.rows;
        if (w <= 0 || h <= 0) {
            if (err) *err = QStringLiteral("ESC/P2 页面尺寸为 0");
            return false;
        }
        // 内容尺寸裁剪由 decode 的 page 提供（已按 P0 对齐）"""
new = """        const int planesCount = info.planes > 0 ? info.planes : int(page.colors.size());
        // 内容区（页面坐标系）：行 p0..p0+H，列 0..W
        int top = info.p0;
        if (top <= 0) top = 640;
        int contentW = info.contentWidthDots;
        int contentH = info.contentHeightDots;
        if (contentW <= 0 && info.paperWidth > 0)
            contentW = static_cast<int>(info.paperWidth);
        if (contentH <= 0)
            contentH = static_cast<int>(info.paperHeight) + info.pageMargin;
        if (contentW <= 0 || contentH <= 0) {
            contentW = page.widthDots;
            contentH = page.rows - top;
        }
        if (contentW <= 0 || contentH <= 0) {
            if (err) *err = QStringLiteral("ESC/P2 内容尺寸解析失败");
            return false;
        }
        for (auto it = page.planes.constBegin(); it != page.planes.constEnd(); ++it) {
            const QString ink = codeToInk(it.key(), planesCount);
            if (ink.isEmpty()) continue;
            // 裁剪：页面坐标 -> 内容坐标（保持内容尺寸，白页=全 0）
            QVector<uint8_t> cropped(static_cast<qsizetype>(contentW) * contentH, 0);
            for (int y = 0; y < contentH; ++y) {
                const int srcY = y + top;
                if (srcY < 0 || srcY >= page.rows) continue;
                const uint8_t *src = it.value().constData() +
                                     static_cast<qsizetype>(srcY) * page.widthDots;
                uint8_t *dst = cropped.data() + static_cast<qsizetype>(y) * contentW;
                const int n = qMin(contentW, page.widthDots);
                for (int x = 0; x < n; ++x) dst[x] = src[x];
            }
            planes.insert(ink, cropped);
        }
        w = contentW;
        h = contentH;"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("preview: crop to content")

# ---------- mainwindow: 减少日志噪声 ----------
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("""    m_prs = cfg;
    m_prsPath = p;""",
"""    m_prs = cfg;
    m_prsPath = p;
    m_modeCombo->blockSignals(true);""")
t = t.replace("""    m_modeCombo->setCurrentIndex(idx);
    onModeChanged();
}""",
"""    m_modeCombo->blockSignals(false);
    m_modeCombo->setCurrentIndex(idx);
    onModeChanged();
}""")
t = t.replace("""    m_mode = *m;
    m_hasMode = true;
    log(QStringLiteral("当前模式: %1").arg(modeLabel(m_mode)));
}""",
"""    m_mode = *m;
    m_hasMode = true;
    static QString lastModeLabel;
    const QString lbl = modeLabel(m_mode);
    if (lastModeLabel != lbl) {
        lastModeLabel = lbl;
        log(QStringLiteral("当前模式: %1").arg(lbl));
    }
}""")
open(p, "w", encoding="utf-8", newline="").write(t)
print("mainwindow: log polish")
