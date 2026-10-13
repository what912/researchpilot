# CLI

Python3.10+：`python /absolute/skill/scripts/researchpilot.py COMMAND --help`。每个命令--help/--json，无LLM Key需求。
核心标准库；可选PDF pypdf>=4,<7或已有pdfplumber，依赖装项目venv。requirements-pdf.txt可给pip。OCR/图像依真实宿主。
stdout JSON，--json紧凑；错误stderr。退出0成功、2输入/契约/网络错误、3运行failed/cancelled。

| 命令 | 参数 |
|---|---|
| doctor | [--project P] [--host JSON] |
| init | --project P [--profile JSON] [--question Q] [--mode M] [--depth D] |
| ingest | --project P PATH [--scope S] [--title T] |
| search | --project P QUERY [--limit 1..100] |
| memory put | --project P --kind KIND --file JSON |
| memory list/get | --project P [--kind KIND] / --id ID |
| plan | --project P JSON |
| run | --project P EXP [--execute] [--run-id EXISTING] |
| record | --project P MANIFEST |
| artifact | --project P REPORT_FILE [--role research_report] [--synthetic] |
| analyze | --project P FILE --metric score --unit seed [--group group] [--paired] [--test signflip] [--synthetic] [--run-id ID] [--predefined] |
| status/resume/validate/export | --project P [export --output reports/export] |
| recover | --project P RUN_ID |
| repo | --project P LOCAL_REPO |
| remote | --project P QUERY [--purpose counterexample] [--rows 1..20] |
| fetch | --project P ALLOWLISTED_HTTPS --output evidence/paper.pdf |
| delete | --project P [--execute --confirm EXACT_PROJECT_ID] |
| contract | [--kind KIND] |

init要求新建或空目录，先init再把材料放入项目；已有材料可先从目录外导入，已有项目用resume。
doctor --host只接受doctor输出已有的能力键（如python/public_web_search/page_read/subagents/gpu/paper_metadata/fulltext_access/network_policy/upload_policy），值为{status,evidence}。示例：{"subagents":{"status":"available","evidence":"宿主实际工具；并发上限4；已完成独立试用"}}。不使用web_search等自定义别名。
Source JSON至少title，可authors/year/url/doi/arxiv_id/reading_scope/text/source_type/version/unread_elements/related_source_ids/synthetic。
fetch仅HTTPS api.crossref.org/export.arxiv.org/arxiv.org，检查DNS/IP和重定向，12秒socket、2尝试、10MiB、24h哈希缓存；任意网页用宿主阅读。
remote只元数据/真实日志，不代表全文；筛选后新修订保存纳入排除。仓库URL用真实宿主git/network下载，不运行安装脚本。
调用示例：
```text
$researchpilot 精读论文路径，核实方法实验，指出值得查新的局限。
$researchpilot 调研最近一年LLM Agent长期交互安全，先核实工作再提出有限算力方案。
$researchpilot 核查轨迹级风险检测改善工具安全的想法，找最近工作，主动反驳并设计最小实验。
$researchpilot 分析仓库能否复现论文，建立论文—代码映射并执行已授权CPU smoke。
$researchpilot 根据结果文件分析负结果、统计不确定性与实现问题，保存下一步。
$researchpilot 恢复项目路径，说明已核实/未解决和下一实验。
```
安装以宿主及当前官方目录规范核实，不硬编码用户名。未发现时可直接指明SKILL.md绝对路径。
