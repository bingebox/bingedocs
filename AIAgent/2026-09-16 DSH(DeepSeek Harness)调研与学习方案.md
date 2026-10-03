# DeepSeek Harness (dsh) 调研与学习方案

> 调研日期：2026-09-16
> 调研依据：本机安装的 `@deepseek-ai/dsh@0.1.2-rc.1`（checkout: `D:\app\nvm\v24.16.0\node_modules\@deepseek-ai\dsh`）、
> `DSH_HOME`（`C:\Users\BingerLiang\.dsh`）真实配置、`plugin_check` 内置校验规则。
> 结论全部可在本机复核，附证据路径。

---

## 一、用了哪些开源框架

### 1.1 自研核心（同属 monorepo `github.com/deepseek-ai/deepseek-harness`）

| 包 | 版本 | 定位 |
|---|---|---|
| `@deepseek-ai/cordis` | 4.0.2 | **"Meta-Framework for Modern JavaScript Applications"**。TypeScript 插件框架：DI 容器（`Context`）、服务（`Service`）、生命周期（`Fiber`，dispose 时自动清理副作用/事件/服务）、事件、`inject` 声明式依赖、配置驱动加载 |
| `cordis-plugin-loader` | 1.0.3 | 运行时插件树 + Loader（把 YAML 配置变成挂载的插件树） |
| `cordis-plugin-include` / `-group` / `-hmr` / `-timer` | — | YAML include、嵌套隔离域（isolate realm）、热替换、定时器管理 |
| `@deepseek-ai/schemastery` | 3.18.x | 类型驱动 schema 校验器：轻量、**可序列化**、支持 union/intersect/transform、兼容 Standard Schema（`~standard`）。配置校验 + 工具参数 schema 的底座 |
| `@deepseek-ai/cosmokit` | 1.8.x | 通用工具库（作者 shigma 的公开库） |
| `@deepseek-ai/dsh-*` | 0.1.2-rc.1 | **约 230 个功能包，全部是 cordis 插件**（本机 `dsh\node_modules\@deepseek-ai\` 下可见全量清单） |

### 1.2 关键第三方依赖（`dsh\node_modules` 顶层可验证）

| 类别 | 依赖 | 用在哪 |
|---|---|---|
| Web 服务 | `hono`、`express` + `express-rate-limit` | `dsh-host-webserver`（"知道路由注册，不知道 harness 概念"的纯 web 插件） |
| Web GUI | `react`、`@lexical`（富文本）、`@xterm`（终端）、`@tanstack`、`@preact`、`clsx` | 浏览器客户端 UI（`dsh-client-ui-*` 约 40 个包） |
| 协议 | `@modelcontextprotocol/sdk`、`@agentclientprotocol/sdk`（Zed 的 ACP）、`dsh-sdk-protocol`（NDJSON-RPC over stdio） | MCP 桥接、自动化 ACP 服务器、进程外 SDK |
| LLM | `@earendil-works/*`（pi-ai 多 provider 生态）、`openai`、`@anthropic-ai`、`gaxios`/`google-auth-library`、`@aws-sdk` | `dsh-llm-pi-ai`（多 provider 孪生适配器）、`dsh-llm-deepseek`（原生适配器） |
| 可观测性 | `@opentelemetry` | OTLP 遥测（默认 FEEDBACK_ONLY，用户 /feedback 才上传） |
| 沙箱 | `node-addon-api`/`koffi` 原生层：`node-addon-landlock-run`（Linux Landlock）、`dsh-sandbox-windows-acl`（**Windows 受限令牌 + capability-SID 写白名单**）、`node-pty` | 文件/进程沙箱、持久终端 |
| Schema | `zod`、`ajv`、`typebox`、`zod-to-json-schema` | 客户端侧校验与互转（与 schemastery 分工） |
| 文件监听 | `chokidar` | skills 热加载、patch 热加载 |
| 其他 | `commander`（CLI）、`js-yaml`（配置）、`ws`（WebSocket）、`turndown`（HTML→MD）、`sharp`（图片） | 各处 |

---

## 二、"一切是插件"的机制拆解

### 2.1 五层结构（自底向上）

```
┌─────────────────────────────────────────────────────────────────┐
│ 5. Hub / Market：npm 包 + GitHub 直装（github:user/repo#sha）      │
│    第三方插件：dsh-email、dsh-memento、@liustack/modsearch、        │
│    @changfenhuang/dsh-genui、dshmarket、dsh-editor …              │
├─────────────────────────────────────────────────────────────────┤
│ 4. Profile：$DSH_HOME/profiles/<name> = 一个 pnpm 工程             │
│    package.json: dsh.profile.bundles = [有序 bundle 栈]           │
│    内置 profile：web / headless / acp / sdk / sdk-minimal         │
│    dsh plugin --profile X add <pkg>  → 转发 pnpm add             │
├─────────────────────────────────────────────────────────────────┤
│ 3. Patch 层（last-write-wins，按 row id 覆盖）：                   │
│    根 cordis.yml([]) ← 各 bundle 的 cordis.patch.yml              │
│    ← profile 用户层 ← $DSH_HOME/cordis.patch.yml ← --patch 叠加   │
│    补丁"整体替换"目标行 config（不深合并）；支持 !!js 运行时表达式   │
├─────────────────────────────────────────────────────────────────┤
│ 2. Row（行）：{ id, name(npm包), config?, disabled? }             │
│    整个应用 = 一份 YAML 行列表。行顺序无语义——                     │
│    激活由"服务可用性"驱动（inject 的服务齐了就挂载）               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Cordis Context：根 DI 容器。所有能力都是 ctx 上的服务或插件：    │
│    ctx.tools / ctx.llm / ctx.fs / ctx.session / ctx.skills /      │
│    ctx.sandbox / ctx.approval / ctx.settings / ctx.subagents …    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心机制逐条（证据路径）

1. **应用 = 空根 + 补丁叠加**
   - 证据：`profiles\web\cordis.yml` 内容就是 `[]`，注释写明 "Edit cordis.patch.yml, not this file"。
   - `dsh-base\cordis.patch.yml`（498 行）= base 层插入的 ~50 个 row：llm 适配器、session、存储、沙箱、审批、全部工具、命令、plan-mode 提示词、token-meter、compaction、subagent 双 provider、workflow、ralph、遥测……
   - **连系统提示词都是插件**：`system-prompt` 行（`persona` 配置）、`plan-mode` 行（整段 plan-mode 行为规则是 YAML 里的字符串）。

2. **Seam（接口包）/ 实现分离**
   - 接口包：`dsh-fs`、`dsh-llm`、`dsh-tools`、`dsh-session`、`dsh-sandbox`、`dsh-sandbox-policy`、`dsh-user-approval`、`dsh-attachment`、`dsh-storage`、`dsh-subagent`、`dsh-skill`、`dsh-settings`。
   - 实现包：`dsh-fs-local`/`dsh-fs-sandbox`、`dsh-llm-deepseek`/`dsh-llm-pi-ai`/`dsh-llm-mock-server`/`dsh-llm-replay`、`dsh-session-persistence-jsonl`/`dsh-session-query-sqlite`、`dsh-skill-filesystem`……
   - 证据：`dsh-tool-fs\package.json` 的 peerDependencies 全部指向接口包——工具只依赖 seam，不依赖实现。多平台就是这么来的：`tool-bash` 行带 `disabled: !!js process.platform === 'win32'`，Windows 上自动换成 pwsh 双生子。

3. **工具管线（`dsh-tools`）**
   - `defineTool`：类型化参数/输出 schema（schemastery DSL，16 层容器类型推断），注册进 `ctx.tools` 后 schema 自动进入提示词组装。
   - 固定执行管线：`tools/pre-execute`（allow/deny/ask 瀑布，可多插件介入）→ 单调 guard（一旦拒绝不可逆转）→ `tools/execute`（around：超时/重试）→ `tools/post-execute`（检查/替换结果）→ `finalizeContent` → `tools/result`（只读观察）。
   - 呈现模式：`native`（原生 function calling）/ `ptc`（只给 `run_code` + 生成的 TS/Python SDK）/ `both`。

4. **Skills：轻量级插件（纯 Markdown）**
   - 格式：`<name>/SKILL.md` 或扁平 `<name>.md`，YAML frontmatter（`name`/`description`/`whenToUse`/`disable-model-invocation`/`user-invocable`）。
   - 发现根按 rank：项目 `.dsh/skills`(100) → 项目 `.agents/skills`(200) → 自定义(300) → `~/.dsh/skills`(400) → `~/.agents/skills`(500) → bundled(600)。
   - chokidar 热加载：新增/改名/删除技能无需重启；正文每次加载重读（catalog 与 body 生命周期分离）。
   - 证据：`dsh-skill-filesystem\README.md` + `DSH_HOME\skills\` 目录。

5. **双半部插件（host/client dual-half）**
   - `dsh-cordis-host-runner`（host 半部沙箱生命周期）+ `dsh-cordis-client-runner`（浏览器半部：事件订阅、loader 条目）。
   - 这就是 Web GUI 里 `dsh-client-ui-*` 约 40 个 UI 插件（chat、sidebar、settings、theme、tool 卡片渲染器……）能随插件安装/卸载的机制。registry 形态的 `dsh.plugin.json` 里有 `client.main` + `client.inject` 字段与之对应。

6. **Typert：类型化远程协议**
   - `dsh-typert-protocol`（compiler-independent 反射/提供者协议）+ `dsh-typert-registry`（生成包反射 + Zod schema 的运行时注册表）+ `dsh-api-gateway`（Remote Host 分发器 + 客户端 API 端点）。
   - 效果：浏览器客户端与 host 之间是**由包反射生成的类型化 RPC**，而不是手写 API。

7. **事件溯源 + 快照回放**
   - `dsh-session` = 事件溯源会话存储（JSONL.zstd 落盘，见 `$env:DSH_SESSION_JSONL`）；`cordis.snapshot.yml` 记录启动时的精确组合树，replay 模式直接启动快照 → 会话可确定性复现（配 `dsh-llm-replay`）。

8. **热加载与故障显式化**
   - web profile `patchReload: live`：用户 patch 文件被监听，合法编辑免重启重组合；`cordis-plugin-hmr` 做代码热替换（client-plugin HMR 需要 dev watcher 配合）。
   - fail-loud：启动失败永远是一行带标签的诊断（点名失败的插件 + 阶段），`--dump-config` 可预览组合结果（带来源注释）。

9. **插件形态（`plugin_check schema` 输出的官方分类）**
   | 形态 | 特征 |
   |---|---|
   | `bundle` | npm 包 + `dsh.bundle.patch` 声明 + `cordis.patch.yml`（声明式配置层，无代码入口要求） |
   | `tool-bundle` | bundle + `src/index.ts`/tsconfig/build 产物（带代码的插件，构建纪律最严） |
   | `registry` | `dsh.plugin.json` 清单：`id`/`version`/`main`/`client.main`/`client.inject`/`engines.dsh`(semver)/`contributes.tools`/`contributes.skills` |
   | `collection` | 多插件集合 |
   | `skill` | 纯 Markdown 技能 |

10. **沙箱与审批（今天亲身踩到的）**
    - `sandbox-policy` row：`mode`（read-only / workspace-write / danger-full-access）+ `workspaceRoot`；审批策略 row 与沙箱 mode 联动（danger-full-access → never 询问）。
    - Windows 实现：`dsh-sandbox-windows-acl` = 受限令牌子进程 + capability-SID 写白名单。
    - 本机实证：`profiles\web\cordis.patch.yml` 里用户层把 `workspaceRoot` 钉到 `D:\`（给 dsh-editor 的 host 侧写文件 RPC 放行），并禁用了 `better-sidebar`。

### 2.3 设计理念小结

1. **配置即组合，代码即补丁**：bundle 本质是"静态补丁文档"（不挂服务、不发事件、无状态），产品面（web/headless/acp/sdk）= 同一启动器 + 不同 bundle 栈。核心 README 明说 "this package is not a library you import"。
2. **声明式 + 全程可审计**：`--dump-config` 输出一棵带来源注释的组合树；谁改了哪一行一目了然。
3. **服务可用性驱动激活**：row 顺序无语义，`inject` 决定挂载时机 → 天然解耦、无循环依赖焦虑。
4. **模型感知工程**：每个包 README 都有 "Model Experience" + "KV Cache effect" 章节——每个包都文档化自己如何影响模型可见的请求前缀（前缀稳定 = KV cache 命中）。这是少见的、把 LLM 推理经济学写进包约定的工程纪律。
5. **文档即接口**：统一 README 结构（Summary / Use this package / Understand the implementation(含 source map) / Further Exploration / Model Experience / Known Limitations / Dev Note），中英双语，README 之间互相交叉引用；monorepo 还有 `.agents/notes`（架构决策记录）。
6. **生态开放**：第三方插件直接作为 pnpm 依赖（含 GitHub 直装）进 profile，`dsh-plugin-check` 提供官方 lint（47 条检查规则），`dshmarket` + `.dsh-market/` 提供发现层。

---

## 三、学习方案（约 2.5 周，可压缩到 1 周核心路径）

### Phase 0 — 环境侦察（0.5 天）
**目标**：建立"看得见"的全局地图。
- 跑 `dsh --dump-config` 和 `dsh --dump-default-config`，对照阅读输出里的来源注释。
- 浏览 `C:\Users\BingerLiang\.dsh`：`profiles\web\`（package.json + cordis.yml + cordis.patch.yml + .dsh-market）、`skills\`、`settings.yaml`、`sessions\`（JSONL.zstd）、`storages\`。
- **DoD**：能徒手画出 2.1 的五层图，并说出"我现在这个 web 会话由哪 20 个 bundle 组成"。

### Phase 1 — Cordis 核心（1–2 天）
**目标**：吃透插件宿主本身。
- 读：`cordis\README.md`（Quick Start 就是最小例子）；monorepo 文档（若有访问权）`docs/tutorials/build-a-plugin.md`、`docs/guides/plugin-lifecycle.md`、`docs/guides/loader-config.md`、`docs/api/core.md`。
- 写一个玩具：一个 `Counter` Service + 一个注入它的函数式插件（照抄 README Quick Start），再手动 `dispose` 观察副作用清理。
- 理解 `Context` / `Service` / `Fiber` / `inject` / 事件四件套，以及 YAML → 插件树的 Loader。
- **DoD**：能解释 "Fiber dispose 时哪些东西会被移除"；能用 `!!js` 标签写配置表达式。

### Phase 2 — DSH 组合模型 + 动手（2–3 天）★核心
**目标**：会"组合"，而不是只会"读"。
- 读：`dsh-base\cordis.patch.yml`（注释极其详尽，逐行读）、`dsh-base\README.md`、`dsh-app-boot\README.md`（profile 章节）。
- 动手：
  1. 建自定义 profile：`package.json` 里 `dsh.profile.bundles: ["@deepseek-ai/dsh-base"]`，跑 `dsh --profile my "hello"`。
  2. 在 `my` 的 `cordis.patch.yml` 里：禁用一个 row（如 `hmr`）、整体替换一个 row 的 config（体会"不深合并"）、insert 一个新 row。
  3. 用 `--dump-config` 对比改前改后的组合树。
  4. 装一个第三方插件：`dsh plugin --profile my add dsh-email`（或任意 hub 包），观察 node_modules 与组合树变化。
- **DoD**：独立完成"改默认模型 / 换权限模式 / 增删工具"三类定制，全部只动 YAML 或装包。

### Phase 3 — Seams 与服务面（2–3 天）
**目标**：建立 `ctx.*` 地图，理解 seam/实现分离。
- 读接口包 README：`dsh-fs`、`dsh-llm`、`dsh-tools`、`dsh-session`、`dsh-sandbox`、`dsh-user-approval`、`dsh-subagent`、`dsh-skill`、`dsh-storage`、`dsh-settings`。
- 对照实现包各读一个：`dsh-fs-sandbox`（fencing 怎么做到）、`dsh-llm-pi-ai`（"dormant 挂载、settings 驱动激活"的懒激活模式）、`dsh-session-persistence-jsonl`、`dsh-skill-filesystem`。
- 读 `dsh-llm-mock-server` / `dsh-llm-replay` / `dsh-llm-retry`：测试与回放是怎么靠 seam 换实现的。
- **DoD**：画出一张 "ctx 服务 → 接口包 → 默认实现 → 可替换实现" 的表；能回答"加一个第二文件系统 provider 为什么会 fail load（双注册）"。

### Phase 4 — 工具系统：写一个自己的工具插件（1–2 天）★动手高潮
**目标**：产出第一个可安装的 dsh 插件。
- 读：`dsh-tools\README.md`（全文，尤其 pipeline 与 defineTool 示例）、`dsh-tool-fs` 的 `lib/` 结构（最小工具包长什么样）。
- 动手：按 `tool-bundle` 形态做一个插件：
  1. `src/index.ts` 里 `defineTool` 注册一个工具（如 `list_workspace`），参数用 schemastery DSL；
  2. `execute` 里走 `ctx.fs`（走 seam！不要直接 node:fs）；
  3. tsconfig/main/files 按 `plugin_check` 的 tool-bundle 检查项配置；
  4. 用 `plugin_check` 工具（action=check）跑官方 lint 直到全绿；
  5. 装进 profile，验证工具出现在模型工具列表、管线事件（pre/post-execute）能挂。
- **DoD**：`plugin_check` 0 error；工具在 web GUI 会话里可被模型调用。

### Phase 5 — Skills 与提示词层（0.5–1 天）
- 读：`dsh-skill-filesystem\README.md`（已很完整）、`dsh-system-prompt`、`dsh-plan-mode`（看 plan-mode 规则如何作为 YAML 字符串注入）、`dsh-agent-instructions`（AGENTS.md 机制）。
- 动手：在 `D:\ai\llmproxy\.dsh\skills\` 写一个 SKILL.md（frontmatter 五字段 + 正文），观察热加载进 catalog；再试 `user-invocable` / `disable-model-invocation` 两种表面开关。
- **DoD**：能说清 catalog 与 body 的双生命周期，以及 skill 与 plugin 的分工（文本指令 vs 代码能力）。

### Phase 6 — Web / 双半部（2–3 天）
- 读：`dsh-web-app`（web patch 层 + 前端 dist 服务）、`dsh-host-webserver`（纯路由注册 seam）、`dsh-client-connection`（浏览器认证 RPC）、`dsh-cordis-host-runner`/`dsh-cordis-client-runner`（双半部）、`dsh-agent-tool-presentation`（工具卡片渲染决策）。
- 动手：装/看一个 `dsh-client-ui-*` 插件（本机已有 `@changfenhuang/dsh-genui` 即 GenUI 组件），理解 `client.inject` 如何把 UI 注入会话；观察 HMR 条件（client-plugin 需要 dev watcher 同时跑）。
- **DoD**：能解释"一个 UI 插件从 npm 安装到出现在 GUI 里"的完整链路（pnpm → bundle patch → host runner → client runner → 组件挂载）。

### Phase 7 — 进阶专题（按兴趣，各 0.5–1 天）
- **typert**：`dsh-typert-protocol`/`-registry`/`dsh-api-gateway` —— 包反射生成类型化远程 API 的机制。
- **SDK/ACP/MCP**：`dsh-sdk-protocol`（NDJSON-RPC stdio）、`dsh-acp`（自动化驱动）、`dsh-mcp-client`（MCP 服务器工具桥接进 ctx.tools）。
- **子代理体系**：`dsh-subagent` seam + `spawn`/`fork` in-process provider + `dsh-workflow-worker-thread` + ralph/goal 工具行（对应 base patch 里的配置行）。
- **上下文工程**：`dsh-compaction-*`、`dsh-token-meter`、`dsh-spill-*`（大输出落盘）、`dsh-repeat-tool-reminder`、`dsh-agent-tool-presentation` —— 围绕 KV cache 稳定性的一组设计。
- **安全纵深**：`dsh-sandbox-policy`（预设联动）、`dsh-sandbox-windows-acl`（受限令牌）、`dsh-fs-observation-policy`、`dsh-user-approval`、`dsh-credentials-local`（凭证不物化进环境变量）。
- **回放**：`cordis.snapshot.yml` + `dsh-llm-replay` + `dsh-session-query-sqlite`。

### 学习资源索引（本机即可）
| 资源 | 路径 |
|---|---|
| CLI 启动器（151 行，带详尽注释） | `...\dsh\lib\bin.js` |
| base 层全量 row + 逐行注释 | `...\dsh-base\cordis.patch.yml` |
| 各包 README（中英双语、交叉引用） | `...\node_modules\@deepseek-ai\dsh\node_modules\@deepseek-ai\<pkg>\README.md` |
| 真实 profile（含第三方插件栈） | `C:\Users\BingerLiang\.dsh\profiles\web\package.json` |
| 用户层补丁（沙箱根钉扎实例） | `C:\Users\BingerLiang\.dsh\profiles\web\cordis.patch.yml` |
| 插件形态 lint（47 条规则） | `plugin_check` 工具 `action=schema` |
| 组合树预览 | `dsh --dump-config` / `--dump-default-config` |
| monorepo（文档/决策记录，访问权限待确认） | `github.com/deepseek-ai/deepseek-harness`（docs/cordis-primer.md、docs/config-catalog.md、.agents/notes/） |

### 里程碑交付物（建议）
1. `my` 自定义 profile + 3 类 YAML 定制（Phase 2）
2. 一个通过 `plugin_check` 全绿的自研 tool-bundle 插件（Phase 4）
3. 一个自研 skill（Phase 5）
4. 一篇"从 npm 到 GUI"的插件生命周期笔记（Phase 6）
5. 本文档的更新：把你验证过的细节回填到第二部分
