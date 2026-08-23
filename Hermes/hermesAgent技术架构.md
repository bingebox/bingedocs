# Hermes Agent 技术架构

## 1. 整体流程

```
用户输入 → 构建系统提示词 → 调用 LLM → LLM 决定是否调用工具 →
有工具调用？→ dispatch 执行 → 结果喂回 LLM → 继续循环
无工具调用？→ 直接返回文本回复
```

核心循环在 `run_agent.py` 和 `agent/conversation_loop.py` 中，大致是：

```python
def run_conversation():
    while iterations < max:
        a. 调用 LLM（带上系统提示词 + 对话历史 + 工具 schema）
        b. 如果 LLM 返回 tool_calls → dispatch 执行每个工具 → 结果追加到对话
        c. 如果 LLM 返回纯文本 → 直接返回
```

**关键：是 LLM 自己决定的。**

Hermes 不预先解析用户意图来选择工具。它的做法是：

1. 把所有可用工具的定义作为 JSON Schema 注入到系统提示词中 — 每个工具都有 `name`、`description`、`parameters`（schema 定义）
2. 把已加载的 skill 内容也注入到系统提示词中 — 这些 skill 的描述告诉 LLM 在什么场景下该用什么
3. MCP 服务器的工具 schema 同样注入到系统提示词中
4. LLM 看到用户输入后，根据工具描述自行判断该调用哪些工具，返回格式如：

```json
{
  "tool_calls": [
    {"name": "terminal", "arguments": {"command": "ls -la"}},
    {"name": "read_file", "arguments": {"path": "/path/to/file"}}
  ]
}
```

5. Hermes 收到这个响应后，由 `model_tools.py` 中的 **dispatch 层**负责实际执行对应工具

**不是 Hermes 代码硬编码了"收到 A 请求就调用 B 工具"的路由逻辑**，而是依靠 LLM 的语义理解能力来做路由。这也是为什么工具描述（description）写得越清晰，LLM 调用越准确。

### 错误恢复与重试机制

对话循环内置了多层容错逻辑（`agent/conversation_loop.py`）：

- **应用层重试**：`agent.api_max_retries`（默认 3 次），每次重试前等待递增时间
- **凭证池轮转**：单次凭证触发限流时，自动切换到下一凭证，无需中断用户
- **故障转移**：速率限制（429）或凭证耗尽时立即切 fallback provider；传输错误（连接失败/超时）允许 1 次重试后切换
- **上下文溢出**：413 payload-too-large 时自动压缩历史并重试；长上下文 tier 限制（如 Anthropic 429）自动降级到 200k tokens
- **中断处理**：用户中断时立即中止，清理未完成的 tool_call 序列，保存已产生的会话状态

---

## 2. 系统提示词构建

Hermes 在每次会话开始时，会构建一个系统提示词。这个提示词不是硬编码的，而是动态拼装的，主要包括：

- **基础身份** — 你是谁、能做什么
- **环境信息** — 你的操作系统、终端类型、工作目录、编码上下文
- **Memory 注入** — 从持久化记忆中加载的相关内容
- **Skills 索引** — 所有已安装技能的描述（不是全文，是描述列表）
- **工具定义** — 当前可用的 toolset 和工具 schema
- **辅助配置** — 多提供商凭证、编码工作区上下文、验证规则等

### Skill 是怎么被"知道"的？

**两个层面：**

**(a) 系统级自动加载（每次会话开始时）**

`agent/prompt_builder.py` 里的 `build_skills_system_prompt()` 函数负责扫描 `~/.hermes/skills/` 目录，读取每个技能的 `SKILL.md` 文件，把 description 和核心内容注入到系统提示词中。**注意：它注入的是 description，不是全部 SKILL.md 内容**，这样既能让 LLM 知道有哪些技能可用，又不会撑爆上下文窗口。

**(b) 会话内按需加载（通过斜杠命令）**

当需要时，`agent/skill_commands.py` 会处理每个已安装技能对应的 **斜杠命令**（如 `/learn-command`、`/humanizer` 等，注册在 `hermes_cli/commands.py` 中），把技能的完整内容作为 **user message**（而不是 system prompt）注入到对话中。**用 user message 而不是 system prompt 是为了保留 prompt caching 的好处** — prompt caching 对 system prompt 部分有效，将动态注入的内容放在 user message 中可避免缓存失效。

**Hermes 怎么知道"要加载哪个 skill"？**

- 在系统提示词中，每个技能有一个 `description` 字段
- LLM 看到系统提示词时会读到所有可用的技能描述
- 当用户输入匹配某个技能的 description 时，LLM 自行决定调用对应的斜杠命令（如 `/learn-command`）来加载技能内容
- 这不是一个规则引擎在匹配，而是 **LLM 自己理解并决定** — 类似于 function calling 的逻辑，但 skill 的"调用"是通过注入上下文实现的

### Skill 预处理与安全

技能加载前会经过 `skill_preprocessing.py` 处理：
- 安全扫描：`guard_agent_created` 防止技能注入有害指令
- 技能包（`skill_bundles.py`）：支持组合多个技能
- 外部技能目录支持（`skills.extra_skills_dirs`）
- 技能写入审批门（`skills.write_approval`）

### Skill 与工具的关系

| | Skill | Tool |
|---|---|---|
| **作用** | 告诉 LLM "怎么做"（方法论、步骤） | 让 LLM "能做什么"（实际执行能力） |
| **注入时机** | 按需加载完整内容 | 每次对话都通过 tool schemas 声明 |
| **存储** | SKILL.md 文件 | 硬编码在工具代码中 |
| **示例** | "系统化调试方法：4 阶段流程" | `terminal()`、`file()`、`search_files()` |

简单说：**Skill 是上下文增强，工具是实际执行能力**。Hermes 通过让 LLM 在系统提示词中看到技能索引，再由 LLM 自己判断何时加载技能内容，从而决定"怎么做"任务。

---

## 3. 核心对话循环

核心循环在 `agent/conversation_loop.py` 的 `AIAgent.run_conversation()` 中，大致流程是：

```
while 迭代次数 < 最大值:
    1. 调用 LLM (OpenAI 格式的消息 + 工具 schema)
    2. 如果 LLM 返回 tool_calls:
       对每个 tool_call → 执行 → 把结果追加到消息列表 → 继续循环
    3. 如果 LLM 只返回纯文本:
       返回最终回复，结束本轮
```

### 上下文压缩机制

**靠近 token 限制时自动触发上下文压缩。** 具体机制：

- `agent/context_compressor.py` 实现有损摘要压缩
- `agent/context_engine.py` 支持插件化引擎（默认 `compressor`，也可配置为 `lcm` 等）
- 由 `compression.enabled` 控制，可被用户手动关闭
- 压缩阈值由 `compression.threshold` 控制（默认 0.50），目标保留比例 `compression.target_ratio`（默认 0.20）
- 关闭后遇到 context overflow 会报错并提示用户手动压缩（`/compress`）或新开会话（`/new`），不会静默压缩
- 错误分类（`agent/error_classifier.py`）识别 6+ 种错误类型：`rate_limit`、`billing`、`timeout`、`overloaded`、`context_overflow`、`payload_too_large`、`long_context_tier` 等，并触发不同恢复策略

### 工具搜索（渐进披露）

当 LLM 连接了大量 MCP 服务器或插件工具时，工具 schema 会消耗大量上下文窗口。`tools/tool_search.py` 提供渐进披露机制：
- 可延迟工具 schemas 超过模型上下文 `threshold_pct`（默认 10%）时自动激活
- 用三个桥接工具（`tool_search` / `tool_describe` / `tool_call`）替代工具数组
- 核心 Hermes 工具（terminal、read_file、write_file 等）**永不延迟**
- 由 `tools.tool_search.enabled` 控制（`auto` / `on` / `off`）

### LLM 什么时候直接回复？
- 当 LLM 认为用户的问题不需要调用任何工具时（比如纯问答、闲聊）
- 它会返回纯文本，Hermes 直接返回给用户

### LLM 什么时候调用工具？
- 当 LLM 判断需要执行某个操作（文件操作、终端命令、搜索等）
- 它会返回 `tool_calls` 列表，Hermes 执行后把结果返回给 LLM
- LLM 再根据工具执行结果继续生成回复（可能需要多轮）

---

## 4. 工具系统

### 工具（Toolsets）
- 定义在 `toolsets.py` 中，每个工具文件注册到 `tools/registry.py`
- 通过 `registry.register(name=..., schema=..., handler=..., check_fn=...)` 注册
- 工具描述（description）就是 LLM 判断的依据
- 用户可以在 `hermes tools` 中启用/禁用某些工具集
- **Auto-discovery**：任何 `tools/*.py` 文件与顶层 `registry.register()` 调用自动导入 — 不需要手动列表
- 所有 handler 必须返回 JSON 字符串
- 工具集变更在 `/reset` 后生效以保持提示缓存（mid-conversation 不变，因为要保持 prompt caching）

### 工具执行与安全护栏
- `agent/tool_executor.py` — 工具执行核心，协调 handler 调用
- `agent/tool_guardrails.py` — 工具执行安全护栏，约束危险操作
- `agent/tool_result_classification.py` — 工具结果分类（区分成功/失败/截断）
- 安全扫描：`security.tirith_enabled` 启用 tirith 预执行扫描；`security.redact_secrets` 自动脱敏输出；`security.allow_private_urls` 控制内网 IP 访问；`website_blocklist` 域名黑名单

### Skill
- 通过斜杠命令触发按需加载
- Skill 本身不是"被调用的工具"，而是**给 LLM 的额外上下文指导**，告诉它某个场景的最佳实践
- 支持外部技能目录、安全扫描、写入审批等高级特性

### MCP 服务器
- MCP 工具通过 `hermes mcp add` 或 config.yaml 配置
- MCP 服务器注册的工具 schema 同样被注入到系统提示词
- LLM 看到它们和普通工具没有区别，按需调用

### Plugin
- Plugin 本质上是额外的工具/技能来源，注册方式跟工具一样
- 平台适配器（`gateway/platforms/`）和 cron 提供商（`cron/providers/`）也通过插件机制扩展

---

## 5. 持久化层

- **SQLite + FTS5** 存储会话和对话历史
- 技能（skills）和记忆（memory）跨会话持久化
- 会话存储在 `~/.hermes/state.db`
- 配置在 `~/.hermes/config.yaml`，密钥在 `~/.hermes/.env`
- 日志在 `~/.hermes/logs/`（agent.log 记录 INFO+，errors.log 记录 WARNING+）

### 会话管理
- `sessions.auto_prune`：自动修剪已结束会话（默认关闭）
- `sessions.retention_days`：保留天数（默认 90 天）
- `sessions.vacuum_after_prune`：修剪后执行 VACUUM 回收磁盘空间
- `sessions.max_live_sessions`：内存中 TUI 会话软上限
- `sessions.write_json_snapshots`：JSON 快照写入（默认关闭）

---

## 6. 网关层（Gateway）

### 平台支持
同一 Agent 可运行在多个平台上，每个平台有独立适配器，工具能力完整保留。实际支持的平台通过 `plugins/platforms/` 目录扩展：

**内置平台**（`gateway/platforms/` + `plugins/platforms/`）：
- Telegram、Discord、Slack、WhatsApp、Teams、钉钉 (DingTalk)、飞书 (Feishu)、微信 (WeCom)
- Email、SMS、Matrix、Mattermost、IRC、LINE
- Home Assistant、Google Chat、NTFY、Photon、Raft、Simplex
- API Server（OpenAI 兼容接口）

**20+ 平台目录**（`plugins/platforms/`）：
dingtalk, discord, email, feishu, google_chat, homeassistant, irc, line, matrix, mattermost, ntfy, photon, raft, simplex, slack, sms, teams, telegram, wecom, whatsapp

### 网关特性
- **Token 级流式输出**：`streaming.enabled` 控制 Telegram/Discord/Slack 的渐进式消息更新（draft 模式或 edit 模式）
- **媒体交付**：`gateway.strict` / `gateway.max_inbound_media_bytes` 控制文件上传/下载的安全策略
- **Scale-to-Zero**：网关空闲时自动休眠，由 NAS/Portal 唤醒
- **消息时间戳**：`gateway.message_timestamps.enabled` 在模型上下文中注入用户消息发送时间
- **会话编排**：`gateway.session` 管理跨平台会话关联

---

## 7. 后台系统

- **`delegate_task`**：子 Agent 委派（隔离上下文和终端），支持并行 batch 执行（最多 3 个并发子代理），非 durable — 如果父进程被中断，子进程也会被取消
- **`cronjob`**：持久化定时任务调度器，支持 duration（`"30m"`, `"2h"`）、"every" 短语（`"every monday 9am"`）、5 字段 cron（`"0 9 * * *"`）或 ISO 时间戳。支持 provider 切换（内置 ticker 或 NAS Chronos）、并行执行控制、连续输出文件保留（默认 50）
- **`kanban`**：多 Agent 协作看板，持久化 SQLite 看板。包含自动分派器、任务分解、失败自动重分配、心跳超时检测等
- **`curator`**：技能生命周期管理（追踪使用、标记闲置技能过时、归档过时技能、合并冗余技能）

---

## 8. 模型路由与提供商无关

- **支持 20+ LLM 提供商**（OpenRouter、Anthropic、OpenAI、DeepSeek、Nous、Azure、Bedrock、Gemini 等），可在工作中途切换
- **凭据池自动轮转**：配置多个 API Key，触发限流时自动切换到下一凭证
- **故障转移链**：`fallback_providers` 配置多提供商故障转移优先级
- **辅助模型**（vision、压缩、搜索、TTS/STT 等）可独立配置提供商和模型
- **提供商设置**通过 `hermes model` 或 `hermes setup`
- **模型目录**：`model_catalog` 从远程拉取模型列表缓存，支持 OpenRouter 和 Nous Portal 的实时更新

---

## 9. 项目结构

```
hermes-agent/
├── run_agent.py          # AIAgent — 核心对话循环入口
├── model_tools.py        # 工具发现与分发
├── toolsets.py           # 工具集定义
├── cli.py                # 交互式 CLI (HermesCLI)
├── hermes_state.py       # SQLite 会话存储
├── hermes_bootstrap.py   # 初始化逻辑（加载配置、设置环境）
├── hermes_logging.py     # 日志系统
├── hermes_constants.py   # 全局常量
├── hermes_time.py        # 时间处理
├── hermes_cli.py         # CLI 入口
├── trajectory_compressor.py  # 上下文压缩
├── toolset_distributions.py  # 工具集分发
├── batch_runner.py       # 批量执行器
├── mini_swe_runner.py    # SWE-bench 迷你 runner
├── agent/                # 核心推理引擎（105+ 文件，见下方详解）
├── tools/                # 工具实现（91 个文件）
│   └── registry.py       # 中央工具注册中心
├── gateway/              # 消息网关 + 平台适配器
│   ├── platforms/        # 平台适配器子目录
│   ├── builtin_hooks/    # 网关内置钩子
│   └── relay/            # 中继传输
├── cron/                 # 定时任务调度
├── hermes_cli/           # CLI 子命令（config, skill, cron, memory 等）
│   ├── commands.py       # Slash 命令注册表 (CommandDef)
│   ├── config.py         # DEFAULT_CONFIG, 环境变量定义
│   └── main.py           # CLI 入口点和 argparse
├── providers/            # LLM 提供商适配器（20+ 提供商支持）
├── transports/           # ACP/WSL 传输层
├── secret_sources/       # 凭证来源模块
├── tui_gateway/          # TUI 终端网关
├── ui-tui/               # 终端 UI 界面
├── web/                  # 网页/Web 相关能力
├── mcp_serve.py          # MCP 服务器端
├── acp_adapter/          # ACP（Agent Communication Protocol）适配器
├── acp_registry/         # ACP 注册中心
├── skills/               # 技能模块
├── plugins/              # 插件系统
│   ├── platforms/        # 平台插件（20+ 目录）
│   └── cron_providers/   # Cron 提供商插件
├── locales/              # 多语言本地化
├── tests/                # ~3000 pytest 测试
├── packaging/            # 打包相关
├── docs/                 # 文档源码
└── website/              # Docusaurus 文档站
```

---

## 10. 核心代码模块/组件

根据源码目录结构，Hermes Agent 的核心代码模块/组件有 **26+ 个 Python 模块/包 + 91 个独立工具文件**。按功能分组如下：

### 核心运行时（根目录文件）

| 模块 | 职责 |
|---|---|
| `run_agent.py` | 核心对话循环（构建提示 → 调用 LLM → 处理工具调用） |
| `hermes_bootstrap.py` | 初始化逻辑（加载配置、设置环境） |
| `model_tools.py` | 工具发现、注册与分发 |
| `hermes_state.py` | SQLite 会话存储（FTS5 全文搜索） |
| `hermes_logging.py` | 日志系统 |
| `hermes_constants.py` | 全局常量 |
| `hermes_time.py` | 时间处理 |
| `hermes_cli.py` | CLI 入口 |
| `trajectory_compressor.py` | 上下文压缩 |
| `toolsets.py` | 工具集管理 |
| `toolset_distributions.py` | 工具集分发 |
| `batch_runner.py` | 批量执行器 |
| `mini_swe_runner.py` | SWE-bench 测试 runner |

### 包（package）模块

| 包 | 职责 |
|---|---|
| `agent/` (105+ 文件) | 核心推理引擎：多提供商适配器（Anthropic/Codex/Bedrock/Azure）、提示构建与缓存、记忆管理（含外部 provider 工具注入）、上下文压缩、错误分类与恢复、工具执行与安全护栏、凭证池轮转、MoA 循环、STT/TTS/图像/视频/搜索能力 |
| `tools/` (91 个文件) | 工具实现（terminal, file, web, browser, search, memory, cronjob, delegate, browser, clarify, code_execution, computer_use, discord, feishu_doc 等） |
| `gateway/` | 网关系统 + 平台适配器（Telegram, Discord, Slack 等），含 hook、中继、认证 |
| `cron/` | 定时任务调度器 |
| `hermes_cli/` | CLI 子命令（config, skill, cron, memory, doctor 等） |
| `providers/` | LLM 提供商适配器（20+ 提供商支持） |
| `transports/` | ACP/WSL 传输层 |
| `tui_gateway/` | TUI 终端网关 |
| `ui-tui/` | 终端 UI 界面 |
| `web/` | 网页/Web 相关能力 |
| `mcp_serve.py` | MCP 服务器端 |
| `acp_adapter/` | ACP（Agent Communication Protocol）适配器 |
| `acp_registry/` | ACP 注册中心 |
| `skills/` | 技能模块 |
| `plugins/` | 插件系统（平台、cron 提供商等） |
| `locales/` | 多语言本地化 |

### 基础设施（包）

| 包 | 职责 |
|---|---|
| `tests/` | 测试套件 |
| `packaging/` | 打包相关 |
| `docs/` | 文档源码 |

**总计：约 26 个核心 Python 模块/包 + 91 个独立工具文件。**

---

## 11. Agent Loop 高层次概览

```
run_conversation():
  1. Build system prompt (identity + env + memory + skills + tools)
  2. Loop while iterations < max:
     a. Call LLM (OpenAI-format messages + tool schemas)
     b. If tool_calls → dispatch each → append results → continue
     c. If text response → return
     d. If error → classify → retry/fallback/compact → retry
  3. Context compression triggers automatically near token limit
     (configurable via compression.enabled/threshold/target_ratio)
```

---

## 12. 关键配置

- 配置文件：`~/.hermes/config.yaml`（设置）、`~/.hermes/.env`（API 密钥）
- 会话存储：`~/.hermes/state.db`（SQLite + FTS5）
- 日志：`~/.hermes/logs/agent.log`（INFO+）、`errors.log`（WARNING+）
- 凭据池：`~/.hermes/auth.json`
- 源码：`~/.hermes/hermes-agent/`
- Profile 使用 `~/.hermes/profiles/<name>/` 具有相同布局

### Config 完整关键段

以下列出 `hermes_cli/config.py` 中 `DEFAULT_CONFIG` 字典的所有顶级 section 及其关键选项：

| Section | Key options（节选） |
|---------|---------------------|
| `providers` | 多提供商定义与凭证（可配置多个） |
| `fallback_providers` | 故障转移提供商链 |
| `credential_pool_strategies` | API Key 池轮转策略 |
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length` |
| `agent` | `max_turns` (90), `tool_use_enforcement`, `api_max_retries` (3), `intent_ack_continuation`, `task_completion_guidance`, `parallel_tool_call_guidance`, `environment_probe`, `coding_context`, `verify_on_stop`, `clarify_timeout` (3600s), `gateway_notify_interval`, `image_input_mode` |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout` (180), `daemon_term_grace_seconds`, `container_*` (Docker/Singularity/Modal 资源限制) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `context` | `engine` (compressor/lcm 等插件) |
| `display` | `skin`, `tool_progress`, `show_reasoning`, `show_cost` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral/elevenlabs), 子配置含模型/语言 |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts) |
| `voice` | `record_key` (ctrl+b), `max_recording_seconds` (120), `auto_tts`, `beep_enabled`, `silence_threshold`, `silence_duration` |
| `memory` | `memory_enabled` (True), `user_profile_enabled` (True), `write_approval` (False), `memory_char_limit` (2200), `user_char_limit` (1375), `provider` (外部 provider) |
| `security` | `allow_private_urls` (False), `redact_secrets` (True), `tirith_enabled` (True), `tirith_path`, `tirith_timeout` (5), `tirith_fail_open` (True), `website_blocklist.enabled`, `acked_advisories`, `allow_lazy_installs` (True) |
| `delegation` | `model`, `provider`, `base_url`, `api_key`, `api_mode`, `inherit_mcp_toolsets` (True), `max_iterations` (50), `child_timeout_seconds`, `reasoning_effort`, `max_concurrent_children` (3), `max_async_children` (3), `max_spawn_depth` (1), `orchestrator_enabled` (True) |
| `goals` | `max_turns` (20) — MoA judge 驱动的自动继续循环 |
| `moa` | Mixture of Agents 预置（聚合器 + 参考模型） |
| `skills` | `extra_skills_dirs`, `inline_shell`, `guard_agent_created`, `write_approval` |
| `curator` | `enabled`, `interval_hours`, `stale_after_days`, `archive_after_days`, `consolidate`, `prune_builtins`, `backup` |
| `cron` | `provider` (内置/chronos), `chronos.*`, `wrap_response` (True), `mirror_delivery` (False), `max_parallel_jobs`, `output_retention` (50) |
| `kanban` | `dispatch_in_gateway` (True), `dispatch_interval_seconds` (60), `failure_limit` (2), `auto_decompose` (True), `dispatch_stale_timeout_seconds` (14400), 等 |
| `checkpoints` | `enabled`, `max_snapshots` (50) |
| `code_execution` | `mode` (project/strict) |
| `tools.tool_search` | `enabled` (auto), `threshold_pct` (10), `search_default_limit` (5), `max_search_limit` (20) |
| `logging` | `level` (INFO), `max_size_mb` (5), `backup_count` (3) |
| `model_catalog` | `enabled` (True), `url`, `ttl_hours` (1) |
| `network` | `force_ipv4` (False) |
| `gateway` | `streaming.enabled` (False), `streaming.transport` (auto), `message_timestamps`, `max_inbound_media_bytes` (128MiB), `strict`, `media_delivery_allow_dirs`, `trust_recent_files`, `api_server.max_concurrent_runs` (10) |
| `sessions` | `auto_prune` (False), `retention_days` (90), `vacuum_after_prune` (True), `min_interval_hours` (24) |
| `human_delay` | `mode` (off), `min_ms` (800), `max_ms` (2500) |
| `toolsets` | 默认工具集配置 |
| `max_concurrent_sessions` | 全局并发会话上限 |
| `max_live_sessions` | 内存中 TUI 会话软上限 |

---

## 13. 补充：运行时核心机制

### 凭证安全与轮转
- `agent/credential_pool.py` — 多 API Key 自动轮转
- `agent/credential_sources.py` — 多来源凭证读取（文件/环境变量/云存储）
- `agent/credential_persistence.py` — 凭证持久化
- `agent/secret_scope.py` — 作用域隔离（不同任务看到不同凭证子集）
- `agent/nous_rate_guard.py` — Nous 提供商速率守卫

### 多提供商适配器
- `agent/anthropic_adapter.py` — Anthropic API 适配
- `agent/codex_responses_adapter.py` — Codex CLI 适配器
- `agent/bedrock_adapter.py` — AWS Bedrock 适配
- `agent/azure_identity_adapter.py` — Azure 身份适配
- `agent/gemini_native_adapter.py` — Google Gemini 原生适配
- `agent/gemini_schema.py` — Gemini Schema 处理
- `agent/moonshot_schema.py` — Moonshot Schema 处理

### 编码与上下文管理
- `agent/coding_context.py` — 编码工作区上下文注入（AGENTS.md/CLAUDE.md/.cursorrules）
- `agent/context_compressor.py` — 有损摘要压缩
- `agent/context_engine.py` — 插件化上下文引擎
- `agent/conversation_compression.py` — 对话级压缩
- `agent/prompt_caching.py` — Prompt 缓存管理（Gemini/Anthropic/Claude 各适配）
- `agent/trajectory.py` — 轨迹管理

### MoA（Mixture of Agents）
- `agent/moa_loop.py` — 聚合器与参考模型并行生成
- 聚合器综合参考输出后决策
- `goals` 配置 judge 驱动的自动继续循环

### 流式输出
- `streaming.enabled` — Telegram/Discord/Slack 的 token 级流式消息更新
- `streaming.transport` — 传输模式（auto/draft/edit/off）
- `streaming.buffer_threshold` — 缓冲区字符阈值
- `streaming.cursor` — 光标符号
