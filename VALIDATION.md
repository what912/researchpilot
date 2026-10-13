# 发布前实际验证

核验日期：2026-10-14（Asia/Shanghai）。当前发布目录由已交付 Skill 的30个资源文件、教程、自写示例和离线测试组成，不把完整研究工作区提交到GitHub。

## 本次实际通过

- 官方 `skill-creator/scripts/quick_validate.py` 校验发布包中的 `researchpilot/`：exit0，`Skill is valid!`。
- 在发布目录运行 `python -B -m unittest discover -s tests -p "test_*.py" -v`：18项通过，exit0，约24秒。PDF fixture也实际执行，未跳过。
- `python -B tools/demo.py --project <新目录>`：实际completed CPU smoke，36行/12合成项；hash/引用校验valid=true；新进程读回负结果；已有run再次进入executed=false。输出仅用于软件验证。
- 公开 `prepare_subset.py` 用同一固定官方源文件实测：389fit/60validation/99test，50test用户；训练、验证、测试、原用户映射、原物品映射与原案例逐项相等。JSON说明文字调整导致文件hash不同，未声称新旧文件字节相同。
- 发布的 `lightgcn_numpy.py` 与案例实际运行的实现SHA256一致；本次没有再次训练来挑有利结果。公开CSV为原始20行逐seed聚合输出，未附原数据/逐用户文件。
- 打包清单、Markdown本地链接、JSON与Python语法、个人路径和敏感文件类型由 `tools/check_release.py` 检查；Skill frontmatter另由官方校验器检查。安装副本在隔离目录实测：30资源文件逐字节一致，基本doctor exit0。

测试覆盖：导入/范围/去重/中英文检索与回退、契约引用与隔离、静态仓库/真实Git版本、查新收缩、预览/执行/恢复、非零/缺产物/超时杀进程树、不可观测费用拒绝、外部manifest与hash、独立单位统计/配对/缺失/失败、数据库迁移、修订、导出/删除保护及分析来源限制。

## 怎样自行复验

在仓库根使用Python3.10+，核心测试为标准库；完整PDF fixture可选装开发依赖：

```powershell
python -m venv .venv
$Py = Join-Path $PWD '.venv\Scripts\python.exe'
& $Py -m pip install -r requirements-dev.txt
& $Py -B -m unittest discover -s tests -p 'test_*.py' -v
& $Py -B tools/check_release.py
& $Py -B tools/demo.py --project ../researchpilot-demo
```

没有reportlab时PDF fixture会跳过，不应把跳过算作PDF已验证。Skill校验器属于Codex系统Skill，仓库没有复制该外部代码；本机有skill-creator时可另外运行它。

## 未验证或条件性

本次现场验证平台为Windows/Python3.12；macOS/Linux提供安装/运行说明，未现场验收。GPU、付费API、扫描PDF OCR、所有宿主自动发现行为、全量真实基准没有验证。符号链接逃逸保护存在，但本机创建symlink权限限制会使该分支不能充分实测；已有路径穿越和边界检查通过。

两真实独立智能体参与了LightGCN案例，独立检查过来源及数学/聚合/数据映射；不等于所有未来宿主都有多智能体或所有研究任务都正确。统计/科学范围限制见案例和FAQ。

