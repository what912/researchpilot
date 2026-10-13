# 证据与查新

Source ID基于原文件SHA256，重复内容不重复计数；版本变化新ID，related_source_ids关联。扩大阅读范围时用新Source+supersedes，不重复导入静默升级。
Claim.references=[{source_id,locator}]；定位是真页/段落字符/章节/表格/代码行。source_fact必须定位；measured_result必须completed RunRecord及哈希吻合产物。
attribution区分author_claim/reported_under_settings/ResearchPilot_measured/user_statement/inferred。用户说法未核验用unknown，不自动标source_fact。
inference写前提与替代解释；hypothesis给反驳规则；confidence_basis解释高/中/低。
metadata_only/abstract_only/partial_text/full_text分开。PDF文本不等于读图，unread_elements保留图表/公式布局/附件。
SearchLog保存query/time/provider/purpose/criteria/time_range/candidates/coverage_limits。purpose=counterexample表示主动找重合工作。
Idea differentiated需最近来源、完成的反例检索及差异；Schema检查流程存在，差异语义由Codex核验。
已有方法重合时新Idea状态overlap/withdrawn并Decision说明收缩。有限检索未发现不等于无人研究。
最近一年用用户当前日期/时区，区分首发/更新/出版，闰日用日历规则。
BibTeX只用已核实字段；缺作者/年份/DOI输出incomplete note，不猜会议信息。
草稿结果句逐项关联Claim→Run→Artifact，smoke或静态阅读不提升成论文结果。
