import type { AnchorHTMLAttributes, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminShell } from "@/components/admin/admin-shell";
import { LandingView } from "@/components/landing-view";
import { LocaleProvider } from "@/lib/i18n";
import { adminNav, primaryNav } from "@/lib/navigation";

const navigation = vi.hoisted(() => ({ pathname: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
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
  useTheme: () => ({ theme: "system", setTheme: vi.fn(), resolvedTheme: "light" }),
}));

function renderWithLocale(ui: ReactNode) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("navigation", () => {
  beforeEach(() => {
    navigation.pathname = "/";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  });

  it("keeps the foundation routes", () => {
    expect(primaryNav.map((item) => item.href)).toEqual(["/chat", "/settings", "/admin"]);
    expect(adminNav.map((item) => item.href)).toEqual([
      "/admin",
      "/admin/ingestion",
      "/admin/knowledge-graph",
      "/admin/users",
    ]);
  });

  it("links the landing page to the workspace, settings, and admin", () => {
    renderWithLocale(<LandingView />);

    expect(screen.getAllByRole("link", { name: "Workspace" })[0]).toHaveAttribute("href", "/chat");
    expect(screen.getAllByRole("link", { name: "Settings" })[0]).toHaveAttribute("href", "/settings");
    expect(screen.getAllByRole("link", { name: "Admin" })[0]).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("link", { name: "Open workspace" })).toHaveAttribute("href", "/chat");
    expect(screen.getAllByTestId("disclaimer")[0]).toHaveTextContent(
      "not a clinically validated diagnostic tool",
    );
  });

  it("links the admin shell to the knowledge graph and back to the workspace", () => {
    navigation.pathname = "/admin";
    renderWithLocale(
      <AdminShell>
        <p>Overview body</p>
      </AdminShell>,
    );

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("link", { name: "Ingestion" })).toHaveAttribute("href", "/admin/ingestion");
    expect(screen.getByRole("link", { name: "Knowledge graph" })).toHaveAttribute(
      "href",
      "/admin/knowledge-graph",
    );
    expect(screen.getByRole("link", { name: "Accounts" })).toHaveAttribute("href", "/admin/users");
    expect(screen.getByRole("link", { name: "Back to workspace" })).toHaveAttribute("href", "/chat");
  });
});
