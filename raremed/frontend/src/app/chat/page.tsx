import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatWorkspace } from "@/components/chat/chat-workspace";
import { RequireSession } from "@/components/require-session";
import { RouteLoading } from "@/components/route-loading";

export const metadata: Metadata = {
  title: "Workspace",
};

export default function ChatPage() {
  return (
    <RequireSession>
      <Suspense fallback={<RouteLoading />}>
        <ChatWorkspace />
      </Suspense>
    </RequireSession>
  );
}
