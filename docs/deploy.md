# Deployment Guide

## Prerequisites

1. **GitHub Pages**: Settings → Pages → Source → select **GitHub Actions**
2. **Repository Secret**: Settings → Secrets and variables → Actions → New repository secret
   - Name: `OPENALEX_API_KEY`
   - Value: your API key from [openalex.org/settings/api](https://openalex.org/settings/api) (free, takes 30 seconds to register)

## How to Trigger

1. Go to the **Actions** tab in the repository
2. Select **Deploy Baseline Trace Graph** in the left sidebar
3. Click **Run workflow**
4. Enter a seed paper identifier:
   - DOI: `10.48550/arXiv.1706.03762`
   - arXiv ID: `1706.03762`
   - Title: `Attention Is All You Need`
5. Click the green **Run workflow** button

## What Happens

The workflow runs two jobs:

### Build job
1. Sets up Python 3.12 and Node 20
2. Installs the `btgraph` pipeline CLI
3. Restores cached OpenAlex API responses (if any)
4. Runs the 8-step pipeline sequentially:
   - `resolve-seed` → resolves the seed paper via OpenAlex
   - `expand-candidates` → BFS expansion of citing papers
   - `classify-papers` → classifies paper types (technical, survey, etc.)
   - `fetch-content` → downloads open-access full text
   - `extract-evidence` → finds baseline/comparison evidence in text
   - `summarize-edges` → generates edge summaries
   - `prune-graph` → ranks and prunes edges, produces final graph
   - `export-site` → copies graph JSON to site/public/
5. Builds the React frontend (`npm ci && npm run build`)
6. Uploads pipeline data as a debug artifact (7-day retention)
7. Uploads the built site for GitHub Pages deployment

### Deploy job
- Deploys the built site to GitHub Pages
- Live URL: `https://<username>.github.io/baseline-trace-graph/`

## Artifacts

| Artifact | Contents | Retention |
|----------|----------|-----------|
| `pipeline-data` | All intermediate JSON files from data/ | 7 days |
| `github-pages` | Built site (site/dist/) | Managed by Pages |

The `pipeline-data` artifact is uploaded even if the workflow fails, which helps with debugging.

## Caching

Three caches speed up subsequent runs:
- **pip**: Python package cache (httpx)
- **npm**: Node module cache (React, Vite, etc.)
- **OpenAlex API**: Response cache in `data/cache/openalex/` — the biggest time saver on reruns with the same or overlapping seed papers

## Troubleshooting

### fetch-content shows "partial results" warning
This is expected. The `fetch-content` step may return exit code 2 when some papers can't be downloaded (404, rate limits, no open-access URL). The pipeline continues with whatever content was fetched. Check the `pipeline-data` artifact's `content_manifest.json` for details.

### Pipeline fails at resolve-seed
The seed query couldn't be resolved. Check:
- Is the DOI/arXiv ID correct?
- For title search, try a more specific title string
- Check if OpenAlex is reachable (rare outages)

### Pipeline fails at expand-candidates
Usually a network issue or OpenAlex rate limiting. The step supports checkpoint/resume, so re-running the workflow will pick up where it left off (via the OpenAlex cache).

### API key issues
- Get a free API key at [openalex.org/settings/api](https://openalex.org/settings/api)
- Without a key, you get very limited access
- Ensure the `OPENALEX_API_KEY` secret is set correctly in repository settings

### Deploy job fails
- Verify GitHub Pages is enabled with source set to "GitHub Actions"
- Check that the repository has Pages permissions (public repos have this by default)

### Checking intermediate results
1. Go to the failed/completed workflow run
2. Scroll to **Artifacts**
3. Download `pipeline-data`
4. Inspect the JSON files: `seed_resolved.json`, `nodes_raw.json`, `paper_types.json`, `edge_evidence.json`, `graph_pruned.json`, etc.

## Security

- `OPENALEX_API_KEY` is only used as a CLI argument during the build job
- No secrets are injected into the frontend bundle (Vite only exposes `VITE_`-prefixed env vars)
- The deployed site contains only static HTML/JS/CSS and JSON data files
