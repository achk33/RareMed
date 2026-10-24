"use client";

import { useCallback, useEffect, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { DependencyRow } from "@/components/status-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getDatasets } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { usePlatformStatus } from "@/lib/use-platform-status";
import type { DiscoveryReport } from "@/lib/types";

export function AdminOverview() {
  const { t } = useLocale();
  const { status, errorCode, loading, reload } = usePlatformStatus();
  const [report, setReport] = useState<DiscoveryReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    try {
      setReport(await getDatasets());
      setReportError(null);
    } catch (error) {
      setReport(null);
      setReportError(error instanceof ApiError ? error.code : "request_failed");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getDatasets()
      .then((next) => {
        if (cancelled) return;
        setReport(next);
        setReportError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setReport(null);
        setReportError(error instanceof ApiError ? error.code : "request_failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const files = report?.sources.flatMap((source) =>
    source.files.map((file) => ({ source: source.source, ...file, truncated: source.truncated })),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
        <h1 className="mt-2 font-heading text-4xl">{t("overview")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("adminLead")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{t("noAuth")}</Badge>
        <Badge variant="secondary">{t("reasoningOff")}</Badge>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{t("postgres")}</CardTitle>
          </CardHeader>
          <CardContent>
            <DependencyRow
              label={t("conversations")}
              state={loading ? "loading" : status?.database.status === "ok" ? "ok" : "unavailable"}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("graphStore")}</CardTitle>
          </CardHeader>
          <CardContent>
            <DependencyRow
              label={t("knowledgeGraph")}
              state={loading ? "loading" : status?.neo4j.status === "ok" ? "ok" : "unavailable"}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("languageModel")}</CardTitle>
          </CardHeader>
          <CardContent>
            <DependencyRow
              label={t("modelCount")}
              state={loading ? "loading" : status?.ollama.status === "ok" ? "ok" : "unavailable"}
              detail={
                status?.ollama.status === "ok"
                  ? String(status.ollama.models.length)
                  : status?.ollama.base_url
              }
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("datasets")}</CardTitle>
          <CardDescription>
            {t("datasetNote")} {t("rawImmutable")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {errorCode || reportError ? <p className="mb-3 text-sm text-muted-foreground">{t("apiOffline")}</p> : null}
          {!report && !reportError ? (
            <p className="text-sm text-muted-foreground">{t("loading")}</p>
          ) : files && files.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-start text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b">
                    <th className="py-2 pe-3 font-medium">{t("source")}</th>
                    <th className="py-2 pe-3 font-medium">{t("file")}</th>
                    <th className="py-2 pe-3 font-medium">{t("size")}</th>
                    <th className="py-2 font-medium">{t("path")}</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr key={file.relative_path} className="border-b last:border-0">
                      <td className="py-2 pe-3">{file.source}</td>
                      <td className="py-2 pe-3">{file.name}</td>
                      <td className="py-2 pe-3">{formatBytes(file.size_bytes)}</td>
                      <td className="py-2 font-mono text-xs">{file.relative_path}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("noDatasets")}</p>
          )}
          {report?.sources.some((source) => source.truncated) ? (
            <p className="mt-3 text-xs text-muted-foreground">{t("filesFound")}: {status?.datasets.total_files}</p>
          ) : null}
          <div className="mt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                void reload();
                void loadReport();
              }}
            >
              {t("refresh")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {report ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("reserved")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {report.reserved_directories.map((directory) => (
              <p key={directory.name}>
                <span className="font-medium">{directory.name}</span>
                <span className="text-muted-foreground"> — {directory.purpose}</span>
              </p>
            ))}
            <p>
              <span className="font-medium">{t("samples")}</span>
              <span className="text-muted-foreground">
                {" "}
                — {report.sample_files.length === 0 ? t("fixtureMissing") : report.sample_files.join(", ")}
              </span>
            </p>
          </CardContent>
        </Card>
      ) : null}
      <Disclaimer text={t("disclaimer")} />
    </div>
  );
}
