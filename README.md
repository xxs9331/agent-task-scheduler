# Global Scheduler

[English](README_EN.md) | 中文

Global Scheduler 是一个面向 Codex 的项目级任务调度插件。它包含可自动引导安装的
Skill 和 Python CLI，并将每个项目的配置、状态、锁、发布历史及可选观测日志保存在
项目内部，避免不同项目互相污染。

## 功能

- 初始化项目级调度器，无需在线下载 Python 包。
- 发布、领取、续租、继续和完成任务。
- 诊断路由、过期 lease、迁移和兼容性问题。
- 隔离不同项目的状态、历史记录和锁。

## 从 Codex 自定义市场安装

```bash
codex plugin marketplace add xxs9331/agent-task-scheduler --ref main
codex plugin add global-scheduler@xxs9331-scheduler
```

重启 Codex 后，在目标项目中输入：

```text
使用 global-scheduler 初始化当前项目。
```

Skill 会安装仓库内置的 wheel、创建项目配置并执行 smoke check。只有运行 Codex 的
用户需要安装插件；A/B/C/D/R 等执行角色在同一项目和 Codex 环境中使用它，无需各自
重复安装。

> 当前支持从本仓库这个自定义市场安装，但尚未收录到 OpenAI 默认 Codex 市场，
> 因此暂时不能只在默认市场中搜索名称完成安装。

## 本地安装

也可以将整个 Skill 目录复制到目标项目：

```bash
mkdir -p .agents/skills
cp -R /path/to/agent-task-scheduler/skills/global-scheduler .agents/skills/
```

## 仓库内容

- `.agents/plugins/marketplace.json`：Codex 自定义市场清单。
- `.codex-plugin/plugin.json`：插件发现及展示元数据。
- `skills/global-scheduler/SKILL.md`：触发规则与操作流程。
- `skills/global-scheduler/scripts/install.py`：离线项目初始化程序。
- `skills/global-scheduler/assets/`：经过验证的内置 wheel。
- `skills/global-scheduler/references/`：契约、错误、迁移和平台边界。
- `tests/`、`evals/`：实现测试、插件基础设施测试和触发用例。

## 验证

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/global-scheduler/scripts/install.py
```

安全、隐私和版本记录见 `SECURITY.md`、`PRIVACY.md` 和 `CHANGELOG.md`。
