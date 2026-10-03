# AGENTS.md — 产品设计与前端编码工作区

本目录是一个「设计即代码」工作区：产品原型用 OpenPencil `.op`（JSON）表达，前端代码由设计稿生成或按设计稿编写。DSH 与 Claude Code 的 Agent 在本目录工作时，遵循以下约定。

## 目录约定

```
product/
├── design/          # 所有 .op 设计稿（一屏/一模块一个 .op，kebab-case 命名）
├── web/             # 前端代码（每个产品/页面一个子目录）
│   └── <feature>/   # 如 web/login-page/
├── exports/         # 导出物：PNG 切图、演示稿 pptx/html/pdf
├── DESIGN.md        # 设计变量/风格规范（出设计前先读它）
└── AGENTS.md        # 本文件
```

## 设计流程（OpenPencil）

1. **先读 `DESIGN.md`**，把其中的颜色/字号/间距/圆角作为设计变量使用。
2. 新建设计稿 → `design/<name>.op`。
   - DSH 会话：直接说需求，Agent 用 `openpencil_new` 生成。
   - 终端 / Claude Code（**已实测**）：
     ```bash
     op start --web --port 4100 --file design/<name>.op   # 无头服务（3100 被 Xshell 占了，固定用 4100）
     op design @batch.dsl                                  # DSL 写进 .dsl 文件用 @file 传！
     op save_document filePath=design/<name>.op            # 必须显式保存，否则不落盘
     op stop
     ```
3. 迭代修改：选中节点后让 Agent 改（DSH: `openpencil_edit`/`openpencil_create`；CLI: `op update <id> {...}` / `op insert {...}`）。改完同样要 `op save_document`。
4. 人工精修：`op start --file design/<name>.op`（桌面编辑器）或 `op start --web`（浏览器编辑器，需 web bundle；缺失时显示构建说明）。
5. 导出切图：`op export --selection --output exports/<name>.png`；整页批量：`op export-frames --output-dir exports/`；或直接用 `openpencil-desktop --render-shots <file.op> <dir> <scale>`。

**禁止手写 .op JSON 文件**——一律通过上述工具生成/修改。

## DSL 与 schema 要点（实测踩坑）

- `batch_design` 是**事务**：一行失败整批回滚，报错会指明行号和原因；改对后重发整批。
- `layout` 只接受 `none | vertical | horizontal`（**没有 CSS 的 `row`**）。
- PowerShell 直接内联 JSON 会吞引号 → 一律 `op design @file.dsl`（Claude Code 的 Bash 无此问题，可直接内联）。
- 常用节点字段：`type`（frame/text/rect/ellipse/image…）、`name`、`x`/`y`/`width`/`height`（`fill_container` 可用）、`fill`（hex）、`cornerRadius`、`gap`、`padding`、`justifyContent`、`alignItems`、`content`/`fontSize`/`fontWeight`（text）、`clipContent`。
- 内置组件库：`insert_shadcn_*` 系列（btn/input/card/nav/tab/dialog/toast/table… 30+ 个）可直接插入；`insert_btn_primary`、`insert_card_basic`、`insert_nav_bar` 等基础件也有。
- 大任务可用 `spawn_agents` 把设计拆成并行子任务（每个子任务带 styleguide + guideline）。
- 风格库：`op styles` / `op list_style_guides`（50+ 风格指南 + 你导入的 DESIGN.md）；模板：`op templates` / `op use-template <id>`（58 个场景模板）。
- 设计变量：`op vars` / `op vars:set`；导出代码时映射为 CSS 自定义属性。
- v0.8.4 共 **166 个 MCP 工具**（`op tools` 可查全表，含 `get_screenshot` 视觉自检、`import_html`/`import_web_snapshot` 回流、`codegen_plan/submit/assemble` 出码）。

## 出码流程（设计 → 前端代码）

按场景三选一：

| 场景 | 方式 | 命令 |
|---|---|---|
| 快速原型 / 独立页面 | OpenPencil 原生 codegen | `op codegen:plan @plan.json` → `op codegen:submit <planId> @chunk.json` → `op codegen:assemble <planId> --framework react`，产物落到 `web/<feature>/` |
| 并入现有工程项目 | Agent 直接读 `.op`（它就是 JSON）→ 按 `DESIGN.md` 的 token 写组件代码 | DSH 会话直接说“把 design/xxx.op 实现成 React 页面，放进 web/xxx/” |
| 需求文档配图 | PNG 导出 | `op export-frames` 后插入文档 |

- 生成的代码默认 **React + Tailwind CSS**（团队栈），除非需求另指。
- 设计变量（`op vars`）映射为 CSS 自定义属性，代码里用 `var(--token)`，不要硬编码色值。
- 出码后必须能在 `web/<feature>/` 里独立运行（`npm run dev` 或静态打开 index.html）。

## 回流（代码 → 设计）

已有页面想继续在设计工具里迭代：
```bash
op import:html web/<feature>/index.html --out design/<name>.op
```

## 常用 op 命令速查

```bash
op status                              # MCP 服务是否在跑
op start --web --port 4100 --file x.op # 无头服务（3100 被 Xshell 占用，固定 4100）
op start --file x.op                   # 桌面编辑器（人工精修）
op stop
op tools                               # 列出全部 166 个 MCP 工具
op save_document filePath=<path>       # 显式保存 .op（改完必做）
op get [--type frame] [--name 标题]    # 查节点
op selection                           # 当前选区
op design @batch.dsl                   # 批量设计（@file 传参，支持 --script 沙箱 JS）
op design:skeleton / :content / :refine # 分层设计工作流
op templates [--scene app]             # 58 个场景模板
op use-template <id>
op styles                              # 50+ 风格指南
op vars / op themes
op import:figma x.fig / :html / :svg   # 导入
op export-deck --output x.pptx         # 演示稿导出
```

## 版本与二进制

- OpenPencil v0.8.4，位于 `D:\app\openpencil\`：
  - `bin\op.exe` — CLI（x64，✅ 可用）
  - `app\openpencil-desktop.exe` — 桌面编辑器 + 无头 serve-web + 精确渲染器（x64，✅ 可用）
  - `bin\op-host-web-server.exe` — **ARM64，本机不可用**（官方该资产只发 ARM64 版；本机已用 desktop 二进制顶替，它共享 `--serve-web` CLI）
- 用户环境变量（已设置）：
  - `DSH_OPENPENCIL_BINARY` = `D:\app\openpencil\app\openpencil-desktop.exe`（DSH 精确渲染）
  - `DSH_OPENPENCIL_EDITOR_BINARY` = `D:\app\openpencil\app\openpencil-desktop.exe`（DSH 新建/托管编辑器守护）
  - `OPENPENCIL_DESKTOP_BIN` = 同上（op CLI 找桌面二进制的兜底；新开的终端 PATH 已含 `D:\app\openpencil\app`）
- 已知限制：浏览器版编辑器（`op start --web` 的 UI 部分）需要 web bundle（wasm+CanvasKit，需源码构建），缺失时 MCP/CLI/渲染/桌面编辑全部照常，只有浏览器画布显示构建说明。DSH 对话里的只读画布用插件自带 viewer，不受影响。
- 换版本时：改 `D:\app\openpencil\download.mjs` 的版本号与 sha256 → 重跑 → 重启 dsh web 与 Claude Code。
