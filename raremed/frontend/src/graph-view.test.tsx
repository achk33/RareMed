import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GraphView } from "@/components/admin/graph-view";
import { LocaleProvider } from "@/lib/i18n";

const getGraphStatus = vi.fn();
const exploreSearch = vi.fn();
const exploreNeighborhood = vi.fn();
const exploreExpand = vi.fn();
const exploreSources = vi.fn();
const getEntityDetail = vi.fn();
const getDiseaseDetail = vi.fn();

vi.mock("@/lib/auth", () => ({
  useOptionalAuth: () => ({ user: { role: "admin", email: "admin@example.com" } }),
}));

vi.mock("next/dynamic", () => ({
  default: () =>
    function GraphCanvasStub({ nodes, edges }: { nodes: { curie: string }[]; edges: { id: string }[] }) {
      return (
        <div data-testid="graph-canvas">
          {nodes.length} nodes, {edges.length} edges
        </div>
      );
    },
}));

vi.mock("@/components/admin/graph-canvas", () => ({
  GraphCanvas: ({ nodes, edges }: { nodes: { curie: string }[]; edges: { id: string }[] }) => (
    <div data-testid="graph-canvas">
      {nodes.length} nodes, {edges.length} edges
    </div>
  ),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status = 500;
    code = "request_failed";
  },
  getGraphStatus: () => getGraphStatus(),
  getGraphStats: () => getGraphStatus(),
  loadGraph: vi.fn(),
  rollbackGraph: vi.fn(),
  exploreSearch: (...args: unknown[]) => exploreSearch(...args),
  exploreNeighborhood: (...args: unknown[]) => exploreNeighborhood(...args),
  exploreExpand: (...args: unknown[]) => exploreExpand(...args),
  explorePath: vi.fn(),
  exploreSources: () => exploreSources(),
  getEntityDetail: (...args: unknown[]) => getEntityDetail(...args),
  getDiseaseDetail: (...args: unknown[]) => getDiseaseDetail(...args),
  searchGraphDiseases: vi.fn(),
  searchGraphPhenotypes: vi.fn(),
  getNeighborhood: vi.fn(),
}));

describe("graph explorer", () => {
  beforeEach(() => {
    getGraphStatus.mockResolvedValue({
      connection: { status: "ok", detail: null },
      loaded: true,
      note: "Version 0.6 explores asserted medical relations from Neo4j.",
      node_counts: { Disease: 2, Phenotype: 3, Gene: 1, InheritancePattern: 1 },
      relationship_counts: { HAS_PHENOTYPE: 4, IS_A: 2 },
      inferred_relationship_count: 0,
      running: false,
    });
    exploreSources.mockResolvedValue([{ name: "hpo", version: "2024", node_count: 3 }]);
    exploreSearch.mockResolvedValue({
      items: [{ curie: "ORPHA:58", kind: "Disease", label: "Alexander disease", score: 1 }],
      offset: 0,
      limit: 12,
      has_more: false,
    });
    exploreNeighborhood.mockResolvedValue({
      center: { curie: "ORPHA:58", kind: "Disease", label: "Alexander disease" },
      nodes: [
        { curie: "ORPHA:58", kind: "Disease", label: "Alexander disease" },
        { curie: "HP:0000256", kind: "Phenotype", label: "Macrocephaly" },
      ],
      edges: [
        {
          id: "e1",
          type: "HAS_PHENOTYPE",
          start: "ORPHA:58",
          end: "HP:0000256",
          inferred: false,
          source: "hpoa",
          polarity: "present",
        },
      ],
      depth: 1,
      bounded: true,
      truncated: true,
      read_only: true,
    });
    exploreExpand.mockResolvedValue({
      nodes: [{ curie: "NCBIGene:2670", kind: "Gene", label: "GFAP" }],
      edges: [
        {
          id: "e2",
          type: "ASSOCIATED_WITH_GENE",
          start: "ORPHA:58",
          end: "NCBIGene:2670",
          inferred: false,
          source: "orphadata",
        },
      ],
      truncated: false,
    });
    getEntityDetail.mockResolvedValue({
      entity: { curie: "ORPHA:58", kind: "Disease", label: "Alexander disease", source: "orphadata" },
      relationships: [
        {
          id: "e1",
          type: "HAS_PHENOTYPE",
          start: "ORPHA:58",
          end: "HP:0000256",
          inferred: false,
          source: "hpoa",
        },
      ],
      evidence: [
        {
          id: "ev1",
          subject: "ORPHA:58",
          object: "HP:0000256",
          rel_type: "HAS_PHENOTYPE",
          inferred: false,
          source: "hpoa",
          source_file: "phenotype.hpoa",
          frequency: "HP:0040281",
        },
      ],
      read_only: true,
    });
    getDiseaseDetail.mockResolvedValue({
      disease: { curie: "ORPHA:58", kind: "Disease", label: "Alexander disease" },
      phenotypes: [{ id: "e1", type: "HAS_PHENOTYPE", start: "ORPHA:58", end: "HP:0000256", inferred: false }],
      genes: [],
      inheritance: [],
    });
  });

  it("shows Version 0.6 explorer statistics without ranking diagnoses", async () => {
    render(
      <LocaleProvider>
        <GraphView />
      </LocaleProvider>,
    );

    expect(await screen.findByText("Version 0.6")).toBeInTheDocument();
    expect(screen.getByText("Graph statistics")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load graph" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Roll back graph import" })).toBeInTheDocument();
    expect(screen.getByText(/does not invent missing associations or rank diagnoses/i)).toBeInTheDocument();
    expect(screen.getByText("Read-only exploration")).toBeInTheDocument();
    expect(screen.getByText("Diseases")).toBeInTheDocument();
  });

  it("searches, loads a bounded neighborhood, and inspects provenance", async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <GraphView />
      </LocaleProvider>,
    );

    expect(await screen.findByText("Alexander disease")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Alexander disease/i }));

    await waitFor(() => {
      expect(exploreNeighborhood).toHaveBeenCalled();
      expect(getEntityDetail).toHaveBeenCalledWith("ORPHA:58");
    });
    expect(screen.getByText(/This neighborhood is truncated/i)).toBeInTheDocument();
    expect(screen.getByText(/HAS_PHENOTYPE · ORPHA:58 → HP:0000256/)).toBeInTheDocument();
    expect(screen.getByText(/hpoa · phenotype.hpoa/)).toBeInTheDocument();
  });

  it("expands neighbors on demand without sending the full graph", async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <GraphView />
      </LocaleProvider>,
    );

    expect(await screen.findByText("Alexander disease")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Alexander disease/i }));
    expect(await screen.findByRole("button", { name: "Expand neighbors" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand neighbors" }));
    await waitFor(() => expect(exploreExpand).toHaveBeenCalled());
    expect(screen.getByText(/Visible nodes: 3/)).toBeInTheDocument();
  });
});
