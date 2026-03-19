import type { PaperNode, GraphEdge } from "../types";

interface Props {
  node: PaperNode;
  edges: GraphEdge[];
}

export default function NodeDetail({ node, edges }: Props) {
  const children = edges.filter((e) => e.source === node.id);
  const parents = edges.filter((e) => e.target === node.id);

  return (
    <div className="detail-panel">
      <h3>Paper Detail</h3>
      <div className="detail-section">
        <h4>{node.title}</h4>
        {node.authors.length > 0 && (
          <p className="authors">
            {node.authors.map((a) => a.name).join(", ")}
          </p>
        )}
        <div className="detail-row">
          <span className="detail-label">Year</span>
          <span>{node.year ?? "—"}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Venue</span>
          <span>{node.venue ?? "—"}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Type</span>
          <span className="badge">{node.paper_type}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Cited by</span>
          <span>{node.cited_by_count?.toLocaleString() ?? "—"}</span>
        </div>
        {node.doi && (
          <div className="detail-row">
            <span className="detail-label">DOI</span>
            <a
              href={`https://doi.org/${node.doi}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {node.doi}
            </a>
          </div>
        )}
        {node.arxiv_id && (
          <div className="detail-row">
            <span className="detail-label">arXiv</span>
            <a
              href={`https://arxiv.org/abs/${node.arxiv_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {node.arxiv_id}
            </a>
          </div>
        )}
      </div>
      {children.length > 0 && (
        <div className="detail-section">
          <h4>Children ({children.length})</h4>
          <ul className="edge-list">
            {children.map((e) => (
              <li key={e.target}>
                <span className={`badge badge-${e.strength}`}>
                  {e.strength}
                </span>{" "}
                {e.target}
              </li>
            ))}
          </ul>
        </div>
      )}
      {parents.length > 0 && (
        <div className="detail-section">
          <h4>Parents ({parents.length})</h4>
          <ul className="edge-list">
            {parents.map((e) => (
              <li key={e.source}>
                <span className={`badge badge-${e.strength}`}>
                  {e.strength}
                </span>{" "}
                {e.source}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
