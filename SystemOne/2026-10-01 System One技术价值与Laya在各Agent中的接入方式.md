# System One 技术价值与 Laya 在各 Agent 中的接入方式

> 调研日期：2026-10-01
> 背景：接《2026-09-23 Jev(System One Model)开源模型调研》（模型选型层），本篇回答三个问题：
> **① 为什么要用 System One 技术？② Laya 怎么用？③ 现有 Agent 体系（Claude Code、oh-my-pi/Pi、Hermes Agent、QwenPaw、DSH、WorkBuddy、自研 Agent）怎么接上它——是否必须自研编码？**
> 结论先行：**不必自研编码。Laya 官方自带 MCP server extra（`laya[mcp]`）和 Jev 兼容 HTTP 端点（`/v1/systemone`），所有支持 MCP 的 Agent 加一条配置即可用；不支持 MCP 的自研系统走 HTTP 也只是几十行 client 代码。**

**关联阅读**：
- [2026-09-23 Jev(System One Model)开源模型调研](2026-09-23%20Jev(System%20One%20Model)开源模型调研.md) — 开源模型/替代实现全景与选型
- [2026-07-02 AI coding从辅助编程走向全流程接管](../AICoding/2026-07-02%20AI%20coding从辅助编程走向全流程接管.md)
- [2026-09-29 tmux跑omp-pi等AI coding agent无人值守后台执行](2026-09-29%20tmux跑omp-pi等AI%20coding%20agent无人值守后台执行.md)

---

## 一、总体结论

1. **System One 的价值不是"更强的模型"，而是"更便宜的判断"**：把高频、低复杂度、答案空间封闭的决策（路由、分诊、分类、安全判断、置信门控）从 LLM 里剥出来，用 33ms 级别（T4）/ 免费本地推理的小模型完成，LLM（System 2）只处理它不确定的部分。
2. **Laya 是目前该方向工程化最完整的开源实现**（29.5k★、Apache-2.0、PyPI/HF/Docker/Nix 齐全，官方 MCP/serve/LangChain/TS SDK/ONNX 全有），上一份调研的选型结论仍然成立。
3. **接入路径分层，从省事到深入**：
   - **零代码**：托管 MCP（laya.studio，付费 API key）→ 任何 MCP 客户端粘贴 URL 即用
   - **本地免 key**：`pip install "laya[mcp]"` 起本地 MCP server → 任何 MCP 客户端配 stdio
   - **服务化**：`laya[serve]` 起 `/v1/systemone`（Jev 兼容 HTTP）→ 任何能发 HTTP 的系统直接调用
   - **嵌入代码**：Python SDK / `laya-ts`（Node/浏览器 ONNX）→ 自研 Agent 进程内调用
4. **只有以下情况才值得在自研 Agent 里深度编码**：需要进程内极低延迟（省掉 MCP/HTTP 往返）、需要把 System 1 决策嵌入 agent loop 的 hook/gate 逻辑（如"每步决策前过一遍 Laya，低置信才升级 LLM"）、或需要批量管线。即便如此，也只是"调用 + 门控逻辑"，不是"重写模型"。

---

## 二、为什么需要 System One 技术

### 2.1 问题：我们在用 70B 模型做"判断题"

一个 Agent 系统 90% 的决策其实不复杂：

- 这条消息该路由给哪个队列/哪个子 agent？（枚举选择）
- 这个工具输出是不是提示注入？（是/否）
- 这张工单紧急程度 0–3 分？（量表打分）
- 这个文件改动风险高吗？该不该走人工审批？（是/否 + 置信度）
- 这段 RAG 召回的内容与问题相关吗？（是/否）

用生成式 LLM 回答这些问题的代价：

| 维度 | 生成式 LLM 做判断题 | System One（Laya 类） |
|---|---|---|
| 延迟 | 500ms–2s（逐 token 流式） | **33ms/问，批量 7.2ms/问**（T4 实测） |
| 成本 | 按 token 计费，高频调用放大 | 本地推理，**$0**（Apache-2.0 权重） |
| 输出形态 | 自由文本 → 还要写 JSON schema 解析、正则兜底 | **原生类型化输出**：choice/score/noul 三种基元，物理上不存在畸形 JSON |
| 置信度 | "confidence: 0.95" 是生成的 token，**无数学校准** | 校准概率（RLCD 训练，ECE 0.081 vs Jev 0.246），**可以直接 `if p < 0.6: 升级`** |
| 幻觉 | 能生成不在选项里的标签 | 只能从你给定的选项中选，**物理上不能编造** |
| 可审计 | 概率藏在 prose 里 | 每个决策都是显式概率向量，可导出、可回放 |

### 2.2 正确的架构：三层分工

```
                    ┌─────────────────────────────────┐
  高频、封闭答案     │ System 1：Laya / Jev（33ms）    │ ← 路由、分诊、守卫、门控
  批量、低容错成本   └──────────────┬──────────────────┘
                                   │ 置信度 < 阈值（如 0.6）
                                   ▼
                    ┌─────────────────────────────────┐
  低频、开放式       │ System 2：LLM（推理/写作/规划）  │ ← 真正的难题才用
                    └──────────────┬──────────────────┘
                                   │ 确定方案后
                                   ▼
                    ┌─────────────────────────────────┐
  确定性执行         │ 传统代码 / 工具调用              │ ← 副作用由代码守卫，不靠 prompt
                    └─────────────────────────────────┘
```

一个有代表性的第三方实测（dev.to，vishalmysore 的 layaAgent 项目）：浏览器内用 Laya(421M) 做 agent 每步决策 + 1.5B 小 LLM 兜底 + 置信门控，任务成功率 94%（人在回路）/21%（全自动），而同样场景纯 1.5B LLM 每步决策只有 10%。**System 1 的价值不在单独替代 LLM，而在"确定时跑快路径、不确定时交出去"的门控机制本身。**

### 2.3 对 Agent 场景的具体收益（对应我们自己的 Agent/运维平台）

| 场景 | System 1 判断内容 | 收益 |
|---|---|---|
| 多 agent 编排 | 子任务路由到哪个专家 agent（choice ≤20 个） | 每次路由省一次 LLM 调用，毫秒级 |
| 工具调用守卫 | 该工具参数是否危险/敏感（noul） | 替代"prompt 里写请不要乱删"，用代码门控 |
| 提示注入防护 | 外部内容（网页/文件/工单）是否注入（noul，ToxicChat 实测 75.5–76.2%，50% 弃权覆盖下 93.1%） | 比大模型快 10× 以上的入口筛查 |
| 工单/告警分诊 | 运维告警分级（score）、归属队列（choice） | 高频批量场景成本≈0 |
| 置信门控 | LLM 输出后自评/复判，低置信升级人工或更强模型 | 用校准概率做分支，而不是靠 LLM 自己说"我很有信心" |
| RAG 相关性 | 召回片段相关与否（noul，单趟 65.7%） | 减少喂给 LLM 的噪声上下文 |

注意（承接上篇调研）：Laya 上下文窗口 512–1024 token（multilingual 可开到 8192 但 >4k 精度波动），**它判断的是"状态摘要 + 类型化问题"，不是长文档深度理解**——长文档深读仍是 LLM 的活。

---

## 三、Laya 怎么用

### 3.1 安装（本地自托管，免费）

```bash
# Python ≥ 3.10
python3 -m venv ~/.venvs/laya && ~/.venvs/laya/bin/pip install "laya[mcp,serve]"
# 或 CPU-only torch（避免误装多 GB 的 CUDA 版）：
# pip install torch --index-url https://download.pytorch.org/whl/cpu  先于 laya
```

首次调用自动从 HuggingFace 下载检查点（english 约 808MB / multilingual 约 647MB），缓存在 `~/.cache/huggingface`。

### 3.2 三个检查点（Router 自动选）

| 检查点 | 编码器 | 参数 | 上下文 | 用途 |
|---|---|---|---|---|
| `laya` | ModernBERT-large | 421M | 512 | 英文分类/守卫/邮件分诊 |
| `laya-multilingual` | mmBERT-base | 322M | 1024（可开 8192） | **100+ 语言（含中文）**，快 2.2× |
| `laya-typed-decisions` | ModernBERT-large | 421M | 1024 | 微调过的 agent 观测/客服/发票/安全告警（0.766 acc） |

**中文场景必须确认路由到 multilingual 检查点**（`Router` 会按文字脚本自动路由；英文检查点读不了 CJK，且此时置信度不下降——不能靠置信度兜底，必要时显式 `model="multilingual"`）。

### 3.3 Python SDK（生产用）

```python
from laya import Router
router = Router(preload=True)   # 三个检查点常驻内存，免冷切换 7–10s

state = {"subject": "生产 API 挂了", "body": "从早上 6 点开始报错，要求按 SLA 退款，否则取消合同"}
questions = {
    "queue": {"type": "choice", "instructions": "归哪个工程队列？",
              "criteria": {"infrastructure": "宕机/网络/数据库故障",
                           "billing": "退款/发票/SLA 争议",
                           "security": "入侵/漏洞", "support": "一般咨询"}},
    "urgency": {"type": "score", "instructions": "多紧急？",
                "criteria": ["不紧急", "尽快", "高优先级", "critical 阻塞"]},
    "churn": {"type": "noul", "instructions": "客户是否威胁取消/流失？"},
}
res = router.predict(state, questions)          # 一次前向，三个问题全答
print(res["answers"]["queue"]["choice"])        # infrastructure
print(res["answers"]["churn"]["noul"])          # 0.91（校准概率，可直接分支）
```

批量：`router.predict_batch(states, questions)`（按长度分组 `sort_by_length`，实测 1.4–2.6× 提速）；低置信弃权：`predict(..., min_confidence=0.6)` 低于阈值标 `low_confidence: True`，`decide()` 直接返回 `None`。

### 3.4 CLI / 本地服务

```bash
laya "我的支付失败了两次" --preset triage --model multilingual --device cpu
# 内置 preset：triage / email / guard / moderation / router
cat tickets.txt | laya --batch - --predict --json        # 批量 JSONL

pip install "laya[serve]"
LAYA_HOST=127.0.0.1 LAYA_MODELS=english,multilingual laya-serve
# POST /v1/systemone —— 与 TypeSafe Jev 的 API 完全同构（Jev 客户端改 baseUrl 即可）
```

### 3.5 已知限制（写进任何方案都要带）

1. **choice 选项 >20 会掉点**（Banking77 77 标签：0.425 vs Jev 0.870）——选项共享 192–256 token 的 head 预算。对策：≤20 选项，或两级 coarse→fine 层次。
2. **零样本≠够用**：typed-decisions 基准上基座 0.362，微调后 0.766。生产关键判断建议用自己的标注数据微调（官方 Kaggle 2×T4 notebook 免费 4 小时跑完）+ 按域拟合温度校准。
3. **上下文短**：512–1024 token（multilingual 可到 8192，>4k 精度波动）。
4. 它是"决策器"，**不写代码、不生成文本**——别指望它替代 LLM 做开放生成。

---

## 四、各 Agent 怎么用上它

### 4.0 两条通用接入面（关键结论）

| 接入面 | 是什么 | 适合 |
|---|---|---|
| **MCP** | Laya 官方 `laya[mcp]` extra（本地 stdio server，`laya_predict`/`laya_decide`/`laya_predict_batch` 等工具）；或托管 `https://api.laya.studio/mcp`（Streamable HTTP，Bearer key，`decide`/`classify`/`yes_no`/`score` 6 个工具）；或社区现成包装（如 `YerikZ/laya-mcp`，把 triage/guard/moderate 包成 agent 友好工具） | 一切支持 MCP 的 agent |
| **HTTP `/v1/systemone`** | `laya-serve` 自托管，Jev 兼容 schema | 不支持 MCP 但能发 HTTP 的系统（自研 agent、后端服务、CI） |
| **进程内** | Python SDK（`from laya import Router`）/ `laya-ts`（Node、浏览器 ONNX） | 自研 agent 内部热路径、批量管线 |

### 4.1 AI Coding Agent 阵营

**Claude Code**（官方文档级支持 MCP，stdio + HTTP 都支持）：

```bash
# 本地自托管 MCP（推荐：免费、离线）
claude mcp add laya -s user -- /home/honya/.venvs/laya/bin/python /path/to/laya-mcp/server.py
# 或官方 laya[mcp] extra 提供的 server（仓库自带 MCP 入口，工具名 laya_predict/laya_decide 等）
# 或托管版（免本地 GPU/依赖）：
claude mcp add --transport http laya https://api.laya.studio/mcp \
  --header "Authorization: Bearer lsk_live_..."
# /mcp 确认连接
```

之后 Claude Code 在任务中可自然调用：判断任务难度/领域做模型路由（`smol` vs `slow` 档）、对抓取的网页/文件做注入与敏感信息守卫、对 PR 描述做分诊打标。

**oh-my-pi（omp）/ Pi agent**（omp.sh，Pi 的 coding-first fork）：

MCP 是一等公民——`/mcp add` 交互添加，或写配置文件（`mcpServers` schema，stdio/http/sse 三种 transport 都支持）：

```json
{
  "mcpServers": {
    "laya": {
      "type": "stdio",
      "command": "/home/honya/.venvs/laya/bin/python",
      "args": ["/path/to/laya-mcp/server.py"]
    }
  }
}
```

或直连托管版 `"type": "http", "url": "https://api.laya.studio/mcp"` + headers。另外 omp 本身有 `smol/slow/plan` 多角色模型路由——正好可以把 Laya 的 choice 判断用作"这轮任务该派给哪个 role"的前置门控（提示词里约定先问 Laya）。

**其他 coding agent（Codex、Gemini CLI、Cursor 等）**：同理，都是标准 MCP client，同一个 server 配置照抄。Laya 上游还自带 LangChain/LlamaIndex/CrewAI 集成（`laya[langchain]` 等），走框架栈的 agent 可以直接用 `LayaDecision` 节点/LlamaIndex selector。

### 4.2 通用 Agent / 个人助理阵营

**Hermes Agent（本系统）**：

- **原生 MCP 客户端**：`config.yaml` 里声明 MCP server（stdio 或 HTTP）即自动发现工具，注册为 `mcp__<server>__<tool>`，用法与调用其他 MCP 一致。配置指向本地 `laya[mcp]` server 或 `api.laya.studio/mcp` 即可，无需写代码。
- 即便不配 MCP，也可以用 `execute_code` 起一个持有 `Router` 的持久 kernel 做进程内调用（变量跨调用保留），或 `terminal` 里跑 `laya --preset ...` CLI——但正式用法还是 MCP。

**QwenPaw**（AgentScope 团队的开源个人助理）：

- 文档级 MCP 集成：Console → 设置里管理 MCP client（stdio/HTTP）；v2.0 的 Drivers 层是协议中立的 MCP/A2A/ACP 连接器，带加密凭据与 per-call 策略门控。
- 接法与上面一样：本地 `laya[mcp]` stdio server 或托管 HTTP endpoint 填进 MCP 配置即可，agent 获得 decide/classify/yes_no/score 工具。

**DSH（DeepSeek Harness）**：

DSH 的哲学是"everything is a plugin"，MCP 通过插件挂载（内置 `@deepseek-ai/dsh-mcp-client` 只支持静态 headers 的 HTTP；社区插件补齐 stdio 与 OAuth）：

```bash
# 路线一：dsh-mcp-manager 插件（支持 stdio + HTTP + OAuth，推荐）
npx -p @deepseek-ai/dsh dsh plugin --profile web add github:hyqhyq3/dsh-mcp-manager
# 然后 设置 → MCP 页面加 server：
#   stdio: command=/path/to/python, args=[/path/to/laya-mcp/server.py]
#   或 HTTP: https://api.laya.studio/mcp + Bearer token
# 工具注册为 mcp__laya__decide 等，所有会话可见
# 路线二：dsh-plugin-mcp-support（settings.yaml 里 mcp-support.servers 声明）
```

**WorkBuddy（腾讯，桌面全场景 agent）**：

- 设置 → MCP 可视化配置（用户级 `~/.workbuddy/mcp.json` / 项目级 `<项目>/.workbuddy/mcp.json`），支持 stdio 命令与远程 HTTP + 标准 OAuth，工具配置完即自然语言可调；另有腾讯云 MCP 市场可逛。
- 接法相同：stdio 指向本地 laya-mcp server，或 HTTP 指向托管 endpoint。企业版（CodeBuddy 系）插件系统也支持 `.mcp.json` 随插件分发。

### 4.3 汇总：谁必须自己编码？

| Agent | 接入方式 | 需要写代码吗 |
|---|---|---|
| Claude Code | `claude mcp add`（stdio/http） | ❌ 一条命令 |
| oh-my-pi / Pi / Codex / Cursor 等 | `mcpServers` 配置 | ❌ 一段 JSON |
| Hermes Agent | config.yaml 声明 MCP server | ❌ 一段 YAML |
| QwenPaw | Console MCP 管理页 | ❌ 配置 |
| DSH | MCP 插件 + 设置页 | ❌ 插件安装 + 配置 |
| WorkBuddy | 设置 → MCP / mcp.json | ❌ 配置 |
| **自研 Agent 系统** | 三选一：① 支持 MCP 协议 → 纯配置；② 不支持 MCP 但能发 HTTP → 调 `/v1/systemone`（请求/响应就是两个 JSON 对象，client 几十行）；③ 要进程内低延迟/深度门控 → `pip install laya` 嵌 SDK，写"门控逻辑"（约百行级），**不需要碰模型本身** | ①❌ ②极少 ③少量 |

**必须自己编码的场景**（第③类的具体形态，供自研 agent 参考）：
- **每步门控**：agent loop 里每个动作前调 `router.predict` 问 noul "该动作有风险吗"，`p(risk) > 0.5` 拦截或升级审批——这是 hook 逻辑，写在你的 loop 里，模型不用动。
- **置信路由**：System 1 先答，`answer_confidence < 0.6` 才调 LLM（Jev 官方 "confidence-gated routing" 模式的开源等价物）。
- **批量管线**：如告警洪峰时用 `predict_batch` 一次性分诊 1000 条。

---

## 五、落地建议（PoC 计划）

**目标**：一周内在本机跑通"本地 Laya + 两个 agent 调用"，验证延迟与中文效果。

| 步骤 | 动作 | 通过标准 |
|---|---|---|
| 1 | `python3.10+ -m venv` + `pip install "laya[mcp,serve]"`（CPU torch） | `import laya` 成功，`laya --preset triage` 出结果 |
| 2 | CLI 中文测试：`laya "生产环境 API 挂了，要求退款，否则解约" --preset triage --model multilingual` | 路由到 multilingual，intent/urgency 合理，记录 CPU 延迟（预期 100ms–1s/问） |
| 3 | 起 `laya-serve`，curl `/v1/systemone` | 返回 Jev 同构 JSON |
| 4 | MCP 接入 Hermes Agent（config.yaml 加 stdio server） | 会话内能调 decide/classify 工具 |
| 5 | MCP 接入 omp（`/mcp add`） | 同左 |
| 6 | 按自己数据构造 50–100 条真实状态（告警/工单/消息），对比 Laya 判断 vs 人工标注 | 记录准确率与 ECE，决定是否值得微调 `typed-decisions` 检查点 |
| 7 | 决策：PoC 达标 → 部署为内网常驻服务（`compose.example.yml` 有 CPU/CUDA 两种 compose），全 agent 统一挂 MCP；不达标 → 退回 LLM 直判 | — |

**需要拍板的点**：
1. 算力：CPU 跑 322M multilingual 够 PoC（秒级/问）；要 33ms 级需挂 GPU（现有 L20/2080Ti 都远超 1GB 需求，可与 vLLM 服务共用卡，显存占比 <5%）。
2. 是否接受托管 `api.laya.studio`（数据出境/合规）还是坚持全本地（内网平台场景建议全本地）。
3. 是否值得微调：取决于步骤 6 的零样本准确率是否满足业务。

## 六、风险提示

1. **项目很年轻**：Laya 首个公开版本 2026-09-18，两周 29.5k★，迭代极快（25 个 release）——接口可能变动，生产接入 pin 版本（当前 0.3.22）。
2. **自述基准**：官方 vs Jev 的对比数字（快 7.8×、校准 3× 好）是作者自测，Jev 侧数字来自第三方；正式决策前用自己的数据测（步骤 6）。
3. **中文效果需实测**：multilingual 检查点覆盖 100+ 语言且官方 51 语言 sweep 显示 45/51 可用，但 CJK 具体领域（如中文告警文本）精度必须自测。
4. **choice >20 选项、长上下文、零样本精度**是三个已知硬边界（见 3.5），方案设计时避开或两级化。
5. 托管 MCP（laya.studio）按输入 token 计费（1 credit=1 input token），高频批量场景成本需评估——这也是"高频决策"选本地自托管的另一个理由。

## 七、本机实测（2026-10-01，CPU + laya 0.3.22，真实运行数据）

### 7.1 环境

- `~/.venvs/laya/`：Python 3.11 + torch 2.14.1+cpu + `laya[mcp]` 0.3.22
- 检查点：multilingual 322M，`~/.cache/huggingface/hub/models--convaiinnovations--laya`（国内需 `HF_ENDPOINT=https://hf-mirror.com` + **`HF_HUB_DISABLE_XET=1`**，否则 hf_xet 走 cas-server.xethub.hf.co 401——本机踩坑，正解是后者而不是 `HF_HUB_DOWNLOAD_XET`）
- 检查点冷加载 **6.0s**（一次性）；MCP server 首调含加载 **10.5s**；SDK 预热后单次 predict **~0.8s（CPU，4 问题一次前向）**

### 7.2 案例：中文 P1 告警（真实输出）

状态：`【P1告警】prod-face-recognition P95 延迟 120ms→4.2s，错误率 38%。门店刷脸门禁全部失败，约2000名员工无法打卡。昨晚22:00人脸模型热更新后出现。现场有领导参观。`

```
路由 : multilingual（脚本检测：non-Latin script (han, 79% of letters); the English checkpoint cannot read it）

choice  queue  → ml_platform
        分布: ml_platform 0.353 / infra 0.319 / network 0.278 / billing 0.025 / other 0.024
        置信度: 0.211  ← 低于 0.6 门控阈值
score   urgency → 期望等级 1.80/3
        分布: P3 0.074 / P2 0.130 / P1 0.721 / P0 0.074
        answer_confidence 0.721
noul    是否模型相关 → P(true) 0.9995
noul    是否需要升级 → P(true) 0.9924
```

**这次实跑最有价值的发现：门控按设计工作了。**
- noul 两个问题（是否模型相关、是否需升级）：概率 0.99+，直接可用，不用问 LLM
- score 紧急度：P1 概率 0.72，"大概率 P1、留了 P2 尾巴"——比 LLM 说"很紧急"可分支得多
- choice 队列归属：置信度只有 0.21（三选都 0.28–0.35，模型不确定）→ **按 `min_confidence=0.6` 门控应升级给 Qwen-27B 复核**，而不是把 0.35 的"ml_platform"当结论用。这正是"校准概率"的意义：模型**诚实地不确定**（零样本、中文运维域、5 选项），而不是像 LLM 那样自信地说错。

### 7.3 MCP stdio 会话实录（Hermes Agent 内部就是这个过程）

```
client → {"jsonrpc":"2.0","id":1,"method":"initialize",
          "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"hermes-agent-demo"}}}
server ← {"result":{"protocolVersion":"2025-06-18",
          "serverInfo":{"name":"laya","version":"0.3.22"},
          "capabilities":{"tools":{"listChanged":false},...}}}

client → {"jsonrpc":"2.0","method":"notifications/initialized"}
client → {"jsonrpc":"2.0","id":2,"method":"tools/list"}
server ← 8 个工具:
          laya_status / laya_route / laya_predict / laya_predict_batch /
          laya_route_batch / laya_shortlist / laya_preset / laya_decide
          （laya_predict 参数: state, questions, model, task, lang,
             max_len, head_max_len, min_confidence）

client → {"jsonrpc":"2.0","id":3,"method":"tools/call",
          "params":{"name":"laya_predict",
                    "arguments":{"state":{...告警...},
                                 "questions":{queue/urgency/is_model_related/needs_escalation}}}}
server ← {"result":{"content":[{"type":"text","text":"{answers..., routing, latency_ms: 10536.67, device: cpu}"}]}}
          （预热后 latency_ms 为百毫秒级 CPU / 33ms 级 T4）
```

注意 `laya_decide` 与 `laya_predict` 的区别：decide 带 `min_confidence` 时低置信项直接返回 `null`，适合"不确定就不许动作"的场景；predict 返回完整分布，适合让 LLM 自己看分布决策。演示用的 laya_predict 保留了完整概率分布。

### 7.4 Hermes Agent 接入配置（已实配并验证）

实际配置（`hermes mcp add` 写入 `~/.hermes/config.yaml` 的 `mcp_servers`）：

```yaml
mcp_servers:
  laya:
    command: /home/honya/.venvs/laya/bin/laya-mcp-async   # 包装器，见下方坑 1
    env:
      LAYA_MODELS: multilingual   # 只预载 multilingual（中文场景）
      LAYA_DEVICE: cpu            # 有 GPU 改 cuda，与 vLLM 共卡显存 <1GB
      HF_HUB_DISABLE_XET: "1"
      HF_HUB_OFFLINE: "1"         # 检查点已缓存，强制离线免每次 revision 检查
    connect_timeout: 120
    # timeout 未显式写：Hermes per-call 超时默认 300s（_DEFAULT_TOOL_TIMEOUT），
    # CPU 推理 8–30s 够用；若换 mcp 2.2 SDK 自研客户端注意其默认 10s 请求超时
```

`hermes mcp test laya` 实测：`✓ Connected (2781ms)，Tools discovered: 8`。工具注册名 `mcp_laya_laya_predict` 等。
**与 vLLM 的关系：两者互不感知**——vLLM 继续服务 Qwen-27B（System 2，OpenAI 兼容端点），Laya MCP server 是独立进程（System 1）；Hermes 同时挂两个，按门控决定哪边答。

**接入踩的两个坑（已解决，记录在此）**：
1. **官方 `laya-mcp-server` 的 main() 在 `server.run()` 前同步预加载检查点**（CPU 上 6–10s），期间事件循环不转 → mcp 2.2 SDK 客户端在 `initialize` 握手就 10s 超时（裸 JSON-RPC 不受影响，因为裸协议无客户端超时）。解法：包装器 `laya-mcp-async`（`~/.venvs/laya/bin/laya-mcp-async`，shebang 用 laya venv 的 python）把预加载放进后台守护线程，握手 0.8s 返回，首调撞上预热未完成则按需加载。
2. **mcp 2.2 SDK 客户端 `tools/call` 默认请求超时 10s**，CPU 上 `laya_predict` 要 8–30s → 自研 MCP client 时必须调大请求超时；Hermes 侧 per-call 默认 300s 无此问题（T4 GPU 上 33ms 则两边都无所谓）。
3. HF 下载坑：镜像 `hf-mirror.com` + `HF_HUB_DISABLE_XET=1`（`HF_HUB_DOWNLOAD_XET` 无效）；缓存就位后加 `HF_HUB_OFFLINE=1` 最干净。

### 7.5 实测结论

1. **架构可行**：MCP 接入零代码，8 工具注册，一次 tools/call 拿到三基元完整概率——全部验证。
2. **noul/score 在中文运维域零样本即可用**（0.99/0.72 置信）；**choice 多选项分类零样本不可靠**（0.21）→ 生产上要么选项 ≤3、要么微调、要么一律走"低置信升级 LLM"门控。
3. **CPU 百毫秒级单问**：PoC/低频场景够用；告警洪峰批量场景要上 GPU（33ms/问，7.2ms/问批量）或用 `laya_predict_batch`。
4. 演示脚本：同目录 `laya_demo.py`（SDK + MCP 双路演示，可复跑：`~/.venvs/laya/bin/python laya_demo.py`）。

---

## 八、资料索引

- Laya 官方：github.com/NandhaKishorM/laya（README 含全部 surface）、laya.convaiinnovations.com（创始人长文 + vs Jev 基准）、nandhakishorm.github.io/laya（hooks/structured/docker/langchain 指南）
- 托管 MCP 文档：laya.studio/docs/mcp、laya.studio/agents.md（agent 接入指引）
- 社区 MCP 包装：YerikZ/laya-mcp（Claude Code 示例）、PerryLink/laya-mcp（`laya-mcp serve/install`，自动注册到 harness）、ThinkFlowLab/system1-agents（jev|laya|cua 三模型可切的 System 1 agent 框架 + `s1a-mcp`）
- 第三方实测：dev.to vishalmysore "A 421M encoder beat a 1.5B LLM at running my agent"（浏览器内 agent 门控架构）、dev.to aifrontierpost "Laya: replace your LLM-as-a-judge with a 322M-parameter decision engine"（含 CPU 安装踩坑：先装 CPU torch）
- Agent 接入文档：omp.sh/docs/mcp、DSH 插件（dsh-mcp-manager / dsh-plugin-mcp-support）、QwenPaw 文档 MCP 章、WorkBuddy 文档 MCP-Guide（codebuddy.cn）、Hermes config.yaml native MCP client
- 同系列：《2026-09-23 Jev(System One Model)开源模型调研》
