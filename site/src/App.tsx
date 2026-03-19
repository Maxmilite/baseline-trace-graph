import { useState, useCallback } from "react";
import { useGraphData } from "./hooks/useGraphData";
import GraphView from "./components/GraphView";
import EdgeDetail from "./components/EdgeDetail";
import NodeDetail from "./components/NodeDetail";
import SideTables from "./components/SideTables";
import FilterBar from "./components/FilterBar";
import type { PaperNode, GraphEdge } from "./types";

type Selection =
  | { kind: "node"; node: PaperNode }
  | { kind: "edge"; edge: GraphEdge }
  | null;

export default function App() {
  const { graph, sideTables, loading, error } = useGraphData();
  const [showMedium, setShowMedium] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<Selection>(null);

  const handleToggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const handleSelectNode = useCallback(
    (node: PaperNode) => setSelection({ kind: "node", node }),
    [],
  );

  const handleSelectEdge = useCallback(
    (edge: GraphEdge) => setSelection({ kind: "edge", edge }),
    [],
  );

  if (loading) return <div className="loading">Loading graph data...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (!graph) return <div className="error">No graph data found.</div>;

  const seed = graph.nodes.find((n) => n.is_seed);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Baseline Trace Graph</h1>
        {seed && (
          <p className="seed-info">
            Seed: {seed.title} ({seed.year})
            <span className="meta">
              {" "}
              &middot; {graph.metadata.node_count} nodes &middot;{" "}
              {graph.metadata.edge_count} edges (
              {graph.metadata.strong_edge_count} strong,{" "}
              {graph.metadata.medium_edge_count} medium)
            </span>
          </p>
        )}
      </header>

      <FilterBar
        showMedium={showMedium}
        onToggleMedium={() => setShowMedium((v) => !v)}
      />

      <div className="main-content">
        <GraphView
          graph={graph}
          showMedium={showMedium}
          expandedNodes={expandedNodes}
          onToggleExpand={handleToggleExpand}
          onSelectNode={handleSelectNode}
          onSelectEdge={handleSelectEdge}
        />
        <aside className="sidebar">
          {selection === null && (
            <div className="detail-panel">
              <p className="hint">Click a node or edge to see details.</p>
            </div>
          )}
          {selection?.kind === "node" && (
            <NodeDetail node={selection.node} edges={graph.edges} />
          )}
          {selection?.kind === "edge" && (
            <EdgeDetail edge={selection.edge} nodes={graph.nodes} />
          )}
        </aside>
      </div>

      {sideTables && <SideTables data={sideTables} />}
    </div>
  );
}
