// ============================================================================
// rip_module_shim.cpp —— 与蒙泰 ripModule.h 完全同签名的 C API 兼容层（DLL）
//
// 目的：提供一个可 1:1 替换 mtrip.dll 的 DLL（默认名 mtr_rip.dll），
//       rip-studio 现有代码（include "ripModule.h" + link mtrip.lib）只需把
//       DLL/lib 换成我们的，即可不依赖蒙泰 SDK / 加密锁地生成 .prn。
//
// 导出函数（与蒙泰一致）：
//   const void* MainTopRip(const void* data, size_t* size);
//   void        MainTopRipCancel();
//   void        MainTopRipReleaseBuffer(const void* buf);
//   void        MainTopShutdown();
//
// 行为：
//   * data = UTF-8 JSON 命令（command: "rip" / "config" / "queryMode" ...）
//   * 返回 = malloc 的 UTF-8 JSON，调用方用 MainTopRipReleaseBuffer 释放
//   * "rip" 命令：解析作业 JSON → 运行 mtr 引擎 → 写 output.file.name 指定的 .prn
//                 → 返回 {"result":0}
//   * "config"/其它命令：返回 {"result":0}（配置项在本实现中无需生效）
// ============================================================================
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <mutex>
#ifdef _WIN32
#include <windows.h>
#endif
#include <string>

#include <QByteArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QString>
#include <QDebug>

#include "core/job_config.h"
#include "core/resources.h"
#include "core/rip_engine.h"

#ifdef _WIN32
#define MTR_API __declspec(dllexport)
#else
#define MTR_API __attribute__((visibility("default")))
#endif

namespace {

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
    const int slash = p.lastIndexOf(QLatin1Char('\\'));
    return slash > 0 ? p.left(slash) : QString();
}
#endif

std::mutex g_mutex;
int g_cancelRequested = 0;
int g_shutdown = 0;

const void *makeResponse(const QByteArray &json)
{
    void *buf = std::malloc(static_cast<size_t>(json.size()));
    if (!buf) return nullptr;
    std::memcpy(buf, json.constData(), static_cast<size_t>(json.size()));
    return buf;
}

QByteArray errorJson(int result, const QString &message)
{
    QJsonObject o;
    o.insert(QStringLiteral("result"), result);
    o.insert(QStringLiteral("errorString"), message);
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

QByteArray okJson()
{
    QJsonObject o;
    o.insert(QStringLiteral("result"), 0);
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

// 一条 "rip" 命令
int runRipJob(const QByteArray &json, QString *err)
{
    QJsonParseError perr;
    const QJsonDocument doc = QJsonDocument::fromJson(json, &perr);
    if (perr.error != QJsonParseError::NoError || !doc.isObject()) {
        if (err) *err = QStringLiteral("invalid json: %1").arg(perr.errorString());
        return 1;
    }
    mtr::RipJob job;
    if (!mtr::RipJob::fromJson(doc.object(), &job, err))
        return 2;
    if (job.inputPath.isEmpty() || job.prnPath.isEmpty()) {
        if (err) *err = QStringLiteral("job missing doc.name or output.file.name");
        return 2;
    }
    mtr::RipEngine engine;
    if (!engine.run(job, err))
        return 3;
    return 0;
}

} // namespace

extern "C" {

MTR_API const void *MainTopRip(const void *data, size_t *size)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_shutdown) {
        const QByteArray r = errorJson(9, QStringLiteral("engine already shut down"));
        if (size) *size = static_cast<size_t>(r.size());
        return makeResponse(r);
    }
#ifdef _WIN32
    static bool s_resourceInited = false;
    if (!s_resourceInited) {
        const QString dir = moduleDirectory();
        if (!dir.isEmpty())
            mtr::setResourceBaseDir(dir);
        s_resourceInited = true;
    }
#endif
    if (!data || !size) {
        const QByteArray r = errorJson(1, QStringLiteral("invalid arguments"));
        if (size) *size = static_cast<size_t>(r.size());
        return makeResponse(r);
    }

    const QByteArray json(static_cast<const char *>(data), static_cast<qsizetype>(*size));
    QJsonParseError perr;
    const QJsonDocument doc = QJsonDocument::fromJson(json, &perr);
    const QString command = (perr.error == QJsonParseError::NoError && doc.isObject())
                                ? doc.object().value(QStringLiteral("command")).toString()
                                : QString();

    QByteArray response;
    if (command == QLatin1String("rip")) {
        QString err;
        const int rc = runRipJob(json, &err);
        response = rc == 0 ? okJson() : errorJson(rc, err);
    } else if (command == QLatin1String("config")) {
        response = okJson(); // 本实现无需配置
    } else if (command == QLatin1String("queryMode")) {
        // 简化：返回空 modes（生产环境由 mtr_cli info --prs 提供模式表）
        QJsonObject o;
        o.insert(QStringLiteral("result"), 0);
        o.insert(QStringLiteral("modes"), QJsonArray());
        response = QJsonDocument(o).toJson(QJsonDocument::Compact);
    } else {
        response = okJson();
    }
    if (response.isEmpty())
        response = okJson();
    *size = static_cast<size_t>(response.size());
    return makeResponse(response);
}

MTR_API void MainTopRipCancel()
{
    g_cancelRequested = 1;
}

MTR_API void MainTopRipReleaseBuffer(const void *buf)
{
    std::free(const_cast<void *>(buf));
}

MTR_API void MainTopShutdown()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_shutdown = 1;
}

} // extern "C"
