# -*- coding: utf-8 -*-
p = r"D:\work\RIP核心分析\docs\07_gui.md"
t = open(p, encoding="utf-8").read()
add = """

## 6. 已知问题与修复：生成后界面"卡住"

### 症状
生成 PRN 完成后界面无响应/光标一直显示"忙"。

### 根因（两处，已修复）
1. **预览在 GUI 主线程同步执行**：早期版本 RIP 线程结束后，直接在 GUI 线程解码 PRN
   （4308×3924 页面要建 4 张全尺寸平面 + 全尺寸通道图，耗时 1s+ 且期间事件循环被阻塞）；
2. **光标栈错误**：`setBusy(false)` 里成对 `setOverrideCursor/restoreOverrideCursor` 用法不对，
   每次生成都会在 Qt 光标栈里残留一个 `WaitCursor` ⇒ 之后光标永远是"等待"图标，看起来像卡死。

### 修复
- 预览改为**独立后台线程**（`PreviewThread`），解码+渲染不再阻塞事件循环；
- 预览渲染改为**按显示分辨率采样**（最长边 ≤1600），大图不再生成全尺寸 QImage；
  金样本预览耗时从 ~1s 降到 **352 ms**，720px 大图端到端从 3.9s 降到 2.3s；
- 光标改为只在 busy=true 时 push、busy=false 时 restore，成对平衡；
- 内容像素 > 40M（约 6600×6600）的超大图**自动跳过预览**并提示"PRN 本身已生成成功"，
  避免内存被打爆导致假死（实测 6600×6600：RIP 1.9s 完成，预览跳过，界面不卡）；
- 关闭窗口时若有后台任务未完成，会提示等待而不是强杀线程；
- 原图预览改用 ≤1600 的缩略图，避免大图切"原图"视图时反复缩放卡顿。

### 自检
```powershell
build\\mtr_gui.exe --selftest reference\\inputs\\flat_black_720.png reference\\prs\\A3-DTF-1390.prs 2 work\\shared\\tmp
# 期望：RIP OK（~0.8s）+ 预览 OK（4320×4320）+ SELFTEST OK，总耗时 ~2.3s
```
"""
if "已知问题与修复" not in t:
    open(p, "w", encoding="utf-8", newline="").write(t + add)
    print("gui doc updated")

# 06_validation 补一条
p2 = r"D:\work\RIP核心分析\docs\06_validation.md"
t2 = open(p2, encoding="utf-8").read()
add2 = """

## 17. GUI 预览卡顿修复（2026-11-06 晚）

生成 PRN 后界面"卡住"的根因与修复：
1. 预览在 GUI 主线程同步解码/渲染 → 改为后台线程（`PreviewThread`）；
2. 预览渲染按显示分辨率采样（最长边 ≤1600，不再建全尺寸通道图）；
3. 修复 `setBusy` 光标栈错误（此前每次生成残留 WaitCursor，界面看起来永久"忙"）；
4. 内容 >40M 像素自动跳过预览并提示（PRN 已生成成功），防内存假死；
5. 关闭窗口时等待后台任务，避免强杀 QThread。

实测：金样本（4308×3924）预览 **352ms**；720px（4320×4320）端到端 **2.3s**（修复前 3.9s）；
6600×6600 超大作业 RIP 1.9s 完成、预览自动跳过、界面不卡。
详见 [docs/07_gui.md](07_gui.md) §6。
"""
if "GUI 预览卡顿修复" not in t2:
    open(p2, "w", encoding="utf-8", newline="").write(t2 + add2)
    print("validation doc updated")
