import { describe, expect, it } from "vitest";

import { DISPLAY_NODE_LIMIT, mergeGraphSlice } from "@/lib/graph-explorer";
import type { GraphNodeRead } from "@/lib/types";

function node(curie: string): GraphNodeRead {
  return { curie, kind: "Phenotype", label: curie };
}

describe("graph explorer limits", () => {
  it("caps visible nodes and reports truncation", () => {
    const incoming = {
      nodes: Array.from({ length: DISPLAY_NODE_LIMIT + 12 }, (_, index) => node(`HP:${String(index).padStart(7, "0")}`)),
      edges: [],
    };
    const merged = mergeGraphSlice([], [], incoming);
    expect(merged.nodes).toHaveLength(DISPLAY_NODE_LIMIT);
    expect(merged.truncated).toBe(true);
  });
});
