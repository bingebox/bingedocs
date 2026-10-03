---
tags: [技术, ClaudeCode, frontend-design, Vue, 前端, 设计规范, AICoding]
星期: 星期五
categories: [tech]
---

# Claude Code frontend-design 插件调研 与 Vue 旧系统风格一致性方案

> 调研日期：2026-09-18
> 调研来源：claude.com/plugins/frontend-design 官方页、anthropics/claude-code 仓库（plugins/frontend-design，2026-09-02 更新 SKILL.md、1.1.0）、GitHub issue #28173（marketplace 标识勘误）、社区使用文章。

**关联阅读**
- [2026-05-19 cluade在已有Java系统上做增改编程的能力表现](2026-05-19%20cluade在已有Java系统上做增改编程的能力表现.md)
- [OpenPencil-产品设计与前端编码系统](OpenPencil-产品设计与前端编码系统.md)
- [2026-08-17 Claude连接Penpot MCP server进行AI原型设计](2026-08-17%20Claude连接Penpot%20MCP%20server进行AI原型设计.md)

---

## 一、frontend-design 插件是什么

Anthropic 官方插件（`anthropics/claude-code` 仓库 `plugins/frontend-design`，安装量 110 万+，2026-09 更新到 1.1.0）。**本质不是命令工具，而是一份 SKILL.md 设计技能**，Claude 做前端任务时自动激活，无需特殊命令。

### 1.1 核心机制（来自 SKILL.md 原文）

- **编码前先定设计方向**：确定主题/受众/页面唯一职责，选定明确审美方向（brutalist、maximalist、retro-futuristic、luxury 等），"做一个能自圆其说的真实审美冒险"
- **反"AI 味"三条默认脸**（brief 未指定时禁止使用）：
  1. 米色底（近 #F4F1EA）+ 高对比衬线大标题 + 陶土色点缀
  2. 纯黑底 + 单个荧光绿/朱红亮色点缀
  3. 报纸风细线 + 零圆角 + 密集多栏
- **先出设计 token 再写码**（两遍工作法）：
  - Color：4–6 个命名 hex 值
  - Type：2+ 角色字体（有个性的展示体 + 互补正文体 + 可选数据/说明体）
  - Layout：一句话布局概念 + ASCII 线框
  - Signature：一个让页面被记住的独特元素
- **自我批判流程**：brainstorm → 对照 brief 批判（"这个选择放在任何类似页面是不是也成立？成立就是默认不是选择"）→ 修订并说明改了什么 → 确认独特性后才写代码
- **写码注意**：CSS 选择器特异性冲突（`.section` 与 `.cta` 这类互相抵消）
- **质量底线**：响应式到移动端、键盘可见焦点、reduced motion 支持
- **文案规范**：主动语态、按钮说清动作（"Save changes" 不是 "Submit"）、错误信息给方向不道歉、空态是行动邀请
- **克制原则**："把大胆花在一处，signature 元素是唯一记忆点，其余保持安静克制"

### 1.2 安装

**方式 1：官方插件命令（推荐）**
```
/plugin marketplace add anthropics/claude-code
/plugin install frontend-design@anthropics-claude-code
```
⚠️ marketplace 标识是 `anthropics-claude-code`。网上大量教程写的 `@claude-code-plugins` / `@claude-plugins-official` 是错的（官方 issue #28173 确认）。

**方式 2：手动放 SKILL.md**（适合内网/项目级，最轻量）
```bash
mkdir -p .claude/skills/frontend-design
curl -o .claude/skills/frontend-design/SKILL.md \
  https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md
```
- `.claude/skills/`（项目根）= 项目级；`~/.claude/skills/` = 全局
- 装完不用任何特殊命令，正常下指令即自动激活

### 1.3 典型用法示例

- "做一个音乐流媒体应用的仪表盘"
- "给 AI 安全创业公司做个 landing page"
- "设计一个带深色模式的设置面板"

### 1.4 配套增强（可选）

- **Context7 MCP**：实时查 Vue/组件库版本文档，防 API 幻觉
- **Playwright MCP**：截图自检，配合技能里 "take screenshots 自我批判" 的要求
- 有 Figma 设计稿时走 Figma→code 流程，比纯文字 brief 效果好得多

---

## 二、用它开发 Vue2/Vue3 前端系统怎么做

关键认知：**技能是框架无关的**（只教设计思维，不绑定框架），示例产出偏单页 HTML。Vue 工程里要做"设计-实现分离"：

### 2.1 流程：先产出设计规范，不直接写组件

```
用 frontend-design 技能为「XX 系统」制定设计规范：
确定审美方向、色板（4-6个hex）、字体配对、布局概念和 signature 元素。
只输出设计规范（design tokens + 线框），先不要写代码。
```

### 2.2 Token 落地方式

| 场景 | 落地建议 |
|---|---|
| Vue3 + Vite | design tokens 写成 CSS 变量放全局 `:root`，配合 scoped CSS / UnoCSS / Tailwind theme 配置 |
| Vue3 + 组件库 | 色板/字体映射到 Element Plus / Ant Design Vue 主题定制（`--el-color-primary` 等 CSS 变量覆盖） |
| Vue2 + 老工程 | 同样 CSS 变量（现代浏览器均支持）或 Less/Sass 变量；注意 Vue2 scoped 穿透写法 `::v-deep` |
| Vue2 + Element UI | 主题定制只能走 Less 变量编译，不能 CSS 变量热替换，token 落地多一步 |

### 2.3 组件级使用节奏

- **系统级**（首页/驾驶舱/大屏）：自由发挥，signature 元素放这里
- **业务页**（表单/列表/CRUD）：不要让每页都"大胆取险"——技能自己说"把大胆花在一处"。做法：首页/看板大胆，业务页收敛为统一 token 的常规实现
- **单组件任务**：把已有设计规范（token）显式贴进提示词，比依赖自动激活更可控

### 2.4 Vue2 特别注意

- 生成代码大概率是 Vue3 语法（`<script setup>`、`ref`），提示词必须显式声明 "Vue 2.7 + Options API，不要用组合式 API"（2.7 可用组合式则放宽）
- Vue2 的 transition 和 CSS 变量都够用，signature 动画不受限
- Element UI（Vue2 版）主题定制走 Less 变量编译，非 CSS 变量热替换

---

## 三、旧系统（Vue2/Vue3 人工开发）加新功能，如何保持界面风格一致

核心思路：**先"考古"提取旧系统的设计规范，再把它变成 AI 强制遵守的约束文件**，而不是让 AI 自由发挥。

### 3.1 第一步：设计规范考古（一次性工作）

让 Claude Code 先做规范提取，**不要直接开始写功能**：

```
分析这个项目的现有 UI 风格，输出一份 DESIGN.md：
- 全局色板（主色/辅助色/语义色，从 CSS 变量、Less/Sass 变量、组件库主题配置里找）
- 字体、字号阶梯、行高
- 圆角、阴影、间距体系（找出常用的 4/8/16px 等节奏）
- 按钮、表单、表格、弹窗、标签页的样式规律
- 布局模式（侧边栏宽度、header 高度、卡片间距）
- 图标库、组件库及版本
```

技巧：
- **从代码反推，不凭感觉描述**。色值往往散落在 `.vue` scoped style、`static/css`、`element-variables.scss`、`tailwind.config.js` 等多处；让 AI 全局搜索实际 hex 值并统计频率，高频值就是事实标准
- 有组件库（Element UI / Element Plus / Ant Design Vue / iView）：**主题配置文件是最高优先级规范**，直接读；再看有没有覆盖定制
- 纯手写 CSS 的老系统考古更重要：常见 3 种按钮圆角、5 种主色深浅并存，要指出"主流用法"，新代码只用主流那套

### 3.2 第二步：固化成上下文文件（关键机制）

仓库根目录 `CLAUDE.md`（Claude Code 每次会话自动加载）：

```markdown
## UI 开发约束（必须遵守）
- 本项目 UI 规范见 DESIGN.md，所有新页面/组件必须引用其中 token，禁止自创新色值
- 组件库：Element UI 2.15，禁止引入新的 UI 库
- 新增颜色/字号必须先加入 src/styles/variables.scss 再使用
- 布局沿用 src/layout 现有结构，不要改全局布局
- 表单/表格写法参照 src/views/xxx/List.vue（项目内标杆页面）
- 状态管理：Vue2 项目用 Vuex，不要用 Pinia
- 路由/权限模式参照 router/index.js 现有写法
```

配套——**指定标杆页面**：旧系统总有几个最规整的页面，点名"新列表页参照 `views/device/List.vue` 的写法"。一个真实参照文件比十句描述有效。

### 3.3 frontend-design 插件在旧系统里的定位

SKILL.md 明确适用范围是 "building new UI or **reshaping an existing one**"：

- ✅ "按 DESIGN.md 的规范，用 frontend-design 技能优化这个列表页的视觉层次"——自动继承项目已定方向
- ❌ "用 frontend-design 给这个系统做个新页面"（无约束直接跑）——会按它自己的审美偏好（独特字体、signature 元素、大胆配色）生成与旧系统格格不入的页面

**结论：旧系统里该插件是"润色器"，不是"设计主"。** 方向锁死在 DESIGN.md，只借它对间距、动效、层次的讲究。

### 3.4 实现层具体约束

| 问题 | 做法 |
|---|---|
| AI 自创色值 | 所有颜色走变量（`var(--el-color-primary)` / `$primary`）；评审/CI grep 新增 hex 值 |
| AI 新造轮子 | CLAUDE.md 明确"优先复用 `src/components` 现有组件，不够再新建，新建后登记到该目录 README" |
| Vue2 项目被写进 Vue3 语法 | CLAUDE.md 声明 "Vue 2.6 + Options API，禁止 `<script setup>`、`ref`、`computed` from vue" |
| scoped 样式互相污染 | 约定新组件必须 scoped + BEM 类名；改全局样式前先问 |
| 图标风格不一 | 锁定图标库与线宽/填充风格，禁止混用 emoji/unicode 符号 |

### 3.5 验证闭环

- **截图对比**：起 dev server 后对新页面截图，与标杆页面截图并排看（配 Playwright MCP 最顺）
- **lint 钩子（可选但有效）**：eslint 自定义规则或 pre-commit 脚本扫描 `.vue` 裸 hex 色值（白名单外），CI 挡掉
- **改动面控制**：旧系统最大风险不是新页面丑，而是新功能"顺手"改了公共组件/全局样式。约定：新功能默认只加文件不改公共文件，要改公共文件必须先列影响面

---

## 四、总体结论

1. frontend-design 是"设计品味注入器"而非 Vue 脚手架：装好后先出 design tokens 与方向，再落到工程 CSS 变量/组件库主题。
2. 新系统：技能做设计主，大胆留给首页/大屏，业务页收敛为统一 token。
3. 旧系统：技能只做润色；一致性主要靠 **DESIGN.md 考古 + CLAUDE.md 强制加载 + 标杆页面参照**，每次提示词重复叮嘱是最差方案。
4. Vue2 老工程两个必做：显式声明 Options API 约束；Element UI 主题走 Less 变量编译路径。
5. 兜底靠验证：截图对比 + hex 值扫描 + 公共文件改动前置审批。

**下一步（需拍板的决策点）**
- [ ] 选一个实际 Vue 旧系统试跑"考古 → CLAUDE.md → 加一个新页面"全流程，验证流程成本
- [ ] 决定是否装 Context7 / Playwright MCP（需 npx 网络环境）
- [ ] 是否把 DESIGN.md 考古 prompt 沉淀为可复用模板（每个旧系统跑一遍）
