# 数据契约与权威

`RP contract --kind KIND --json`列必填字段及类型，scripts/rp_contracts.py执行枚举/语义/引用校验。
Source/PaperCard/Claim/IdeaCard/Hypothesis/Decision/ExperimentPlan/RunRecord/Artifact/ProjectProfile均有专门结构；另含SearchLog/RepoMap/CodeMapping/OpenQuestion/Review/Delegation。
id小写字母开头，[a-z0-9_-]最长101字符。未知元数据null，未知描述unknown，空列表表示没有该项，不编造。
缺关键字段/无定位/非有限数字/不存在ID/跨项目引用退出2。RunRecord/Artifact只能run/record/recover写入。
records存通过类型、必填、枚举校验的结构JSON；projects归属；record_refs是真外键；chunks保存来源/项目/定位/原文/token。
record_versions保留修订，events有序留痕，FTS可重建。schema_version=2；V1→V2添加版本历史并保留已有数据。新版本数据库拒绝打开。
非RunRecord不可就地更改，更正新id+supersedes；checkpoint排除过时记录。RunRecord只允许合法状态转移。
SQLite事务/10秒锁和execution.lock保护正式写入；Coordinator单写入者。不要让子智能体同时编辑数据库或同一文件。
权威state.sqlite3；project.json/checkpoint/Markdown/JSONL都是可重建导出。
CodeMapping必须匹配RepoMap文件哈希和真实行范围；源仓库变化后重建快照/映射。
写入拒绝绝对路径、..、冒号及逃逸symlink。材料可从项目外读取，运行程序本身不是安全沙箱。
不同项目独立数据库，无隐式全局私有记忆共享。
