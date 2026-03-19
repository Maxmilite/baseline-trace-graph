import { useState, useEffect } from "react";
import type { GraphData, SideTablesData } from "../types";

interface UseGraphDataResult {
  graph: GraphData | null;
  sideTables: SideTablesData | null;
  loading: boolean;
  error: string | null;
}

export function useGraphData(): UseGraphDataResult {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [sideTables, setSideTables] = useState<SideTablesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        // Try real data first, fall back to sample
        const graphRes = await tryFetch<GraphData>("graph_pruned.json", "sample_graph.json");
        const sideRes = await tryFetch<SideTablesData>("side_tables.json", "sample_side_tables.json");
        setGraph(graphRes);
        setSideTables(sideRes);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return { graph, sideTables, loading, error };
}

async function tryFetch<T>(primary: string, fallback: string): Promise<T> {
  const base = import.meta.env.BASE_URL;
  let res = await fetch(`${base}${primary}`);
  if (!res.ok) {
    res = await fetch(`${base}${fallback}`);
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch ${primary} or ${fallback}`);
  }
  return res.json() as Promise<T>;
}
