# OpenPencil 产品设计与前端编码系统

> 本机整套系统搭建手册（2026-09-17 搭建，OpenPencil v0.8.4）。
> 目标：需求 → 高保真原型（.op）→ 前端代码（React+Tailwind）→ 导出/回流，全程 Agent 可驱动、人可随时接管。

## 1. 系统总览

```
                        ┌────────────────────────────────────────────┐
 需求（自然语言）        │              设计层（OpenPencil）             │
 ──────────────►        │  ① DSH 对话: openpencil_new/render/edit      │
                        │  ② Claude Code / 终端: op CLI（129 个 MCP 工具）│
                        │  ③ 人工: openpencil-desktop 桌面端 / op start --web │
                        └──────────────────┬─────────────────────────┘
                                           ▼
                        design/<name>.op   （JSON，git 可 diff，设计即代码）
                                           │
        ┌──────────────────────────────────┼──────────────────────────┐
        ▼                                  ▼                          ▼
 出码 A: op codegen:plan →        出码 B: Agent 直接读 .op JSON     出码 C: op export-frames
 submit → assemble                  按 DESIGN.md token 写生产代码      导出 PNG（文档配图）
 (React/HTML/Vue/Flutter…)         （并入现有工程项目）
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
                 web/<feature>/  （可独立运行的前端代码）
                       │
                       ▼
        回流: op import:html index.html --out design/xxx.op  → 回到设计层继续迭代
```

### 四个入口各自负责什么

| 入口 | 擅长 | 命令/工具 |
|---|---|---|
| **DSH + dsh-openpencil 插件** | 对话式出稿：聊天里直接看 PNG 预览、开画布、让 Agent 改选区 | `openpencil_new` `openpencil_render` `openpencil_create` `openpencil_edit` `openpencil_selection` |
| **`op` CLI（终端/Claude Code）** | 批量化、脚本化、CI：分层设计（skeleton→content→refine）、模板、风格库、代码生成流水线、批量导出 | `op design` `op codegen:*` `op export*` `op templates` `op styles` |
| **OpenPencil 桌面端 / 浏览器端** | 人工精修：图层、属性、组件、交互原型、协同 | `op start --file x.op`（桌面）/ `op start --web`（浏览器） |
| **DSH + dsh-mcp-client（可选增强）** | 把 129 个 MCP 工具全部接进 DSH（模板/风格/codegen/导出/页面管理） | `mcp__openpencil__*` |

## 2. 本机已安装（2026-09-17，全部实测通过）

| 组件 | 位置 | 状态 |
|---|---|---|
| `op.exe`（CLI，166 个 MCP 工具客户端） | `D:\app\openpencil\bin\` | ✅ x64 可用 |
| `openpencil-desktop.exe`（编辑器 + 无头 serve-web + 精确渲染器） | `D:\app\openpencil\app\` | ✅ x64 可用 |
| `op-host-web-server.exe` | `D:\app\openpencil\bin\` | ❌ **ARM64，本机不可用**（官方只发了这一个架构）；已用 desktop 二进制顶替（它共享 `--serve-web` CLI） |
| DSH 插件 `@zseven-w/dsh-openpencil@0.1.0-rc.1` | `C:\Users\BingerLiang\.dsh\profiles\web\` | ✅ 5 个 openpencil_* 工具；`--managed` 守护模式已验证可启动 |
| 用户环境变量 | `HKCU\Environment` | ✅ `DSH_OPENPENCIL_BINARY` / `DSH_OPENPENCIL_EDITOR_BINARY`（均指向 desktop 二进制）/ `OPENPENCIL_DESKTOP_BIN` / PATH |

**已验证的完整管线**（2026-09-17 实测，产物见 `product/design/hello-world.op` + `product/exports/hello-world.png`）：
`op start --web --port 4100` → `op design @hello.dsl`（5 节点）→ `op save_document`（.op 落盘 2150B）→ `op stop` → `openpencil-desktop --render-shots`（PNG 422×876）

> 下载走 `gh-proxy.com` 镜像（本机直连 GitHub 不通），全部文件按官方 SHA256 校验。
> 升级脚本保留在 `D:\app\openpencil\download.mjs`（改版本号+哈希重跑即可）。
> ⚠️ 本机 3100 端口被 Xshell 8 占用，OpenPencil 服务固定用 **4100**。

## 3. 日常工作流（推荐节奏）

### 3.1 出原型（DSH 对话，最快）

```
你: “读 product/DESIGN.md，设计一个会员订阅页，390×844，
     三个套餐卡片、月度/年度切换、底部安全区”
Agent: openpencil_new → product/design/subscription-page.op
      → openpencil_render（editable+autoOpen）→ 对话里出预览 + 右侧编辑器
你: “第二张卡片标‘推荐’，主色用 DESIGN.md 里的 primary”
Agent: openpencil_edit / openpencil_create（活画布上改，实时可见）
你: 点编辑器 Save
```

### 3.2 出原型（终端 / Claude Code，适合批量）

```bash
cd D:\ai\mywiki\mydocs\product
op start --web --port 4100 --file design/subscription-page.op   # 无头服务（4100 避开 Xshell 的 3100）
op use-template <模板id>                                 # 从 58 个模板起步（可选）
op design @batch.dsl                                       # 或分阶段（@file 传参！）:
op design:skeleton @skeleton.json
op design:content hero @content.json
op design:refine --root-id <id>
op save_document filePath=design/subscription-page.op       # 显式保存
op stop
```

### 3.3 出码

**快速原型（独立页面）**：
```bash
op codegen:plan @plan.json          # 1) 计划（指定 framework: react）
op codegen:submit <planId> @chunk1.json   # 2) 分块提交
op codegen:assemble <planId> --framework react   # 3) 组装 → web/<feature>/
cd web/<feature> && npm run dev
```

**并入工程（推荐，质量更高）**：
```
你（对 DSH 或 Claude Code）: “把 design/subscription-page.op 实现成
  React+Tailwind 页面，放进 web/subscription-page/，
  颜色字号用 DESIGN.md 的 token，组件拆到 components/”
```
（`.op` 就是 JSON，Agent 直接读节点树/坐标/样式/设计变量即可。）

### 3.4 导出

```bash
op export-frames --output-dir exports/                 # 每帧一张 PNG
op export --selection --output exports/xxx.png --scale 2
op export-deck --output exports/deck.pptx              # 16:9 演示稿 → pptx/html/pdf
```

### 3.5 回流（代码改完想继续在设计里迭代）

```bash
op import:html web/subscription-page/index.html --out design/subscription-page-v2.op
```

## 4. Claude Code 侧接入（与 DSH 并行驱动同一个 .op）

二选一（或都用）：

**A. openpencil-skill（官方一键，教 Agent 用 op CLI）**
```powershell
D:\app\openpencil\bin\op.exe install --target claude-code
```
装完 Claude Code 会自动发现 OpenPencil 技能，按技能指引驱动 `op` CLI（166 个 MCP 工具）。

**B. MCP server（stdio，经桌面二进制）**
在 `~/.claude.json` 的 `mcpServers` 里加（与现有 gitnexus 并列）：
```json
"openpencil": {
  "command": "D:\\app\\openpencil\\app\\openpencil-desktop.exe",
  "args": ["--mcp", "D:\\ai\\mywiki\\mydocs\\product\\design"]
}
```

**C. MCP server（HTTP，常驻无头服务）**：先 `op start --headless --file design/x.op`，再把 MCP client 指向 `http://127.0.0.1:3100/mcp`。

> 注意：同一个 `.op` 同一时间只让一个 Agent/编辑器驱动（文件型服务有锁与版本哈希），避免两边同时写同一文件。

## 5. DSH 侧（本 GUI）使用要点

- 会话工作区是 `D:\ai\mywiki\mydocs`，`openpencil_new` 的 `.op` 就落在这里（建议放 `product/design/`）。
- 权限：需要 **Workspace Write** 模式（当前已满足）。
- 保存语义：`openpencil_new` 立即落盘；`create/edit` 的修改要在编辑器里点 **Save**。
- 未保存内容若 DSH 重载，有最多 7 天的本地恢复草稿。
- 渲染预览：精确渲染走 `openpencil-desktop.exe`（已配置）；缺它时才会降级为低保真 jian 预览。

## 6. 维护

- **升级**：去 [Releases](https://github.com/ZSeven-W/openpencil/releases) 拿新版资产 → 改 `download.mjs` 里的版本号与 sha256 → 重跑 → 重启 dsh web 与 Claude Code。
- **排错**：
  - DSH 里 `openpencil_new` 报 “editor host binary is unavailable” → 环境变量没生效，**重启 dsh web**。
  - `op` 报 “server must be running” → 先 `op start --headless --file xxx.op`。
  - 预览报渲染器错误 → 确认 `DSH_OPENPENCIL_BINARY` 指向的 exe 存在且版本匹配。
- **安全**：`.op` 与代码都进 git 时，仓库里不要放敏感内容（设计稿可能含未发布产品）。

## 7. 验收清单

- [x] CLI 管线：`op start --web --port 4100` → `op design @dsl` → `op save_document` → `op stop`（2026-09-17 实测通过）
- [x] 精确渲染：`openpencil-desktop --render-shots` 出 PNG（422×876，见 `product/exports/hello-world.png`）
- [x] 桌面二进制 `--managed` 守护模式可启动（dsh-openpencil 的实际调用方式）
- [x] Claude Code：`op install --target claude-code` → openpencil-skill v0.8.4 已装入 `~/.claude/plugins/cache/openpencil-skill`
- [ ] **DSH 对话侧**（需重启 dsh web 加载环境变量后验证）：新会话说“设计一张 390×844 登录页”→ 应生成 `.op` + 出 PNG 预览
- [ ] 出码实测：挑一个 `.op` 跑 `op codegen:*` 或让 Agent 直接读 `.op` 写 React 页面到 `web/<feature>/`
- [ ] （可选）浏览器编辑器 UI：构建 web bundle 后 `op start --web` 才有画布（不影响其他一切功能）
