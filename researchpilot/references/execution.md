# 执行与分析

ExperimentPlan必填见contract。budget/requested均含time_seconds/gpu_seconds/api_usd/samples/download_mb，requested不得超budget。
dataset含version/source/license_status/split/preprocessing/deduplication/contamination_check；metrics含primary/secondary/calculation/failure_rate/resource_cost。
含强与简单baseline、方法/消融、参数、种子、独立单位、测试保护/调参、统计、预算估计依据与unknown、sequence/go_no_go/stop_conditions。
authorization包含local_execute/reviewed_code/resource_profile=local_cpu_no_network，只在真实用户授权与审查支持时填true。
command是argv无shell，替换{python}/{project}/{run_dir}/{samples}/{seed}。inputs是项目内脚本/数据/配置；artifacts建议{run_dir}/metrics.json；cwd是.或项目内目录。
stage=smoke/pilot/main/ablation/robustness。dry-run不启动进程/创建RunRecord；--execute与计划授权都满足才运行。
硬控墙钟/日志8MiB/进程树：Windows Job Object关闭/终止关联树，POSIX session group。Windows启动后立即绑定，绑定失败拒绝运行。
不是OS沙箱；CPU/no-network是代码审查断言，CUDA_VISIBLE_DEVICES不限制所有GPU API。正GPU/API/下载请求拒绝，因为不能严格观测限额。
样本预检查、--samples参数、输出数量检查需代码遵守，不能严格约束任意程序内部工作量。更严格资源环境由宿主/提供方执行后record。
超时cancelled，非0failed，0但缺产物failed。保存配置/输入/输出哈希、起止/命令/种子/环境/日志。
completed不重复；失败取消要显式新run重试；recover只取消已无所有者的孤儿running。
外部manifest需experiment_id/command/started_at/ended_at/exit_code/environment/input_hashes/stdout/stderr文件/artifacts[{path,sha256}]，可metrics/seed/synthetic。复制与哈希可核，外部执行本身为用户提供provenance，不能声称独立观察。
分析CSV/JSON rows列表或{rows:[...]}/JSONL；列group、明确独立单位、metric。非completed记失败，空/非有限/无法解析记缺失，不填补。
--run-id关联时输入文件哈希必须匹配这些运行的真实产物，并重核产物哈希。拼接/派生数据尚无自动血缘追踪，可不关联run进行来源受限分析，由Codex保存提取与派生规则，不能伪装成某个运行原始输出。
group/unit多行先均值，再单位等权；任务/种子/轨迹依预设协议。Bootstrap seed42、2000次，n<2无CI，小n提示不稳。
配对只用匹配单位，报告未匹配ID。Cohen dz以差值SD为分母，零SD保持null。
--paired要求输入恰好两组；三组及以上需按预设对比另存可追溯的两组子集。不能自动挑最有利比较。
signflip仅显式选择，假设独立单位且差值符号可交换，n<=16枚举，否则10000次MC。不机械显著性检验。
默认exploratory，--predefined需事前计划，语义由Codex核验。CLI只给链路或方向信号，较强/跨设置证据由Codex核实充分协议/重复。
