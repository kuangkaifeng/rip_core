# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\06_validation.md"
t = open(p, encoding="utf-8").read()
add = """

## 15. DLL drop-in 与板卡机 HSSF 路径验证（收口轮）

### 15.1 `mtr_rip.dll` 按蒙泰 C API 端到端调用（`tools/validate/test_dll_api.py`）
用 Python ctypes 以**蒙泰 `ripModule.h` 完全相同的签名**加载 `mtr_rip.dll` 并调用：

| case | 结果 |
|---|---|
| `MainTopRip(rip 作业 JSON)` → 纯白 100×100 m2 | 返回 `{"result":0}`；生成 264B PRN，与 oracle **TI 归一化后逐字节一致** |
| 灰度 64×64 m2 作业 | 返回 `{"result":0}`，输出 104,612B（与 `mtr_cli` 路径一致） |
| 非法输入（图片不存在） | 返回 `{"result":3,"errorString":"image not found: ..."}`，不崩溃 |
| `MainTopRip(config)` | 返回 `{"result":0}` |
| `MainTopRipReleaseBuffer` / `MainTopShutdown` | 正常 |

> 说明：DLL 内部已支持"非 Qt 宿主"资源解析（以 DLL 所在目录为基准查找 `icc/`、`screen/`、`color/`），
> 部署时把这三个资源目录放到 `mtr_rip.dll` 同目录即可（`build.cmd` 已自动布置）。
> 在 Qt 宿主（rip-studio）中则同时支持 `QCoreApplication::applicationDirPath()`。

### 15.2 板卡机 H13 / HSSF 0x5555 生成（引擎 `writeHssf` 路径）
以 `probe_black_64_h13_m0` 作业（H13 XP600.prs / mode0 / flat_black_64）实测：

| 项目 | 结果 |
|---|---|
| 文件大小 | 184,368B = oracle 184,368B ✅ |
| 48B 头 12 字段（sig/xDPI/yDPI/BPL/H/W/paperWidth/planes/reserved[4]） | **12/12 完全一致**（reserved 对齐为 0） |
| 平面数/顺序 | 5 平面 K,C,M,Y,W1 ✅（5-plane 模式已修：白墨通道数 = planes−4） |
| W1 平面 | ours 0 = oracle 0（**100% 一致**；没有 `inputColorEditor` 时白墨应为空） |
| K/C/M/Y 点阵 | 62%~77% 一致 —— 差异来自 H13 **自身**的加网/线性化/色彩链（我们当前套用 A3 mode2 的加网 tile 与灰度标定），属"未采集 H13 专用数据"的已知限制 |

**结论**：HSSF 容器/头/平面布局/白墨语义已完全复刻；H13 内容级复刻需要按同方法补 H13 探针语料
（H13 各 mode 的 CMYK 阶梯/加网探针），属后续可选工作。
"""
if "## 15. DLL drop-in" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("validation doc: section 15 added")

# 集成文档补资源部署说明
p2 = r"D:\work\RIP核心分析\docs\05_integration.md"
t2 = open(p2, encoding="utf-8").read()
add2 = """

## 7. 资源文件部署（DLL 形态必读）

`mtr_rip.dll` 运行需要三份数据（`build.cmd` 会从 `3rdparty/` 自动复制到 `build/`）：

| 目录 | 内容 | 说明 |
|---|---|---|
| `icc/` | sRGB / CoatedFOGRA39 / SWOP / A3-DTF-1390 输出 ICM / dtf ICM | 颜色转换 |
| `screen/` | `screen_meta.json` + `thr_{C,M,Y,K}.bin`（1024² 加网 tile） | FM 加网复刻 |
| `color/` | `calib_gray.bin`（灰度轴标定 LUT） | RGB→CMYK 数值标定 |

部署：把上述三个目录放到 `mtr_rip.dll` 同目录（或 Qt 宿主 exe 所在目录）即可；
DLL 在首次调用时会自动以自身所在目录作为资源基准。
"""
if "## 7. 资源文件部署" not in t2:
    open(p2, "w", encoding="utf-8", newline="").write(t2 + add2)
    print("integration doc: resources section added")
