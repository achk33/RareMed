import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IngestionView } from "@/components/admin/ingestion-view";
import { LocaleProvider } from "@/lib/i18n";

const getIngestionStatus = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status = 500;
    code = "request_failed";
  },
  getIngestionStatus: () => getIngestionStatus(),
  runIngestion: vi.fn(),
  rollbackIngestion: vi.fn(),
}));

describe("ingestion view", () => {
  beforeEach(() => {
    getIngestionStatus.mockResolvedValue({
      running: false,
      current_run: { run_id: "run-1", status: "succeeded", entity_count: 3, relationship_count: 4, warning_count: 1, missing_required: ["hpo/hp.obo"] },
      last_successful_import: "2026-10-24T12:00:00Z",
      missing_required: ["hpo/hp.obo", "hpo/phenotype.hpoa"],
      sources: [
        {
          source: "hpo",
          role: "hpo_ontology_json",
          file_path: "raw/hpo/hp.json",
          expected_path: "raw/hpo/hp.json",
          version: "2026-09-01",
          release_date: "2026-09-01",
          import_status: "parsed",
          entity_counts: { phenotype: 20482 },
          relationship_counts: { is_a: 24436 },
          validation_warnings: ["Required source files are absent: hpo/hp.obo"],
          last_successful_import: "2026-10-24T12:00:00Z",
          required: false,
          schema_name: "obo_graphs_json",
        },
      ],
      history: [],
      counts: { entities: 3, relationships: 4 },
      note: "Relationships come only from downloaded source files.",
    });
  });

  it("shows source path, version, status, counts, warnings, and last import", async () => {
    render(
      <LocaleProvider>
        <IngestionView />
      </LocaleProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Ingestion" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Source" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "File path" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Version" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Import status" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Entities" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Relationships" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Validation warnings" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Last successful import" })).toBeInTheDocument();
    expect(screen.getByText("raw/hpo/hp.json")).toBeInTheDocument();
    expect(screen.getByText("2026-09-01")).toBeInTheDocument();
    expect(screen.getByText("parsed")).toBeInTheDocument();
    expect(screen.getByText("phenotype 20482")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run import" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Roll back to previous import" })).toBeEnabled();
  });
});
