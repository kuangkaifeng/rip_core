# -*- coding: utf-8 -*-
"""DLL 端到端测试：把 mtr_rip.dll 当作蒙泰 mtrip.dll 调用（MainTopRip C API），
生成 PRN 并与 oracle 参考对比（TI 时间戳归一化）。

用法: python tools/validate/test_dll_api.py
"""
import ctypes, json, os, sys
from ctypes import c_void_p, c_size_t, POINTER

WS = r"D:\work\RIP核心分析"
BUILD = os.path.join(WS, "build")
DLL = os.path.join(BUILD, "mtr_rip.dll")
PR = os.path.join(WS, "reference", "prn_samples")
OUT = os.path.join(WS, "work", "shared", "dll_api_test")
os.makedirs(OUT, exist_ok=True)

if not os.path.exists(DLL):
    print("missing DLL:", DLL)
    sys.exit(1)

# 让 Windows 找到 Qt 依赖
os.add_dll_directory(BUILD)
lib = ctypes.WinDLL(DLL)

lib.MainTopRip.argtypes = [c_void_p, POINTER(c_size_t)]
lib.MainTopRip.restype = c_void_p
lib.MainTopRipCancel.argtypes = []
lib.MainTopRipCancel.restype = None
lib.MainTopRipReleaseBuffer.argtypes = [c_void_p]
lib.MainTopRipReleaseBuffer.restype = None
lib.MainTopShutdown.argtypes = []
lib.MainTopShutdown.restype = None


def call(json_bytes):
    buf = ctypes.create_string_buffer(json_bytes, len(json_bytes))
    size = c_size_t(len(json_bytes))
    ret = lib.MainTopRip(buf, ctypes.byref(size))
    if not ret:
        return None, 0
    data = ctypes.string_at(ret, size.value)
    lib.MainTopRipReleaseBuffer(ret)
    return data, size.value


def norm_ti(b):
    i = b.find(b"TI\x08\x00")
    if i < 0:
        return b
    bb = bytearray(b)
    for k in range(8):
        if i + 4 + k < len(bb):
            bb[i + 4 + k] = 0
    return bytes(bb)


# ---- case 1: 纯白 100x100 m2（oracle 264B, 期望逐字节一致）----
job = json.load(open(os.path.join(WS, "reference", "jobs",
                                  "a3dtf1390_flat_white_100_m2.json"), encoding="utf-8"))
out_prn = os.path.join(OUT, "dll_white_100_m2.prn")
job["prs"] = "D:/work/RIP核心分析/reference/prs/A3-DTF-1390.prs"
job["output"]["file"]["name"] = out_prn.replace("\\", "/")
rsp, n = call(json.dumps(job).encode("utf-8"))
print("case1 response:", rsp.decode("utf-8", "replace") if rsp else None)
ours = open(out_prn, "rb").read()
ref = open(os.path.join(PR, "a3dtf1390_flat_white_100_m2.prn"), "rb").read()
print("case1 (white): ours=%d ref=%d  bytes_equal(normTI)=%s" %
      (len(ours), len(ref), norm_ti(ours) == norm_ti(ref)))

# ---- case 2: 灰度 64x64 m2（对比页面点阵统计：结构/尺寸）----
job2 = json.load(open(os.path.join(WS, "reference", "jobs",
                                   "probe_scan_gray000_a3dtf1390_m2.json"), encoding="utf-8"))
out2 = os.path.join(OUT, "dll_gray000_64_m2.prn")
job2["prs"] = "D:/work/RIP核心分析/reference/prs/A3-DTF-1390.prs"
job2["output"]["file"]["name"] = out2.replace("\\", "/")
rsp, n = call(json.dumps(job2).encode("utf-8"))
print("case2 response:", rsp.decode("utf-8", "replace") if rsp else None)
ours2 = open(out2, "rb").read()
ref2 = open(os.path.join(PR, "probe_scan_gray000_a3dtf1390_m2.prn"), "rb").read()
print("case2 (gray000): ours=%d ref=%d  head_equal=%s" %
      (len(ours2), len(ref2), norm_ti(ours2)[:120] == norm_ti(ref2)[:120]))

# ---- case 3: 错误 JSON / 未知命令 的鲁棒性 ----
rsp, n = call(b'{"command":"rip","doc":{"name":"nope.png"},"output":{"file":{"name":"x.prn"}}}')
print("case3 bad input response:", rsp.decode("utf-8", "replace") if rsp else None)
rsp, n = call(b'{"command":"config","type":"errorString","setting":0}')
print("case4 config response:", rsp.decode("utf-8", "replace") if rsp else None)

lib.MainTopShutdown()
print("DLL API test done.")
