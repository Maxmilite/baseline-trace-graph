# Baseline Trace Graph

研究演化主干图工具 — 从一篇 seed paper 出发，递归追踪后续工作，只保留真正的 baseline / predecessor 关系，输出干净的研究主干图。

A research evolution backbone graph tool — starting from a seed paper, recursively trace subsequent work, keep only genuine baseline/predecessor relationships, and output a clean research backbone graph.

## 这是什么 / What is this

给定一篇论文（seed paper），本工具会：

1. 通过 OpenAlex 查找所有引用它的后续论文
2. 递归展开，构建候选引用网络
3. 对每条引用边进行分级（strong / medium / weak），只保留"真正把前人工作当作 baseline 来比较或继承"的边
4. 输出一个可交互的静态网页，展示研究主干图

Given a seed paper, this tool will:

1. Find all subsequent papers citing it via OpenAlex
2. Recursively expand to build a candidate citation network
3. Grade each citation edge (strong / medium / weak), keeping only edges where the citing paper genuinely treats the cited work as a baseline to compare against or build upon
4. Output an interactive static website showing the research backbone graph

## 不是什么 / What this is NOT

- 不是全量 citation graph — Not a full citation graph
- 不是文献管理器 — Not a reference manager
- 不是通用学术搜索 — Not a general academic search engine

## 快速开始 / Quick Start

### 环境要求 / Requirements

- Python 3.10+
- Node.js 20+

### 安装 / Installation

```bash
# 安装 pipeline CLI
cd pipeline && pip install -e .

# 安装前端依赖
cd ../site && npm install
```

### 本地运行 / Local Run

```bash
# 1. 解析 seed paper
btgraph resolve-seed "Attention Is All You Need" --mailto your@email.com

# 2. 展开候选引用网络
btgraph expand-candidates --mailto your@email.com

# 3. 分类论文类型
btgraph classify-papers

# 4. 抓取全文内容
btgraph fetch-content

# 5. 提取边证据
btgraph extract-evidence

# 6. 生成边摘要
btgraph summarize-edges

# 7. 剪枝排序
btgraph prune-graph

# 8. 导出到前端
btgraph export-site
```

```bash
# 构建并预览前端
cd site && npm run build && npm run preview
```

### GitHub Actions 部署 / Deploy via GitHub Actions

本项目支持通过 GitHub Actions 一键部署到 GitHub Pages：

This project supports one-click deployment to GitHub Pages via GitHub Actions:

1. Settings → Pages → Source → **GitHub Actions**
2. Settings → Secrets → 添加 `OPENALEX_MAILTO`（你的邮箱）
3. Actions → **Deploy Baseline Trace Graph** → Run workflow → 输入 seed paper

详见 / See [docs/deploy.md](docs/deploy.md)

## 项目结构 / Project Structure

```
├── pipeline/          Python 数据管线 / Python data pipeline
│   └── src/btgraph/   CLI 工具和各阶段实现 / CLI tool and stage implementations
├── site/              React + Vite 静态前端 / React + Vite static frontend
├── schemas/           JSON Schema 定义 / JSON Schema definitions
├── docs/              文档 / Documentation
├── data/              运行产物（gitignored）/ Runtime artifacts (gitignored)
├── prompts/           Prompt 模板 / Prompt templates
└── scripts/           辅助脚本 / Helper scripts
```

## Pipeline 阶段 / Pipeline Stages

| 阶段 / Stage | 命令 / Command | 产出 / Output |
|---|---|---|
| 1. 解析 seed | `resolve-seed` | `seed_resolved.json` |
| 2. 展开候选 | `expand-candidates` | `nodes_raw.json`, `edges_raw.json` |
| 3. 分类论文 | `classify-papers` | `paper_types.json` |
| 4. 抓取全文 | `fetch-content` | `content_manifest.json` |
| 5. 提取证据 | `extract-evidence` | `edge_evidence.json` |
| 6. 生成摘要 | `summarize-edges` | `edge_summaries.json` |
| 7. 剪枝排序 | `prune-graph` | `graph_pruned.json`, `side_tables.json` |
| 8. 导出前端 | `export-site` | 复制到 `site/public/` |

## 边分级规则 / Edge Grading

- **Strong**: 论文 A 出现在论文 B 的实验表格、结果比较或 figure caption 中
- **Medium**: A 在 B 的方法动机中被讨论，或 B 明确说在 A 基础上改进，但无定量证据
- **Weak**: A 只出现在 related work 或泛泛引用（不进入主图）

- **Strong**: Paper A appears in Paper B's experiment tables, result comparisons, or figure captions
- **Medium**: A is discussed in B's method motivation, or B explicitly claims to improve upon A, but without quantitative evidence
- **Weak**: A only appears in related work or generic citations (excluded from main graph)

## 前端功能 / Frontend Features

- DAG 可视化（React Flow + dagre 自动布局）
- 点击节点查看论文详情（标题、作者、年份、venue、引用数、DOI/arXiv 链接）
- 点击边查看关系摘要和排名分解
- 展开/折叠隐藏的子节点
- Medium 边显示切换
- Side tables 展示 survey / dataset / benchmark 论文

## 数据源 / Data Source

当前仅使用 [OpenAlex](https://openalex.org/)（免费、开放的学术元数据 API）。

Currently using [OpenAlex](https://openalex.org/) only (free, open academic metadata API).

## License

MIT
