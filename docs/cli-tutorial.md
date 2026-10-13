# CLI 教程：脚本怎样配合 Codex

日常使用建议直接在 Codex 里调用 `$researchpilot`。CLI 提供确定性的整理、记录、运行和统计；不会独立完成论文语义理解、创新判断或自动写科学结论。

## 1. 环境探测

以下 PowerShell 示例在仓库根目录运行，不需要安装成全局 shell 命令：

```powershell
$Py = 'python'
$Skill = Join-Path $PWD 'researchpilot\scripts\researchpilot.py'
& $Py -B $Skill doctor --json
```

若用了虚拟环境，把 `$Py` 改成 `.venv\Scripts\python.exe` 的实际路径。已安装的 Skill 可把 `$Skill` 改为安装目录中的 `scripts/researchpilot.py`。

每个命令都支持 `--help` 和 `--json`。退出码：0 成功；2 输入、契约或网络错误；3 运行 failed/cancelled。不要只看 stdout 的某个指标就忽略退出码。

## 2. 新建、导入与检索

```powershell
$Project = Join-Path $PWD '..\paper-project'
& $Py -B $Skill init --project $Project --question '理解并核验一篇论文' --mode read --depth standard --json
$Paper = Read-Host '输入你的真实论文 PDF 或文本路径'
& $Py -B $Skill ingest --project $Project $Paper --json
& $Py -B $Skill search --project $Project 'layer combination' --limit 5 --json
```

`init` 要求新/空目录。`ingest` 接受 TXT/Markdown/有文本层 PDF/结构化 Source JSON；同一项目内按文件hash去重。`search` 返回真实片段与定位，是词法检索。`partial_text` 是默认范围；不能把提取完全文误标成读懂全部公式/图。

若只有链接、标题或 DOI，让 Codex 先查身份、消歧与获取范围，再导入合适的 Source。`remote` 只查询 Crossref 元数据：

```powershell
& $Py -B $Skill remote --project $Project 'LightGCN recommendation' --rows 3 --purpose counterexample --json
& $Py -B $Skill fetch --project $Project 'https://arxiv.org/pdf/2002.02126' --output evidence/lightgcn.pdf --json
```

需要实际网络权限；`fetch` 限定 HTTPS 的 api.crossref.org、export.arxiv.org、arxiv.org，并有大小/超时限制。其他网页用宿主阅读，不扩大允许域。

## 3. 结构化记录

查看字段，再让 Codex 根据真实来源填写模板：

```powershell
& $Py -B $Skill contract --kind PaperCard --json
& $Py -B $Skill memory --project $Project list --kind Source --json
```

`memory list` 的结果形如 `{"records": [...]}`，`memory get` 返回单条记录。其他类型见 `researchpilot/assets/templates/` 和 `references/contracts.md`。JSON 中的 unknown/null 是待核实内容，不是有效科学发现。

准备好真实 JSON 后，例如 `evidence/paper-card.json`：

```powershell
& $Py -B $Skill memory --project $Project put --kind PaperCard --file (Join-Path $Project 'evidence\paper-card.json') --json
```

必须使用存在的 `source_id`、`claim_ids` 等引用。更正时新 ID + `supersedes`，保留历史；RunRecord/Artifact 不能靠普通 `memory put` 伪造。

## 4. 一个真正可执行的完整练习

如果还没有真实实验代码，用随附演示先走完整流程：

```powershell
& $Py -B tools/demo.py --project ../researchpilot-demo
```

该脚本已经逐项生成 Source、Idea、Hypothesis、ExperimentPlan 与真实短 CPU RunRecord，输出 `demo-summary.json`、`demo-commands.json`、运行日志和校验/导出。全部 synthetic，不能拿其数字当科研结果。

真实项目的执行顺序：

```powershell
$PlanFile = Join-Path $Project 'evidence\experiment-plan.json'
& $Py -B $Skill plan --project $Project $PlanFile --json
& $Py -B $Skill run --project $Project exp_your_id --json
& $Py -B $Skill run --project $Project exp_your_id --execute --json
```

先用真实计划 ID 替换 `exp_your_id`。dry-run 只显示命令/预算，不产生运行。实际执行要求同时具备 `--execute`、已审查代码与计划授权，以及 `local_cpu_no_network` 配置。每次明确的新运行保存在新的 `{run_dir}`，不覆盖旧结果；调参/代码配置变化新建 ExperimentPlan。

## 5. 统计真实结果

```powershell
$Rows = Read-Host '输入真实 CSV/JSON/JSONL 结果路径'
& $Py -B $Skill analyze --project $Project $Rows --metric ndcg20 --unit seed --json
```

恰好两组、相同单位能配对时加 `--paired`；需要且满足符号可交换假设时，显式加 `--test signflip`。`--predefined` 只有事前已有真实预设协议才使用。

`--run-id` 可关联已完成运行，但文件hash必须匹配该run的真实原始产物。派生/拼接文件还没有完整自动血缘系统，须保存提取规则；不能硬关联成原始输出。更多细节见 `references/execution.md`。

## 6. 仓库、报告和外部运行

`repo --project PROJECT LOCAL_REPO` 做静态库存、AST、Git/许可/入口检查，不执行仓库。`artifact --project PROJECT REPORT_FILE` 保存真实报告快照及hash。

外部受限环境的真实运行可以用 `record` 登记 manifest，必填实验 ID、命令、起止、退出码、环境、输入hash、stdout/stderr与产物路径/hash。工具可核文件和hash，不能把提供方执行升级为自己独立观察。清单结构见 `references/execution.md` 与 CLI帮助。

## 7. 恢复、校验、导出

```powershell
& $Py -B $Skill status --project $Project --json
& $Py -B $Skill validate --project $Project --json
& $Py -B $Skill export --project $Project --output reports/export --json
& $Py -B $Skill resume --project $Project --json
```

`state.sqlite3` 是权威。导出包括记录JSONL、来源表、BibTeX与检查点；保留历史版本，可能包含同一工作多个来源。缺失元数据明确可见。

按已有 run ID 再进入不会重跑：

```powershell
& $Py -B $Skill run --project $Project exp_your_id --run-id run_your_id --execute --json
```

若是 running，先核进程所有者；`recover` 只显式取消已无所有者的孤儿，不把中断自动标为成功。`delete` 默认预览；实际删除必须明确执行和匹配项目 ID，会删除该项目，因此不放进日常练习命令。

