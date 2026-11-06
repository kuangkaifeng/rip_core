# -*- coding: utf-8 -*-
# 1) previewrenderer: add QFile/QIODevice includes
p = r"D:\work\RIP核心分析\src\gui\previewrenderer.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("#include <QColor>", "#include <QColor>\n#include <QFile>")
open(p, "w", encoding="utf-8", newline="").write(t)
print("previewrenderer includes fixed")

# 2) CMake automoc ON
p = r"D:\work\RIP核心分析\src\CMakeLists.txt"
t = open(p, encoding="utf-8").read()
t = t.replace("set(CMAKE_AUTOMOC OFF)", "set(CMAKE_AUTOMOC ON)")
open(p, "w", encoding="utf-8", newline="").write(t)
print("automoc ON")

# 3) mainwindow: static_cast instead of qobject_cast
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("auto *th = qobject_cast<RipThread *>(m_thread);",
              "auto *th = static_cast<RipThread *>(m_thread);")
open(p, "w", encoding="utf-8", newline="").write(t)
print("static_cast fixed")

# 4) build.cmd: deploy Qt Widgets + platform plugin (newline='' 保留 CRLF)
p = r"D:\work\RIP核心分析\build.cmd"
t = open(p, encoding="ascii", newline="").read()
needle = 'copy /y "%QTDIR%\\bin\\Qt6Gui.dll" "build\\" >nul 2>&1'
assert needle in t, "needle missing"
add = (needle + '\r\n'
       'copy /y "%QTDIR%\\bin\\Qt6Widgets.dll" "build\\" >nul 2>&1\r\n'
       'if not exist "build\\platforms" mkdir "build\\platforms"\r\n'
       'copy /y "%QTDIR%\\plugins\\platforms\\qwindows.dll" "build\\platforms\\" >nul 2>&1\r\n'
       'if not exist "build\\styles" mkdir "build\\styles"\r\n'
       'copy /y "%QTDIR%\\plugins\\styles\\*.dll" "build\\styles\\" >nul 2>&1')
t = t.replace(needle, add, 1)
t = t.replace('echo [build] OK: %ROOT%build\\mtr_cli.exe',
              'echo [build] OK: %ROOT%build\\mtr_cli.exe\r\necho [build] OK: %ROOT%build\\mtr_gui.exe (GUI)')
open(p, "w", encoding="ascii", newline="").write(t)
print("build.cmd updated")
