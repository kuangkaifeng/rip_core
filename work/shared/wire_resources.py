# -*- coding: utf-8 -*-
import io
# 1) CMake
p = r"D:\work\RIP核心分析\src\CMakeLists.txt"
t = open(p, encoding="utf-8").read()
if "core/resources.cpp" not in t:
    t = t.replace("    core/image_io.cpp\n", "    core/image_io.cpp\n    core/resources.cpp\n")
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("cmake: resources.cpp added")

# 2) prs_config.cpp bundledIccDir -> ResourceBaseDir 优先
p = r"D:\work\RIP核心分析\src\core\prs_config.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include <QCoreApplication>', '#include <QCoreApplication>\n\n#include "core/resources.h"')
old = """QString PrsConfig::bundledIccDir()
{
    const QString appDir = QCoreApplication::applicationDirPath();
    const QStringList candidates = {
        QDir(appDir).filePath(QStringLiteral("icc")),
        QDir(appDir).filePath(QStringLiteral("3rdparty/icc")),
        QDir(appDir).absoluteFilePath(QStringLiteral("../../3rdparty/icc")),
        QDir(appDir).absoluteFilePath(QStringLiteral("../3rdparty/icc")),
    };
    for (const QString &c : candidates)
        if (QDir(c).exists()) return c;
    return QString();
}"""
new = """QString PrsConfig::bundledIccDir()
{
    const QString base = resourceBaseDir();
    QStringList candidates;
    if (!base.isEmpty())
        candidates << QDir(base).filePath(QStringLiteral("icc"))
                   << QDir(base).filePath(QStringLiteral("3rdparty/icc"));
    if (QCoreApplication::instance()) {
        const QString appDir = QCoreApplication::applicationDirPath();
        if (!appDir.isEmpty()) {
            candidates << QDir(appDir).filePath(QStringLiteral("icc"))
                       << QDir(appDir).filePath(QStringLiteral("3rdparty/icc"))
                       << QDir(appDir).absoluteFilePath(QStringLiteral("../../3rdparty/icc"))
                       << QDir(appDir).absoluteFilePath(QStringLiteral("../3rdparty/icc"));
        }
    }
    for (const QString &c : candidates)
        if (QDir(c).exists()) return QDir::cleanPath(c);
    return QString();
}"""
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("prs_config: bundledIccDir uses resourceBaseDir")

# 3) rip_engine.cpp: screen/color dirs
p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include "core/image_io.h"', '#include "core/image_io.h"\n#include "core/resources.h"')
old2 = """    QString screenDir = QCoreApplication::applicationDirPath() + QStringLiteral("/screen");
    if (!QFileInfo::exists(screenDir + QStringLiteral("/screen_meta.json")))
        screenDir = QFileInfo(job.prsPath).absolutePath() + QStringLiteral("/screen");"""
new2 = """    QString screenDir = resolveResourceDir(QStringLiteral("screen"));
    if (screenDir.isEmpty() || !QFileInfo::exists(screenDir + QStringLiteral("/screen_meta.json")))
        screenDir = QFileInfo(job.prsPath).absolutePath() + QStringLiteral("/screen");"""
assert old2 in t
t = t.replace(old2, new2)
old3 = """        const QString calibPath =
            QCoreApplication::applicationDirPath() + QStringLiteral("/color/calib_gray.bin");"""
new3 = """        QString calibDir = resolveResourceDir(QStringLiteral("color"));
        const QString calibPath = calibDir.isEmpty()
                                      ? QString()
                                      : QDir(calibDir).filePath(QStringLiteral("calib_gray.bin"));"""
assert old3 in t
t = t.replace(old3, new3)
open(p, "w", encoding="utf-8", newline="").write(t)
print("rip_engine: resource dirs")

# 4) DLL shim: 设置 DLL 目录为资源基准
p = r"D:\work\RIP核心分析\src\api\rip_module_shim.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace('#include "core/job_config.h"', '#include "core/job_config.h"\n#include "core/resources.h"')
old4 = """namespace {

std::mutex g_mutex;"""
new4 = """namespace {

#ifdef _WIN32
QString moduleDirectory()
{
    HMODULE hmod = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(&moduleDirectory), &hmod))
        return QString();
    wchar_t path[MAX_PATH] = {0};
    if (GetModuleFileNameW(hmod, path, MAX_PATH) == 0)
        return QString();
    QString p = QString::fromWCharArray(path);
    const int slash = p.lastIndexOf(QLatin1Char('\\\\'));
    return slash > 0 ? p.left(slash) : QString();
}
#endif

std::mutex g_mutex;"""
assert old4 in t
t = t.replace(old4, new4)
old5 = """    if (!data || !size) {"""
new5 = """#ifdef _WIN32
    static bool s_resourceInited = false;
    if (!s_resourceInited) {
        const QString dir = moduleDirectory();
        if (!dir.isEmpty())
            mtr::setResourceBaseDir(dir);
        s_resourceInited = true;
    }
#endif
    if (!data || !size) {"""
assert old5 in t
t = t.replace(old5, new5, 1)
# 需要 windows.h
if "#include <windows.h>" not in t:
    t = t.replace("#include <mutex>", "#include <mutex>\n#ifdef _WIN32\n#include <windows.h>\n#endif")
open(p, "w", encoding="utf-8", newline="").write(t)
print("shim: resource base dir init")
