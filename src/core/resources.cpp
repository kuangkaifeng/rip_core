#include "core/resources.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QStringList>

namespace mtr {

namespace {
QString g_baseDir;
}

void setResourceBaseDir(const QString &dir)
{
    g_baseDir = dir;
}

QString resourceBaseDir()
{
    return g_baseDir;
}

QString resolveResourceDir(const QString &name)
{
    QStringList candidates;
    if (!g_baseDir.isEmpty())
        candidates << QDir(g_baseDir).filePath(name);
    if (QCoreApplication::instance()) {
        const QString appDir = QCoreApplication::applicationDirPath();
        if (!appDir.isEmpty()) {
            candidates << QDir(appDir).filePath(name)
                       << QDir(appDir).filePath(QStringLiteral("../") + name);
        }
    }
    for (const QString &c : candidates) {
        if (QFileInfo(c).isDir())
            return QDir::cleanPath(c);
    }
    return QString();
}

} // namespace mtr
