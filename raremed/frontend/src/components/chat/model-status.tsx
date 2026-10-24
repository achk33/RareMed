"use client";

import { useEffect, useState } from "react";

import { ApiError, getModelStatus } from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import type { ModelIndicator } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ModelStatus() {
  const { t } = useLocale();
  const [model, setModel] = useState<ModelIndicator | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getModelStatus()
      .then((next) => {
        if (cancelled) return;
        setModel(next);
        setOffline(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setModel(null);
        setOffline(!(error instanceof ApiError) || error.code === "network_error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = Boolean(model?.reachable && model.model_ready);
  const missing = Boolean(model?.reachable && !model.model_ready);
  const label = ready ? t("modelReady") : missing ? t("modelMissing") : t("modelOffline");
  const detail = offline
    ? t("apiOffline")
    : missing
      ? t("modelMissingDetail")
      : !model?.reachable
        ? t("ollamaUnavailable")
        : model.model;

  return (
    <span
      className="inline-flex max-w-40 items-center gap-2 text-[11px] text-muted-foreground sm:max-w-none"
      title={detail}
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          ready ? "bg-primary" : "bg-copper",
          !model && !offline && "animate-pulse bg-muted-foreground",
        )}
        aria-hidden="true"
      />
      <span className="truncate">
        <span className="sr-only">{label}. </span>
        {model?.model ?? "qwen3:4b"}
      </span>
    </span>
  );
}
