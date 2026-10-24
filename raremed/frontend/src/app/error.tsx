"use client";

import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { useLocale } from "@/lib/i18n";

export default function AppError({ reset }: { error: Error; reset: () => void }) {
  const { t } = useLocale();

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center gap-4 px-6">
      <h1 className="font-heading text-3xl">{t("requestFailed")}</h1>
      <p className="text-sm text-muted-foreground">{t("disclaimer")}</p>
      <div className="flex gap-2">
        <Button type="button" onClick={() => reset()}>
          {t("retry")}
        </Button>
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          {t("home")}
        </Link>
      </div>
    </div>
  );
}
