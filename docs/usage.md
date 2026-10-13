# 怎样把 ResearchPilot 用在真实研究里

## 一条好请求要给哪些信息

尽量提供：对象或研究问题、材料位置、项目目录、期望产物、时间/算力预算、允许的外部操作。可以先给论文，其他非阻塞信息未知时记录为 unknown；不会为了凑卡片而编造信息。

```text
$researchpilot 我研究图协同过滤，先分析 LightGCN。
论文：（PDF 路径或 arXiv:2002.02126）
项目：./projects/lightgcn
希望得到：方法理解、相关方法比较、一个可证伪的小实验。
范围：公开只读检索；本轮不训练，不上传私有材料。
深度：standard；中文输出。
```

模式可显式指定，也可让 Skill 按任务路由。普通聊天或简单语法问题无需整套科研流程。

## read：精读，而不是只写摘要

```text
$researchpilot 精读（论文路径）。项目 ./projects/paper-a，read/standard。
解释方法模块、关键公式、训练与推理；核实数据划分、候选集、指标、基线、消融、资源与局限。
重要事实给页码或章节；列出未读图表、未知细节和复现所需材料。
```

期望产物：Source 阅读范围、PaperCard、定位 Claim、下一行动。全文不可用时继续摘要级/局部分析，并说明范围。文本提取成功不自动代表图表、公式和附件已理解。

## survey：有界调研

```text
$researchpilot 调研图协同过滤的层融合与对比学习。
项目 ./projects/paper-a；限定 ID-only 隐式推荐。
先选五篇最相关原文，并筛查最近一年候选，保存真实中英查询与纳入/排除理由。
对比机制、数据、划分、指标和预算；主动找反例，不拼跨文排行榜。
```

期望产物：SearchLog、来源范围、可比矩阵、空白类型及反证、覆盖不足。有限调研不能推出无人研究或当前最新方法保证。

## ideate：先找重复，再收缩想法

```text
$researchpilot 核查这个想法：给 LightGCN 加可学习层权重以适应用户稀疏度。
主动查找已经做过的工作；给最接近方法、相似/差异与未覆盖范围。
若重复就撤回宽泛创新表述；保留可解释的工程假设，并设计最小反驳实验。
```

期望产物：IdeaCard、countersearch、可证伪 Hypothesis、推荐与备选、Decision。不会承诺创新概率、发表或录用。LightGCN 原文本身就讨论过 alpha 学习；示例展示为何要先查新。

## reproduce：论文到代码

```text
$researchpilot 分析论文与作者仓库（论文/仓库链接）。
项目 ./projects/paper-a；允许只读公开检索与小型源码下载。
先固定 commit、阅读 AGENTS/依赖/许可/入口，建立论文—代码对应关系。
先交付可运行性与差异分析，本轮不要安装/执行未经审查的仓库入口。
```

期望产物：RepoMap、CodeMapping、依赖/版本/初始化/采样/评价差异、缺口与 smoke 方案。静态对应不代表官方代码运行或论文性能复现成功。

## experiment：授权边界内真正运行

```text
$researchpilot 根据已保存假设准备并运行一个小型 CPU pilot。
项目 ./projects/paper-a；仅运行你已审查、无网络的本地程序。
每个 run 最多120秒、0 GPU、0付费API、0运行内下载；最多5000条不同训练交互。
先冻结划分、参数、种子、主指标和反驳规则；保存命令/输入配置hash、日志与真实指标。
先 smoke，只根据链路/公式/指标正确性决定是否继续，别按测试成绩调参。
```

期望产物：完整 ExperimentPlan、dry-run、RunRecord、Artifact、停止原因与检查点。执行器不提供恶意代码 OS 隔离；正 GPU/API/下载费用应交实际能限制资源的环境执行，不能拿环境变量当严格成本控制。

## analyze：数据格式和独立单位

```csv
group,seed,score,status
baseline,0,0.50,completed
method,0,0.54,completed
baseline,1,0.52,completed
method,1,0.51,completed
```

上表是**合成格式示例**，不是实测。JSON 行数组、`{"rows": [...]}`、JSONL 也可用。

```text
$researchpilot 分析（真实结果文件），项目 ./projects/paper-a。
指标 ndcg20，独立单位为训练 seed；同组同 seed 多行先按预设规则聚合。
报告配对差值、区间、失败/缺失、未匹配 seed，并解释负结果。
不要把用户行数当种子重复；若文件来自已完成 run，链接并核验原产物hash。
```

期望产物：描述统计、独立单位 Bootstrap、按需配对差异/dz、Decision。显式请求并满足假设时才做 sign-flip；少量重复不自动升格为强科学证据。

## review：让反驳有依据

```text
$researchpilot 审查 ./projects/paper-a 的当前主张与证据。
重点检查查新、协议公平、数据泄漏、测试保护、代码差异与结论外推。
若宿主支持且有实际收益，使用独立 Reviewer，只给原材料与待审主张，不预灌结论。
分歧逐项核原始证据，再保存 Review 和 Decision。
```

支持真实多智能体时，分别写隔离输出，主智能体核查并单一写正式库；无此工具则串行审查并说明同一智能体完成，不能伪造独立评审。

## pipeline 与 resume

```text
$researchpilot 以（论文/方向）串联必要阶段，pipeline/standard。
项目 ./projects/paper-a；公开只读查询；小型 CPU 预算按上面的明确范围。
持续至范围内全部产物完成，报告已核实、条件性能力、负结果及未完成项。
```

```text
$researchpilot 恢复 ./projects/paper-a。
按 checkpoint 与数据库说明当前约束、最近决定、失败、负结果和未解决问题。
已完成 run 不重跑；若发现孤儿 running，先检查所有者和实际日志，再提出明确恢复动作。
```

项目属于研究工作目录；Skill 安装目录只放静态资源。变更目标、主张或配置应留修订，不能直接覆盖旧结果或偷偷改假设。

## 怎么判断交付是否可信

看四件事：来源与实际定位；运行状态与日志/产物；统计独立单位和数据范围；结论是否保留反证、负结果和未知。链路跑通、小图方向信号、强实验证据与跨设置稳健是不同层级。

