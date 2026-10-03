---
tags: [Laya, Hermes Agent, MCP, System One, 决策模型]
星期: 星期四
categories: [tech]
---

# Laya 在 Hermes Agent 中安装与使用

> 范围：记录 Laya System 1 决策模型在 Hermes Agent 中的完整落地链路——本地安装、MCP 配置、工具实测、踩坑记录，以及"一次聊天中如何决定是否调用 Laya"的机制分析。
>
> **关联阅读**：
> - [2026-10-01 System One技术价值与Laya在各Agent中的接入方式](../AICoding/2026-10-01%20System%20One技术价值与Laya在各Agent中的接入方式.md)
> - [2026-10-02 Laya系统调研-部署与使用指南](../AICoding/2026-10-02%20Laya系统调研-部署与使用指南.md)
> - [2026-09-23 Jev(System One Model)开源模型调研](../AICoding/2026-09-23%20Jev(System%20One%20Model)开源模型调研.md)

## 1. 为什么是 Laya + Hermes Agent

Laya 是非自回归 System 1 决策引擎（Apache-2.0，ConvAI Innovations）：类型化问题（choice/score/noul）单次前向输出校准概率，不生成文本，物理上不能编造标签。适合路由、分诊、注入守卫、置信门控；长文档理解与开放生成仍归 LLM。

Hermes Agent 内置 MCP 客户端：在 config.yaml 声明 server 后，工具自动发现并注册进 agent 工具列表——Laya 的 8 个工具因此变成 Hermes 里"一等公民"工具，和 terminal、web_search 同等地位被模型按需调用。

## 2. 本地安装（WSL，CPU）

### 2.1 环境

- venv：`~/.venvs/laya/`（Python 3.11 + torch 2.14.1+cpu + `laya[mcp]` 0.3.22）
- 检查点：multilingual 322M，HF 缓存 `~/.cache/huggingface/hub/models--convaiinnovations--laya`

```bash
python3 -m venv ~/.venvs/laya
# CPU-only torch 必须先装（避免误装多 GB CUDA 版）
~/.venvs/laya/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
~/.venvs/laya/bin/pip install "laya[mcp]"
```

### 2.2 检查点下载（国内网络已踩坑验证）

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1        # 关键：关掉 hf_xet 协议（默认走 cas-server.xethub.hf.co，镜像不支持 → 401）
~/.venvs/laya/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('convaiinnovations/laya', allow_patterns=['multilingual/*'])"
```

坑：`HF_HUB_DOWNLOAD_XET=0` 无效（不是真实变量名），只有 `HF_HUB_DISABLE_XET=1` 生效。只按需下子文件夹（`allow_patterns=['multilingual/*']` ≈647MB），别整包 2.5GB。

## 3. Hermes Agent 配置

### 3.1 config.yaml

```yaml
mcp_servers:            # 注意 key 是 mcp_servers，不是 mcp.servers
  laya:
    command: /home/honya/.venvs/laya/bin/laya-mcp-async   # 必须用 async 包装器，别用官方 laya-mcp-server
    env:
      LAYA_MODELS: multilingual
      LAYA_DEVICE: cpu
      HF_HUB_DISABLE_XET: "1"
      HF_HUB_OFFLINE: "1"
    connect_timeout: 120
```

验证：`hermes mcp test laya` → Connected ~2.8s、8/8 工具。MCP 工具只在**新会话**出现，无热加载。

### 3.2 关键坑：为什么必须用 `laya-mcp-async` 包装器

官方 `laya-mcp-server` 在 `server.run()` 前**同步预加载**检查点（CPU 6-10s），期间事件循环不转，mcp 2.2 SDK 客户端 `initialize` 握手 10s 超时，`hermes mcp add` 报 `✗ Failed to connect:`（错误信息为空）。

`laya-mcp-async` 包装器把预热挪到后台线程，握手 0.8s 即过。判别特征：裸 JSON-RPC-over-stdio 能通、SDK 客户端不通 = 启动阻塞握手，不是服务器坏了。包装器内容见技能 `laya-system-one` 的 `references/mcp-wrapper.md`。

### 3.3 技能 `laya-system-one` 的分工

技能**不是访问通道**（真正调用走 MCP 工具 `mcp__laya__*`），而是"说明书"：环境重建命令、8 个工具的参数格式、门控策略、11 条 pitfalls。模型在任务沾边 Laya 时加载它，保证选对工具后用得对。

## 4. 工具实测（2026-10-01，CPU）

测试输入：中文运维告警"机房3号空调外机温度传感器读数92°C，持续15分钟，环境温度35°C"。

### 4.1 laya_status

返回 device=cpu、torch 2.14.1+cpu、multilingual 已加载、router 就绪——接入健康检查入口。

### 4.2 laya_predict（noul + score）

| 问题 | 类型 | 结果 | 置信度 |
|---|---|---|---|
| 是否垃圾/误报 | noul | P(垃圾) = 0.74 → 判为真实告警 | 0.74 |
| 严重度 0-3 | score | 得分 1.06（1=68%，3=6%）→ "轻微" | 0.31 |

路由正确：自动检测 92% 汉字 → multilingual checkpoint。耗时 1.28s（CPU）。

### 4.3 min_confidence 门控

设 `min_confidence=0.85` 后两个答案都带 `"low_confidence": true`（值仍返回）。门控行为符合预期：调用方见 flag 即升级 LLM 复核。对比：`laya_decide` 门控时直接把字段置 null（"不确定就不许动作"的强语义）。

### 4.4 laya_decide（schema 投影）

| 字段 | 值 | 置信度 |
|---|---|---|
| category（enum 4 选项） | 设备告警 (99.2%) | 0.96 ✅ |
| need_dispatch（boolean） | false (96.4%) | 0.96 ✅ |
| priority（integer 0-3） | 0 | **0.005** ❌ 概率近均匀 (30/24/23/23) |

### 4.5 laya_route（纯路由，无 forward）

正确返回 multilingual，reason："non-Latin script (han, 92% of letters)"。零推理成本，用于解释/预判路由。

### 4.6 能力边界结论

- **可靠区**：enum 分类、noul 布尔（高置信）
- **不可靠区**：数值/序数定级（score、integer priority）、choice 多选项零样本——必须 `min_confidence` 门控 + 低置信升级 LLM
- 生产提精度路线：自有域标注数据微调 typed-decisions 检查点 + 按域温度校准（零样本 0.362 vs 微调 0.766）

## 5. 实测踩的参数坑（已录入技能）

| 坑 | 现象 | 正解 |
|---|---|---|
| score 的 criteria 格式 | 传 dict `{"0": "描述"}` 报 `invalid_questions: criteria must be a non-empty list` | score 用 list `["档位0 描述", ...]`；choice 才用 dict |
| laya_route 的 questions 格式 | 值写成字符串 `{"q": "问题"}` 报 `must be an object` | 必须是完整问题对象 `{"q": {"type": "noul", "instructions": "..."}}`，与 laya_predict 同结构 |
| MCP arguments 传参 | `vo='{...}'` 或扁平参数名报错 | `arguments` 必须是 JSON 对象 `{"key": value}` |

## 6. 八个 MCP 工具详解与选型

通用前提：`state` 是要分析的上下文（任意对象）；只用于结构化决策（choice/score/noul），开放问答、摘要、改写、代码、多跳推理不要用；单次前向 ~33ms（GPU）/ ~200ms（CPU）。

### 6.1 回答类（跑一次前向）

**`laya_predict` —— 最通用的"手写问题"入口**
返回**完整概率分布** + 路由元数据。三种题型：
- `choice`：有限标签，`criteria: {标签: 描述}`（**≤20 个选项**）
- `score`：有序量表，`criteria: ["档位0描述", "档位1描述", ...]`（**必须是 list**）
- `noul`：校准的 P(true)，可选 `labels: {true: 文本, false: 文本}`

```json
{"state": {"text": "【告警】机房3号空调外机92°C"},
 "questions": {
   "is_spam": {"type": "noul", "instructions": "是否垃圾/误报"},
   "severity": {"type": "score", "instructions": "严重度", "criteria": ["正常","轻微","一般","严重"]}}}
```

常用可选参数：`min_confidence`（低置信标 `low_confidence: true`，值仍返回）、`model`（中文显式 `"multilingual"` 最稳）、`lang`、`head_max_len`（选项多时调大，防标签糊掉）。

**`laya_decide` —— 答案形状已定时用**
给一个 JSON Schema，返回值**直接投影到 schema**（enum 成员 / 整数 / 布尔），不用解析 answer map。schema 里只允许 enum / boolean / 带 min/max 的 integer；自由字符串、数组、嵌套对象会被拒。

```json
{"state": {"text": "【告警】..."},
 "schema": {"type": "object", "properties": {
   "category": {"enum": ["设备告警","网络安全","业务故障","其他"]},
   "need_dispatch": {"type": "boolean"},
   "priority": {"type": "integer", "minimum": 0, "maximum": 3}}}}
```

与 predict 的关键区别：`min_confidence` 门控时 decide 把低置信字段**直接置 null**（"不确定就不许动作"的强语义），predict 只打 flag。需要程序化 abstain 用 decide，需要看分布做二次分析用 predict。

**`laya_shortlist` —— choice 选项 >20 的救星**
先用检查点自带 encoder 的嵌入相似度把 N 个选项收窄到 k 个（默认 20，不下载额外模型），再走一次前向作答。返回答案 + 每问题的短列元数据（保留标签、余弦分、k、原选项数）。choice 超 20 选项**必须**走它（77 标签零样本实测 0.425 崩塌）。`k` + `head_max_len` 是处理大 criteria 问题的组合拳。

**`laya_preset` —— 五套内置工作流，免手写问题**

| preset | state 读取字段 | 用途 |
|---|---|---|
| `triage` | `message` | 消息分诊 |
| `guard` | `prompt` | 注入/安全守卫 |
| `moderation` | `post` | 内容审核 |
| `email` | `body` | 邮件处理 |
| `model_router` | `request` | 模型路由（别名 `router`） |

state 只含单个字符串时会自动放进对应字段；多 key 则原样透传（所以要把文本放在对应字段名下）。

### 6.2 批量类

**`laya_predict_batch` —— 一批请求，一次往返**
`requests` 是 `{state, questions, model?, task?, lang?, max_len?, head_max_len?}` 数组，每项同 predict 结构。先路由、按检查点分组、**schema 相同的请求共享前向**——评 100 条告警是一次 round trip 而不是 100 次。返回按输入顺序，附每请求路由/device、`model_counts`、批量延迟。注意 `max_len`/`head_max_len` 是**每请求**的，不同 budget 的请求会被拆成多个前向。

**`laya_route_batch` —— 批量只判路由，零推理成本**
与 predict_batch 同构，但**不跑前向、不加载检查点**，每条返回 `{model, repo, reason}`。用于付模型加载成本前先盘点 workload 的路由分布（"这批消息会走几个检查点"）。

### 6.3 路由类（单条版，无 forward）

**`laya_route` —— 单条路由预判**
不推理，只返回这条 state+questions 会被路由到哪个检查点及原因。用途：① 调试"为什么中文没走 multilingual"；② 传入某次 predict 的 `model`/`task`/`lang` 可复现它的 routing 块而不付前向成本。坑：`questions` 的每个值必须是完整问题对象，不能写成字符串。

### 6.4 诊断类

**`laya_status` —— 健康检查**
无参数。返回实际在用设备（区分"配置偏好"和"实际加载设备"）、torch CUDA 可用性、已加载检查点、router 就绪状态、包版本。部署完先跑它，接入异常时用它判别是配置问题还是模型没加载。

### 6.5 选型速查表

| 场景 | 用哪个 |
|---|---|
| 单条、要看概率分布 | `laya_predict` |
| 单条、答案形状已定、要 abstain | `laya_decide` |
| choice >20 选项 | `laya_shortlist` |
| 任务恰好是邮件/守卫/审核/分诊/路由 | `laya_preset` |
| 大批量同构请求 | `laya_predict_batch` |
| 先盘点路由再决定加载 | `laya_route_batch` |
| 调试路由/接入体检 | `laya_route` / `laya_status` |

## 7. 一次聊天中怎么决定是否调用 Laya

**没有自动触发器，由模型（agent）每轮自行判断**，依据三层信号：

1. **工具目录常驻**：系统提示里列着 12 个 laya 工具的延迟加载目录（laya_predict、laya_decide、laya_route...），每个带描述。描述写死了适用边界——"只用于结构化决策：choice/score/noul；开放问答、摘要、代码不要用"。任务匹配（如"这条告警是垃圾吗"→noul）→ 调；不匹配（"帮我总结"）→ 不调
2. **技能触发**：用户提到 Laya 或任务沾结构化决策/分诊/告警守卫 → 按技能 tags（laya, decision-model, agent-integration）加载技能，拿到完整用法与避坑清单
3. **memory 经验**：中文 choice 多选项不可靠、数值定级要门控升级 LLM——决定"调了之后怎么用"（带 min_confidence、低置信转 LLM 复核）

即：**路由判断本身靠"读工具描述做匹配"**，与 Hermes 选任何工具同机制；技能保证用得对；memory 保证策略稳。

想要"某类消息必过 Laya 预筛"的确定行为时，不靠聊天里自觉，应写成 cronjob / webhook / 脚本显式调用。

## 8. 下一步

- [ ] 在真实告警流上跑 laya_preset（guard/triage），验证预设问题集的中文表现
- [ ] 收集低置信样本，评估是否需要微调 typed-decisions 检查点
- [ ] 把 min_confidence 门控 + LLM 复核写成可复用脚本（cronjob 场景）
