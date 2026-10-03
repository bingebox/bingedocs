# dsh-openpencil 使用教程

> ⚠️ **已被取代（2026-09-17）**：已确定放弃 Penpot、改用 OpenPencil 做产品原型。完整系统见 [`OpenPencil-产品设计与前端编码系统.md`](OpenPencil-产品设计与前端编码系统.md) 与工作区规范 [`product/AGENTS.md`](product/AGENTS.md)。本文仅保留 dsh-openpencil 插件本身的说明（第 1–4 节仍有效；第 5 节 Penpot 部分不再使用）。
>
> 适用环境：本机 DSH Web（profile: web），插件 `@zseven-w/dsh-openpencil@0.1.0-rc.1` 已安装。
> 本文所有事实均在本机实测/源码核验（2026-09-17）。

## 0. 先说结论（重要）

| 问题 | 答案 |
|---|---|
| dsh-openpencil 能对接我本机的 Penpot（localhost:9001）的 MCP server 吗？ | **不能。** dsh-openpencil 与 Penpot 完全无关（源码中零处提及 Penpot）。它驱动的是另一个设计工具 **OpenPencil**（`.op` 文件格式，开源 Figma 替代品，[GitHub: ZSeven-W/openpencil](https://github.com/ZSeven-W/openpencil)）。 |
| 那我在 DSH 里想用 Penpot 的 MCP 怎么办？ | 用 DSH **内置的 `dsh-mcp-client` 插件**（见第 5 节），直接连 Penpot 的 streamable-HTTP 端点，效果等同于 Claude Code 的接法，且不需要 `mcp-remote` 桥接。 |
| dsh-openpencil 现在能用吗？ | 插件已装、5 个工具已注册，但**本机缺少 OpenPencil 二进制**，当前调用会报错（实测 `openpencil_new` → `Error: OpenPencil editor host binary is unavailable`）。按第 4 节装好二进制即可用。 |

## 1. dsh-openpencil 是什么

DSH 的官方生态插件（OpenPencil 作者 ZSeven-W 出品），让 Agent 直接在 DSH 对话里驱动 OpenPencil 设计画布：

- 用自然语言生成 `.op` 设计稿（JSON，设计即代码）
- 在对话里渲染 PNG 预览 / 多画板画廊 / 可交互只读画布
- 打开托管的 OpenPencil 编辑器（图层、属性、绘图、组件、撤销重做）
- Agent 能读取画布结构、选区，直接改节点

OpenPencil 背景：Rust 原生（非 Electron）、支持 macOS/Windows/Linux、可导入 Figma `.fig`、支持代码导出（React/HTML/Vue/Flutter 等）、自带 MCP server。

## 2. 五个工具

| 工具 | 作用 | 前置条件 |
|---|---|---|
| `openpencil_new` | 从一段 `batch_design` 程序**新建** `.op` 文档（原子写入工作区，绝不覆盖已有文件） | `op-host-web-server` 守护进程二进制 |
| `openpencil_render` | 渲染 `.op`：工具卡片出 PNG 大图 + 多画板缩略图 + 缩放；`editable:true` 时可打开托管编辑器 | `openpencil-desktop` 精确渲染器（缺失时回退 jian，标注 runtime-preview） |
| `openpencil_create` | 对**已打开的**画布执行批量 `batch_design`（生成/重构节点，整批事务） | 该文件正在托管编辑器中打开 |
| `openpencil_edit` | 修改**单个节点**，或你在画布上**当前选中**的节点 | 同上 |
| `openpencil_selection` | 读取画布当前选区（节点 id/名称/类型/坐标/尺寸） | 同上 |

典型提示词示例（直接对 Agent 说）：

- “设计一个移动端 App 登录页，390×844，暖色调，有标题、副标题、邮箱输入框、登录按钮” → `openpencil_new`
- “把这个按钮改成深绿色、圆角 12” → `openpencil_edit`（先在画布上选中按钮，或直接说节点名）
- “在页面底部加一张卡片，放三行文字” → `openpencil_create`
- “把首页的标题字号调大” / “预览一下 design.op” → `openpencil_render`

## 3. 标准工作流

```
你说需求
  → Agent: openpencil_new（生成 xxx.op，立即落盘到会话工作区）
  → Agent: openpencil_render(path, editable=true, autoOpen=true)
  → 对话里出现 PNG 预览 + 右侧可编辑画布
  → 你说“改一下/加一点”
  → Agent: openpencil_edit / openpencil_create（改在活画布上，实时可见）
  → 你在画布上手动选中某节点 → “把选中的放大一倍”
  → 满意后：点编辑器里的 Save 落盘
```

保存语义（务必记住）：

- `openpencil_new` 创建即保存。
- `openpencil_create` / `openpencil_edit` 的修改**不会自动落盘**，必须点编辑器的 Save。
- 画布有未保存内容时 DSH 重载/卸载插件，会保留最多 7 天的本地恢复草稿；再次打开同一文件会询问是否恢复，恢复也不会覆盖磁盘文件。
- 渲染出的 PNG/画廊是**快照**（内容寻址），与后续编辑互不影响。

## 4. 本机环境配置（当前缺失项 + 安装步骤）

### 4.1 插件如何找二进制（源码核验）

| 用途 | 查找顺序 |
|---|---|
| 精确渲染（`openpencil_render`） | 1) 环境变量 `DSH_OPENPENCIL_BINARY` 或 `DSH_OPENPENCIL_DESKTOP` → 2) macOS 应用路径（Windows 忽略）→ 3) PATH 中的 `openpencil-desktop`。都找不到时回退 `jian`（`DSH_OPENPENCIL_JIAN` / `~/workspace/jian/target/release/jian` / PATH），产出明确标注为低保真 runtime-preview |
| 新建/编辑守护（`openpencil_new`、编辑器） | 1) 环境变量 `DSH_OPENPENCIL_EDITOR_BINARY` → 2) 源码根（`DSH_OPENPENCIL_SOURCE_ROOT` 或 `OPENPENCIL_SOURCE_ROOT` 或 `~/workspace/openpencil`）下的 `target/release|debug/op-host-web-server` → 3) PATH 中的 `op-host-web-server` → 4) macOS 应用 |
| 编辑器 Web bundle（可选增强） | 源码根需含 `crates/op-host-web/pkg/op_host_web.js` 与 `crates/op-host-web/assets/canvaskit/canvaskit.wasm`；也可用 `OPENPENCIL_WEB_BUNDLE_DIR` / `OPENPENCIL_CANVASKIT_DIR` 指定 |

> ⚠️ **Windows 关键点**：PATH 查找用的是**不带 `.exe` 的精确文件名**（`openpencil-desktop`、`op-host-web-server`），Windows 上即使加入 PATH 也匹配不到 `.exe`。**必须用环境变量显式指向 .exe 全路径。**

### 4.2 本机实测状态（2026-09-17）

- `openpencil-desktop`、`op-host-web-server`、`jian`：均未安装（PATH/常见目录均无）
- scoop：未安装
- 实测 `openpencil_new` → `Error: OpenPencil editor host binary is unavailable`

### 4.3 安装（三选一，推荐 A）

**A. GitHub Releases 直接下载（Windows x64，当前 v0.8.4）**

```powershell
# 1) 桌面应用（含 openpencil-desktop.exe，精确渲染用）
#    https://github.com/ZSeven-W/openpencil/releases/tag/v0.8.4
#    下载 OpenPencil-0.8.4-x64-win-setup.exe 安装；
#    或下 openpencil-desktop-windows-x86_64.zip 解压即用（便携）

# 2) 无头 Web server（新建文档/托管编辑器用，约 68MB）
Invoke-WebRequest `
  https://github.com/ZSeven-W/openpencil/releases/download/v0.8.4/op-host-web-server.exe `
  -OutFile D:\app\openpencil\op-host-web-server.exe
```

**B. Scoop（需先装 scoop）**

```powershell
scoop bucket add openpencil https://github.com/zseven-w/scoop-openpencil
scoop install openpencil
```

**C. 源码构建**：`git clone --recurse-submodules https://github.com/ZSeven-W/openpencil.git` + Rust stable，`cargo build --release`（需要 wasm 工具链才能构建 Web bundle；适合要完整编辑器的场景）。

### 4.4 设置环境变量（用户级，设完**重启 dsh web**）

```powershell
[Environment]::SetEnvironmentVariable("DSH_OPENPENCIL_BINARY", "C:\Program Files\OpenPencil\openpencil-desktop.exe", "User")   # 按实际路径
[Environment]::SetEnvironmentVariable("DSH_OPENPENCIL_EDITOR_BINARY", "D:\app\openpencil\op-host-web-server.exe", "User")
# 可选：完整编辑器 UI
# [Environment]::SetEnvironmentVariable("DSH_OPENPENCIL_SOURCE_ROOT", "C:\src\openpencil", "User")
```

然后重启 `dsh web`（环境变量在 dsh web 进程启动时读取）。

### 4.5 验证

重启后新开一个会话，直接说：“设计一张 390×844 的 App 启动页”。正常时你会看到：
1. 工作区里生成 `xxx.op`
2. 工具卡片出现 PNG 预览 + “Open interactive canvas / Edit” 按钮

## 5. 在 DSH 里对接 Penpot 的 MCP（你真正想要的）

Claude Code 的接法（`D:\ai\llmmaster\.mcp.json`）：

```json
"penpot": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "http://localhost:9001/mcp/stream?userToken=<你的token>", "--allow-http"]
}
```

DSH 有**内置**的 `@deepseek-ai/dsh-mcp-client` 插件（一等包，支持 stdio 和 streamable-http），可以直接连 Penpot 的 `/mcp/stream`，**不需要 mcp-remote 桥**。端点已实测可用（initialize 返回 200，serverInfo: penpot 1.0.0，带 `high_level_overview` 等工具）。

### 步骤（需要一次 `dsh web` 重启）

1. **启用插件**（在任意终端，dsh web 运行中执行也可以，重启后生效）：

   ```powershell
   dsh plugin --profile web add @deepseek-ai/dsh-mcp-client
   ```

2. **追加配置**到 `C:\Users\BingerLiang\.dsh\profiles\web\cordis.patch.yml` 末尾：

   ```yaml
   - id: mcp-penpot
     name: '@deepseek-ai/dsh-mcp-client'
     config:
       serverName: penpot
       transport: streamable-http
       url: 'http://localhost:9001/mcp/stream?userToken=<粘贴你自己的userToken>'
   ```

   （token 就是 Claude Code 那边 URL 里的那个；它是你的 Penpot 用户令牌，**不要提交到 git**。也可以改用 `headers` 方式，视 Penpot 端支持而定。）

3. **重启 dsh web**。

4. **验证**：新会话里问“列出 Penpot 里我的文件”之类。工具会以 `mcp__penpot__<工具名>` 出现（如 `mcp__penpot__high_level_overview`、`mcp__penpot__*`）。Penpot MCP 自身建议：先用 `high_level_overview` 工具读一遍高层概览再操作。

### 行为说明

- 每个工具形如 `mcp__penpot__search_files`，与 Claude Code 命名规则一致；会话历史和权限规则稳定。
- 连接断开自动重连（500ms 起指数退避到 30s，10 次失败后放弃直到配置重载）。
- 成本：这些工具的定义会计入每次请求的 token（工具多时略增）。
- 只桥接 tools；MCP 的 resources/prompts 不支持（不影响 Penpot）。

## 6. 两套生态怎么共存 / 互通

- **Penpot**（localhost:9001）：团队文件、`.penpot` 格式 → 通过 `dsh-mcp-client` 驱动。
- **OpenPencil**（.op 文件）：个人/Agent 快速出稿、设计即代码、代码导出 → 通过 `dsh-openpencil` 驱动。
- **互通桥梁：Figma `.fig` 格式**。OpenPencil 原生支持 `.fig` 导入/导出（保留布局/填充/描边/文本/图片/矢量）；Penpot 同样支持导入 `.fig`。需要跨工具迁移设计时，走 `.fig` 中转。

## 7. FAQ

**Q: 不装 OpenPencil，dsh-openpencil 还有用吗？**
A: 本机当前状态就是“装了插件但没有二进制”，5 个工具都会失败（渲染还可能走 jian 回退，但你也没装 jian）。想用它就先完成第 4 节；不想装就只用第 5 节的 Penpot 方案。

**Q: 为什么 `openpencil_new` 报错 “editor host binary is unavailable”？**
A: 找不到 `op-host-web-server`。按 4.3 A 下载，4.4 设置 `DSH_OPENPENCIL_EDITOR_BINARY`，重启 dsh web。

**Q: PNG 预览能看，但编辑器打不开？**
A: 托管编辑器还需要 Web bundle（wasm+CanvasKit）。发布版 `op-host-web-server.exe`（68MB）通常已内嵌；若仍报错，按 4.3 C 源码构建后用 `DSH_OPENPENCIL_SOURCE_ROOT` 指向源码根。

**Q: .op 文件在哪？**
A: 会话工作区（本会话是 `D:\ai\mywiki\mydocs`）。JSON 文本，可 git 管理、可 diff、可手动编辑（但插件要求 Agent 不手写 .op）。

**Q: 只读画布和编辑器有什么区别？**
A: “Open interactive canvas” 是 Web SDK 只读画布（平移/缩放/定位）；完整编辑走 managed editor（右侧可缩放工作台，可全屏；小视口自动全屏）。两者同时只能各开一个。

**Q: 多页面 .op？**
A: 渲染画廊只覆盖当前激活页的顶层 frame；其他页面用交互画布查看。

## 附：关键路径速查

| 项 | 路径 |
|---|---|
| 插件源码/README | `C:\Users\BingerLiang\.dsh\profiles\web\node_modules\@zseven-w\dsh-openpencil\README.md` |
| web profile 配置 | `C:\Users\BingerLiang\.dsh\profiles\web\package.json`（bundles 数组）、`cordis.patch.yml`（用户覆盖层） |
| Claude Code 的 Penpot MCP 配置 | `D:\ai\llmmaster\.mcp.json` |
| Penpot MCP 端点 | `http://localhost:9001/mcp/stream?userToken=...`（实测 200） |
| dsh-mcp-client 文档 | `C:\Users\BingerLiang\.dsh\profiles\node_modules\@deepseek-ai\dsh-mcp-client\README.md`（含中文 README.zh.md） |
| OpenPencil 仓库 | https://github.com/ZSeven-W/openpencil （Releases: v0.8.4） |
