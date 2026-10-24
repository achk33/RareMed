import { AdminShell } from "@/components/admin/admin-shell";
import { RequireSession } from "@/components/require-session";
import type { ReactNode } from "react";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <RequireSession roles={["clinician", "admin"]}>
      <AdminShell>{children}</AdminShell>
    </RequireSession>
  );
}
