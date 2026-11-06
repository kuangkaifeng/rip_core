# -*- coding: utf-8 -*-
# 1) build.cmd：构建前强制清理 GUI 目标对象（避免头文件签名变化时的陈旧 obj 链接错误）
p = r"D:\work\RIP核心分析\build.cmd"
t = open(p, encoding="ascii", newline="").read()
needle = '"%CMAKE%" -S src -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=%QT%'
assert needle in t, "cmake line missing"
add = ('rem ---- force rebuild GUI objects: avoid stale object/header signature mismatch ----\r\n'
       'if exist "build\\CMakeFiles\\mtr_gui.dir" rmdir /s /q "build\\CMakeFiles\\mtr_gui.dir"\r\n'
       + needle)
t = t.replace(needle, add, 1)
open(p, "w", encoding="ascii", newline="").write(t)
print("build.cmd: force gui rebuild")

# 2) CMake：给 obj 加显式头文件依赖（双保险）
p = r"D:\work\RIP核心分析\src\CMakeLists.txt"
t = open(p, encoding="utf-8").read()
add2 = """
set_source_files_properties(
    gui/main.cpp gui/mainwindow.cpp
    PROPERTIES OBJECT_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/gui/previewrenderer.h;${CMAKE_CURRENT_SOURCE_DIR}/gui/mainwindow.h"
)
"""
if "OBJECT_DEPENDS" not in t:
    t = t.replace("target_link_libraries(mtr_gui PRIVATE mtr_core Qt6::Widgets)",
                  "target_link_libraries(mtr_gui PRIVATE mtr_core Qt6::Widgets)\n" + add2)
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("cmake: OBJECT_DEPENDS set")
