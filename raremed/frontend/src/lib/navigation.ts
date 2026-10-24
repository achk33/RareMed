export const primaryNav = [
  { href: "/chat", labelKey: "workspace" },
  { href: "/settings", labelKey: "settings" },
  { href: "/admin", labelKey: "admin" },
] as const;

export const adminNav = [
  { href: "/admin", labelKey: "overview" },
  { href: "/admin/ingestion", labelKey: "ingestion" },
  { href: "/admin/knowledge-graph", labelKey: "knowledgeGraph" },
  { href: "/admin/users", labelKey: "users" },
] as const;

export type NavLabelKey = (typeof primaryNav)[number]["labelKey"] | (typeof adminNav)[number]["labelKey"];
