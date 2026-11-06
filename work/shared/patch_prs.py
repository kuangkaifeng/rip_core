# -*- coding: utf-8 -*-
import re
p = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t = open(p, encoding="utf-8").read()
# 1) curve extraction: gap only between curves
old = """            rec.curves.append(curve);
            p += 256 * 8 + 12;"""
new = """            rec.curves.append(curve);
            p += 256 * 8;
            if (c + 1 < 8) p += 12;"""
assert old in t
t = t.replace(old, new)
# 2) path record: only accept string starts (prev byte not printable)
old2 = """            QString s = cstr(m_raw, off, 260);
            if (s.size() >= 4 && looksLikeIccRecord(s))
                found.append({off, s});"""
new2 = """            if (off > 0) {
                const unsigned char prev = static_cast<unsigned char>(m_raw[off - 1]);
                if ((prev >= 0x20 && prev < 0x7f) || (prev >= '0' && prev <= '9'))
                    continue; // 说明处于字符串中间
            }
            QString s = cstr(m_raw, off, 260);
            if (s.size() >= 4 && looksLikeIccRecord(s))
                found.append({off, s});"""
assert old2 in t
t = t.replace(old2, new2)
# 3) dedupe by keeping longest string (SRGB vs RGB issues)
old3 = """        QStringList paths;
        for (const auto &pr : found) {
            if (paths.contains(pr.second)) continue;
            paths.append(pr.second);
            if (paths.size() >= 4) break;
        }"""
new3 = """        // 合并被截断的字符串：只保留“从记录起点开始”的完整路径（同一记录内 4 个不同后缀）
        QStringList paths;
        for (const auto &pr : found) {
            if (paths.contains(pr.second)) continue;
            bool isSuffixOfExisting = false;
            for (QString &e : paths) {
                if (e.endsWith(pr.second)) { isSuffixOfExisting = true; break; }
                if (pr.second.endsWith(e)) { e = pr.second; isSuffixOfExisting = true; break; }
            }
            if (isSuffixOfExisting) continue;
            paths.append(pr.second);
            if (paths.size() >= 4) break;
        }"""
assert old3 in t
t = t.replace(old3, new3)
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched ok")
