"use client";

import { useEffect, useRef } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";

import { kindStyle } from "@/lib/graph-explorer";
import type { GraphEdgeRead, GraphNodeRead } from "@/lib/types";

export type GraphCanvasApi = {
  exportPng: () => string | null;
  fit: () => void;
  zoomBy: (factor: number) => void;
};

type GraphCanvasProps = {
  nodes: GraphNodeRead[];
  edges: GraphEdgeRead[];
  selectedId: string | null;
  selectedEdgeId: string | null;
  pathIds: string[];
  layoutName: string;
  onSelectNode: (curie: string) => void;
  onSelectEdge: (id: string) => void;
  onExpand: (curie: string) => void;
  onApi?: (api: GraphCanvasApi) => void;
};

export function GraphCanvas({
  nodes,
  edges,
  selectedId,
  selectedEdgeId,
  pathIds,
  layoutName,
  onSelectNode,
  onSelectEdge,
  onExpand,
  onApi,
}: GraphCanvasProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const callbacks = useRef({ onSelectNode, onSelectEdge, onExpand, onApi });
  callbacks.current = { onSelectNode, onSelectEdge, onExpand, onApi };

  useEffect(() => {
    if (!hostRef.current || cyRef.current) return;
    const cy = cytoscape({
      container: hostRef.current,
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.25,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#e7e5e4",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": "92px",
            "text-valign": "center",
            "text-halign": "center",
            width: 42,
            height: 42,
            "background-color": "data(color)",
            shape: "data(shape)",
            "border-width": 2,
            "border-color": "#1c1917",
            "overlay-padding": 6,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "line-color": "#78716c",
            "target-arrow-color": "#78716c",
            label: "data(type)",
            "font-size": 8,
            color: "#a8a29e",
            "text-rotation": "autorotate",
            "text-margin-y": -8,
          },
        },
        {
          selector: "node:selected",
          style: { "border-color": "#f8fafc", "border-width": 4 },
        },
        {
          selector: "edge:selected",
          style: { width: 3, "line-color": "#fb923c", "target-arrow-color": "#fb923c" },
        },
        {
          selector: ".path",
          style: { "border-color": "#fb923c", "line-color": "#fb923c", "target-arrow-color": "#fb923c", width: 3 },
        },
      ],
    });
    cy.on("tap", "node", (event) => {
      callbacks.current.onSelectNode(String(event.target.id()));
    });
    cy.on("tap", "edge", (event) => {
      callbacks.current.onSelectEdge(String(event.target.id()));
    });
    cy.on("dbltap", "node", (event) => {
      callbacks.current.onExpand(String(event.target.id()));
    });
    cyRef.current = cy;
    callbacks.current.onApi?.({
      exportPng: () => cy.png({ full: true, bg: "#0c0a09", scale: 2 }),
      fit: () => cy.fit(undefined, 48),
      zoomBy: (factor) => {
        cy.zoom(cy.zoom() * factor);
      },
    });
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const elements: ElementDefinition[] = [
      ...nodes.map((node) => {
        const style = kindStyle(node.kind);
        return {
          data: {
            id: node.curie,
            label: node.label ?? node.curie,
            kind: node.kind,
            color: style.color,
            shape: style.shape,
          },
        };
      }),
      ...edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.start,
          target: edge.end,
          type: edge.type.replaceAll("_", " "),
        },
      })),
    ];
    cy.elements().remove();
    cy.add(elements);
    if (nodes.length) {
      cy.layout({ name: layoutName, animate: false, fit: true, padding: 40 }).run();
    }
  }, [nodes, edges, layoutName]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().unselect();
    cy.elements().removeClass("path");
    if (selectedId && cy.$id(selectedId).length) cy.$id(selectedId).select();
    if (selectedEdgeId && cy.$id(selectedEdgeId).length) cy.$id(selectedEdgeId).select();
    for (const id of pathIds) {
      if (cy.$id(id).length) cy.$id(id).addClass("path");
    }
  }, [selectedId, selectedEdgeId, pathIds, nodes, edges]);

  return <div ref={hostRef} className="h-full min-h-[420px] w-full" data-testid="graph-canvas" />;
}
