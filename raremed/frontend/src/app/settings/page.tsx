import type { Metadata } from "next";

import { RequireSession } from "@/components/require-session";
import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <RequireSession>
      <SettingsView />
    </RequireSession>
  );
}
