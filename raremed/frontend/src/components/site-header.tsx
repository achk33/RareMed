"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
import { LanguageMenu } from "@/components/language-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";
import { useOptionalAuth } from "@/lib/auth";
import { useLocale } from "@/lib/i18n";
import { primaryNav } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const pathname = usePathname();
  const { t } = useLocale();
  const auth = useOptionalAuth();

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur-md">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
      >
        {t("skip")}
      </a>
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-medium">
          <BrandMark />
          <span className="leading-tight">
            <span className="block font-heading text-base">{t("product")}</span>
            <span className="block text-[11px] tracking-wide text-muted-foreground uppercase">
              {t("decisionSupport")}
            </span>
          </span>
        </Link>
        <nav aria-label={t("primaryNav")} className="ms-auto hidden items-center gap-1 md:flex">
          {primaryNav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
                  active && "bg-muted text-foreground",
                )}
                aria-current={active ? "page" : undefined}
              >
                {t(item.labelKey)}
              </Link>
            );
          })}
        </nav>
        <div className="ms-auto flex items-center gap-1 md:ms-0">
          {auth?.user ? (
            <button type="button" className={buttonVariants({ variant: "ghost", size: "sm" })} onClick={() => void auth.logout()}>
              {t("logout")}
            </button>
          ) : (
            <Link href="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              {t("login")}
            </Link>
          )}
          <LanguageMenu />
          <ThemeToggle />
        </div>
      </div>
      <nav aria-label={t("primaryNav")} className="flex gap-1 border-t px-4 py-2 md:hidden">
        {primaryNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {t(item.labelKey)}
          </Link>
        ))}
      </nav>
    </header>
  );
}
