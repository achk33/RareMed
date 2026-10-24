import type { AnchorHTMLAttributes, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatWorkspace } from "@/components/chat/chat-workspace";
import { MessageContent } from "@/components/chat/message-content";
import { LocaleProvider } from "@/lib/i18n";
import { parseSseBlock } from "@/lib/api";

const streamChat = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
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
    listConversations: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0, has_more: false }),
    updateConversation: vi.fn().mockResolvedValue({}),
    getConversation: vi.fn(),
    getMe: vi.fn().mockRejectedValue(new actual.ApiError(401, "unauthenticated", "Sign in")),
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
    createConversation: vi.fn().mockRejectedValue(new actual.ApiError(503, "database_unavailable", "down")),
    deleteConversation: vi.fn().mockResolvedValue(undefined),
    streamChat,
  };
});

function renderWorkspace(ui: ReactNode = <ChatWorkspace />) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("chat streaming", () => {
  beforeEach(() => {
    streamChat.mockReset();
  });

  it("renders markdown tables for right-to-left and left-to-right text", () => {
    render(
      <MessageContent content={"| Phenotype | Note |\n| --- | --- |\n| مثال | demo |"} />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "مثال" })).toBeInTheDocument();
    expect(document.querySelector(".markdown-body")).toHaveAttribute("dir", "auto");
  });

  it("parses a token event", () => {
    expect(parseSseBlock('event: token\ndata: {"text":"مرحبًا"}')).toEqual({
      event: "token",
      data: { text: "مرحبًا" },
    });
  });

  it("shows tokens as they arrive and can stop or regenerate", async () => {
    const user = userEvent.setup();
    let release: (error?: unknown) => void = () => undefined;
    streamChat.mockImplementation(async (_body, handlers: { onToken: (text: string) => void; signal: AbortSignal }) => {
      handlers.onToken("Hello");
      await new Promise((resolve, reject) => {
        release = (error) => (error ? reject(error) : resolve(undefined));
        handlers.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    renderWorkspace();
    await user.type(screen.getByRole("textbox", { name: "Write a workspace note" }), "Hi");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(await screen.findByRole("button", { name: "Regenerate" })).toBeInTheDocument();

    streamChat.mockImplementation(async (_body, handlers: { onToken: (text: string) => void; onDone: (done: object) => void }) => {
      handlers.onToken(" again");
      handlers.onDone({
        model: "qwen3:4b",
        provider: "ollama",
        elapsed_ms: 1200,
        eval_count: 4,
        tokens_per_second: 3.3,
        stopped: false,
        saved: false,
        think: false,
      });
    });
    await user.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(await screen.findByText(/again/)).toBeInTheDocument();
    expect(streamChat).toHaveBeenLastCalledWith(
      expect.objectContaining({ regenerate: true, locale: "en" }),
      expect.any(Object),
    );
    release();
  });
});
