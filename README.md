# ResearchPilot

**把论文阅读、查新、实验与下一步决策连接成可追溯的研究项目。**

ResearchPilot 是一个面向 Codex 的科研 Skill，适用于 AI/机器学习研究。Codex 负责理解、推理、设计与实现；随附 Python 工具负责材料整理、项目记录、执行、统计和恢复。默认中文输出，保留英文术语与引用。

它可以在没有外部 LLM API Key 的情况下使用。核心 CLI 使用 Python 标准库；读取 PDF 时可选装 `pypdf`。论文性能、创新性和工具可用性都要根据实际证据判断。

## 第一次使用，按这三步走

### 1. 安装 Skill

在 Codex 中调用内置安装器，把本仓库 URL 粘贴到下面提示词中：

```text
$skill-installer 请从这个 GitHub 仓库安装 researchpilot 子目录到 ~/.agents/skills：
https://github.com/what912/researchpilot
如果已存在同名 Skill，先说明，不覆盖已有文件。
```

也可以下载仓库，手动复制 **`researchpilot/` 文件夹** 到：

- 个人使用：`~/.agents/skills/researchpilot/`
- 当前项目使用：`项目目录/.agents/skills/researchpilot/`

复制后应能看到 `researchpilot/SKILL.md`，不要把整个仓库的文档、测试或研究项目一起放进 Skill 目录。安装方式依据[官方本地 Skill 说明](https://learn.chatgpt.com/docs/build-skills)。若发现列表未更新，重开对话或重启 Codex；避免在多个发现目录放置同名副本。

Windows/macOS/Linux 的完整复制与依赖命令见[安装指南](docs/installation.md)。

### 2. 让 Codex 读一篇论文

在 Codex 对话中粘贴下面的提示词，再附论文或填写你的真实路径：

```text
$researchpilot 精读这篇论文。
项目保存在 ./projects/my-paper，使用 read 模式、standard 深度。
解释问题、方法公式、训练推理、实验协议、关键消融和局限。
重要结论给出处，区分作者报告与推断；未读图表明确标注。
把结论保存为可恢复项目。本次先不训练。
论文：（你的 PDF 路径、链接、DOI 或 arXiv ID）
```

你会获得阅读范围、来源定位、Paper Card、重要 Claim、局限和下一步。项目通常包含 `state.sqlite3`、`project.json`、`checkpoint.json` 与报告/来源文件。具体研究内容由 Codex 综合，不是 CLI 自动生成整套科研结论。

### 3. 继续研究或下次恢复

```text
$researchpilot 继续这个项目：./projects/my-paper。
围绕刚才的局限做有界查新，主动找已经做过的工作。
比较最接近方法，给可证伪的最小实验和停止规则。
先把来源、假设和计划保存，不启动长时间或付费任务。
```

```text
$researchpilot 恢复 ./projects/my-paper。
先说明已核实结论、负结果、未解决问题和下一步；不要重跑已完成实验。
```

## 能做什么

| 模式 | 输入示例 | 主要结果 |
|---|---|---|
| `read` | PDF、论文链接、DOI/arXiv ID | 来源、阅读范围、Paper Card、定位事实、局限 |
| `survey` | 研究方向、时间范围、检索预算 | 真实 SearchLog、比较矩阵、覆盖不足与研究空白 |
| `ideate` | 一个想法或论文局限 | 主动反证、最近方法、IdeaCard、可证伪 Hypothesis |
| `reproduce` | 论文及代码仓库 | 仓库版本、依赖/许可/入口检查、论文—代码映射、复现缺口 |
| `experiment` | 假设、代码、数据与预算 | 实验计划、命令预览、授权运行、日志/指标/产物哈希 |
| `analyze` | CSV/JSON/JSONL 或完成的运行 | 独立单位统计、配对差异、区间、失败/缺失、Decision |
| `review` | 研究方案、结论与证据 | 来源、查新、公平性、泄漏、实现与论证问题 |
| `resume` | 已有项目目录 | 约束、决定、负结果、待解问题与下一行动 |
| `pipeline` | 明确范围的完整任务 | 串联适用阶段并保存检查点 |

这些是工作流标签，不是注册的 `/read`、`/survey` 命令。可以在普通自然语言中说明需求，或显式使用 `$researchpilot`。`quick`、`standard`、`deep` 改变覆盖深度，不降低证据标准。

更多可复制提示词：[使用指南](docs/usage.md)。需要直接操作项目文件时：[CLI 教程](docs/cli-tutorial.md)。

## 无网络、无论文的可运行演示

克隆或下载本仓库，在仓库根目录运行：

```powershell
python -B tools/demo.py --project ../researchpilot-demo
```

它会新建隔离项目，实际执行导入→检索→假设/计划→dry-run→短 CPU smoke→分析→负结果决策→校验/导出→新进程恢复。目录必须新建或为空；已有演示项目请用 `resume` 或换一个输出目录。

**这个演示全部使用虚构材料与合成数据，只验证软件工作流。** oracle 读取标签，不能作为公平科研基线；只有一个训练种子，不得据此宣称统计显著或科研提升。该命令会运行随附的已审查 CPU 小程序，不下载模型、不调用付费 API。

## 真论文示例：LightGCN

[LightGCN 案例](docs/lightgcn-case.md)展示了实际论文阅读、有界查新、九处代码映射、真实 LastFM 子图 CPU 实验、独立评审和负结果决策。

| 方法 | Recall@20，五种子均值 | NDCG@20，五种子均值 |
|---|---:|---:|
| MF | 0.2702 | 0.1273 |
| LightGCN，均匀融合 | 0.3491 | 0.1639 |
| LightGCN，最后层 | 0.3578 | 0.1667 |
| 固定度数权重变体 | 0.3463 | 0.1573 |

范围是 60 用户、180 物品、50 测试用户的小图；原论文三数据集基准尚未复现。度数权重方案五个种子均低于标准版，其改善假设不受支持。本仓库只分享自写实现、聚合结果和教程，不附论文全文、原数据、完整研究数据库或个人文件。

## 环境与能力边界

- Python **3.10+**；本次实际在 Windows/Python 3.12 验证。SQLite/FTS5 不可用时词法检索有有限回退。
- PDF 可选 `pypdf>=4,<7`；图表阅读、OCR、公开搜索、GPU、训练框架和多智能体依赖宿主工具，启动时以 `doctor` 与实际探测区分可用、不可用、未检查。
- 本地执行器支持审查过的 **CPU、无网络** 程序，硬控墙钟、进程树及日志大小。它不是 OS 安全沙箱；样本上限仍要求程序正确遵守参数。
- 正 GPU/API/运行内下载预算无法可靠观测时，V1 拒绝直接运行；应在具备真实限额的外部环境执行，再登记真实 manifest。
- 默认词法检索，未实现语义向量/Embedding 检索；Crossref 元数据检索也不等于全面查新。
- 保存正结果、负结果和失败；`completed` 运行不能因恢复自动重跑。作者性能、自身实测、推断与未知必须分开。

详细限制和问题排查：[FAQ](docs/faq.md)。

## 目录与测试

```text
researchpilot/           安装到 Codex 的 Skill，30 个资源文件
docs/                   面向使用者的安装、使用、CLI、案例与 FAQ
tools/demo.py           离线端到端演示
examples/lightgcn/      自写小图实现及聚合结果；不含原数据
tests/                  18 项离线行为测试与合成 fixture
```

```powershell
python -B -m unittest discover -s tests -p "test_*.py" -v
```

可选 PDF 测试依赖与验证结果见 [VALIDATION.md](VALIDATION.md)。代码/文档中的临时路径均由运行时生成。

## 许可

作者选择暂不指定开源许可，本仓库未附 LICENSE。第三方论文、数据集、仓库及依赖各自的许可仍需单独核验。

