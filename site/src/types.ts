export interface Author {
  name: string;
}

export interface PaperNode {
  id: string;
  title: string;
  authors: Author[];
  year: number | null;
  paper_type: string;
  venue: string | null;
  doi: string | null;
  arxiv_id: string | null;
  cited_by_count: number | null;
  is_seed: boolean;
}

export interface RankFactor {
  value: number;
  weight: number;
  contribution: number;
  detail: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  strength: "strong" | "medium";
  rank_score: number;
  rank_breakdown: Record<string, RankFactor>;
  rank_among_siblings: number;
  default_visible: boolean;
  summary: string | null;
  evidence_count: number;
}

export interface GraphMetadata {
  seed_id: string;
  generated_at: string;
  node_count: number;
  edge_count: number;
  strong_edge_count: number;
  medium_edge_count: number;
}

export interface GraphData {
  nodes: PaperNode[];
  edges: GraphEdge[];
  metadata: GraphMetadata;
}

export interface SideTableEdge {
  source: string;
  target: string;
  strength: string;
}

export interface SideTableEntry {
  id: string;
  title: string;
  authors: Author[];
  year: number | null;
  paper_type: string;
  venue: string | null;
  cited_by_count: number | null;
  edges_to_main_graph: SideTableEdge[];
}

export interface SideTablesData {
  tables: Record<string, SideTableEntry[]>;
  metadata: Record<string, unknown>;
}
