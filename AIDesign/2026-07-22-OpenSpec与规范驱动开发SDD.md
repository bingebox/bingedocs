---
tags: 工作日记
星期:  星期三
---
# OpenSpec与规范驱动开发SDD

## 1. 前言

OpenSpec 是一个面向 AI 编程助手的「规范驱动开发（Spec-Driven Development）」框架：在让 AI 写代码之前，先在仓库里生成并维护一套"规范+变更"文档，作为系统意图的唯一真相来源，从而减少"需求在聊天记录里、改了啥不知道"的问题。

**官网：** [https://openspec.dev](https://openspec.dev)
**GitHub：** [https://github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)

## 2. OpenSpec是什么

OpenSpec 是一套**规范驱动开发（SDD）**的工具链和方法论，由 Fission AI 开源。它的核心理念可以用一句话概括：

> **Specs = what is true. Changes = what should change.**

在传统的 AI 编程中，需求讨论散落在聊天记录中，代码修改缺乏上下文追溯。OpenSpec 通过强制在编码前撰写结构化的规范文档（specs），将"要构建什么"和"已经构建了什么"明确分离，让 AI 辅助编程有据可循。

OpenSpec 不是代码生成工具，也不是项目管理工具。它是一个**意图对齐框架**——在人和 AI 之间建立共同的语言，确保双方在动手写代码前对"做什么"达成共识。

### 核心概念

- **Specs（规范）**：描述系统**当前**的行为，是系统的"真相来源"。每个 spec 定义了某个功能领域的可观察行为，包括输入、输出和错误条件。
- **Changes（变更）**：对系统的**提议修改**，住在独立的文件夹中，直到被合并。变更在完成归档后，其差异（delta）会合并到主 specs 中。
- **Delta（差异）**：变更对规范造成的增删改，使用 `ADDED`、`MODIFIED`、`REMOVED` 标记，而非重写整个文件。

### 关键区分：Spec 与 Design

| 维度 | Spec（规范） | Design（设计） |
|------|-------------|---------------|
| 关注点 | **可观察行为** | **实现方式** |
| 内容 | 输入、输出、错误条件 | 架构决策、文件变更、技术选型 |
| 何时写入 | 变更影响外部行为时 | 内部重构、架构调整 |
| 修改频率 | 较低（行为不变则不修改） | 较高（实现过程中频繁调整） |

简而言之：如果变更不改变系统的外部可观察行为，它应该进入 Design 而非 Spec。

## 3. OpenSpec解决什么问题

### 问题 1：需求在聊天记录里迷失

传统 AI 编程中，需求讨论散落在对话历史中。AI 助手在后续对话中可能忘记上下文，导致功能漂移或遗漏。

**OpenSpec 的解法：** 所有需求先写进规范的 `proposal.md` 和 `spec.md`，成为持久化的、可查阅的文档。

### 问题 2：改了啥不知道

多人协作或长时间开发后，很难回溯"这个功能上次改了什么"。PR 描述往往过于笼统。

**OpenSpec 的解法：** 每个变更都有完整的 `proposal.md`（意图和范围）、`design.md`（技术设计）、`tasks.md`（任务清单）、`specs/`（规范差异），形成完整的审计链。

### 问题 3：并行开发冲突

多个开发者同时修改同一模块时，规范文档容易产生命令行级别的冲突。

**OpenSpec 的解法：** 每个变更在独立的文件夹中工作，互不干扰。归档时差异合并，避免了直接修改主 specs 带来的冲突。

### 问题 4：AI 助手缺乏上下文

AI 编程助手在长对话中容易遗忘早期约定。

**OpenSpec 的解法：** 通过 `/opsx:explore` 等命令，AI 助手会读取规范文档作为上下文的"真相来源"，确保实现与规范一致。

## 4. OpenSpec目录结构

### 4.1 单仓库标准结构

```
openspec/
├── specs/                          # 当前系统真相
│   ├── auth/
│   │   └── spec.md                 # 认证行为规范
│   ├── payments/
│   │   └── spec.md                 # 支付处理规范
│   ├── checkout/
│   │   └── spec.md                 # 结账流程规范
│   └── openspec-conventions/
│       └── spec.md                 # OpenSpec 自身约定
├── changes/                        # 提议中的变更
│   └── add-oauth/
│       ├── proposal.md             # 1. 意图和范围（先读这个）
│       ├── design.md               # 2. 技术设计（可选）
│       ├── tasks.md                # 3. 任务清单
│       └── specs/                  # 规范差异（delta）
│           ├── auth/spec.md        # 对 auth 规范的修改
│           └── checkout/spec.md    # 对 checkout 规范的修改
└── config.yaml                     # 项目配置
```

### 4.2 规范文件内部结构

```markdown
## CURRENT Requirements            # 当前已有需求（保持不变）
### Requirement: 登录功能
用户通过邮箱和密码登录系统。

#### Scenario: 正确凭据登录
- **WHEN** 用户输入有效邮箱和密码
- **THEN** 系统返回 JWT token
- **AND** 重定向到首页

## ADDED Requirements              # 本次变更新增的需求
### Requirement: OAuth 登录
用户可以通过 Google、GitHub 等第三方 OAuth 提供商登录。

#### Scenario: Google OAuth 登录
- **WHEN** 用户点击"Google 登录"并成功授权
- **THEN** 系统创建或关联本地用户账户
- **AND** 返回 JWT token

## MODIFIED Requirements           # 本次变更修改的需求
（无）

## REMOVED Requirements            # 本次变更移除的需求
（无）
```

### 4.3 变更文件结构

```
openspec/changes/add-oauth/
├── .openspec.yaml                  # 变更配置（关联倡议、链接其他项目）
├── proposal.md                     # 意图、范围、背景
├── design.md                       # 技术设计（大型变更需要）
├── tasks.md                        # 可执行任务清单
└── specs/                          # 规范差异
    ├── auth/spec.md                # 认证规范变更
    └── checkout/spec.md            # 结账规范变更
```

### 4.4 多仓库（Monorepo）适配

**嵌套结构：**
```
repo/
└── openspec/
    ├── specs/
    │   ├── contracts/
    │   │   └── checkout/spec.md
    │   ├── billing/
    │   │   └── spec.md
    │   └── checkout/
    │       ├── web/spec.md
    │       ├── ios/spec.md
    │       └── android/spec.md
    └── changes/
        └── add-3ds/
            ├── proposal.md
            └── specs/
                ├── contracts/checkout/spec.md
                ├── checkout/web/spec.md
                └── checkout/ios/spec.md
```

**分布式结构：** 每个服务有自己的 `openspec/`，根目录管理跨切面规范。

## 5. 使用OpenSpec开发的主流工作流

### 5.1 完整生命周期

```text
1. 探索阶段          /opsx:explore              ← AI 帮你研究问题和方案
2. 提议阶段          /opsx:propose add-oauth    ← AI 起草提案+规范+设计+任务
3. 人工审查          阅读 proposal.md 等文档     ← 人在写代码前先审查
4. 实施阶段          /opsx:apply                 ← AI 按任务清单编码
5. 提交与 PR         git commit && git push      ← PR 包含规范差异和代码变更
6. 归档阶段          /opsx:archive               ← 变更合并到主 specs，归档到 archive/
```

### 5.2 详细流程

#### Step 1：初始化（首次使用）

```bash
# 安装 OpenSpec CLI
npm install -g @fission-ai/openspec@latest

# 进入项目并初始化
cd your-project
openspec init
# 这会安装斜杠命令到你的 AI 工具中
```

#### Step 2：探索（可选但推荐）

在 AI 聊天中输入：

```
/opsx:explore
```

AI 会询问你要探索什么，例如：

```
AI:  What would you like to explore?
You: Our checkout sometimes creates duplicate orders.
AI:  [研究代码库]
     我发现两个原因：
     1. 客户端可能双击提交（缺少防抖）
     2. 支付 webhook 可能重复触发（缺少幂等键）
     建议方案：在订单创建接口增加幂等键，可以解决两个问题。
     要我进一步规划吗？
You: Yes, let's do the idempotency key.
```

#### Step 3：提议

```
/opsx:propose add-order-idempotency-key
```

AI 会创建 `openspec/changes/add-order-idempotency-key/` 文件夹，包含：
- `proposal.md` — 变更意图、背景、范围
- `design.md` — 技术设计方案（如需要）
- `tasks.md` — 可执行的任务清单
- `specs/` — 规范差异（ADDED/MODIFIED/REMOVED）

#### Step 4：审查

**在 AI 写任何代码之前，人工审查变更文档：**

推荐的审查顺序：
1. **proposal.md** — 意图和范围（如果这个错了，立刻停止）
2. **specs/**/*.md** — 需求（审查的核心）
3. **design.md** — 技术方法（大型变更才需要）
4. **tasks.md** — 工作计划

#### Step 5：实施

```
/opsx:apply
```

AI 助手会读取任务清单，逐个完成编码任务，并勾选完成状态。

#### Step 6：归档

```
/opsx:archive
```

将变更差异合并到 `openspec/specs/`，将变更文件夹移入 `archive/`。归档后的变更仍可查阅，但不再可编辑。

### 5.3 团队 Git 分支工作流

```bash
git switch -c add-dark-mode              # 1. 创建分支
/opsx:propose add-dark-mode              # 2. AI 起草方案
# 人工审查 plan                         # 3. 人在编码前审查
/opsx:apply                              # 4. AI 编码
git commit && open a PR                  # 5. 提交 PR（包含规范差异和代码）
# 队友审查、合并                         # 6. 代码审查
/opsx:archive                            # 7. 归档变更，合并规范
```

### 5.4 更新 vs 新建决策

当已有变更存在时，判断是更新还是新建：

```
        是相同的工作？
        ├─ YES → 同一意图？同一问题？ → YES → 更新现有变更
        └─ NO → 重叠 > 50%？
            ├─ YES → 更新现有变更（补充差异）
            └─ NO → 新建变更
```

### 5.5 何时需要 design.md

不是每个变更都需要 `design.md`。满足以下任一条件时创建：

- 跨切面变更（影响多个服务/模块）或新的架构模式
- 新增外部依赖或重大数据模型变更
- 涉及安全性、性能或迁移复杂性
- 存在需要技术决策澄清的模糊点

## 6. Claude Code中使用OpenSpec

### 6.1 安装方式

```bash
npm install -g @fission-ai/openspec@latest
cd your-project
openspec init
```

`openspec init` 会自动在 Claude Code 中注册斜杠命令（slash commands），使 `/opsx:*` 系列命令可用。

### 6.2 常用斜杠命令

| 命令 | 用途 | 何时使用 |
|------|------|---------|
| `/opsx:explore` | 探索问题和方案 | 不确定怎么做时 |
| `/opsx:propose <name>` | 创建变更提案 | 确定要做某个功能时 |
| `/opsx:apply` | 实施变更 | 审查通过后 |
| `/opsx:archive` | 归档变更 | PR 合并后 |

### 6.3 典型对话流程

```
# 用户
/opsx:explore

# Claude Code
AI: What would you like to explore?

# 用户
You: 我们的搜索结果显示的数据总是过时，我想改善这个问题。

# Claude Code
AI: [读取搜索服务和缓存层的代码]
     我分析了你的代码库：
     - 索引每晚重建一次，编辑后当天不可见
     - 写入频率较低
     两个方案：
     1. 写入时重建索引（简单，写入时负载增加）
     2. 短 TTL 缓存失效（更多组件，但写入无额外负载）
     根据你的写入频率，方案 1 更干净。要我规划吗？

# 用户
/opsx:propose rebuild-search-index-on-write
```

### 6.4 与 Claude Code 的协作要点

1. **先读规范，再写代码：** Claude Code 在 `/opsx:apply` 时会读取规范文档作为实现依据。
2. **规范即文档：** 生成的 `proposal.md` 和 `design.md` 可以直接作为 PR 描述。
3. **差异化管理：** 使用 `ADDED/MODIFIED/REMOVED` 而非重写整个 spec 文件，便于审查和合并。
4. **审查优先：** 在 `/opsx:apply` 之前务必人工审查 `proposal.md`，这是防止需求漂移的关键防线。

### 6.5 高级用法

- **跨项目关联：** 在 `.openspec.yaml` 中通过 `links` 字段关联其他仓库的变更：
  ```yaml
  links:
    - project: github.com/fission/web-client
      change: add-3ds-checkout
    - project: github.com/fission/ios-client
      change: add-3ds-checkout
  ```
- **倡议管理：** 大型项目可以使用 `initiatives/` 管理多个相关变更的分组。

## 7. Cursor 中使用OpenSpec

> 注：原文标题为"omp"，根据上下文推断应为 Cursor（另一款流行的 AI 编程工具）。

### 7.1 安装方式

在 Cursor 中使用 OpenSpec，同样需要先全局安装 CLI：

```bash
npm install -g @fission-ai/openspec@latest
cd your-project
openspec init
```

`openspec init` 会在项目目录中生成 Cursor 所需的配置文件和斜杠命令。

### 7.2 Cursor 中的工作流

Cursor 的 AI 对话与 OpenSpec 的集成方式与 Claude Code 类似：

1. 在 Cursor 聊天中使用 `/opsx:explore` 探索问题
2. 使用 `/opsx:propose <name>` 创建变更
3. 人工审查生成的提案文档
4. 使用 `/opsx:apply` 实施变更
5. 使用 `/opsx:archive` 归档

### 7.3 Cursor 使用要点

- Cursor 的 Composer 模式天然适合 OpenSpec 工作流，可以在同一对话中同时编辑规范文档和代码文件。
- 建议将 `openspec/` 目录添加到 Cursor 的上下文感知范围中，确保 AI 始终能看到最新的规范。
- 在 Cursor 设置中，可以将 `openspec/config.yaml` 作为项目配置引用。

## 8. OpenSpec工具安装和使用

### 8.1 安装

```bash
# 全局安装
npm install -g @fission-ai/openspec@latest

# 验证安装
openspec --version
```

### 8.2 初始化

```bash
cd your-project
openspec init
```

初始化后会生成：
- `openspec/config.yaml` — 项目配置
- `openspec/specs/` — 规范目录
- 斜杠命令配置（供 AI 工具使用）

### 8.3 命令速查

| 命令 | 描述 |
|------|------|
| `openspec init` | 初始化 OpenSpec 项目 |
| `openspec validate` | 验证规范文件结构是否正确 |
| `openspec list` | 列出所有变更 |
| `openspec diff <change-name>` | 查看变更与主规范的差异 |

### 8.4 规范编写最佳实践

#### 要求格式

使用结构化格式，每个需求必须包含至少一个场景：

```markdown
### Requirement: 用户登录

用户通过邮箱和密码登录系统，系统验证凭据并返回认证令牌。

#### Scenario: 正确凭据登录成功

- **WHEN** 用户提交有效的邮箱和密码
- **THEN** 系统返回 200 状态码
- **AND** 响应体包含 `access_token` 字段
- **AND** `access_token` 是有效的 JWT 格式
- **AND** token 的过期时间为 24 小时

#### Scenario: 错误凭据登录失败

- **WHEN** 用户提交无效的邮箱或密码
- **THEN** 系统返回 401 状态码
- **AND** 响应体包含 `error` 字段，值为 "INVALID_CREDENTIALS"
- **AND** 不返回任何 token
```

#### 撰写规范的原则

1. **描述行为，不描述实现：** 说"系统应返回 JWT token"，而不是"系统应调用 auth.service.login()"。
2. **每个需求至少一个场景：** 没有场景的需求是不可测试的。
3. **使用 SHALL/MUST 表述要求：** 避免 should/may 等模糊词汇。
4. **包含错误场景：** 不只写 happy path，还要写错误和边界条件。
5. **差异使用 ADDED/MODIFIED/REMOVED：** 不重写整个 spec 文件，只标记变更部分。

## 9. OpenSpec在前端Vue3系统开发中的使用方法

### 9.1 项目背景

使用 Vue 3 + TypeScript + Vite 开发企业管理后台系统。典型模块包括：用户管理、角色权限、数据仪表盘、系统设置等。

### 9.2 目录结构规划

```
my-admin/
├── openspec/
│   ├── specs/
│   │   ├── auth/
│   │   │   └── spec.md           # 认证、登录、权限规范
│   │   ├── dashboard/
│   │   │   └── spec.md           # 数据仪表盘规范
│   │   ├── user-management/
│   │   │   └── spec.md           # 用户管理规范
│   │   └── permissions/
│   │       └── spec.md           # 角色权限规范
│   ├── changes/
│   │   └── add-role-permission/
│   │       ├── proposal.md
│   │       ├── design.md
│   │       ├── tasks.md
│   │       └── specs/
│   │           └── permissions/
│   │               └── spec.md
│   └── config.yaml
├── src/
│   ├── api/
│   ├── components/
│   ├── views/
│   └── stores/
└── package.json
```

### 9.3 典型使用流程

#### Step 1：探索权限管理模块

```
/opsx:explore
# "我想为系统增加细粒度角色权限控制，包括按钮级别权限"
```

#### Step 2：创建权限变更提案

```
/opsx:propose add-role-permission
```

AI 会生成：

**proposal.md** 示例：
```markdown
## 变更：增加细粒度角色权限控制

### 背景
当前系统只有粗粒度的路由级权限控制（管理员/普通用户），
无法满足多租户场景下对功能模块的精细化权限管理需求。

### 范围
- 新增角色-权限关联表
- 新增权限标识系统（模块:资源:操作）
- 新增按钮级权限指令 v-permission
- 管理员后台新增角色权限管理页面

### 不在这个范围内
- 组织架构管理
- 审计日志
```

**specs/permissions/spec.md** 示例：
```markdown
## ADDED Requirements

### Requirement: 权限标识格式

系统使用 `module:resource:action` 格式标识权限，例如 `user:list`、`user:create`。

#### Scenario: 权限标识解析

- **WHEN** 用户角色被授予 `user:create` 权限
- **THEN** 当用户访问用户创建页面时
- **AND** `v-permission` 指令检查通过后，创建按钮可见

### Requirement: 按钮级权限控制

系统通过 `v-permission` Vue 指令实现按钮级权限控制。

#### Scenario: 有权限时按钮可见

- **WHEN** 当前用户角色包含 `user:create` 权限
- **THEN** `<button v-permission="'user:create'">` 渲染为可见
- **AND** 按钮可以点击并触发动作

#### Scenario: 无权限时按钮隐藏

- **WHEN** 当前用户角色不包含 `user:create` 权限
- **THEN** `<button v-permission="'user:create'">` 渲染为 display:none
```

#### Step 3：实施变更

```
/opsx:apply
```

AI 会按 `tasks.md` 中的任务逐个实施：
1. 创建权限类型定义
2. 实现权限 store（Pinia）
3. 编写 `v-permission` 指令
4. 创建角色管理页面组件
5. 编写 API 调用函数

### 9.4 实战要点

1. **前端规范关注 UI 行为：** 规范中描述"按钮可见/隐藏"、"表单验证提示"等可观察行为，而非"使用 Pinia store"这样的实现细节。
2. **复用性设计：** 权限指令 `v-permission` 的规范应足够通用，可复用于所有页面。
3. **渐进式规范：** 先写核心权限模型规范，再逐步扩展子模块规范。

## 10. OpenSpec在前端微信小程序开发中使用

### 10.1 项目背景

微信小程序前端 + 后台服务（Node.js/Python 等）开发。前后端在同一个 Git 仓库中，采用 Monorepo 结构。

### 10.2 目录结构规划

```
miniapp-monorepo/
├── openspec/
│   ├── specs/
│   │   ├── user-auth/
│   │   │   └── spec.md           # 用户认证规范（前后端共享）
│   │   ├── order/
│   │   │   └── spec.md           # 订单流程规范（前后端共享）
│   │   ├── payment/
│   │   │   └── spec.md           # 支付规范（前后端共享）
│   │   ├── miniapp/
│   │   │   └── spec.md           # 小程序前端行为规范
│   │   └── backend/
│   │       └── spec.md           # 后端 API 行为规范
│   ├── changes/
│   │   └── add-wechat-pay/
│   │       ├── proposal.md
│   │       ├── design.md
│   │       ├── tasks.md
│   │       └── specs/
│   │           ├── payment/spec.md
│   │           ├── miniapp/spec.md
│   │           └── backend/spec.md
│   └── config.yaml
├── packages/
│   ├── miniapp/                  # 小程序前端
│   │   ├── pages/
│   │   ├── components/
│   │   └── utils/
│   └── backend/                  # 后端服务
│       ├── src/
│       ├── routes/
│       └── services/
└── package.json
```

### 10.3 跨端规范管理

小程序和后端共享 API 契约，OpenSpec 的规范可作为**前后端共同的真相来源**：

```markdown
## ADDED Requirements

### Requirement: 微信支付下单

小程序端调用微信支付 JSAPI 完成下单支付。

#### Scenario: 正常下单流程

- **WHEN** 用户在小程序中点击"确认支付"
- **AND** 订单金额大于 0
- **AND** 用户已登录（拥有有效 openid）
- **THEN** 小程序调用 `wx.requestPayment` 唤起支付面板
- **AND** 后端创建预支付订单，返回 `prepay_id`
- **AND** 支付完成后后端通过 webhook 接收支付结果通知

#### Scenario: 支付超时

- **WHEN** 用户唤起支付面板后 5 分钟内未完成支付
- **THEN** 订单状态变更为"已超时"
- **AND** 用户无法再次使用同一订单支付
```

### 10.4 微信小程序开发要点

1. **规范关注用户行为：** 小程序规范应描述页面交互、跳转逻辑、表单验证等行为，而非 wx API 的具体调用。
2. **前后端规范对齐：** 订单、支付等核心模块的规范应同时涵盖前端行为和后端 API 行为，确保两端一致。
3. **变更跨端同步：** 一个变更可能同时影响小程序前端和后端，在 `changes/*/specs/` 中分别声明各自的规范差异。
4. **后台服务 API 规范：** 后端 spec 描述 API 端点的输入、输出、错误码，作为前后端的契约。

### 10.5 典型工作流

```
# 1. 探索支付流程
/opsx:explore
# "我想在小程序中集成微信支付功能"

# 2. 创建变更
/opsx:propose add-wechat-pay

# 3. AI 生成的变更包含：
#    - proposal.md：支付流程设计意图
#    - design.md：微信支付 JSAPI 技术选型、安全考虑
#    - tasks.md：前后端任务清单
#    - specs/payment/spec.md：支付行为规范
#    - specs/miniapp/spec.md：小程序支付页面规范
#    - specs/backend/spec.md：后端支付 API 规范

# 4. 审查通过后实施
/opsx:apply

# 5. PR 合并后归档
/opsx:archive
```

## 11. OpenSpec在后台业务系统（Spring Boot）中的使用方法

### 11.1 项目背景

使用 Spring Boot 框架开发微服务后台系统。典型场景：多微服务协作、数据一致性要求高、复杂业务逻辑。

### 11.2 目录结构规划

```
microservice-platform/
├── openspec/
│   ├── specs/
│   │   ├── order-service/
│   │   │   └── spec.md           # 订单服务规范
│   │   ├── inventory-service/
│   │   │   └── spec.md           # 库存服务规范
│   │   ├── payment-service/
│   │   │   └── spec.md           # 支付服务规范
│   │   └── notification-service/
│   │       └── spec.md           # 通知服务规范
│   ├── changes/
│   │   └── add-distributed-tx/
│   │       ├── proposal.md        # 分布式事务方案
│   │       ├── design.md          # 技术设计（重要！跨服务变更）
│   │       ├── tasks.md
│   │       └── specs/
│   │           ├── order-service/spec.md
│   │           ├── inventory-service/spec.md
│   │           └── payment-service/spec.md
│   └── config.yaml
├── services/
│   ├── order-service/
│   ├── inventory-service/
│   ├── payment-service/
│   └── notification-service/
└── openspec.yaml                 # 根目录配置
```

### 11.3 Spring Boot 微服务使用要点

#### 要点 1：跨服务变更需要 design.md

微服务间的变更往往是跨切面的，必须包含 `design.md`：

```markdown
## 技术设计：分布式事务方案

### Context
当前订单创建与库存扣减是两步独立调用，
在网络异常时可能导致订单已创建但库存未扣减的一致性问题。

### Goals / Non-Goals
- **Goals：** 确保订单创建与库存扣减的最终一致性
- **Non-Goals：** 强一致性（不追求分布式事务的原子性）

### Decisions
1. **选择 Saga 模式而非 2PC**
   - 理由：2PC 锁持有时间长，影响吞吐量
   - Saga 允许补偿，适合业务场景

2. **使用事件驱动协调**
   - 订单服务发布 OrderCreatedEvent
   - 库存服务消费事件并扣减库存
   - 扣减失败则发布 StockRollbackEvent
   - 订单服务消费补偿事件并取消订单

### Risks / Trade-offs
- [风险] 事件重复投递导致重复扣减 → [缓解] 库存扣减接口设计为幂等
- [风险] Saga 步骤中间服务故障 → [缓解] 使用持久化事件日志
```

#### 要点 2：规范描述业务行为，不描述技术实现

好的 Spring Boot 规范：
```markdown
### Requirement: 订单创建

系统接收订单创建请求，验证库存后创建订单。

#### Scenario: 库存充足时订单创建成功

- **WHEN** 用户提交包含有效商品的订单
- **AND** 库存数量 >= 订购数量
- **THEN** 系统创建状态为"PENDING"的订单
- **AND** 库存数量相应减少
- **AND** 返回订单 ID 和预计送达时间
```

不好的规范（泄露了实现细节）：
```markdown
### Requirement: 使用 @Transactional 创建订单（❌ 这是实现细节）
OrderController 调用 OrderService.createOrder() 方法，
通过 JPA Repository 保存订单实体...
```

#### 要点 3：规范与 API 文档联动

规范中的场景定义可以直接转化为 API 测试用例：

```markdown
#### Scenario: 库存不足时拒绝创建

- **WHEN** 用户提交订单且某商品库存 < 订购数量
- **THEN** 系统返回 HTTP 409 Conflict
- **AND** 响应体 `error.code = "INSUFFICIENT_STOCK"`
- **AND** 响应体 `error.message` 包含商品名称和当前库存
```

这可以直接映射为：
```java
@Test
void shouldRejectOrderWhenInsufficientStock() {
    // Arrange
    given(stockService.hasStock("SKU-001", 5)).willReturn(false);
    given(stockService.getAvailableStock("SKU-001")).willReturn(2);

    // Act
    var response = restTemplate.postForEntity("/api/orders", orderRequest, OrderResponse.class);

    // Assert
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    assertThat(response.getBody().getError().getCode()).isEqualTo("INSUFFICIENT_STOCK");
}
```

### 11.4 典型使用流程

```
# 1. 探索：订单库存一致性
/opsx:explore
# "订单创建和库存扣减之间有不一致问题"

# 2. 提议
/opsx:propose add-distributed-tx
# AI 生成包含 Saga 方案的设计文档和跨服务规范差异

# 3. 审查
# 人工审查 proposal.md 和 design.md
# 重点关注 Saga 补偿逻辑是否正确

# 4. 实施
/opsx:apply
# AI 按任务清单在三个服务中实施代码变更

# 5. 提交
git commit && git push -u origin add-distributed-tx

# 6. 归档
/opsx:archive
```

### 11.5 微服务规范组织建议

| 策略 | 适用场景 |
|------|---------|
| 按服务划分子目录 | 服务边界清晰，职责单一 |
| 按领域划分子目录 | 跨服务共享同一个业务概念 |
| 共享契约 spec | 前后端或 API 消费者需要共同参考 |
| 各服务独立 openspec/ | 超大型 Monorepo，每个服务有独立团队 |

## 12. 结束语

OpenSpec 代表了 AI 辅助编程的一种重要范式转变：**从"先说再做"到"先写再做"**。它不是银弹，但对于以下场景尤其有价值：

- **AI 重度协作：** 频繁使用 AI 助手，需要维护意图连续性
- **团队协作：** 多人参与，需要规范化的变更追踪
- **长期项目：** 代码库持续增长，需要可追溯的文档链
- **高可靠要求：** 对行为一致性要求严格（金融、电商等）

OpenSpec 的核心理念——**规范先行、差异管理、变更隔离**——不仅适用于 AI 编程，也适用于传统开发中的需求管理和架构决策。值得每个注重工程质量的团队尝试和借鉴。

### 参考资料

- [OpenSpec 官方文档](https://docs.openspec.dev/)
- [OpenSpec GitHub 仓库](https://github.com/Fission-AI/OpenSpec)
- [OpenSpec 核心概念文档](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md)
- [OpenSpec 工作流指南](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md)
- [OpenSpec 编写规范指南](https://github.com/Fission-AI/OpenSpec/blob/main/docs/writing-specs.md)
