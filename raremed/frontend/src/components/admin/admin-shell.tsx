"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand-mark";
import { LanguageMenu } from "@/components/language-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/lib/i18n";
import { adminNav } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t } = useLocale();

  return (
    <div className="min-h-dvh bg-background">
      <header className="flex h-16 items-center gap-3 border-b px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <BrandMark className="size-7" />
          <span className="font-heading">{t("product")}</span>
        </Link>
        <Badge variant="outline">{t("adminPrivate")}</Badge>
        <div className="ms-auto flex items-center gap-1">
          <LanguageMenu />
          <ThemeToggle />
        </div>
      </header>
      <div
        className={cn(
          "mx-auto grid w-full gap-6 px-4 py-6 sm:px-6 md:grid-cols-[200px_minmax(0,1fr)]",
          pathname.includes("/knowledge-graph") ? "max-w-[1680px]" : "max-w-6xl",
        )}
      >
        <nav aria-label={t("adminNav")} className="flex flex-col gap-1">
          {adminNav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
                  active && "bg-muted font-medium text-foreground",
                )}
                aria-current={active ? "page" : undefined}
              >
                {t(item.labelKey)}
              </Link>
            );
          })}
          <Link href="/chat" className="mt-4 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
            {t("backToApp")}
          </Link>
        </nav>
        <div id="main">{children}</div>
      </div>
    </div>
  );
}
