p = r"D:\work\RIP核心分析\src\main.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('    mtr::PrsConfig cfg;\r\n    QString err;', '    fprintf(stderr, "[trace] info start\\n");\r\n    mtr::PrsConfig cfg;\r\n    QString err;')
t = t.replace('    if (!cfg.load(parser.value(prsOpt), &err)) {', '    fprintf(stderr, "[trace] loading prs\\n");\r\n    if (!cfg.load(parser.value(prsOpt), &err)) {')
t = t.replace('    QString text;\r\n    QTextStream ts(&text);', '    fprintf(stderr, "[trace] loaded, dump\\n");\r\n    QString text;\r\n    QTextStream ts(&text);')
t = t.replace('    fputs(qPrintable(text), stdout);', '    fprintf(stderr, "[trace] dump done len=%d\\n", (int)text.size());\r\n    fputs(qPrintable(text), stdout);')
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched" if "[trace] info start" in t else "PATCH FAILED (maybe LF file)")
