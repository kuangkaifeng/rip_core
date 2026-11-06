# Additional clean files
cmake_minimum_required(VERSION 3.16)

if("${CONFIG}" STREQUAL "" OR "${CONFIG}" STREQUAL "Debug")
  file(REMOVE_RECURSE
  "CMakeFiles\\lcms2_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\lcms2_autogen.dir\\ParseCache.txt"
  "CMakeFiles\\mtr_cli_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\mtr_cli_autogen.dir\\ParseCache.txt"
  "CMakeFiles\\mtr_core_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\mtr_core_autogen.dir\\ParseCache.txt"
  "CMakeFiles\\mtr_gui_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\mtr_gui_autogen.dir\\ParseCache.txt"
  "CMakeFiles\\mtr_prncheck_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\mtr_prncheck_autogen.dir\\ParseCache.txt"
  "CMakeFiles\\mtr_rip_autogen.dir\\AutogenUsed.txt"
  "CMakeFiles\\mtr_rip_autogen.dir\\ParseCache.txt"
  "lcms2_autogen"
  "mtr_cli_autogen"
  "mtr_core_autogen"
  "mtr_gui_autogen"
  "mtr_prncheck_autogen"
  "mtr_rip_autogen"
  )
endif()
