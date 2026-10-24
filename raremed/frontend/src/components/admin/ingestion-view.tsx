"use client";

import { useCallback, useEffect, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, getIngestionStatus, rollbackIngestion, runIngestion } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import type { IngestionStatus } from "@/lib/types";

function countLabel(counts: Record<string, number>) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return "0";
  return entries.map(([key, value]) => `${key} ${value}`).join(", ");
}

export function IngestionView() {
  const { t, locale } = useLocale();
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setStatus(await getIngestionStatus());
      setErrorCode(null);
    } catch (error) {
      setStatus(null);
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: "import" | "rollback") {
    setBusy(true);
    try {
      setStatus(action === "import" ? await runIngestion(false) : await rollbackIngestion());
      setErrorCode(null);
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
        <h1 className="mt-2 font-heading text-4xl">{t("ingestion")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("ingestionLead")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">{t("reasoningOff")}</Badge>
        <Badge variant="outline">{status?.running ? t("importRunning") : t("rawImmutable")}</Badge>
      </div>

      {errorCode ? (
        <p className="text-sm text-muted-foreground" role="status">
          {errorCode === "required_source_missing"
            ? t("strictMissing")
            : errorCode === "ingestion_rollback_unavailable"
              ? t("noIngestionRuns")
              : t("apiOffline")}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("currentRun")}</CardTitle>
          <CardDescription>{status?.note ?? t("ingestionNote")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p>
            <span className="font-medium">{t("lastSuccessfulImport")}</span>
            <span className="text-muted-foreground">
              {" "}
              —{" "}
              {status?.last_successful_import
                ? formatTimestamp(status.last_successful_import, locale)
                : t("noIngestionRuns")}
            </span>
          </p>
          <p>
            <span className="font-medium">{t("entities")}</span>
            <span className="text-muted-foreground">
              {" "}
              — {String((status?.counts?.entities as number | undefined) ?? 0)}
            </span>
          </p>
          <p>
            <span className="font-medium">{t("relationships")}</span>
            <span className="text-muted-foreground">
              {" "}
              — {String((status?.counts?.relationships as number | undefined) ?? 0)}
            </span>
          </p>
          {status?.missing_required.length ? (
            <p>
              <span className="font-medium">{t("missingSource")}</span>
              <span className="text-muted-foreground"> — {status.missing_required.join(", ")}</span>
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button type="button" onClick={() => void run("import")} disabled={busy || status?.running}>
              {busy || status?.running ? t("importRunning") : t("runImport")}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void run("rollback")}
              disabled={busy || status?.running}
            >
              {t("rollbackImport")}
            </Button>
            <Button type="button" variant="outline" onClick={() => void load()} disabled={busy}>
              {t("refresh")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("datasets")}</CardTitle>
          <CardDescription>{t("ingestionNote")}</CardDescription>
        </CardHeader>
        <CardContent>
          {!status && !errorCode ? (
            <p className="text-sm text-muted-foreground">{t("loading")}</p>
          ) : status && status.sources.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-start text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b">
                    <th className="py-2 pe-3 font-medium">{t("source")}</th>
                    <th className="py-2 pe-3 font-medium">{t("sourceFile")}</th>
                    <th className="py-2 pe-3 font-medium">{t("version")}</th>
                    <th className="py-2 pe-3 font-medium">{t("importStatus")}</th>
                    <th className="py-2 pe-3 font-medium">{t("entities")}</th>
                    <th className="py-2 pe-3 font-medium">{t("relationships")}</th>
                    <th className="py-2 pe-3 font-medium">{t("validationWarnings")}</th>
                    <th className="py-2 font-medium">{t("lastSuccessfulImport")}</th>
                  </tr>
                </thead>
                <tbody>
                  {status.sources.map((source) => (
                    <tr key={`${source.source}-${source.role}-${source.expected_path}`} className="border-b last:border-0 align-top">
                      <td className="py-2 pe-3">{source.source}</td>
                      <td className="py-2 pe-3 font-mono text-xs">{source.file_path ?? source.expected_path}</td>
                      <td className="py-2 pe-3">{source.version ?? "—"}</td>
                      <td className="py-2 pe-3">{source.import_status}</td>
                      <td className="py-2 pe-3">{countLabel(source.entity_counts)}</td>
                      <td className="py-2 pe-3">{countLabel(source.relationship_counts)}</td>
                      <td className="max-w-xs py-2 pe-3 text-xs text-muted-foreground">
                        {source.validation_warnings.length ? source.validation_warnings.slice(0, 3).join(" ") : "—"}
                      </td>
                      <td className="py-2 text-xs">
                        {source.last_successful_import
                          ? formatTimestamp(source.last_successful_import, locale)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("noDatasets")}</p>
          )}
        </CardContent>
      </Card>
      <Disclaimer text={t("disclaimer")} />
    </div>
  );
}
