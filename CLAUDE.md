## 项目名称
baseline-trace-graph

## 项目目标
这是一个“研究演化主干图 / baseline-trace graph”工具，不是全量 citation 图。

系统的核心目标是：
- 输入一篇 seed paper
- 递归找到后续工作
- 只保留那些“真正把前人工作当作 baseline / predecessor 来比较或继承”的边
- 输出一个干净、可展开的研究主干图
- 帮助研究者回答：写论文时，最新且真正需要比较的 baseline 到底是谁

## 不是要做什么
本项目**不是**：
- 全量 citation network 可视化工具
- 文献管理器
- 通用学术搜索引擎
- 社交推荐系统
- 自动写 related work 的大而全产品

## 当前产品定义
### 输入
- 起步阶段只支持单篇 seed paper
- seed paper 可通过 DOI / arXiv ID / title 解析

### 输出
- 一个静态网页
- 一个 graph JSON
- 节点表示论文
- 边表示“有意义的 baseline / predecessor 关系”，不是普通 citation

## 核心图定义
默认显示的边 \(A \rightarrow B\) 必须满足：
1. B 引用了 A
2. B 不只是把 A 放在 related work 里，而是把 A 当成了需要认真比较、继承或超越的 predecessor
3. B 属于 technical line 的延续，而不是 survey / dataset / benchmark / 纯 application

## 边分级规则
### strong edge
满足任一：
- A 出现在 B 的实验表格中
- A 出现在 B 的 results / experiments 段落中，并且有明确比较语义
- A 出现在 figure caption 或结果分析里，且明显是 direct comparison

### medium edge
满足任一：
- A 在 B 的方法动机 / method comparison 中被明确讨论
- B 明确说自己是在 A 基础上改进
- 但没有找到强有力的 quantitative evidence

### weak edge
- A 只出现在 related work
- 或只有泛泛引用
- weak edge 不进入主图

## 默认显示策略
- 主图默认只显示 strong edge
- medium edge 默认隐藏，但可以展开
- weak edge 不显示
- 图优先展示“主干、可逐步展开”，而不是尽量全

## 节点类型策略
论文类型包括：
- technical
- survey
- dataset
- benchmark
- application
- theory
- system
- unknown

默认规则：
- 只有 technical 默认进入主图
- dataset / benchmark / survey 不进主图，进入 side tables
- application 默认隐藏
- theory / system 作为可选节点，默认不显示

## 数据源策略
当前阶段只使用：
- OpenAlex 作为主元数据和 citation 数据源
- Open-access full text 用于证据抽取

当前阶段不使用：
- Semantic Scholar
- 闭源付费数据库
- 需要复杂运维的服务

## 构图终止条件
“直到没有新的 citing papers”在实现上定义为：
- 在当前数据源快照下
- 对每个 frontier node 继续扩展
- 直到没有新的 eligible child

eligible child 指：
- cite 了 parent
- 通过 technical filter
- 边等级达到 strong 或 medium 的最小阈值

## 当前阶段优先级
开发优先级按以下顺序执行：
1. 稳定 schema 和中间产物
2. seed resolve
3. candidate expansion
4. paper type classification
5. content fetching
6. edge evidence extraction
7. edge summary
8. graph pruning / ranking
9. 前端展示
10. GitHub Actions / Pages

## 工程原则
- 先做本地可跑通，再做云端自动化
- 先保证 JSON contract 稳定，再做复杂前端
- 每一步都要产出中间文件，便于人工检查
- 优先可解释的规则，不要一开始就堆复杂模型
- 所有网络请求必须有缓存、重试、断点恢复
- 不要为了“工程上很酷”而偏离产品目标

## 建议技术栈
如果没有特殊理由，默认：
- pipeline: Python
- site: TypeScript + React + Vite
- schemas: JSON Schema
- local cache: 文件缓存，必要时再引入 SQLite

如果要偏离这套栈，必须先说明理由。

## 目录约定
建议目录：
- /pipeline        数据抓取、解析、评分、构图
- /site            静态前端
- /data            运行产物和缓存
- /schemas         JSON schema
- /prompts         供模型调用的 prompt 模板
- /docs            架构和设计说明
- /scripts         辅助脚本

## 中间产物要求
每个阶段尽量输出可检查文件，例如：
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

## agent 工作方式要求
每次开始新任务时，请先：
1. 复述你理解的目标
2. 给出实现计划
3. 说明将修改哪些文件
4. 说明风险点和假设

每次完成任务后，请输出：
1. 改了哪些文件
2. 为什么这么改
3. 如何运行 / 测试
4. 当前未解决的问题
5. 下一步建议

## 禁止事项
请不要：
- 把项目做成普通 citation graph
- 默认展示所有引用边
- 在 schema 未稳定前大量写前端
- 无依据地把 weak edge 当成主干边
- 引入复杂微服务、消息队列、数据库集群
- 为了泛化而牺牲当前目标的清晰度

## 遇到不确定需求时
如果遇到以下情况，不要擅自拍板：
- strong / medium / weak 判定冲突
- benchmark shift 是否应保留边
- 没有全文但有 citation 的 frontier 节点如何显示
- 节点类型无法判断
- 技术栈重大变更

此时请：
- 明确列出选项
- 给出推荐方案
- 等待用户确认，或先实现最保守版本

## 本项目的成功标准
成功不是“图很大”，而是：
- 图足够干净
- 主干有研究意义
- strong edge 大多经得起人工检查
- 点击边时，summary 能准确回答“B 相对 A 改了什么，为什么更值得比较”

## 当前默认决策
在用户没有进一步修改前，默认：
- 只支持单 seed
- 主图只显示 technical
- dataset / benchmark / survey 放 side tables
- strong edge 默认显示
- medium edge 默认隐藏
- weak edge 不显示
- OpenAlex only
- public repo + GitHub Pages