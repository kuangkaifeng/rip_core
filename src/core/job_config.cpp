#include "core/job_config.h"

#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonValue>
#include <QJsonObject>
#include <QFileInfo>
#include <QDir>

namespace mtr {

bool RipJob::loadFromFile(const QString &path, RipJob *job, QString *err)
{
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        if (err) *err = QStringLiteral("cannot open job json: %1").arg(path);
        return false;
    }
    const QByteArray data = f.readAll();
    f.close();

    QJsonParseError perr;
    const QJsonDocument doc = QJsonDocument::fromJson(data, &perr);
    if (perr.error != QJsonParseError::NoError || !doc.isObject()) {
        if (err) *err = QStringLiteral("job json parse error: %1").arg(perr.errorString());
        return false;
    }
    if (!fromJson(doc.object(), job, err))
        return false;

    // 相对路径以 JSON 文件所在目录为基准
    const QString base = QFileInfo(path).absolutePath();
    auto absolutize = [&base](QString &p) {
        if (p.isEmpty()) return;
        QFileInfo fi(p);
        if (fi.isRelative())
            p = QDir(base).absoluteFilePath(p);
    };
    absolutize(job->inputPath);
    absolutize(job->prnPath);
    absolutize(job->prsPath);
    return true;
}

bool RipJob::fromJson(const QJsonObject &root, RipJob *job, QString *err)
{
    if (!job) return false;
    RipJob &j = *job;

    if (root.value(QStringLiteral("command")).toString() != QLatin1String("rip")) {
        if (err) *err = QStringLiteral("job.command is not \"rip\"");
        return false;
    }

    j.inputPath = root.value(QStringLiteral("doc")).toObject()
                      .value(QStringLiteral("name")).toString();
    j.prsPath = root.value(QStringLiteral("prs")).toString();
    j.modeId = root.value(QStringLiteral("modeId")).toInt(0);
    j.rotate = root.value(QStringLiteral("rotate")).toDouble(0.0);
    j.viewXDPI = root.value(QStringLiteral("view")).toObject()
                     .value(QStringLiteral("xdpi")).toInt(120);
    j.viewYDPI = root.value(QStringLiteral("view")).toObject()
                     .value(QStringLiteral("ydpi")).toInt(120);

    const QJsonArray scale = root.value(QStringLiteral("scale")).toArray();
    j.scale.clear();
    if (scale.size() >= 2) {
        j.scale = {scale.at(0).toDouble(100.0), scale.at(1).toDouble(100.0)};
    } else {
        j.scale = {100.0, 100.0};
    }

    j.margin.clear();
    const QJsonArray margin = root.value(QStringLiteral("margin")).toArray();
    for (int i = 0; i < 4; ++i)
        j.margin.append(margin.size() > i ? margin.at(i).toInt(0) : 0);

    const QJsonObject color = root.value(QStringLiteral("color")).toObject();
    if (!color.isEmpty()) {
        j.readTransparency = color.value(QStringLiteral("readTransparency")).toBool(true);
        j.transparencyToWhite = color.value(QStringLiteral("transparencyToWhite")).toBool(false);
    }

    j.inputColorEditor.clear();
    const QJsonArray ice = root.value(QStringLiteral("inputColorEditor")).toArray();
    for (const QJsonValue &v : ice) {
        const QJsonObject o = v.toObject();
        WhiteInkSpec s;
        s.inkName = o.value(QStringLiteral("inkName")).toString();
        s.mode = o.value(QStringLiteral("mode")).toString(QStringLiteral("full"));
        s.invert = o.value(QStringLiteral("invert")).toBool(false);
        j.inputColorEditor.append(s);
    }

    j.inkIE.clear();
    const QJsonArray ie = root.value(QStringLiteral("inkIE")).toArray();
    for (const QJsonValue &v : ie) {
        const QJsonObject o = v.toObject();
        InkIESpec s;
        s.index = o.value(QStringLiteral("index")).toInt(4);
        s.mode = o.value(QStringLiteral("mode")).toString(QStringLiteral("invaginate"));
        const QJsonArray dots = o.value(QStringLiteral("dots")).toArray();
        for (const QJsonValue &d : dots)
            s.dots.append(d.toDouble(0.0));
        j.inkIE.append(s);
    }

    const QJsonObject file = root.value(QStringLiteral("output")).toObject()
                                 .value(QStringLiteral("file")).toObject();
    const QString outName = file.value(QStringLiteral("name")).toString();
    if (!outName.isEmpty())
        j.prnPath = outName;

    return true;
}

int RipJob::effectiveDPI(int fallback) const
{
    return fallback;
}

} // namespace mtr
