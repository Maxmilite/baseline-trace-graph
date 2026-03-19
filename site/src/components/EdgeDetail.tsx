import type { GraphEdge, PaperNode } from "../types";

interface Props {
  edge: GraphEdge;
  nodes: PaperNode[];
}

export default function EdgeDetail({ edge, nodes }: Props) {
  const source = nodes.find((n) => n.id === edge.source);
  const target = nodes.find((n) => n.id === edge.target);

  return (
    <div className="detail-panel">
      <h3>Edge Detail</h3>
      <div className="detail-row">
        <span className="detail-label">From</span>
        <span>{source?.title ?? edge.source}</span>
      </div>
      <div className="detail-row">
        <span className="detail-label">To</span>
        <span>{target?.title ?? edge.target}</span>
      </div>
      <div className="detail-row">
        <span className="detail-label">Strength</span>
        <span className={`badge badge-${edge.strength}`}>{edge.strength}</span>
      </div>
      {edge.summary && (
        <div className="detail-section">
          <h4>Summary</h4>
          <p>{edge.summary}</p>
        </div>
      )}
      <div className="detail-section">
        <h4>Ranking</h4>
        <div className="detail-row">
          <span className="detail-label">Score</span>
          <span>{edge.rank_score.toFixed(4)}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Rank among siblings</span>
          <span>#{edge.rank_among_siblings}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Evidence count</span>
          <span>{edge.evidence_count}</span>
        </div>
      </div>
      <div className="detail-section">
        <h4>Rank Breakdown</h4>
        <table className="rank-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Value</th>
              <th>Weight</th>
              <th>Contrib</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(edge.rank_breakdown).map(([name, f]) => (
              <tr key={name}>
                <td title={f.detail}>{name}</td>
                <td>{f.value.toFixed(3)}</td>
                <td>{f.weight.toFixed(2)}</td>
                <td>{f.contribution.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
