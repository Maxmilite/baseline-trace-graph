import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphData, GraphEdge, PaperNode } from "../types";
import { applyDagreLayout } from "../layout";

interface Props {
  graph: GraphData;
  showMedium: boolean;
  expandedNodes: Set<string>;
  onToggleExpand: (nodeId: string) => void;
  onSelectNode: (node: PaperNode) => void;
  onSelectEdge: (edge: GraphEdge) => void;
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

export default function GraphView({
  graph,
  showMedium,
  expandedNodes,
  onToggleExpand,
  onSelectNode,
  onSelectEdge,
}: Props) {
  // Build visible edges
  const visibleEdges = useMemo(() => {
    return graph.edges.filter((e) => {
      if (e.default_visible) return true;
      if (e.strength === "medium" && showMedium) return true;
      // Expanded nodes show all their hidden children
      if (expandedNodes.has(e.source)) return true;
      return false;
    });
  }, [graph.edges, showMedium, expandedNodes]);

  // Visible node IDs
  const visibleNodeIds = useMemo(() => {
    const ids = new Set<string>();
    // Always show seed
    for (const n of graph.nodes) {
      if (n.is_seed) ids.add(n.id);
    }
    for (const e of visibleEdges) {
      ids.add(e.source);
      ids.add(e.target);
    }
    return ids;
  }, [graph.nodes, visibleEdges]);

  // Count hidden children per node
  const hiddenChildCount = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of graph.edges) {
      if (!visibleEdges.includes(e)) {
        counts[e.source] = (counts[e.source] ?? 0) + 1;
      }
    }
    return counts;
  }, [graph.edges, visibleEdges]);

  // Build React Flow nodes
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));

    const rfNodes: Node[] = [];
    for (const id of visibleNodeIds) {
      const paper = nodeMap.get(id);
      if (!paper) continue;
      const hidden = hiddenChildCount[id] ?? 0;
      const isExpanded = expandedNodes.has(id);
      const label =
        truncate(paper.title, 40) +
        (paper.year ? ` (${paper.year})` : "") +
        (hidden > 0 ? ` [${isExpanded ? "−" : "+"}${hidden}]` : "");

      rfNodes.push({
        id,
        data: { label, paperId: id },
        position: { x: 0, y: 0 },
        className: paper.is_seed ? "node-seed" : "node-default",
      });
    }

    const rfEdges: Edge[] = visibleEdges
      .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
      .map((e) => ({
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        style:
          e.strength === "medium"
            ? { strokeDasharray: "6 3", stroke: "#999" }
            : { stroke: "#333", strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
        data: { edgeKey: `${e.source}->${e.target}` },
      }));

    return applyDagreLayout(rfNodes, rfEdges);
  }, [visibleNodeIds, visibleEdges, hiddenChildCount, expandedNodes, graph.nodes]);

  // Edge lookup for click handler
  const edgeMap = useMemo(() => {
    const m = new Map<string, GraphEdge>();
    for (const e of graph.edges) {
      m.set(`${e.source}->${e.target}`, e);
    }
    return m;
  }, [graph.edges]);

  const nodeMap = useMemo(
    () => new Map(graph.nodes.map((n) => [n.id, n])),
    [graph.nodes],
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const paper = nodeMap.get(node.id);
      if (!paper) return;
      // Check if click is on the expand badge area
      const hidden = hiddenChildCount[node.id] ?? 0;
      if (hidden > 0) {
        onToggleExpand(node.id);
      }
      onSelectNode(paper);
    },
    [nodeMap, hiddenChildCount, onToggleExpand, onSelectNode],
  );

  const onEdgeClick: EdgeMouseHandler = useCallback(
    (_event, edge) => {
      const ge = edgeMap.get(edge.id);
      if (ge) onSelectEdge(ge);
    },
    [edgeMap, onSelectEdge],
  );

  return (
    <div className="graph-container">
      <ReactFlow
        nodes={layoutNodes}
        edges={layoutEdges}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        fitView
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
