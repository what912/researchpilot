# 安装与第一次验证

## 前提

需要能读取本地 Skill、文件和运行 Python 的 Codex 宿主。核心工具依赖 Python 3.10+ 标准库；PDF 提取可选装 pypdf。网络/多智能体/GPU 等先由宿主实际核验，不是安装 Skill 就全部获得。

## 推荐：让 Codex 安装

```text
$skill-installer 从当前 GitHub 仓库的 researchpilot 子目录安装这个 Skill。
仓库 URL：https://github.com/what912/researchpilot
目标目录：~/.agents/skills。
如果同名目录已经存在，请先说明，不直接覆盖。
```

明确填入 URL；独立对话不会知道“当前仓库”是哪个。安装器若选择其他目录，以该宿主当前支持的发现位置为准。

## 手动安装：Windows PowerShell

先通过 GitHub 的 Code → Download ZIP 解压，或复制 HTTPS 地址后克隆；进入包含 `README.md` 的仓库根目录。

```powershell
$RepoUrl = Read-Host '粘贴本仓库的 GitHub HTTPS 地址'
git clone $RepoUrl researchpilot-release
Set-Location researchpilot-release
```

安装到个人 Skill 目录，不覆盖已有副本：

```powershell
$SkillDir = Join-Path $HOME '.agents\skills\researchpilot'
if (Test-Path -LiteralPath $SkillDir) {
    throw '同名 Skill 已存在。先检查旧版本，选择明确的更新/备份方案。'
}
New-Item -ItemType Directory -Path (Split-Path $SkillDir) -Force | Out-Null
Copy-Item -LiteralPath '.\researchpilot' -Destination $SkillDir -Recurse
Test-Path -LiteralPath (Join-Path $SkillDir 'SKILL.md')
```

只安装当前项目时，将 `$SkillDir` 改为项目根下 `.agents\skills\researchpilot`。

### 可选：PDF 依赖

虚拟环境放仓库或研究工作区，别放在安装的 Skill 目录里。

```powershell
python --version
python -m venv .venv
$Py = Join-Path $PWD '.venv\Scripts\python.exe'
& $Py -m pip install -r .\researchpilot\scripts\requirements-pdf.txt
$Skill = Join-Path $SkillDir 'scripts\researchpilot.py'
& $Py -B $Skill doctor --json
```

没有 `python` 命令时，可使用已安装的 `py -3` 或宿主提供的 Python。不要把多个解释器下“装过包”混为当前解释器可以导入。

## 手动安装：macOS/Linux

下载/克隆仓库后，在仓库根运行：

```bash
skill_dir="$HOME/.agents/skills/researchpilot"
if [ -e "$skill_dir" ]; then
    printf '%s\n' '同名 Skill 已存在，请先检查旧版本。'
else
    mkdir -p "$HOME/.agents/skills"
    cp -R ./researchpilot "$skill_dir"
fi
```

可选 PDF 环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r researchpilot/scripts/requirements-pdf.txt
.venv/bin/python -B "$HOME/.agents/skills/researchpilot/scripts/researchpilot.py" doctor --json
```

这些安装命令按目录结构提供；本次没有在 macOS/Linux 机器上现场安装验收。

## 确認发现与调用

安装后开启 Codex 对话，输入 `$researchpilot` 或从 Skill 选择器查找 ResearchPilot。列表未更新时重开对话或重启 Codex；也可先明确给出已安装 `SKILL.md` 的路径。

当前官方目录说明：[Build skills](https://learn.chatgpt.com/docs/build-skills)，核对日期 2026-10-14。不要把同名副本放在多个扫描目录后期待它们自动合并。

CLI 方式验证只说明脚本能运行；还应在 Codex 中实际完成一次阅读/演示，确认宿主有对应文件和工具权限。

## 无网络验收

回到仓库根，运行：

```powershell
python -B tools/demo.py --project ../researchpilot-demo
```

这会执行短 CPU 合成演示。结束应输出 `completed`、`integrity_valid: true`、`resume_negative_decision: true` 和导出路径。已有目录请选择另一个新路径，不删除旧结果。

