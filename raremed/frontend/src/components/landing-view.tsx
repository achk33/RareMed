"use client";

import Link from "next/link";

import { Disclaimer } from "@/components/disclaimer";
import { SiteHeader } from "@/components/site-header";
import { DependencyRow, LaterBadge } from "@/components/status-row";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiBaseUrl } from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import { usePlatformStatus } from "@/lib/use-platform-status";

const capabilities = [
  ["capPhenotypeTitle", "capPhenotypeBody"],
  ["capEvidenceTitle", "capEvidenceBody"],
  ["capExplainTitle", "capExplainBody"],
] as const;

export function LandingView() {
  const { t } = useLocale();
  const { status, errorCode, loading } = usePlatformStatus();

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="main" className="flex-1">
        <section className="relative overflow-hidden border-b">
          <div className="raremed-grid pointer-events-none absolute inset-0" />
          <div className="relative mx-auto grid w-full max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)] lg:py-24">
            <div className="flex flex-col items-start gap-6">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{t("landingIndex")}</Badge>
                <Badge variant="outline">{t("roleLabel")}</Badge>
              </div>
              <div className="space-y-4">
                <p className="text-xs tracking-[0.18em] text-copper uppercase">{t("foundation")}</p>
                <h1 className="max-w-xl font-heading text-4xl leading-tight text-balance sm:text-5xl">
                  {t("heroTitle")}
                </h1>
                <p className="max-w-xl text-base leading-7 text-muted-foreground">{t("heroLead")}</p>
              </div>
              <Disclaimer text={t("disclaimer")} />
              <div className="flex flex-wrap gap-3">
                <Link href="/chat" className={buttonVariants({ size: "lg" })}>
                  {t("openWorkspace")}
                </Link>
                <Link href="/login" className={buttonVariants({ variant: "outline", size: "lg" })}>
                  {t("login")}
                </Link>
                <Link href="/admin" className={buttonVariants({ variant: "outline", size: "lg" })}>
                  {t("admin")}
                </Link>
              </div>
            </div>
            <Card>
              <CardHeader>
                <CardTitle>{t("statusTitle")}</CardTitle>
                <CardDescription>{t("versionNote")}</CardDescription>
              </CardHeader>
              <CardContent>
                {errorCode ? (
                  <p className="text-sm text-muted-foreground">{t("apiOffline")}</p>
                ) : (
                  <div className="divide-y">
                    <DependencyRow
                      label={t("postgres")}
                      state={loading ? "loading" : status?.database.status === "ok" ? "ok" : "unavailable"}
                    />
                    <DependencyRow
                      label={t("graphStore")}
                      state={loading ? "loading" : status?.neo4j.status === "ok" ? "ok" : "unavailable"}
                    />
                    <DependencyRow
                      label={t("languageModel")}
                      state={loading ? "loading" : status?.ollama.status === "ok" ? "ok" : "unavailable"}
                      detail={
                        status?.ollama.status === "ok" ? String(status.ollama.models.length) : undefined
                      }
                    />
                  </div>
                )}
                <p className="mt-4 text-xs text-muted-foreground">
                  {t("reasoningOff")}
                  {status ? ` · ${status.datasets.total_files} ${t("filesFound").toLowerCase()}` : ""}
                </p>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6">
          <div className="grid gap-4 md:grid-cols-3">
            {capabilities.map(([title, body]) => (
              <Card key={title}>
                <CardHeader>
                  <div className="mb-2">
                    <LaterBadge />
                  </div>
                  <CardTitle>{t(title)}</CardTitle>
                  <CardDescription>{t(body)}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>

        <section className="border-t">
          <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-16 sm:px-6 md:grid-cols-2">
            <div>
              <h2 className="font-heading text-3xl">{t("architectureTitle")}</h2>
              <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">{t("connectionHint")}</p>
            </div>
            <dl className="grid gap-3 text-sm">
              <ArchitectureRow term="Next.js" detail={t("workspace")} />
              <ArchitectureRow term="FastAPI" detail={`${t("apiBase")} · ${getApiBaseUrl()}`} />
              <ArchitectureRow term="PostgreSQL" detail={t("savedThreads")} />
              <ArchitectureRow term="Neo4j" detail={t("graphNotLoaded")} />
              <ArchitectureRow
                term="Ollama"
                detail={
                  status?.ollama.status === "ok"
                    ? `${t("connected")} · ${status.ollama.models.length}`
                    : status
                      ? t("unavailable")
                      : t("checking")
                }
              />
            </dl>
          </div>
        </section>
      </main>
      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-6 text-xs text-muted-foreground sm:px-6">
          <Disclaimer text={t("disclaimer")} compact />
          <p>{t("footerNote")}</p>
        </div>
      </footer>
    </div>
  );
}

function ArchitectureRow({ term, detail }: { term: string; detail: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b pb-3">
      <dt className="font-medium">{term}</dt>
      <dd className="text-end text-muted-foreground">{detail}</dd>
    </div>
  );
}
