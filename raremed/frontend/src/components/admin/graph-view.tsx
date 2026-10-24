"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { DependencyRow } from "@/components/status-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useOptionalAuth } from "@/lib/auth";
import {
  ApiError,
  exploreExpand,
  exploreNeighborhood,
  explorePath,
  exploreSearch,
  exploreSources,
  getDiseaseDetail,
  getEntityDetail,
  getGraphStatus,
  loadGraph,
  rollbackGraph,
} from "@/lib/api";
import {
  DISPLAY_EDGE_LIMIT,
  DISPLAY_NODE_LIMIT,
  EXPLORER_KINDS,
  EXPAND_LIMIT,
  SEARCH_PAGE_SIZE,
  downloadPng,
  kindStyle,
  mergeGraphSlice,
} from "@/lib/graph-explorer";
import { useLocale } from "@/lib/i18n";
import type {
  DiseaseDetail,
  EntityDetail,
  GraphEdgeRead,
  GraphNodeRead,
  GraphSearchHit,
  GraphStatus,
  SourceFacetRead,
} from "@/lib/types";

import type { GraphCanvasApi } from "@/components/admin/graph-canvas";

const GraphCanvas = dynamic(() => import("@/components/admin/graph-canvas").then((mod) => mod.GraphCanvas), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[420px] items-center justify-center text-sm text-muted-foreground">
      Loading canvas
    </div>
  ),
});

const LAYOUTS = ["cose", "breadthfirst", "circle", "grid", "concentric"] as const;

export function GraphView() {
  const { t } = useLocale();
  const auth = useOptionalAuth();
  const isAdmin = auth?.user?.role === "admin";
  const canvasApi = useRef<GraphCanvasApi | null>(null);

  const [graph, setGraph] = useState<GraphStatus | null>(null);
  const [sources, setSources] = useState<SourceFacetRead[]>([]);
  const [query, setQuery] = useState("Alexander");
  const [suggestions, setSuggestions] = useState<GraphSearchHit[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [kinds, setKinds] = useState<string[]>([...EXPLORER_KINDS]);
  const [source, setSource] = useState("");
  const [sourceVersion, setSourceVersion] = useState("");
  const [nodes, setNodes] = useState<GraphNodeRead[]>([]);
  const [edges, setEdges] = useState<GraphEdgeRead[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [disease, setDisease] = useState<DiseaseDetail | null>(null);
  const [pathStart, setPathStart] = useState<string | null>(null);
  const [pathEnd, setPathEnd] = useState<string | null>(null);
  const [pathIds, setPathIds] = useState<string[]>([]);
  const [layoutName, setLayoutName] = useState<(typeof LAYOUTS)[number]>("cose");
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedNode = nodes.find((item) => item.curie === selectedId) ?? entity?.entity ?? null;
  const selectedEdge = edges.find((item) => item.id === selectedEdgeId) ?? null;
  const nodeCounts = graph?.node_counts ?? {};
  const relCounts = graph?.relationship_counts ?? {};

  const reload = useCallback(async () => {
    try {
      setGraph(await getGraphStatus());
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("apiOffline"));
    }
    try {
      setSources(await exploreSources());
    } catch {
      setSources([]);
    }
  }, [t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (query.trim().length >= 2) void search(0, false);
    }, 280);
    return () => window.clearTimeout(handle);
    // kinds/source are intentional search inputs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, kinds, source, sourceVersion]);

  async function search(nextOffset = 0, append = false) {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const page = await exploreSearch({
        q: query.trim(),
        kinds,
        source: source || undefined,
        sourceVersion: sourceVersion || undefined,
        offset: nextOffset,
        limit: SEARCH_PAGE_SIZE,
      });
      setSuggestions(append ? [...suggestions, ...page.items] : page.items);
      setOffset(page.offset);
      setHasMore(page.has_more);
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("apiOffline"));
    } finally {
      setSearching(false);
    }
  }

  async function openNeighborhood(curie: string) {
    setLoadingGraph(true);
    setSelectedId(curie);
    setSelectedEdgeId(null);
    setPathIds([]);
    try {
      const found = await exploreNeighborhood({
        curie,
        depth: 1,
        limit: 40,
        kinds,
        source: source || undefined,
      });
      const merged = mergeGraphSlice([], [], found);
      setNodes(merged.nodes);
      setEdges(merged.edges);
      setTruncated(Boolean(found.truncated) || merged.truncated);
      await inspect(curie, found.center.kind);
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("requestFailed"));
    } finally {
      setLoadingGraph(false);
    }
  }

  async function expandNode(curie: string) {
    setLoadingGraph(true);
    try {
      const slice = await exploreExpand({
        curie,
        limit: EXPAND_LIMIT,
        kinds,
        source: source || undefined,
      });
      const merged = mergeGraphSlice(nodes, edges, slice);
      setNodes(merged.nodes);
      setEdges(merged.edges);
      setTruncated(truncated || slice.truncated || merged.truncated);
      setSelectedId(curie);
      await inspect(curie);
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("requestFailed"));
    } finally {
      setLoadingGraph(false);
    }
  }

  async function inspect(curie: string, kind?: string) {
    try {
      const detail = await getEntityDetail(curie);
      setEntity(detail);
      if ((kind ?? detail.entity.kind) === "Disease") {
        setDisease(await getDiseaseDetail(curie));
      } else {
        setDisease(null);
      }
    } catch {
      setEntity(null);
      setDisease(null);
    }
  }

  async function highlightPath() {
    if (!pathStart || !pathEnd || pathStart === pathEnd) return;
    setLoadingGraph(true);
    try {
      const slice = await explorePath(pathStart, pathEnd);
      const merged = mergeGraphSlice(nodes, edges, slice);
      setNodes(merged.nodes);
      setEdges(merged.edges);
      setTruncated(truncated || merged.truncated);
      setPathIds([...slice.nodes.map((item) => item.curie), ...slice.edges.map((item) => item.id)]);
      setError(null);
    } catch (cause) {
      setPathIds([]);
      setError(cause instanceof ApiError ? cause.message : t("noPath"));
    } finally {
      setLoadingGraph(false);
    }
  }

  async function run(action: "load" | "rollback") {
    if (!isAdmin) return;
    setBusy(true);
    try {
      setGraph(action === "load" ? await loadGraph() : await rollbackGraph());
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("requestFailed"));
    } finally {
      setBusy(false);
    }
  }

  function toggleKind(kind: string) {
    setKinds((current) => {
      const next = current.includes(kind) ? current.filter((item) => item !== kind) : [...current, kind];
      return next.length ? next : current;
    });
  }

  function exportVisible() {
    const png = canvasApi.current?.exportPng();
    if (png) downloadPng(png);
  }

  const sourceOptions = useMemo(() => {
    const seen = new Map<string, SourceFacetRead[]>();
    for (const item of sources) {
      const rows = seen.get(item.name) ?? [];
      rows.push(item);
      seen.set(item.name, rows);
    }
    return seen;
  }, [sources]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
        <h1 className="mt-2 font-heading text-4xl">{t("knowledgeGraph")}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("graphBody")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">{t("reasoningOff")}</Badge>
        <Badge variant="outline">{graph?.loaded ? t("graphLoaded") : t("graphNotLoaded")}</Badge>
        <Badge variant="outline">{t("graphReadOnly")}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("graphStats")}</CardTitle>
          <CardDescription>{graph?.note ?? t("graphNotLoaded")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DependencyRow
            label={t("graphStore")}
            state={!graph ? "loading" : graph.connection.status === "ok" ? "ok" : "unavailable"}
          />
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6 text-sm">
            <Stat label={t("diseases")} value={nodeCounts.Disease ?? 0} />
            <Stat label={t("phenotypes")} value={nodeCounts.Phenotype ?? 0} />
            <Stat label={t("genes")} value={nodeCounts.Gene ?? 0} />
            <Stat label={t("inheritance")} value={nodeCounts.InheritancePattern ?? 0} />
            <Stat
              label={t("relationships")}
              value={Object.values(relCounts).reduce((sum, value) => sum + value, 0)}
            />
            <Stat label={t("inferredRelations")} value={graph?.inferred_relationship_count ?? 0} />
          </div>
          <p className="text-xs text-muted-foreground">
            {t("visibleNodes")}: {nodes.length}/{DISPLAY_NODE_LIMIT} · {t("visibleEdges")}: {edges.length}/
            {DISPLAY_EDGE_LIMIT}
          </p>
          <div className="flex flex-wrap gap-2">
            {isAdmin ? (
              <>
                <Button type="button" onClick={() => void run("load")} disabled={busy || graph?.running}>
                  {t("loadGraph")}
                </Button>
                <Button type="button" variant="outline" onClick={() => void run("rollback")} disabled={busy}>
                  {t("rollbackGraph")}
                </Button>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">{t("adminOnlyLoad")}</p>
            )}
            <Button type="button" variant="outline" onClick={() => void reload()}>
              {t("refresh")}
            </Button>
            <a href="http://localhost:7474" target="_blank" rel="noreferrer">
              <Button type="button" variant="outline">
                {t("openNeo4j")}
              </Button>
            </a>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>{t("graphSearch")}</CardTitle>
            <CardDescription>{t("graphSearchLead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label={t("graphSearch")}
              onKeyDown={(event) => {
                if (event.key === "Enter") void search(0, false);
              }}
            />
            <div className="flex flex-wrap gap-2">
              {EXPLORER_KINDS.map((kind) => (
                <Button
                  key={kind}
                  type="button"
                  size="sm"
                  variant={kinds.includes(kind) ? "default" : "outline"}
                  onClick={() => toggleKind(kind)}
                >
                  {kindStyle(kind).label}
                </Button>
              ))}
            </div>
            <div className="grid gap-2">
              <label className="text-xs text-muted-foreground" htmlFor="graph-source">
                {t("sourceFilter")}
              </label>
              <select
                id="graph-source"
                className="h-8 rounded-lg border bg-background px-2 text-sm"
                value={`${source}::${sourceVersion}`}
                onChange={(event) => {
                  const [name, version] = event.target.value.split("::");
                  setSource(name === "all" ? "" : name);
                  setSourceVersion(version && version !== "all" ? version : "");
                }}
              >
                <option value="all::all">{t("allSources")}</option>
                {[...sourceOptions.entries()].map(([name, versions]) =>
                  versions.map((item) => (
                    <option key={`${item.name}-${item.version}`} value={`${item.name}::${item.version ?? "all"}`}>
                      {name}
                      {item.version ? ` ${item.version}` : ""} ({item.node_count})
                    </option>
                  )),
                )}
              </select>
            </div>
            <Button type="button" onClick={() => void search(0, false)} disabled={searching}>
              {searching ? t("loading") : t("graphSearch")}
            </Button>
            <ul className="divide-y rounded-xl border" aria-label={t("searchSuggestions")}>
              {suggestions.map((hit) => (
                <li key={`${hit.kind}-${hit.curie}`}>
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => void openNeighborhood(hit.curie)}
                  >
                    <span>
                      {hit.label ?? hit.curie}
                      <span className="block text-xs text-muted-foreground">
                        {hit.curie} · {hit.kind}
                      </span>
                    </span>
                    <span className="mt-1 size-2 shrink-0 rounded-full" style={{ background: kindStyle(hit.kind).color }} />
                  </button>
                </li>
              ))}
            </ul>
            {suggestions.length === 0 && !searching ? (
              <p className="text-xs text-muted-foreground">{t("nodeSearchEmpty")}</p>
            ) : null}
            {hasMore ? (
              <Button type="button" variant="outline" onClick={() => void search(offset + SEARCH_PAGE_SIZE, true)}>
                {t("loadMore")}
              </Button>
            ) : null}
          </CardContent>
        </Card>

        <Card className="min-w-0 overflow-hidden">
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>{t("graphExplorer")}</CardTitle>
                <CardDescription>{t("graphExploreLead")}</CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => canvasApi.current?.zoomBy(1.2)}>
                  {t("zoomIn")}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => canvasApi.current?.zoomBy(0.8)}>
                  {t("zoomOut")}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => canvasApi.current?.fit()}>
                  {t("fitGraph")}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={exportVisible} disabled={!nodes.length}>
                  {t("exportGraph")}
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-muted-foreground" htmlFor="graph-layout">
                {t("layoutLabel")}
              </label>
              <select
                id="graph-layout"
                className="h-8 rounded-lg border bg-background px-2 text-sm"
                value={layoutName}
                onChange={(event) => setLayoutName(event.target.value as (typeof LAYOUTS)[number])}
              >
                {LAYOUTS.map((name) => (
                  <option key={name} value={name}>
                    {t(`layout${name[0].toUpperCase()}${name.slice(1)}` as "layoutCose")}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setNodes([]);
                  setEdges([]);
                  setPathIds([]);
                  setTruncated(false);
                }}
              >
                {t("clearGraph")}
              </Button>
            </div>
            {truncated ? <p className="text-sm text-amber-600 dark:text-amber-400">{t("graphTruncated")}</p> : null}
            {loadingGraph ? <p className="text-sm text-muted-foreground">{t("loading")}</p> : null}
          </CardHeader>
          <CardContent className="p-0">
            <div className="h-[min(70vh,640px)] bg-zinc-950">
              <GraphCanvas
                nodes={nodes}
                edges={edges}
                selectedId={selectedId}
                selectedEdgeId={selectedEdgeId}
                pathIds={pathIds}
                layoutName={layoutName}
                onSelectNode={(curie) => {
                  setSelectedId(curie);
                  setSelectedEdgeId(null);
                  void inspect(curie);
                }}
                onSelectEdge={(id) => setSelectedEdgeId(id)}
                onExpand={(curie) => void expandNode(curie)}
                onApi={(api) => {
                  canvasApi.current = api;
                }}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>{t("diseasePanel")}</CardTitle>
            <CardDescription>{t("graphEditLocked")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {selectedNode ? (
              <div className="space-y-2">
                <p className="font-medium">{selectedNode.label ?? selectedNode.curie}</p>
                <p className="text-muted-foreground">
                  {selectedNode.curie} · {selectedNode.kind}
                </p>
                {selectedNode.definition ? <p>{selectedNode.definition}</p> : null}
                <p className="text-xs text-muted-foreground">
                  {t("source")}: {selectedNode.source ?? "—"}
                  {selectedNode.source_version ? ` ${selectedNode.source_version}` : ""}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" onClick={() => void expandNode(selectedNode.curie)}>
                    {t("expandNeighbors")}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setPathStart(selectedNode.curie)}>
                    {t("pathStart")}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setPathEnd(selectedNode.curie)}>
                    {t("pathEnd")}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground">{t("explorerReady")}</p>
            )}

            <div className="space-y-2 rounded-xl border p-3">
              <p className="text-xs font-medium uppercase tracking-wide">{t("highlightPath")}</p>
              <p className="text-xs text-muted-foreground">{t("pathHint")}</p>
              <p>
                {pathStart ?? "—"} → {pathEnd ?? "—"}
              </p>
              <Button type="button" size="sm" onClick={() => void highlightPath()} disabled={!pathStart || !pathEnd}>
                {t("highlightPath")}
              </Button>
            </div>

            {selectedEdge ? (
              <section className="space-y-1">
                <h2 className="font-medium">{t("relationshipDetails")}</h2>
                <p>
                  {selectedEdge.type} · {selectedEdge.start} → {selectedEdge.end}
                </p>
                <p className="text-xs text-muted-foreground">
                  {selectedEdge.polarity ?? "asserted"}
                  {selectedEdge.frequency ? ` · ${selectedEdge.frequency}` : ""}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("source")}: {selectedEdge.source ?? "—"}
                  {selectedEdge.source_file ? ` · ${selectedEdge.source_file}` : ""}
                  {selectedEdge.source_version ? ` · ${selectedEdge.source_version}` : ""}
                </p>
                {selectedEdge.evidence ? <p className="text-xs">{selectedEdge.evidence}</p> : null}
              </section>
            ) : null}

            {entity?.relationships.length ? (
              <section className="space-y-1">
                <h2 className="font-medium">{t("relationshipDetails")}</h2>
                <ul className="max-h-40 space-y-1 overflow-auto text-xs">
                  {entity.relationships.map((item) => (
                    <li key={item.id}>
                      <button type="button" className="text-left hover:underline" onClick={() => setSelectedEdgeId(item.id)}>
                        {item.type} {item.start} → {item.end}
                        {item.source ? ` · ${item.source}` : ""}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="space-y-1">
              <h2 className="font-medium">{t("evidenceInspector")}</h2>
              {entity?.evidence.length ? (
                <ul className="max-h-48 space-y-2 overflow-auto text-xs">
                  {entity.evidence.map((item) => (
                    <li key={item.id} className="rounded-lg border p-2">
                      <p>
                        {item.rel_type} · {item.subject} → {item.object}
                      </p>
                      <p className="text-muted-foreground">
                        {item.source ?? "—"}
                        {item.source_version ? ` ${item.source_version}` : ""}
                        {item.source_file ? ` · ${item.source_file}` : ""}
                      </p>
                      {item.frequency ? <p>{item.frequency}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">{t("provenanceEmpty")}</p>
              )}
            </section>

            {disease ? (
              <section className="space-y-1">
                <h2 className="font-medium">{disease.disease.label}</h2>
                <p>
                  {t("phenotypes")}: {disease.phenotypes.length} · {t("genes")}: {disease.genes.length} ·{" "}
                  {t("inheritance")}: {disease.inheritance.length}
                </p>
                <ul className="max-h-36 list-disc overflow-auto ps-5 text-xs">
                  {disease.phenotypes.slice(0, 12).map((item) => (
                    <li key={item.id}>
                      {item.end} ({item.polarity ?? "unknown"}
                      {item.frequency ? `, ${item.frequency}` : ""})
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </CardContent>
        </Card>
      </div>
      <Disclaimer text={t("disclaimer")} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <p>
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground"> — {value}</span>
    </p>
  );
}
