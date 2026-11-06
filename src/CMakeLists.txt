cmake_minimum_required(VERSION 3.21)

# ============================================================================
# mtr = MainTop Replacement —— 不依赖蒙泰 SDK 的 .prn 生成 RIP 引擎
# 只依赖 Qt6 (Core/Gui) + lcms2（源码内置）
# ============================================================================
project(mtr LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC OFF)
set(CMAKE_AUTOUIC OFF)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)

# ---- lcms2 (third party, source) -------------------------------------------
set(LCMS2_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../3rdparty/lcms2)
if(EXISTS ${LCMS2_DIR}/src/cmsio0.c)
    file(GLOB LCMS2_SOURCES ${LCMS2_DIR}/src/*.c)
    add_library(lcms2 STATIC ${LCMS2_SOURCES})
    target_include_directories(lcms2 PUBLIC ${LCMS2_DIR}/include)
    target_compile_definitions(lcms2 PRIVATE CMS_USE_CPP_API=0)
    message(STATUS "mtr: using bundled lcms2 from ${LCMS2_DIR}")
else()
    message(STATUS "mtr: bundled lcms2 not found, expecting system lcms2")
    add_library(lcms2 INTERFACE)
    target_link_libraries(lcms2 INTERFACE lcms2)
endif()

# ---- core library ----------------------------------------------------------
set(MTR_CORE_SOURCES
    core/image_io.cpp
    core/resources.cpp
    core/prs_config.cpp
    core/job_config.cpp
    core/rip_engine.cpp
    core/color/icc_transform.cpp
    core/color/rgb_cube_lut.cpp
    core/color/ink_limit.cpp
    core/color/linearization.cpp
    core/color/white_ink.cpp
    core/halftone/am_screen.cpp
    core/halftone/error_diffusion.cpp
    core/halftone/screen.cpp
    core/encode/plane_pack.cpp
    core/encode/escp2_writer.cpp
    core/encode/layout_escp2.cpp
    core/encode/hssf_writer.cpp
    core/decode/prn_reconstruct.cpp
    core/debug/prn_decode.cpp
    core/debug/bmp_writer.cpp
)

add_library(mtr_core STATIC ${MTR_CORE_SOURCES})
target_include_directories(mtr_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/core
)
target_link_libraries(mtr_core PUBLIC Qt6::Core Qt6::Gui lcms2)

# ---- CLI -------------------------------------------------------------------
add_executable(mtr_cli main.cpp)
target_link_libraries(mtr_cli PRIVATE mtr_core)

# ---- DLL: 与蒙泰 ripModule.h 同签名的兼容层（可直接替换 mtrip.dll）----------
add_library(mtr_rip SHARED api/rip_module_shim.cpp)
target_link_libraries(mtr_rip PRIVATE mtr_core)
set_target_properties(mtr_rip PROPERTIES OUTPUT_NAME "mtr_rip")

# ---- PRN 反解/验证工具（T5） ------------------------------------------------
add_executable(mtr_prncheck tools/mtr_prncheck.cpp)
target_link_libraries(mtr_prncheck PRIVATE mtr_core)

# ---- GUI（Qt Widgets 可视化工具）-------------------------------------------
add_executable(mtr_gui
    gui/main.cpp
    gui/mainwindow.cpp
    gui/previewrenderer.cpp
)
target_include_directories(mtr_gui PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(mtr_gui PRIVATE mtr_core Qt6::Widgets)

set_source_files_properties(
    gui/main.cpp gui/mainwindow.cpp
    PROPERTIES OBJECT_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/gui/previewrenderer.h;${CMAKE_CURRENT_SOURCE_DIR}/gui/mainwindow.h"
)

