"use client";

import { SiteHeader } from "@/components/site-header";
import { Disclaimer } from "@/components/disclaimer";
import { DependencyRow } from "@/components/status-row";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { getApiBaseUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/i18n";
import type { LocaleCode } from "@/lib/types";
import { usePlatformStatus } from "@/lib/use-platform-status";
import { useStoredFlag } from "@/lib/use-stored-flag";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";

const locales: { code: LocaleCode; label: string }[] = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "ar", label: "العربية" },
  { code: "ary", label: "الدارجة" },
];

export function SettingsView() {
  const { t, locale, setLocale } = useLocale();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [showTimestamps, setShowTimestamps] = useStoredFlag("raremed.timestamps", true);
  const { status, errorCode, loading, reload } = usePlatformStatus();

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="main" className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div>
          <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
          <h1 className="mt-2 font-heading text-4xl">{t("settings")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t("settingsLead")}</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t("account")}</CardTitle>
            <CardDescription>{t("accountLead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              {t("signedInAs")} {user?.display_name} ({user?.email})
            </p>
            <p className="text-muted-foreground">
              {user?.role === "admin"
                ? t("roleLabelAdmin")
                : user?.role === "clinician"
                  ? t("roleLabelClinician")
                  : t("roleLabelUser")}
            </p>
            <Button type="button" variant="outline" onClick={() => void logout()}>
              {t("logout")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("appearance")}</CardTitle>
            <CardDescription>{t("themeHint")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {(["light", "dark", "system"] as const).map((choice) => (
              <Button
                key={choice}
                type="button"
                variant={theme === choice ? "default" : "outline"}
                onClick={() => setTheme(choice)}
              >
                {t(choice)}
              </Button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("language")}</CardTitle>
            <CardDescription>{t("languageHint")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {locales.map((item) => (
              <Button
                key={item.code}
                type="button"
                variant={locale === item.code ? "default" : "outline"}
                onClick={() => setLocale(item.code)}
              >
                {item.label}
              </Button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("workspace")}</CardTitle>
            <CardDescription>{t("workspaceHint")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label htmlFor="timestamps">{t("showTimestamps")}</Label>
                <p className="text-xs text-muted-foreground">{t("timestampsHint")}</p>
              </div>
              <Switch
                id="timestamps"
                checked={showTimestamps}
                onCheckedChange={(checked) => setShowTimestamps(checked)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("connection")}</CardTitle>
            <CardDescription>{t("connectionHint")}</CardDescription>
          </CardHeader>
          <CardContent>
            {errorCode ? <p className="mb-3 text-sm text-muted-foreground">{t("apiOffline")}</p> : null}
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
                detail={status?.ollama.base_url}
              />
            </div>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">{t("apiBase")}</dt>
                <dd className="truncate">{getApiBaseUrl()}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">{t("environment")}</dt>
                <dd>{status?.environment ?? t("checking")}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">{t("modelCount")}</dt>
                <dd>{status ? status.ollama.models.length : "—"}</dd>
              </div>
            </dl>
            <Button type="button" variant="outline" className="mt-4" onClick={() => void reload()}>
              {t("refresh")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("safety")}</CardTitle>
          </CardHeader>
          <CardContent className={cn("space-y-4")}>
            <p className="text-sm leading-6">{t("safetyBody")}</p>
            <Disclaimer text={t("disclaimer")} />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
