// ============================================================================
// resources.h —— 运行资源目录解析（icc / screen / color）
//
// 有两种运行形态：
//   1) mtr_cli.exe：Qt 应用，资源在 exe 同目录（build/icc、build/screen、build/color）；
//   2) mtr_rip.dll 被非 Qt 宿主（如 rip-studio 里我们的 drop-in 场景）加载时，
//      QCoreApplication::applicationDirPath() 不可用，因此用 DLL 自身所在目录作为基准，
//      并由 DLL 入口调用 setResourceBaseDir(dllDir)。
// ============================================================================
#pragma once

#include <QString>

namespace mtr {

void setResourceBaseDir(const QString &dir);   // DLL 入口设置（exe 形态可不设）
QString resourceBaseDir();                     // 当前基准（可能为空）
// 依次在 基准目录、exe 目录、常见相对位置 下查找 <name> 子目录，返回第一个存在者
QString resolveResourceDir(const QString &name);
// 在 resolveResourceDir 失败时返回空字符串

} // namespace mtr
