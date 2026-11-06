# -*- coding: utf-8 -*-
# 1) CMake: Qt Widgets + mtr_gui
p = r"D:\work\RIP核心分析\src\CMakeLists.txt"
t = open(p, encoding="utf-8").read()
t = t.replace("find_package(Qt6 REQUIRED COMPONENTS Core Gui)",
              "find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)")
t = t.replace("set(CMAKE_AUTOMOC OFF)\nset(CMAKE_AUTORCC OFF)",
              "set(CMAKE_AUTOMOC OFF)\nset(CMAKE_AUTORCC OFF)\nset(CMAKE_AUTOUIC OFF)")
t += """
# ---- GUI（Qt Widgets 可视化工具）-------------------------------------------
add_executable(mtr_gui
    gui/main.cpp
    gui/mainwindow.cpp
    gui/previewrenderer.cpp
)
target_include_directories(mtr_gui PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(mtr_gui PRIVATE mtr_core Qt6::Widgets)
"""
open(p, "w", encoding="utf-8", newline="").write(t)
print("cmake: mtr_gui added")

# 2) mainwindow.cpp: connect mode combo
p = r"D:\work\RIP核心分析\src\gui\mainwindow.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("""    connect(m_prsCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onLoadPrs);""",
"""    connect(m_prsCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onLoadPrs);
    connect(m_modeCombo, &QComboBox::currentIndexChanged, this, &MainWindow::onModeChanged);""")
open(p, "w", encoding="utf-8", newline="").write(t)
print("mainwindow: mode connect added")
