"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { useLocale } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useLocale();

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center gap-4 px-6">
      <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
      <h1 className="font-heading text-3xl">{t("home")}</h1>
      <p className="text-sm text-muted-foreground">{t("disclaimer")}</p>
      <Link href="/" className={buttonVariants()}>
        {t("home")}
      </Link>
    </div>
  );
}
