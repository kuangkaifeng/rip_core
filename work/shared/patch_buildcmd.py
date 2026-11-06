p = r"D:\work\RIP核心分析\build.cmd"
t = open(p, encoding="ansi").read()
old = 'if exist "reference\prs" ('
new = 'if exist "3rdparty\color" (\r\n  if not exist "build\color" mkdir "build\color"\r\n  copy /y "3rdparty\color\*.*" "build\color\" >nul 2>&1\r\n)\r\nif exist "reference\prs" ('
assert old in t
t = t.replace(old, new, 1)
open(p, "w", encoding="ansi", newline="").write(t)
print("build.cmd updated (color copy)")
