import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";
import { RouteLoading } from "@/components/route-loading";

export const metadata: Metadata = {
  title: "Create account",
};

export default function RegisterPage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <AuthForm mode="register" />
    </Suspense>
  );
}
