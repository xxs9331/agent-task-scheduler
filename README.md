# Codex Team

[English](README_EN.md) | 中文

Codex Team 是一个面向 Codex 的通用团队与项目级任务调度插件。它包含可自动引导安装的
Skill 和 Python CLI，并将每个项目的配置、状态、锁、发布历史及可选观测日志保存在
项目内部，避免不同项目互相污染。

## 功能

- 初始化项目级调度器，无需在线下载 Python 包。
- 发布、原子权限校验、带 fencing token 的领取、续租、继续和完成任务。
- 诊断路由、过期 lease、迁移和兼容性问题。
- 隔离不同项目的状态、历史记录和锁。
- 使用 `codex-team` 在任意项目初始化、诊断和启动全新的通用团队，并核对原生角色身份、连续性和收尾状态。

## 可移植 Codex Team

跨电脑首次使用只需要安装本插件；插件本身没有也不声称存在 post-install hook。重启
Codex 后，在任意项目中对它说“安装 codex-team 并初始化团队模式”。Skill 会从自己的
相对 `scripts/install_codex_team.py` 运行内置安装器，无需 clone、复制文件或定位插件
缓存。安装器仅用内置 0.3.8 wheel 创建用户级隔离环境和受管理的 launcher，输出 JSON
receipt；它绝不改写 PATH、bashrc 或 PowerShell profile。若 receipt 提示 bin 不在 PATH，
只在当前 shell 执行其一次性提示即可。安装后先运行 `type -a codex-team`：若受管理的
launcher 前出现旧 shell function 或 alias，请在当前 shell unset，并手动删除 shell profile
里的旧 block；安装器绝不会改写 profile。静态 `multi_agent` feature 状态不能证明 native
custom-agent runtime attestation。fresh root 必须从父级可见的原生证据核对请求的 agent
type、spawn agent/thread id 以及固定 model/reasoning 合同，再通过 `send_input` 把
attestation 发送到同一个 `product_manager` 线程。子线程不需要、也不应伪造仅父级可见
的字段；真正缺少父级证据时仍然 fail closed。

所有项目共用 `codex-team` 内置的唯一最新团队配置和 Skill。`doctor`
要求受管理配置与当前模板完全等价；`init` 会将不同的旧配置和旧 Skill
事务性更新到 0.3.8。升级成功后，项目只保留 `.agents/skills/codex-team`，并移除旧的
`.agents/skills/global-scheduler` 和 `.agents/skills/codex-team-staff`。裸 `codex-team`/`start` 会先自动执行这个更新，成功后才
启动 Codex；更新失败则回滚受管理配置和 Skill，且不启动 Codex。

然后在目标项目目录运行：

```bash
codex-team init
codex-team doctor
codex-team start
```

所有命令默认当前目录；也可以显式给出含空格的项目路径：

```bash
codex-team init "/work/my project"
codex-team role-A "/work/my project"
```

`init` 只管理项目本地 `.codex/`、`.agents/skills/` 和 scheduler bootstrap；它会在
receipt 中分开报告 `created`、`updated` 和 Skill 版本迁移。`doctor` 只验证静态
文件，不能证明运行时 native identity。`start` 在自动升级和 doctor 通过后
调用 `codex -C <目标项目>`，要求新建
`product_manager`（`fork_turns=none`）而不继承历史。`role-A/B/C/D/R` 分别映射到
`window_a/window_b/window_c/window_d/researcher`，其 scheduler worker id 为小写
`role-a...role-r`。

## Skill 是什么

Codex Team Skill 是 Codex 使用团队和调度器时的可复用操作手册。它不保存任务数据，
也不代替 Scheduler CLI；它负责让 Codex 在正确的项目边界内调用 CLI，并遵守初始化、
发布、领取、续租、完成、故障恢复和迁移检查等契约。

以下请求会触发或适合使用这个 Skill：

- “使用 Codex Team 初始化当前项目。”
- “发布这一批 A/B/C/D/R 任务，并检查依赖和并行关系。”
- “检查为什么任务无法 claim，是否存在有效 lease。”
- “执行 release-expired，恢复已关闭窗口遗留的任务。”
- “先 dry-run 检查旧任务池是否可以迁移。”

典型流程是：Codex 读取 Skill → 定位当前项目配置 → 调用项目内的 `scheduler` CLI →
根据 JSON receipt 判断成功、重试或停止。worker roster 通过 `staff-sync` 写入项目状态，
`claim` 在同一锁事务内复核 worker、任务 kind、required worker、依赖和写范围冲突；
Skill 明确禁止跨项目复用状态、直接编辑状态
JSON、静默迁移 legacy 数据，以及在等待 gate 时长期占用任务 lease。

0.2.1 明确新旧边界：新 `publish` 的每个 create task 必须包含非空的
`metadata.team_mode.kind`，否则整批原子拒绝；升级前已存在且缺少 kind 的任务仍按
`unclassified` 兼容，由项目审计工具告警。

从 0.2.0 起，`claim` 返回唯一 `lease_id`；`heartbeat`、`complete`、`block`、`fail`
和 `retry` 必须回传该 token。`complete --summary` 为必填，父代理应在子线程结束后重新
`describe`，只把持久 `done`、summary、receipt 和任务验证证据同时成立视为完成。
`--agent-id` 只是调用者写入 lease 的关联字段，不证明 Codex 已加载 custom-agent TOML。

复杂任务拆分可以从随插件安装的
[《任务计划书模板》](skills/codex-team/assets/任务计划书模板.md)开始。模板包含调研、
批次、并行节点、R gate、任务合并和最终验收结构；gate 不单独算作执行批次。

## 从 Codex 自定义市场安装

插件安装名仍为 `global-scheduler` 以保持兼容；安装后展示和项目内使用的核心
Skill 名称是 Codex Team。

```bash
codex plugin marketplace add xxs9331/agent-task-scheduler --ref main
codex plugin add global-scheduler@xxs9331-scheduler
```

重启 Codex 后，在目标项目中输入：

```text
使用 Codex Team 初始化当前项目。
```

Skill 会安装仓库内置的 wheel、创建项目配置并执行 smoke check。只有运行 Codex 的
用户需要安装插件；A/B/C/D/R 等执行角色在同一项目和 Codex 环境中使用它，无需各自
重复安装。首次需要 `codex-team` 时，改为让 Skill 运行其相对用户安装器；插件安装
不会自动执行该代码。

> 当前支持从本仓库这个自定义市场安装，但尚未收录到 OpenAI 默认 Codex 市场，
> 因此暂时不能只在默认市场中搜索名称完成安装。

## 本地安装

也可以将整个 Skill 目录复制到目标项目：

```bash
mkdir -p .agents/skills
cp -R /path/to/agent-task-scheduler/skills/codex-team .agents/skills/codex-team
```

## 仓库内容

- `.agents/plugins/marketplace.json`：Codex 自定义市场清单。
- `.codex-plugin/plugin.json`：插件发现及展示元数据。
- `skills/codex-team/SKILL.md`：团队启动、角色身份与调度器操作流程。
- `skills/codex-team/scripts/install.py`：离线项目初始化程序。
- `skills/codex-team/scripts/install_codex_team.py`：从内置 wheel 安全安装用户级
  `codex-team` launcher 的一次性程序。
- `skills/codex-team/assets/`：经过验证的内置 wheel。
- `skills/codex-team/assets/任务计划书模板.md`：可直接复用的中文任务计划模板。
- `skills/codex-team/references/`：契约、错误、迁移和平台边界。
- `tests/`、`evals/`：实现测试、插件基础设施测试和触发用例。

## 验证

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/codex-team/scripts
```

安全、隐私和版本记录见 `SECURITY.md`、`PRIVACY.md` 和 `CHANGELOG.md`。
