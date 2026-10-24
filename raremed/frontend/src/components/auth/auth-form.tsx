"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/i18n";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { t } = useLocale();
  const { login, register } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/chat";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function submit() {
    setSending(true);
    setErrorCode(null);
    try {
      if (mode === "register") await register(email, password, displayName);
      else await login(email, password);
      router.replace(next.startsWith("/") ? next : "/chat");
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    } finally {
      setSending(false);
    }
  }

  const errorText =
    errorCode === "invalid_credentials"
      ? t("invalidCredentials")
      : errorCode === "email_taken"
        ? t("emailTaken")
        : errorCode === "validation_error"
          ? t("weakPassword")
          : errorCode === "database_unavailable"
            ? t("databaseUnavailable")
            : errorCode
              ? t("requestFailed")
              : null;

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
        <Card>
          <CardHeader>
            <CardTitle>{mode === "login" ? t("login") : t("register")}</CardTitle>
            <CardDescription>{mode === "login" ? t("loginLead") : t("registerLead")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              {mode === "register" ? (
                <div className="space-y-2">
                  <Label htmlFor="display-name">{t("displayName")}</Label>
                  <Input
                    id="display-name"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    autoComplete="name"
                  />
                </div>
              ) : null}
              <div className="space-y-2">
                <Label htmlFor="email">{t("email")}</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{t("password")}</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={mode === "register" ? 10 : 1}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                />
                {mode === "register" ? (
                  <p className="text-xs text-muted-foreground">{t("passwordHint")}</p>
                ) : null}
              </div>
              {errorText ? (
                <p className="text-sm text-copper" role="status">
                  {errorText}
                </p>
              ) : null}
              <Button type="submit" className="w-full" disabled={sending}>
                {mode === "login" ? t("login") : t("register")}
              </Button>
            </form>
            <p className="mt-4 text-sm text-muted-foreground">
              {mode === "login" ? t("needAccount") : t("haveAccount")}{" "}
              <Link className="underline" href={mode === "login" ? "/register" : "/login"}>
                {mode === "login" ? t("register") : t("login")}
              </Link>
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
