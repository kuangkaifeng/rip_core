p = r"D:\work\RIP核心分析\tools\color_tools\build_rgb_cube17.py"
t = open(p, encoding="utf-8").read()
# 采样窗放大到 72（patch 内容 84px，留 6px 边）
t = t.replace("SAMPLE = 60", "SAMPLE = 72")
# 关闭像素级精化（内容平面存在 weave 相位差异，像素级不可靠），仅用均值反解
old = """        v0 = best_v_mean(ink, mean)
        # 像素级精化
        best = (match_score(ink, data, x0, y0, REFINE, 1, v0), v0)
        for dv in (-2, -1, 1, 2):
            v = max(0, min(255, v0 + dv))
            sc = match_score(ink, data, x0, y0, REFINE, 1, v)
            if sc > best[0]:
                best = (sc, v)
        v = best[1]
        vals[ink][idx] = v
        if v != v0:
            stats[ink]["v0_fix"] += 1
        if best[0] < 0.999:
            stats[ink]["wrong0"] += 1
        if best[0] < stats[ink]["maxerr"]:
            stats[ink]["maxerr"] = best[0]"""
new = """        v = best_v_mean(ink, mean)
        vals[ink][idx] = v
        stats[ink]["v0_fix"] += 0
        # 记录均值反解的预测误差（level 单位）
        err = abs(HIST[ink][v] - mean)
        if err > stats[ink]["maxerr"]:
            stats[ink]["maxerr"] = err"""
assert old in t
t = t.replace(old, new)
t = t.replace('print("  %s: v0_fixed=%d  low_match_patches=%d  worst_match=%.5f" %\n          (ink, stats[ink]["v0_fix"], stats[ink]["wrong0"], stats[ink]["maxerr"]))',
              'print("  %s: worst_mean_err=%.5f levels" % (ink, stats[ink]["maxerr"]))')
open(p, "w", encoding="utf-8", newline="").write(t)
print("patched mean-only")
