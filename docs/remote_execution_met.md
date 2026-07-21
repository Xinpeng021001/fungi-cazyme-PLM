# met 服务器与 Cursor/Codex 可复现执行指南

## 1. 当前环境事实

- SSH host：`met.unl.edu`（本机 `~/.ssh/config` 已配置 user `xinpeng`）。
- 项目目录：`/array1/xinpeng/fungi-cazyme-PLM`。
- Git：服务器目录为 clean `main`，tracking `origin/main`。
- GPU：8 × NVIDIA RTX A5500，单卡约 24 GB。
- 磁盘：2026-07-21 检查时 `/array1` 约 2.0 TB 可用。
- 无 Slurm/PBS；有 `tmux` 3.2a。
- `uv` 位于 `~/.local/bin/uv`；已安装 Python 3.11/3.12。
- system Python 3.10 不满足项目 `requires-python >=3.11`。
- Cursor 已安装 Codex extension；服务器 shell 当前未检测到 Codex CLI。

这些值是环境快照，不是永久保证。每次正式 run 仍需由 wrapper 保存新的 GPU、磁盘、Python、commit 和 package 状态。

## 2. SSH 连接

从本地终端：

```bash
ssh met.unl.edu
cd /array1/xinpeng/fungi-cazyme-PLM
git status --short --branch
```

只做连通性测试：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=12 met.unl.edu \
  'cd /array1/xinpeng/fungi-cazyme-PLM && hostname && git status --short --branch'
```

不要把私钥、Biohub token、Hugging Face token 写入仓库。token 应通过交互式登录、环境变量或权限受限的 secret file 提供。

## 3. 在 Cursor Remote-SSH 中使用 Codex

OpenAI 的 Codex IDE extension 支持 VS Code-compatible editors，包括 Cursor。推荐流程：

1. Cursor 通过 Remote-SSH 打开 `met.unl.edu`。
2. 左下角确认显示远端连接，而不是本地窗口。
3. 打开 `/array1/xinpeng/fungi-cazyme-PLM` 文件夹。
4. 若扩展面板提示安装位置，选择安装/启用于该 Remote-SSH workspace。
5. Command Palette 运行 `Codex: Open Codex Sidebar`。
6. 在新任务开头写明：只读 raw sibling data；所有运行使用 `scripts/remote/met_run.sh`；不得把 token/大数据加入 Git。

Codex Desktop、本地 Cursor 和远端 Cursor 不共享同一个 shell process，也不应依赖聊天历史“自动转移”。共享上下文应通过 Git 中的 `project.md`、设计文档、报告、schema 和 `AGENTS.md`（如后续创建）实现。

官方参考：[Codex IDE extension](https://developers.openai.com/codex/ide)。

## 4. 同步代码和报告

推荐 Git 路线：

```bash
# 本地：review -> commit -> push
git status --short
git diff --check
git push origin main

# met：只做 fast-forward
ssh met.unl.edu
cd /array1/xinpeng/fungi-cazyme-PLM
git pull --ff-only
```

如果暂时不提交，只移植报告包：

```bash
cd /Users/xinpengzhang/Documents/dbcan-fungi
rsync -av --relative \
  docs/esmc_2026_integration_report_zh.md \
  docs/remote_execution_met.md \
  output/pdf/esmc_2026_integration_report_zh.pdf \
  scripts/report/render_esmc_report.py \
  scripts/remote/met_run.sh \
  met.unl.edu:/array1/xinpeng/fungi-cazyme-PLM/
```

直接 rsync 会让服务器 Git tree 变 dirty，只适合审阅和短期试验。正式计算应先 commit/push，再在服务器 `git pull --ff-only`，这样 manifest 能记录可追溯 commit。

## 5. 建立 Python 环境

```bash
ssh met.unl.edu
cd /array1/xinpeng/fungi-cazyme-PLM
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest
```

后续 ESMC 环境应单独锁定依赖，不在 base environment 里无版本安装 PyTorch/Transformers：

```bash
uv pip compile envs/embeddings.in -o envs/embeddings.lock
uv pip sync --python .venv-esmc/bin/python envs/embeddings.lock
```

在创建 `envs/embeddings.in` 前，应根据 driver 580.126.09、RTX A5500 和 Biohub 当前兼容矩阵固定 PyTorch/CUDA 版本。不要从教程的 H100 时间推断 A5500 吞吐。

## 6. 运行短任务

wrapper 默认拒绝 dirty worktree：

```bash
cd /array1/xinpeng/fungi-cazyme-PLM
./scripts/remote/met_run.sh --name tests -- \
  .venv/bin/python -m pytest

./scripts/remote/met_run.sh --name phase0-smoke --gpu 0 -- \
  .venv/bin/python -m fungi_cazyme_plm.cli smoke \
  --config tests/fixtures/config.yaml
```

输出目录：

```text
logs/remote_runs/<UTC timestamp>_<git short SHA>_<name>/
├── run.json
├── environment.txt
├── stdout.log
└── stderr.log
```

`--allow-dirty` 只允许用于明确标记的 smoke/debug run；该 run 的 `git_dirty=true`，不能晋级为 promoted scientific result。

## 7. 长任务与 tmux

```bash
ssh met.unl.edu
tmux new -s fcplm-esmc
cd /array1/xinpeng/fungi-cazyme-PLM
./scripts/remote/met_run.sh --name esmc-layer-pilot --gpu 0 -- \
  .venv-esmc/bin/python scripts/extract_embeddings/example.py \
  --config configs/models/esmc.pinned.yaml
```

- detach：`Ctrl-b d`
- 列出：`tmux ls`
- 恢复：`tmux attach -t fcplm-esmc`
- wrapper 会把 stdout/stderr 同时显示和记录。

服务器没有调度器。启动任务前运行 `nvidia-smi`，不要抢占已有进程。多个单卡实验使用不同 `--gpu`；6B 模型如果需要多 GPU，显式传 `--gpu 0,1,...` 并在 model config 记录 sharding strategy。

## 8. 正式 ESMC run 的最小检查表

- Git clean，commit 已 push。
- source snapshot pinned，输入 checksum 验证通过。
- 36 alias conflicts 已解决；正式 join 不使用 `--skip-aliases`。
- 模型使用 immutable revision，不使用 floating `main`。
- 模型卡与 license snapshot 已归档。
- `sequence_sha256`、layer、pooling、window policy、dtype 写入 model artifact manifest。
- 先运行 1k/10k throughput benchmark，再外推全库 GPU-hour 与存储。
- 全库不保存 all-layer residue states。
- run 完成后检查 `run.json` status、stdout/stderr 和产物 checksum。
- promoted run ID 写入 `project.md`，不创建 mutable `latest` symlink。

## 9. 报告的可移植性

下列文件不依赖服务器数据即可独立审阅：

- `docs/esmc_2026_integration_report_zh.md`
- `output/pdf/esmc_2026_integration_report_zh.pdf`
- `schemas/model_artifact_manifest.schema.json`
- `configs/models/esmc.example.yaml`

PDF 可在本地生成；服务器不需要安装中文字体或 PDF 工具。若需要重建，使用 `scripts/report/render_esmc_report.py` 和仓库 README 中记录的命令。

