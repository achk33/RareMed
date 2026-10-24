"use client";

import { useEffect, useState } from "react";

import { ApiError, listUsers } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatTimestamp } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import type { SessionUser } from "@/lib/types";

export function AdminUsers() {
  const { t, locale } = useLocale();
  const { user } = useAuth();
  const [items, setItems] = useState<SessionUser[]>([]);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listUsers()
      .then((next) => {
        if (!cancelled) setItems(next);
      })
      .catch((error: unknown) => {
        if (!cancelled) setErrorCode(error instanceof ApiError ? error.code : "request_failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (user?.role !== "admin") {
    return <p className="text-sm text-muted-foreground">{t("forbidden")}</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
        <h1 className="mt-2 font-heading text-3xl">{t("users")}</h1>
      </div>
      {errorCode ? (
        <p className="text-sm" role="status">
          {errorCode === "forbidden" ? t("forbidden") : t("requestFailed")}
        </p>
      ) : (
        <ul className="divide-y rounded-xl border">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <div>
                <p className="font-medium">{item.display_name}</p>
                <p className="text-muted-foreground">{item.email}</p>
              </div>
              <div className="text-end text-muted-foreground">
                <p>
                  {item.role === "admin"
                    ? t("roleLabelAdmin")
                    : item.role === "clinician"
                      ? t("roleLabelClinician")
                      : t("roleLabelUser")}
                </p>
                <p className="text-[11px]">{formatTimestamp(item.created_at, locale)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
