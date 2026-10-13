# 自写 NumPy LightGCN 小图示例

仅用于教学与低成本机制复核，不是官方实现或原论文三基准性能复现。代码使用 dense 240×240 传播矩阵，不能据此宣称大图效率。

包含：`lightgcn_numpy.py`（核心传播/BPR/Adam/指标与检查）、`prepare_subset.py`（从用户提供的官方 LastFM 文件冻结子图）、`results/`（本次20行逐seed聚合指标与摘要）。不包含原数据、论文或完整研究项目。

## 准备输入

使用你已有且许可适用的 [作者链接的 PyTorch 仓库](https://github.com/gusye1234/LightGCN-PyTorch) 的 `data/lastfm/data1.txt` 与 `test1.txt`。本案例固定 commit：`947ca2b3b1d2d3545b114145710cb06c4e57b3d2`。脚本核对文件hash并报告是否匹配案例，不安装或执行该仓库入口。

在本仓库根，用含 NumPy 的 Python：

```powershell
python -m venv .venv-lightgcn
$Py = Join-Path $PWD '.venv-lightgcn\Scripts\python.exe'
& $Py -m pip install 'numpy==2.3.1'
$Source = Read-Host '填入你已有的官方 data/lastfm 目录'
& $Py -B examples/lightgcn/prepare_subset.py --source-dir $Source --output ./data/lightgcn-demo
```

建议为固定NumPy2.3.1使用Python3.11–3.13，参见[NumPy2.3支持范围](https://numpy.org/doc/2.3/release/2.3.0-notes.html)；核心Skill仍要求Python3.10+。本案例用Python3.12.1/NumPy2.3.1。没有NumPy不影响基础Skill和合成演示。

## 先检查链路，再跑小型 pilot

```powershell
& $Py -B examples/lightgcn/lightgcn_numpy.py --data ./data/lightgcn-demo/lastfm-subset.json --samples 389 --steps 4 --seeds 0 --stage smoke --output ./demo-output/lightgcn-smoke
& $Py -B examples/lightgcn/lightgcn_numpy.py --data ./data/lightgcn-demo/lastfm-subset.json --samples 389 --steps 180 --seeds '0,1,2,3,4' --stage pilot --output ./demo-output/lightgcn-pilot
```

只有相同源文件才预期389条fit；不同输入先检查manifest，不调高预算掩盖数据差异。直接脚本会写同名结果文件，请为每次运行选新输出目录。这两个直接Python命令没有ResearchPilot墙钟/进程树控制。要演示完整可审计执行，让Codex将该脚本/数据复制进独立研究项目，创建ExperimentPlan并用RP run；不要把上面的普通执行结果假装成已经由RP观察的run。

数学检查包括：手工归一化、迭代传播与P多项式一致、四方法梯度有限差分、Recall/NDCG小例、已知正例mask和split互斥。训练结束保存 `metrics.json`、`checks.json`、`config.json`、`rows.csv`、`users.csv`、`curves.csv` 与两份预设比较子集。

## 必须保留的解释

同normal.1初始化、BPR sampled-E0正则、Adam lr.02、维度16、batch256、180steps和seed采样序列；并未验证各模型充分调参后的表现。smoke也输出test指标；应只检查链路，不按test改pilot配置。负采样排除fit正例，仍可能抽到未观察验证/测试正例。

60用户、180物品，389fit/60validation/99test，只有50用户有保留test；29候选物品fit度为零。末层给这些物品零表示并按固定索引处理同分，不能作冷启动或完整覆盖结论。

本次标准LightGCN−MF NDCG为+.036606；固定度数权重−标准为−.006656。五seed只是同一固定子图的训练重复，不是五个数据集；不重做当前test调参获得有利结论。细节见 [公开案例](../../docs/lightgcn-case.md)。

