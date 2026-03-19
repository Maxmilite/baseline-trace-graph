# Architecture: baseline-trace-graph

## System Goal

Given a seed paper, recursively discover subsequent work and retain only edges where a later paper genuinely treats the earlier paper as a baseline to compare against or build upon. The output is a clean, expandable trunk graph that answers: **"What are the latest baselines I actually need to compare against?"**

This is NOT a full citation network. It is a research evolution trunk graph.

## Baseline-Trace Graph vs Citation Graph

| Aspect | Citation Graph | Baseline-Trace Graph |
|--------|---------------|---------------------|
| Edges | All citations | Only baseline/predecessor relationships |
| Node filter | None | Technical papers only (surveys, datasets → side tables) |
| Display | Everything | Strong edges default; medium expandable; weak hidden |
| Goal | Completeness | Research-relevant trunk |
| Scale | Explodes quickly | Stays focused and pruned |

## Pipeline Stages

```
seed query ──→ [1] resolve-seed
                    │
            seed_resolved.json
                    │
               [2] expand-candidates
                    │
         nodes_raw.json + edges_raw.json
                    │
               [3] classify-papers
                    │
             paper_types.json
                    │
               [4] fetch-content
                    │
           content_manifest.json
                    │
               [5] extract-evidence
                    │
            edge_evidence.json
                    │
               [6] summarize-edges
                    │
           edge_summaries.json
                    │
               [7] prune-graph
                    │
            graph_pruned.json
                    │
               [8] export-site
                    │
            site_graph.json ──→ static site
```

### Stage Details

| # | Stage | Input | Output | Description |
|---|-------|-------|--------|-------------|
| 1 | resolve-seed | DOI / arXiv ID / title | seed_resolved.json | Resolve user query to canonical paper record via OpenAlex |
| 2 | expand-candidates | seed_resolved.json | nodes_raw.json, edges_raw.json | Recursively find citing papers until no new eligible children |
| 3 | classify-papers | nodes_raw.json | paper_types.json | Classify each paper as technical/survey/dataset/benchmark/etc. |
| 4 | fetch-content | nodes_raw.json | content_manifest.json | Download open-access full text for evidence extraction |
| 5 | extract-evidence | content_manifest.json + edges_raw.json | edge_evidence.json | Find evidence snippets that justify each edge |
| 6 | summarize-edges | edge_evidence.json | edge_summaries.json | Generate human-readable summary for each edge |
| 7 | prune-graph | all intermediate files | graph_pruned.json | Apply edge strength + node type filters, produce final graph |
| 8 | export-site | graph_pruned.json | site_graph.json | Format graph for frontend consumption |

## Edge Classification

### Strong (default visible)
- A appears in B's experiment tables
- A appears in B's results/experiments with comparison semantics
- A in figure captions or result analysis as direct comparison

Evidence types: `table_mention`, `result_comparison`, `figure_caption`

### Medium (expandable)
- A discussed in B's method motivation / method comparison
- B explicitly claims improvement over A
- No strong quantitative evidence found

Evidence types: `method_discussion`, `improvement_claim`

### Weak (hidden, not in main graph)
- A only in related work or generic citation

Evidence types: `related_work_only`, `generic_citation`

## Node Types

| Type | Default behavior |
|------|-----------------|
| technical | Enters main graph |
| survey | Side table only |
| dataset | Side table only |
| benchmark | Side table only |
| application | Hidden |
| theory | Optional, hidden by default |
| system | Optional, hidden by default |
| unknown | Pending classification |

## Data Source

Current stage: **OpenAlex only**.
- Metadata and citation data from OpenAlex API
- Open-access full text for evidence extraction
- No Semantic Scholar, no paid databases

## Intermediate Artifacts

Every stage produces inspectable JSON files in `/data/`:
- seed_resolved.json
- nodes_raw.json
- edges_raw.json
- paper_types.json
- content_manifest.json
- edge_evidence.json
- edge_summaries.json
- graph_pruned.json
- site_graph.json
- run_manifest.json
