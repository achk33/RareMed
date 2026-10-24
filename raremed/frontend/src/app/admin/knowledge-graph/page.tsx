import type { Metadata } from "next";

import { GraphView } from "@/components/admin/graph-view";

export const metadata: Metadata = {
  title: "Knowledge graph",
};

export default function KnowledgeGraphPage() {
  return <GraphView />;
}
