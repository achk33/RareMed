import type { Metadata } from "next";

import { AdminUsers } from "@/components/admin/admin-users";

export const metadata: Metadata = {
  title: "Accounts",
};

export default function AdminUsersPage() {
  return <AdminUsers />;
}
