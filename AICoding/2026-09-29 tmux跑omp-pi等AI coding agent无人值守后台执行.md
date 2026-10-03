---
tags: [技术, tmux, omp, pi, AICoding, 无人值守, 后台任务]
星期: 星期二
categories: [tech]
---

# tmux 跑 omp / pi 等 AI coding agent：无人值守后台执行 + 随时回看操作

> 调研日期：2026-09-29
> 调研来源：omp.sh 官方文档（CLI reference / Goal mode）、pi.dev 官方包文档（pi-background-task）、GitHub（omux、cc-tmux-agents、tmux-pi-session-manager、omp team SKILL）、本机实测（tmux 3.6 / omp 17.2.10 / pi 0.84.1，WSL Kali）。

**关联阅读**
- [2026-07-02 AI coding从辅助编程走向全流程接管](2026-07-02%20AI%20coding从辅助编程走向全流程接管.md)
- [2026-09-18 Claude Code frontend-design插件调研与Vue旧系统风格一致性方案](2026-09-18%20Claude%20Code%20frontend-design插件调研与Vue旧系统风格一致性方案.md)
- [2026-07-22-opencode1.x的问题](2026-07-22-opencode1.x的问题.md)

## 1. 总体结论

tmux 是 AI coding agent 无人值守的事实标准载体，核心原因三条：

1. **detach 后进程不死**：agent 跑在 tmux server 里，关掉终端、断 SSH、重启客户端都不影响任务；随时 `tmux attach` 回到完全相同的 TUI 现场（TUI 类 agent 的 UI 状态、会话上下文都在）。
2. **可脚本化"远程操控"**：`send-keys` 注入按键、`capture-pane` 读屏、`pipe-pane` 全程落盘，等于一个极简的 PTY 远程操控协议——agent 无需任何改造。
3. **会话可恢复**：omp/pi 本身把会话存成 JSONL 文件，即使 tmux 会话被杀，也能用 `omp -c` / `omp -r`、`pi -c` / `pi -r` 接着上次干。tmux 管"进程活着"，agent 的 session 管"上下文活着"，两层保险。

**推荐工作流（一句话版）**：`tmux new -s omp-<项目> -c <项目目录>` → 起 agent → `Ctrl-b d` 走人 → 回来 `tmux ls` + `tmux attach`（或手机 SSH 进去 attach）→ 需要自动化时 `capture-pane` 看状态 / `send-keys` 发指令。

## 2. tmux 核心概念与命令速查

### 2.1 层级结构

```
tmux server（常驻后台进程，第一个 new-session 时自动启动）
 └── session（会话，命名单位，无人值守的基本单位）
      └── window（窗口）
           └── pane（窗格，一个 pane = 一个 PTY = 一个程序）
```

关键认知：**detach 杀的是"连接"，不是 session**。`tmux ls` 里每个 session 的 `attached` 列显示当前有几个客户端连着，0 也表示它在正常后台跑。

### 2.2 无人值守四板斧（本机实测通过）

```bash
# ① 建命名会话并直接启动 agent（-c 指定项目目录，agent 依赖 cwd 识别项目）
tmux new-session -d -s omp-web -c ~/code/myweb 'omp "修掉所有失败的测试"'
tmux new-session -d -s pi-core  -c ~/code/mycore 'pi'

# ② 列出所有会话（随时"看一眼"，不用 attach）
tmux ls
# omp-web: 1 windows (created Tue Sep 29 11:49:26 2026) (attached)
# pi-core: 1 windows (created ...)(grouped)  ← 无 (attached) 表示在后台

# ③ 不 attach 直接读屏（agent 在干嘛，一眼看到）
tmux capture-pane -t omp-web -p            # 当前可视区
tmux capture-pane -t omp-web -pS -200      # 往回滚动 200 行历史
tmux capture-pane -t omp-web -pJ          # -J 把软换行的折行拼回整行（看长报错必备）

# ④ 远程注入按键（"回去操作"的脚本化形式）
tmux send-keys -t omp-web:0.0 '继续，注意别动 schema' Enter   # 发一段话
tmux send-keys -t omp-web:0.0 Escape                        # 打断当前回合
tmux send-keys -t omp-web:0.0 C-c                           # Ctrl-C
tmux send-keys -t omp-web:0.0 C-d                           # Ctrl-D (EOF)
tmux send-keys -t omp-web:0.0 'yes' Enter                   # 应答 y/n 确认
```

target 语法：`<session>` 指向其当前窗口当前 pane；`<session>:<window>.<pane>` 精确到 pane。**带窗口指定更稳**（`omp-web:0.0`），多窗口会话里裸 session 名可能打到非预期 pane。

### 2.3 attach / detach

```bash
tmux attach -t omp-web        # 进入现场（TUI 完整恢复）
# 在 tmux 内按 Ctrl-b d  = detach（走人，任务继续）
# Ctrl-b ?  = 看快捷键全表；Ctrl-b 后跟数字键切窗口
tmux switch-client -t pi-core  # 已 attach 状态下切到另一个 session
tmux kill-session -t omp-web   # 确认干完后再杀（先让 agent 正常退出更好）
```

### 2.4 pipe-pane 全程落盘（推荐每个长跑任务都开）

```bash
tmux pipe-pane -t omp-web:0.0 'tee -a ~/logs/omp-web.log'   # 开：实时追加全部输出
tmux pipe-pane -t omp-web:0.0                               # 关（不带命令即停）
```

注意两点：
- **必须在程序输出发生前/时打开才抓得到**（本机实测：attach 之前发生的内容抓不到），所以建议"建会话 → 开 pipe-pane → 发启动命令"这个顺序。
- 落盘内容带 ANSI 转义，看的时候 `cat -v` 或送 `ansi2text` 处理；只想看纯文本还是优先 `capture-pane -pS -N`。

### 2.5 多 agent 并排看（split）

```bash
tmux split-window -h -t omp-web      # 横向再切一个 pane（放第二个 agent 或监控）
tmux select-layout -t omp-web tiled  # 自动平铺
tmux select-pane -t omp-web:0.1      # 键盘焦点切 pane（attach 后 Ctrl-b 方向键也一样）
```

## 3. omp 在 tmux 里的无人值守

本机 omp 17.2.10（`~/.bun/bin/omp`，fork of Pi，MIT）。官方入口四形态，无人值守场景下用前两个：

| 形态 | 命令 | 用途 |
|---|---|---|
| 交互 TUI | `omp` / `omp "任务"` | tmux 里跑这个，可 attach 回看 |
| 一次性 headless | `omp -p "任务"` | 不进 TUI，跑完即退（适合脚本，不需要 tmux） |
| JSON 事件流 | `omp -p --mode json "任务" > events.jsonl` | 给自动化消费 |
| RPC/ACP server | `omp --mode rpc` / `omp acp` | 给别的程序驱动 |

### 3.1 与无人值守直接相关的启动参数

```bash
omp \
  --approval-mode yolo \        # 跳过所有确认（always-ask / write / yolo 三档）
  --max-time 4h \               # 总时长保险丝，到点自己停
  --no-session ...              # （反向）默认会存会话，别加
  "把 importer 迁移到 streaming，改完所有调用方，测试通过才算完"
```

- `--approval-mode write`：只放行写文件、仍问危险操作——比 yolo 稳一档，多数无人值守任务用它。
- `--max-time`：官方 CI 示例即 `omp -p --mode json --no-session --max-time 10m`，无人值守必配。
- `--plan-yolo`：先只读规划、自动批准第一个计划再执行，适合"让它自己定方案自己干"。
- 会话恢复：`omp -c`（接当前项目最近会话）、`omp -r`（picker）、`omp -r <id>`、`omp --fork <id>`（分叉试错不污染主线）。**tmux 会话死了也不怕，重开一个 tmux 会话用 `omp -c` 续上即可**，这是"两层保险"的下层。

### 3.2 Goal mode（omp 原生的"目标长跑"机制，最适合无人值守）

`/goal <目标>` 给一个带完成判据的持久目标，omp 每回合结束自动判断"完成没，没完成继续干"，直到：验证通过 / 预算用完 / 你打断。

```
/goal 把 importer 迁移到 streaming。更新所有调用方和文档，保持错误行为不变，
      只有当 importer 测试和 typecheck 全绿才算完成。
/goal budget 200000        # token 预算 = 安全边界
/goal show                 # 看目标、状态、已用 token、运行时长
/goal pause                # 暂停自动续跑（保留目标与记账）
/goal resume               # 恢复
/goal drop                 # 彻底放弃
```

关键语义（官方文档，务必知道）：

- **目标写法决定效果**：必须写清"交付物 + 验证命令 + 禁止事项"，例如"删掉旧 session API 并迁移所有调用方，保持公共行为兼容，不要改数据库 schema，跑 session 相关测试和 typecheck"。含糊的目标 = 失控的烧钱。
- **Esc 打断**：中断进行中的目标会被存成 paused，检查完手动 `/goal resume`——**冷启动恢复的 goal 默认是 paused，不会自动无人续跑**，这是官方刻意留的人工闸门。
- 官方明确提示：**生产变更、破坏性操作、凭据类工作不要挂 goal 无人跑**，把这些动作在目标里写成"需要确认"。
- 配置项（`~/.omp/agent/config.yml`）：`goal.enabled`、`goal.statusInFooter`、`goal.continuationModes`（默认 `["interactive"]`，即 TUI 里才自动续跑——**所以 goal 模式必须跑在 tmux 这类可 attach 的 TTY 里，纯 `omp -p` 里不自动续**）。
- 启动时 `/guided-goal <粗略目标>` 让它先访谈你、把目标写成可验证的形式再开跑。

### 3.3 omp 其他长跑辅助

- `omp team N:copilot "任务" --name xxx`：官方 team 模式，在**独立 tmux 会话** `omp-team-<name>` 里起 N 个 agent 并行干同一任务；`omp team status <name>` 查进度，`tmux attach -t omp-team-<name>` 围观，`omp team shutdown <name>` 收工。注意其 skill 文档的坑：**分屏版 launcher 必须前台跑**（`nohup/&` 会被 shell 工具清理杀掉，导致 prompt 没发出去 agent 空转）。
- `omp ps` / `omp worktree`：受管子进程与 worktree 的查看/清理，多 agent 并行时配合用。
- `omp join <link>` / `/collab`：把活会话分享成链接（可只读围观或共写），远程协作/让别人看你 agent 在干嘛。

## 4. pi 在 tmux 里的无人值守

本机 pi 0.84.1（`~/.hermes/node/bin/pi`，Mario Zechner 的 AI coding assistant）。

### 4.1 启动与会话恢复（与 omp 几乎同构）

```bash
pi                          # 交互 TUI
pi -c                       # 续当前项目最近会话
pi -r                       # session picker
pi -r <id>                  # 按 ID 前缀恢复
pi --fork <id> "换个方向试"   # 分叉
pi --session-id <id>        # 指定固定 session ID（适合脚本固定入口）
pi -p "一次性任务"           # headless
pi --mode json / rpc        # 事件流 / JSON-RPC server
```

tmux 里跑 `pi -c` 就能实现"昨天的活今天接着干"，即使中间 tmux server 重启过。

### 4.2 pi 官方 pi-background-task 扩展（pi ≥ 0.85.1）

让 **pi 自己**把长命令（build/test/训练）丢进 tmux 后台跑，agent 继续推理不阻塞：

- 6 个工具：`task_start` / `task_status` / `task_logs` / `task_send` / `task_wait` / `task_kill`；
- 每个任务是独立 tmux session 里的真 PTY，输出 `pipe-pane` 全程落盘、按字节偏移分页（大日志不塞爆模型上下文）；
- `task_wait` 在单次工具调用内阻塞等待，**无模型轮询**；完成事件唤醒 pi；
- `/bg-tasks` 看任务列表，`/bg-attach <id>` 打印精确的 `tmux attach` 命令（人接管时直接 attach，pi 不抢终端）；
- 生命周期安全：`/resume`、`/fork`、`/new` 不会误杀任务；会话树感知，兄弟分支的任务历史不串。

⚠️ 本机 pi 0.84.1 < 0.85.1，用之前先 `pi update`。注意它管的是"pi 在会话内执行的后台命令"，和"pi 进程本身跑在 tmux 里"是两回事，两者叠加效果最好。

### 4.3 第三方 tmux-pi-session-manager（值得装）

`x0d7x/tmux-pi-session-manager`：专为 pi + tmux 做的会话管理器（tmux ≥ 3.2、fzf、jq）：

- 每个项目目录可挂多个 pi，各占独立 tmux 会话 `pi-<dir>-<n>`；
- 靠 `/proc` 指纹 + tty→pane 映射**自动发现**所有 tmux 里的 pi 进程（手动起的也能看见）；
- pi 扩展订阅 session 事件，实时给出 `WORKING / BLOCKED / ERROR / WAITING / IDLE` 状态（文件态，无守护进程）；
- **事件驱动桌面通知**（notify-send）：agent 被问题卡住（BLOCKED）、等输入、报错时弹通知——无人值守时不用一直盯着，通知来了再 `pi-tmux pick`（fzf picker）跳过去回答；
- 全功能 CLI：`pi-tmux list / launch --dir ~/project / resume / kill / focus / status / doctor`。

这套"状态 + 通知 + picker"就是无人值守 pi 的完整闭环：**agent 干活 → 卡住/完成 → 桌面通知 → fzf 一跳过去处理**。

### 4.4 其他第三方

- **cc-tmux-agents**（phuongduyphan）：让 agent 之间互相使唤——Claude/Codex/OpenCode/pi 任一当"老板"，另一个跑在 tmux 里当"工人"，六动词统一：start / check（读屏总结）/ tell（追加指令）/ interrupt（发 Escape）/ wait（等空闲再通知）/ kill。老板 agent 可以用自然语言"check pi"、"tell pi: 别动 auth/，bug 在 session/store.ts:42"。跨厂商的"执行-评审"组合（强模型规划 + 便宜模型执行）就是靠它做的。
- **omux**（@happenmass/omux，Node 20+ + tmux）：更重的元 agent——tmux pane 里起多个 CLI agent，靠正则 + 兜底 LLM 分类识别 pane 状态（等输入/干活中/完成/报错），push 式等待（不轮询不烧 token），双层记忆（全局+项目，SQLite+vec+FTS5），子 agent 被杀留 resume id 可复活。适合"多 agent 舰队"规模。

## 5. 无人值守安全清单（重要）

1. **审批档别无脑 yolo**：omp 用 `--approval-mode write` 起步；pi/omp 均无 OS 级沙箱（官方明说），真正要放开的任务放独立容器/VM/专用用户，只给需要的凭据，仓库用 worktree 隔离。
2. **保险丝三件套**：`--max-time`（总时长）+ omp `/goal budget`（token 预算）+ git 干净起点（跑前 commit 或开新分支，随时能回滚）。
3. **目标必须可验证**：写清"跑哪些测试、typecheck 通过才算完、哪些不许动"；含糊目标 = 无限循环烧 token。
4. **凭据最小化**：worker 环境只放该 provider 的 key（cc-tmux-agents 的做法是 `~/.config/cc-agents/env`，600 权限，dispatcher 只读它不读完整 shell 环境）；push 凭据单独放。
5. **日志与现场保留**：`pipe-pane` 落盘 + agent 自己的 JSONL 会话双备份；`omp render <session>` 可把整段会话渲染成 HTML 存档，`omp export` 同理。
6. **远程 attach 用密钥登录**，别把 tmux socket 端口暴露；`omp join`/`/collab` 的链接注意 read-only vs read-write 权限。

## 6. 实战模板（可直接抄）

### 6.1 ~/.tmux.conf 最小配置

```tmux
# 无人值守友好
set -g history-limit 100000        # 长任务滚屏要够深
set -g mouse on                    # 滚轮翻历史、点 pane
set -g escape-time 10              # vim/TUI 里 Esc 不再卡顿
set -g focus-events on             # 某些 TUI 需要
setw -g mode-keys vi               # 复制模式用 vi 键
# 大字体/高刷屏下降低默认 2s 前缀等待无必要，保持默认 Ctrl-b 即可
```

### 6.2 起一个无人值守 omp 任务（标准流程）

```bash
# 0) 项目先提交干净
cd ~/code/myweb && git add -A && git commit -m wip || true

# 1) 建会话 + 落盘 + 启动（顺序：先开 pipe-pane 再发命令）
tmux new-session -d -s omp-myweb -c ~/code/myweb
tmux pipe-pane -t omp-myweb:0.0 'tee -a ~/logs/omp-myweb-$(date +%F).log'
tmux send-keys -t omp-myweb:0.0 'omp --approval-mode write --max-time 6h "迁移 importer 到 streaming，更新所有调用方，importer 测试与 typecheck 全绿才算完，不要改数据库 schema"' Enter

# 2) 走人。之后任何时刻：
tmux ls                                   # 在不在
tmux capture-pane -t omp-myweb:0.0 -p | tail -30      # 干到哪了
tmux capture-pane -t omp-myweb:0.0 -pS -500 -pJ       # 深挖历史
tmux attach -t omp-myweb                  # 回现场（Ctrl-b d 离开）
```

### 6.3 goal 模式长跑（tmux 内交互操作）

```bash
tmux attach -t omp-myweb
# 进入 omp TUI 后：
#   /guided-goal 上线前把认证弄安全一些        # 让它访谈你后写成硬目标
#   /goal budget 300000
# 走人（Ctrl-b d）。回来：
#   /goal show   → 看进度/预算
#   直接打字     → 中途纠偏（"保持现有 wire 格式，给坏帧加个回归测试"）
#   Esc          → 打断当前回合（goal 存为 paused）
#   /goal resume → 确认安全后继续
```

### 6.4 手机/笔记本远程接管（Termius 或任意 SSH 客户端）

```bash
ssh user@host
tmux ls                    # omp-myweb: 1 windows (attached=0)
tmux attach -t omp-myweb   # 完整 TUI 恢复，像一直在看一样
# 处理完 Ctrl-b d，SSH 断开也不影响
```

### 6.5 清理

```bash
tmux kill-session -t omp-myweb          # agent 进程 + 会话一起走
# JSONL 会话仍在 ~/.omp 下，omp -c 可随时续
```

## 7. 常见坑（含本机实测踩到的）

| 坑 | 现象 | 处理 |
|---|---|---|
| send-keys target 不带窗口号 | 多窗口时按键发错 pane；会话刚建完立即 send 偶发 "can't find pane" | 一律用 `session:0.0` 显式指定；建会话后 `sleep 1` 或先 `tmux list-panes` 确认 |
| capture-pane 内容带 ANSI / 折行 | 读屏文本里混着转义、长行被折断 | `-pJ` 拼折行；纯文本处理再套 `ansi2text`（apt 装） |
| pipe-pane 抓不到早期输出 | 建会话后没先开 pipe-pane，agent 第一波输出全丢 | 顺序铁律：new-session → pipe-pane → send-keys 启动命令 |
| Kali 最小化安装的登录横幅 | 新 pane 里 agent 启动前屏幕被开发者提示占住，capture 时看到无关内容 | 建议 pane 内先跑 `touch ~/.hushlogin`（写进 .bashrc 一劳永逸） |
| TUI agent 误判"已完成" | 屏幕出现"Done"字样其实还在跑 | 别只靠读屏判断完成：以 git diff / 测试输出 / agent 的显式完成协议（omp goal 的完成报告、pi 的 result.json）为准 |
| nohup/后台化 tmux 内的 TUI | agent 直接死或空转 | agent 必须由 tmux 管理，不要用 nohup/`&` 另搞一套；要"后台"就用 tmux 的 -d |
| 冷启动恢复的 goal 不自动跑 | omp 重启后 goal 变 paused | 设计如此（防无人失控）：review 后手动 /goal resume |
| pi 版本不够 | pi-background-task 要求 ≥0.85.1，本机 0.84.1 | 先 `pi update` |
| WSL 休眠杀 tmux server | 电脑睡眠/WSL 停止后 tmux server 也没了 | agent JSONL 会话还在，`omp -c`/`pi -c` 续；长任务建议挂 Linux 主机或用 systemd --user 保 tmux |

## 8. 工具生态对照（按需上强度）

| 层级 | 工具 | 适用 |
|---|---|---|
| 裸 tmux（本文主体） | tmux + capture-pane/send-keys/pipe-pane | 1-3 个 agent，自己盯，最可控 |
| 单 agent 增强 | pi: pi-background-task；omp: goal mode / team | 单 agent 长跑 + 后台子任务 |
| 会话管理 | tmux-pi-session-manager | 多 pi 实例，状态灯 + 通知 + fzf 跳 |
| agent 互相协作 | cc-tmux-agents | 强模型老板 + 便宜模型工人，跨厂商执行-评审 |
| 舰队编排 | omux | 多 agent 并行、自动续跑门、跨会话记忆 |

**选型建议**：起步就用"裸 tmux + goal 模式 + pipe-pane"（零依赖、全可控），规模到了多实例再上 tmux-pi-session-manager 管 pi、cc-tmux-agents 做分工，最后才考虑 omux 这类重编排——编排层越重，黑盒越厚，出问题越难 debug。

## 9. 下一步 checklist

- [ ] `pi update` 升到 ≥0.85.1，装 pi-background-task 验证 `/bg-tasks`（需 pi 会话里跑一个 `sleep 60` 类任务确认落盘与唤醒）
- [ ] 装 fzf/jq/ansi2text，按 §6.1 落 tmux.conf
- [ ] 选一个真实小任务走一遍 §6.2 全流程（含 detach 过夜、次日 `omp -c` 续跑），记录实际体验
- [ ] 评估 tmux-pi-session-manager 的 pi 扩展是否影响现有 pi 配置（它会往 pi 装扩展）
- [ ] 决策：WSL 上的长任务是否迁到独立 Linux 主机（WSL 休眠风险 vs 内网合规）
