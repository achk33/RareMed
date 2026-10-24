import type { AnchorHTMLAttributes, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatWorkspace } from "@/components/chat/chat-workspace";
import { LocaleProvider } from "@/lib/i18n";

const getConversation = vi.hoisted(() => vi.fn());
const listConversations = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("c=thread-1"),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "light", setTheme: vi.fn(), resolvedTheme: "light" }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listConversations,
    getConversation,
    getSamples: vi.fn().mockResolvedValue({ fixtures: [], note: "" }),
    getModelStatus: vi.fn().mockResolvedValue({
      provider: "ollama",
      model: "qwen3:4b",
      base_url: "http://localhost:11434",
      reachable: true,
      model_ready: true,
      think: false,
      installed_models: ["qwen3:4b"],
      detail: null,
    }),
    createConversation: vi.fn(),
    deleteConversation: vi.fn(),
    updateConversation: vi.fn(),
    streamChat: vi.fn(),
  };
});

function renderWorkspace(ui: ReactNode = <ChatWorkspace />) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("chat session persistence", () => {
  beforeEach(() => {
    listConversations.mockResolvedValue({
      items: [
        {
          id: "thread-1",
          title: "Saved note",
          locale: "en",
          created_at: "2026-10-24T12:00:00.000Z",
          updated_at: new Date().toISOString(),
          message_count: 2,
          preview: "ready",
          archived: false,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
      has_more: false,
    });
    getConversation.mockResolvedValue({
      id: "thread-1",
      title: "Saved note",
      locale: "en",
      created_at: "2026-10-24T12:00:00.000Z",
      updated_at: new Date().toISOString(),
      has_more: false,
      messages: [
        {
          id: "m1",
          conversation_id: "thread-1",
          role: "user",
          content: "Reply with exactly one word: ready",
          status: "complete",
          created_at: "2026-10-24T12:00:00.000Z",
        },
        {
          id: "m2",
          conversation_id: "thread-1",
          role: "assistant",
          content: "ready",
          status: "interrupted",
          extra: { medical_evidence: [], hpo_entities: [], diagnostic_session_id: null },
          created_at: "2026-10-24T12:00:01.000Z",
        },
      ],
    });
  });

  it("reloads a previous thread after a browser refresh and shows interrupted recovery", async () => {
    renderWorkspace();
    expect(await screen.findAllByText("Saved note")).not.toHaveLength(0);
    expect(await screen.findByText("Reply with exactly one word: ready")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText(/interrupted/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate" })).toBeInTheDocument();
    const active = screen.getAllByRole("button", { name: /Saved note/ })[0];
    expect(active.closest("[aria-current='true']")).not.toBeNull();
  });

  it("can search the sidebar", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const box = await screen.findByRole("textbox", { name: "Search conversations" });
    await user.type(box, "Saved");
    expect(listConversations).toHaveBeenCalled();
  });
});
