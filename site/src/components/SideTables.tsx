import { useState } from "react";
import type { SideTablesData } from "../types";

interface Props {
  data: SideTablesData;
}

const TAB_ORDER = ["survey", "dataset", "benchmark"];

export default function SideTables({ data }: Props) {
  const availableTabs = TAB_ORDER.filter((t) => data.tables[t]?.length);
  const [activeTab, setActiveTab] = useState(availableTabs[0] ?? "");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (availableTabs.length === 0) {
    return null;
  }

  const entries = data.tables[activeTab] ?? [];

  return (
    <div className="side-tables">
      <h3>Side Tables</h3>
      <div className="tab-bar">
        {availableTabs.map((tab) => (
          <button
            key={tab}
            className={`tab-btn ${tab === activeTab ? "active" : ""}`}
            onClick={() => {
              setActiveTab(tab);
              setExpandedRow(null);
            }}
          >
            {tab} ({data.tables[tab]?.length ?? 0})
          </button>
        ))}
      </div>
      <table className="side-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Year</th>
            <th>Venue</th>
            <th>Cited by</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <>
              <tr
                key={entry.id}
                className={expandedRow === entry.id ? "expanded" : ""}
                onClick={() =>
                  setExpandedRow(expandedRow === entry.id ? null : entry.id)
                }
              >
                <td className="title-cell">{entry.title}</td>
                <td>{entry.year ?? "—"}</td>
                <td>{entry.venue ?? "—"}</td>
                <td>{entry.cited_by_count?.toLocaleString() ?? "—"}</td>
              </tr>
              {expandedRow === entry.id &&
                entry.edges_to_main_graph.length > 0 && (
                  <tr key={`${entry.id}-edges`} className="edge-row">
                    <td colSpan={4}>
                      <div className="edge-detail-inline">
                        <strong>Edges to main graph:</strong>
                        <ul>
                          {entry.edges_to_main_graph.map((e, i) => (
                            <li key={i}>
                              {e.source} → {e.target}{" "}
                              <span className={`badge badge-${e.strength}`}>
                                {e.strength}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </td>
                  </tr>
                )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
