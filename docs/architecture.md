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
| 2 | expand-candidates | seed_resolved.json | nodes_raw.json, edges_raw.json, run_manifest.json | BFS expansion of citing works from seed |

## Stage 2: expand-candidates Details

### Strategy
BFS (breadth-first search) from seed paper using incoming citations (works that cite the current node). At this stage, all edges are raw citation candidates — no strength classification yet.

### OpenAlex API
- Endpoint: `GET /works?filter=cites:{openalex_id}&per_page=200&cursor=*`
- Cursor-based pagination: first page uses `cursor=*`, subsequent pages use `meta.next_cursor`
- Each page URL is independently cached

### Default Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| max_depth | 3 | BFS depth from seed (0=seed, 1=direct citers, 2=citers of citers) |
| max_nodes | 500 | Soft cap on total nodes collected |
| max_pages | 5 | Pages per node (~1000 citers max per node) |

### Checkpoint/Resume
- BFS state saved to `expand_checkpoint.json` after each node expansion
- On resume: validates seed_id and config match, otherwise starts fresh
- Atomic writes via temp file + rename to prevent corruption
- Checkpoint deleted on successful completion

### Known Noise Sources
At this stage, the raw candidate graph contains significant noise:
1. **Non-technical papers**: surveys, benchmarks, datasets, applications that cite the seed but aren't part of the research trunk
2. **Tangential citations**: papers that cite the seed in related work only, without treating it as a baseline
3. **Breadth explosion**: highly-cited papers generate many candidates at depth 1, most of which are irrelevant
4. **Missing edges**: OpenAlex may not have complete citation data for recent papers

These are addressed by downstream stages (classify-papers, extract-evidence, prune-graph).
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

## Visibility Policy

Each paper type maps to a display strategy:

| Type | Main Graph | Side Table | Side Table Kind |
|------|-----------|------------|-----------------|
| technical | Yes | No | — |
| survey | No | Yes | survey |
| dataset | No | Yes | dataset |
| benchmark | No | Yes | benchmark |
| application | No | No | — |
| theory | No | No | — |
| system | No | No | — |
| unknown | Yes | No | — |

`unknown` defaults to main graph (conservative: prefer showing over hiding).

### Classification Rules (priority order)

1. **Title keywords** (confidence 0.9): word-boundary match for survey/review/benchmark/dataset/corpus
2. **OpenAlex type** (confidence 0.85): `review` → survey, `dataset` → dataset
3. **Venue keywords** (confidence 0.7): venue name contains dataset/benchmark/shared task
4. **Abstract keywords** (confidence 0.6-0.7): specific phrases like "we survey", "we introduce a dataset"
5. **Topic signals** (confidence 0.5): OpenAlex topic display_name with score > 0.5
6. **Default** (confidence 0.4): article/preprint/conference-paper → technical; otherwise unknown

Application, theory, and system types are not auto-classified — they require deeper semantic understanding and are deferred to future LLM-based classification.

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
