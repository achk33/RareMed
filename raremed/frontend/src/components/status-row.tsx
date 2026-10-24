"use client";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function StatusDot({
  state,
}: {
  state: "ok" | "unavailable" | "loading";
}) {
  return (
    <span
      className={cn(
        "size-2 rounded-full",
        state === "ok" && "bg-primary",
        state === "unavailable" && "bg-copper",
        state === "loading" && "animate-pulse bg-muted-foreground",
      )}
      aria-hidden="true"
    />
  );
}

export function DependencyRow({
  label,
  state,
  detail,
}: {
  label: string;
  state: "ok" | "unavailable" | "loading";
  detail?: string;
}) {
  const { t } = useLocale();
  const text = state === "loading" ? t("checking") : state === "ok" ? t("connected") : t("unavailable");

  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="flex items-center gap-2">
        <StatusDot state={state} />
        <span className="font-medium">{label}</span>
      </div>
      <span className="text-end text-xs text-muted-foreground">
        {detail ? `${text} · ${detail}` : text}
      </span>
    </div>
  );
}

export function LaterBadge() {
  const { t } = useLocale();
  return <Badge variant="outline">{t("later")}</Badge>;
}
