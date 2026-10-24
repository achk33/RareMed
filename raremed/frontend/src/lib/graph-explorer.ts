import type { GraphEdgeRead, GraphNodeRead } from "@/lib/types";

export const DISPLAY_NODE_LIMIT = 80;
export const DISPLAY_EDGE_LIMIT = 120;
export const SEARCH_PAGE_SIZE = 12;
export const EXPAND_LIMIT = 16;
export const EXPLORER_KINDS = ["Disease", "Phenotype", "Gene", "InheritancePattern"] as const;

export type ExplorerKind = (typeof EXPLORER_KINDS)[number];

export const KIND_STYLE: Record<string, { color: string; shape: string; label: string }> = {
  Disease: { color: "#c4784a", shape: "ellipse", label: "Disease" },
  Phenotype: { color: "#2f8f86", shape: "round-rectangle", label: "HPO" },
  Gene: { color: "#d4a017", shape: "diamond", label: "Gene" },
  InheritancePattern: { color: "#7c6bc4", shape: "hexagon", label: "Inheritance" },
  Variant: { color: "#8b5a2b", shape: "triangle", label: "Variant" },
  DiagnosticTest: { color: "#4f83b8", shape: "pentagon", label: "Test" },
  Identifier: { color: "#6b7280", shape: "rectangle", label: "Identifier" },
};

export function kindStyle(kind: string) {
  return KIND_STYLE[kind] ?? { color: "#64748b", shape: "ellipse", label: kind };
}

export function mergeGraphSlice(
  nodes: GraphNodeRead[],
  edges: GraphEdgeRead[],
  incoming: { nodes: GraphNodeRead[]; edges: GraphEdgeRead[] },
): { nodes: GraphNodeRead[]; edges: GraphEdgeRead[]; truncated: boolean } {
  const nodeMap = new Map(nodes.map((node) => [node.curie, node]));
  const edgeMap = new Map(edges.map((edge) => [edge.id, edge]));
  let truncated = false;

  for (const node of incoming.nodes) {
    if (nodeMap.has(node.curie)) {
      nodeMap.set(node.curie, node);
      continue;
    }
    if (nodeMap.size >= DISPLAY_NODE_LIMIT) {
      truncated = true;
      continue;
    }
    nodeMap.set(node.curie, node);
  }

  for (const edge of incoming.edges) {
    if (edgeMap.has(edge.id)) {
      edgeMap.set(edge.id, edge);
      continue;
    }
    if (edgeMap.size >= DISPLAY_EDGE_LIMIT) {
      truncated = true;
      continue;
    }
    if (!nodeMap.has(edge.start) || !nodeMap.has(edge.end)) {
      continue;
    }
    edgeMap.set(edge.id, edge);
  }

  return { nodes: [...nodeMap.values()], edges: [...edgeMap.values()], truncated };
}

export function downloadPng(dataUrl: string, filename = "raremed-graph.png") {
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  link.click();
}
