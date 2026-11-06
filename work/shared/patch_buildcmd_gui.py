# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\build.cmd"
t = open(p, encoding="ascii").read()
old = 'copy /y "%QTDIR%\\bin\\Qt6Gui.dll" "build\\" >nul 2>&1\r\n'
new = ('copy /y "%QTDIR%\\bin\\Qt6Gui.dll" "build\\" >nul 2>&1\r\n'
       'copy /y "%QTDIR%\\bin\\Qt6Widgets.dll" "build\\" >nul 2>&1\r\n'
       'if not exist "build\\platforms" mkdir "build\\platforms"\r\n'
       'copy /y "%QTDIR%\\plugins\\platforms\\qwindows.dll" "build\\platforms\\" >nul 2>&1\r\n'
       'if not exist "build\\styles" mkdir "build\\styles"\r\n'
       'copy /y "%QTDIR%\\plugins\\styles\\*.dll" "build\\styles\\" >nul 2>&1\r\n')
assert old in t
t = t.replace(old, new, 1)
t = t.replace('echo [build] OK: %ROOT%build\\mtr_cli.exe',
              'echo [build] OK: %ROOT%build\\mtr_cli.exe\r\necho [build] OK: %ROOT%build\\mtr_gui.exe (GUI)')
open(p, "w", encoding="ascii", newline="").write(t)
print("build.cmd deploy updated")
