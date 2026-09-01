---
tags: [技术, LLM, Transformer, API, 教程]
星期: 星期一
categories: [tech]
---

# LLM 使用教程：Transformer 直觉 → 采样参数 → 结构化输出 → 流式与错误处理

> 面向：会写代码、要直接调 LLM API（OpenAI 兼容协议）做工程落地的开发者。
> 每个知识点按"是什么 → 为什么 → 怎么用"展开，附可直接跑的示例代码。

## 1. Transformer 直觉：模型到底在干什么

### 1.1 一句话版本

**LLM 是一个"给定前文，预测下一个 token 概率分布"的模型。** 所有花哨的功能（对话、推理、function calling）都是在这个机制上反复采样 + 训练目标引导出来的。

```
输入: "北京的首都..."
模型输出下一个 token 的概率:
  是      0.62
  是     0.31
  为      0.04
  ...
取一个（采样规则见 §4）→ 拼回去 → 再预测下一个 → 循环到 EOS
```

### 1.2 内部发生了什么（够用版）

```
文本 → tokenizer 切成 token → 每个 token 变向量(embedding)
     → 堆叠 N 层 Transformer Block：
         ① Self-Attention：每个 token 回头看所有前文 token，
            决定"我现在该关注哪些前文"（Q/K/V 打分）
         ② FFN：对聚合后的信息做非线性变换
     → 最后一层输出：词表大小（几万个）的概率分布
```

关键直觉：
- **Attention 是"检索"，FFN 是"计算"**：模型回答问题 = 先用注意力从上下文里找相关信息，再用 FFN 加工。这解释了为什么上下文里**没有**的信息模型答不了（幻觉的根源之一）。
- **位置信息是"相对"的**：模型知道 token 的先后顺序，但越靠近序列**中间**的位置，注意力越弱（"lost in the middle" 现象）——重要信息放开头或结尾。
- **每次生成都是增量计算**：生成第 100 个 token 时不用重算前 99 个的表示（KV Cache），所以首 token 慢（prefill，要把全部输入过一遍），后续 token 快（decode，每次只算 1 个）。**这直接决定了流式体验和延迟成本模型（§5）。**

### 1.3 对工程最重要的三个推论

| 推论 | 工程后果 |
|---|---|
| 模型"看到"的是 token 不是字符 | 输入按 token 计费/限长，中文 1 字 ≈ 1~2 token |
| 模型只能依赖上下文 | Prompt 里不给的信息它不知道；历史要自己管理 |
| 输出是概率采样的 | 同样输入每次结果可能不同；要确定性就控温度（§4） |

---

## 2. Token 与上下文成本

### 2.1 Token 是什么

- 文本被切成子词单元。英文常见词 1 词 ≈ 1~2 token；**中文 1 个汉字通常 1~2 token**（取决于 tokenizer，GPT 系对中文偏贵，Qwen 系对中文更省）。
- 数字、代码、特殊符号切碎后更贵：`"1234567890"` 可能 = 4~6 token。
- 估算工具：`tiktoken`（OpenAI 系）、`transformers` 的 `AutoTokenizer`（其他模型）。**精确计费以模型自己的 tokenizer 为准。**

```python
# 快速估算
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B")
print(len(tok.encode("这是一条中文消息，用于估算 token 数量")))
```

### 2.2 上下文窗口与成本结构

**上下文窗口 = 一次请求能"塞进"模型的最大 token 数（输入 + 输出共享）。**

```
总 token = system prompt + 历史消息 + 用户输入 + 工具定义 + 模型输出
         └──────────── 每一轮都在涨 ────────────┘
```

成本公式（每次 API 调用）：
```
费用 = (输入 token × 输入单价) + (输出 token × 输出单价)
     输出单价通常是输入的 3~5 倍
```

**多轮对话的隐藏成本**：每轮都重发全部历史。10 轮对话、每轮平均 500 token 输入 → 第 10 轮的输入账单 ≈ 5000 token 起。**对话越长越贵，长对话必须做截断/摘要。**

### 2.3 控制成本的六个手法（按性价比）

1. **历史管理**：保留最近 N 轮 + 早期轮次摘要化；或"滑动窗口 + 首条 system 永远保留"
2. **精简 system prompt**：重复的指令放 system 里一次，不要每轮重说
3. **大输入先压缩**：长文档先 RAG 检索 top-k 片段，不要整篇塞
4. **工具定义瘦身**：function calling 的 schema 也计入输入 token，10 个工具 ≈ 1000+ token，只注册当前任务需要的
5. **小模型干粗活**：分类/抽取用 7B，推理用大模型（模型路由）
6. **`max_tokens` 封顶**：防止失控输出烧钱（详见 §4）

### 2.4 截断行为（必须知道）

- **输入超长**：各厂商行为不一——OpenAI 直接报错 400；有些网关静默截断（丢开头或丢中间）。**不要依赖静默截断**，自己算 token 提前处理。
- **输出达到 max_tokens**：响应 `finish_reason: "length"`，内容在句中戛然而止。生产代码必须处理这个分支（§6）。

---

## 3. 采样参数

模型输出的是概率分布，采样参数决定"怎么从这个分布里挑 token"。

| 参数 | 范围 | 作用 | 常用值 |
|---|---|---|---|
| **temperature** | 0~2 | 温度。低温=概率分布变尖锐（保守），高温=变平缓（冒险） | 事实/抽取 `0~0.3`；代码 `0.2~0.4`；创意 `0.7~1.0` |
| **top_p**（nucleus） | 0~1 | 从累积概率达到 p 的最小集合里采样。`0.9` = 只考虑概率累计 90% 的头部 token | `0.9~1.0` |
| **top_k** | 0~100 | 只从概率最高的 k 个 token 里采样 | 默认即可，一般不动 |
| **frequency_penalty** | -2~2 | 按出现**次数**惩罚已出现 token（防重复） | 0；啰嗦严重时 `0.3~0.5` |
| **presence_penalty** | -2~2 | 只要出现**过**就惩罚（鼓励话题扩展） | 0~0.3 |
| **seed** | int | 固定随机种子，同输入同参数尽量复现同输出 | 需要复现时设 |

### 3.1 两个最常见的误区

1. **temperature=0 ≠ 100% 确定**：理论上贪心解码应该确定，但分布式推理（浮点非结合律、batch 变化）会让 `temperature=0` 偶尔有微小差异。要严格复现：`temperature=0 + seed + 固定输入`，并理解仍不保证 bit 级一致。
2. **temperature 和 top_p 同时调**：一般**只动一个**。同时动两个，行为不可解释。推荐：日常用 `temperature`，需要"收窄候选集"时才用 `top_p`。

### 3.2 按任务类型给参数（可直接抄）

```python
PROFILES = {
  "extract":  {"temperature": 0,   "top_p": 1,    "max_tokens": 2048},   # 信息抽取
  "classify": {"temperature": 0,   "top_p": 1,    "max_tokens": 128},    # 分类
  "code":     {"temperature": 0.2, "top_p": 0.95, "max_tokens": 8192},   # 写代码
  "chat":     {"temperature": 0.7, "top_p": 0.9,  "max_tokens": 4096},   # 对话
  "creative": {"temperature": 1.0, "top_p": 0.95, "max_tokens": 4096},   # 创作
}
```

---

## 4. 结构化输出与 Function Calling

### 4.1 两种机制对比

| | **JSON Mode / Structured Outputs** | **Function Calling** |
|---|---|---|
| 目的 | 让模型**输出**结构化数据 | 让模型**决定调用哪个工具/函数**及参数 |
| 机制 | 解码时按 JSON schema 约束（constrained decoding，保证语法合法） | 模型输出"调用请求"JSON，**程序执行后把结果喂回去**继续生成 |
| 典型场景 | 抽取字段、打标签、生成配置 | 查天气、查数据库、执行代码 |
| 可靠性 | 格式 100% 合法；**字段值语义仍需校验** | 参数名/类型有约束；**可能不调用任何函数**（模型判断不需要） |

**核心心智模型：函数调用是"模型举手，程序执行"。模型永远不自己执行代码——它只输出调用意图。**

### 4.2 Function Calling 完整流程

```
① 请求：messages + tools=[函数schema]
② 模型响应：
   要么 A: 正常文本（content）
   要么 B: tool_calls: [{function: "get_weather", arguments: '{"city":"北京"}'}]
③ 程序自己执行 get_weather("北京") → "晴, 26°C"
④ 再发一次请求：messages + [
     {role: "assistant", tool_calls: [...]},        # 回显模型的调用
     {role: "tool", tool_call_id: "...", content: "晴, 26°C"}
   ]
⑤ 模型基于工具结果生成最终回答
   （可能还有第二轮 tool_calls，循环直到 finish_reason != "tool_calls"）
```

### 4.3 可运行示例（OpenAI 兼容协议，vLLM/DeepSeek/OpenAI 通用）

```python
import json, openai

client = openai.OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")

tools = [{
    "type": "function",
    "function": {
        "name": "query_order",
        "description": "按订单号查询订单状态",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "订单号"}
            },
            "required": ["order_id"],
        },
    },
}]

def query_order(order_id: str) -> str:
    return f'{{"status": "shipped", "order_id": "{order_id}"}}'

messages = [{"role": "user", "content": "帮我查一下订单 20260831-001 的状态"}]

# 循环处理（模型可能连续调多次工具）
for _ in range(5):
    resp = client.chat.completions.create(
        model="my-model", messages=messages, tools=tools, temperature=0)
    msg = resp.choices[0].message
    if msg.tool_calls:
        messages.append(msg)                       # 回显 assistant 消息
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = query_order(**args)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": result})
    else:
        print(msg.content)                          # 最终回答
        break
```

### 4.4 生产要点

- **arguments 是字符串不是 dict**：拿到要 `json.loads`，且模型偶尔会输出非法 JSON → 必须 try/except，失败时把错误信息作为 tool 结果回喂让它重试
- **description 就是 prompt**：写清楚"什么时候用这个函数、参数怎么填"，比函数名重要得多
- **参数校验别省**：模型可能编造 order_id 格式、传超范围数字；schema 管语法，业务校验管语义
- **工具数量克制**：一次挂 10~20 个以内，多了选择准确率下降、token 成本上升
- **`parallel_tool_calls`**：允许模型一次返回多个调用（默认开）；不想要就关
- **兜底路径**：`finish_reason` 既不是 `stop` 也不是 `tool_calls` 时（如 `length`），当作失败重试

---

## 5. 流式（SSE）

### 5.1 为什么用流式

由 §1.3 的延迟模型决定：prefill 时间 ≈ 输入长度 × 常数，**用户要等首 token 出现才能看到任何输出**。流式让"首字延迟"从"整段生成时间"降到"首 token 时间"，体感提升巨大。

### 5.2 SSE 协议长什么样

`stream: true` 后，HTTP 响应体变成一串 `data:` 行（Server-Sent Events）：

```
data: {"id":"...","choices":[{"delta":{"role":"assistant","content":""}}]}

data: {"id":"...","choices":[{"delta":{"content":"北"}}]}

data: {"id":"...","choices":[{"delta":{"content":"京"}}]}

...

data: {"id":"...","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

- 每个 chunk 是**增量 delta**，不是累积全文——客户端自己拼接
- `finish_reason` 只在**最后一个** chunk 出现
- 连接以 `data: [DONE]` 结束
- function calling 流式时，`delta.tool_calls` 里的 `arguments` 是**分段字符串**，要按 `index` 累积拼接后再解析

### 5.3 可运行的流式消费代码（Python，httpx 手写 SSE 解析）

```python
import json, httpx

def stream_chat(base_url, model, messages):
    url = base_url + "/v1/chat/completions"
    with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
        with client.stream("POST", url, json={
            "model": model, "messages": messages, "stream": True
        }, headers={"Authorization": "Bearer sk-xxx"}) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():          # 按行读
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].delta
                if delta.get("content"):
                    print(delta["content"], end="", flush=True)
                fr = chunk["choices"][0].get("finish_reason")
                if fr == "length":
                    print("\n[警告: 输出被 max_tokens 截断]", flush=True)
                elif fr == "stop":
                    print()
```

用 SDK 的话更简单：`stream=True` 后直接 `for chunk in stream: print(chunk.choices[0].delta.content or "")`。

### 5.4 流式工程要点

1. **客户端超时设置**：首 token 可能等 5~30s（长输入 prefill），`connect` 超时和 `read` 超时分开设；read 超时应设"两次 chunk 间隔"的阈值（如 60s），不是总时长
2. **中途断开 = 半截答案**：客户端断了服务端也会中止生成（省 token），但已生成的内容已计费
3. **前端渲染**：直接 append 到 DOM 没问题；但要防 XSS——内容进 DOM 前按纯文本处理，或转 HTML 后再显示 Markdown
4. **不要对每个 chunk 都触发前端 reflow**：攒到一帧（16ms）或一小段再渲染
5. **tool_calls 与流式**：能用非流式就别流式（多轮工具调用中间态复杂）；必须流式时按 index 拼 arguments
6. **网关/代理**：Nginx 前面记得 `proxy_buffering off;`，否则 SSE 会被缓冲成一次性吐出

---

## 6. 错误处理

### 6.1 错误分类与应对策略

| 错误 | HTTP | 含义 | 策略 |
|---|---|---|---|
| **429** rate_limit | 429 | 超 QPS/TPM 限额 | **指数退避重试**（1s→2s→4s，上限 30s），尊重 `Retry-After` 头；客户端加限流器 |
| **5xx / 网络超时 / 连接断** | 500/502/503/504 | 服务端故障 | 指数退避重试 2~3 次；流式中断了则整请求重发 |
| **400 invalid_request** | 400 | 参数错：超长、格式错、模型名错 | **不重试**（重试也是错），记日志告警 |
| **401/403** | 401/403 | 鉴权失败/key 额度用完 | **不重试**，告警运维 |
| **408/超时（客户端）** | — | prefill 太慢 | 重试一次；长期方案：降输入长度或换快模型 |
| **内容审查拦截** | 400 (content filter) | 触发安全过滤 | 不重试；对用户给友好提示 |

### 6.2 重试封装（生产级模板）

```python
import time, random, httpx

RETRYABLE = {429, 500, 502, 503, 504}

def call_with_retry(fn, max_attempts=3, base_delay=1.0, max_delay=30.0):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == max_attempts:
                raise
            delay = min(max_delay, base_delay * 2 ** (attempt - 1))
            delay += random.uniform(0, delay * 0.25)   # 抖动，防重试风暴
            time.sleep(delay)
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRYABLE or attempt == max_attempts:
                raise
            retry_after = e.response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after \
                    else min(max_delay, base_delay * 2 ** (attempt - 1))
            time.sleep(delay + random.uniform(0, 1))
```

### 6.3 六条生产军规

1. **所有 API 调用都要有 `max_tokens`**——没有封顶 = 没有成本上限
2. **超时必须有，且分两段**：连接 10s + 读 60~300s（按模型和输入长度定）
3. **finish_reason 必须检查**：`stop`（正常）/ `length`（截断，内容不完整！）/ `tool_calls`（要执行工具）/ `content_filter`（被拦截）
4. **流式错误**：SSE 流中途可能收到 `data: {"error": ...}` 或连接直接断——消费循环里要能识别，半截输出要标记为不完整（别把半截 JSON 当完整结果用）
5. **结构化输出 + 解析双重防护**：即使开了 JSON mode/schema 约束，解析仍要 try/except；失败时把解析错误回喂给模型重试一次（"你上次的输出不是合法 JSON，请重新输出"），两次失败走降级
6. **降级链**：主模型不可用 → 备用模型（换 base_url 重试同样的请求体，OpenAI 兼容协议的好处就是请求体通用）→ 静态兜底回复。降级要**对用户可见地诚实**（"当前响应较慢"），别假装一切正常

### 6.4 可观测性

每次调用记录一行结构化日志：`{request_id, model, input_tokens, output_tokens, finish_reason, latency_first_token, latency_total, status, retry_count}`。
`input_tokens/output_tokens` 在响应 `usage` 字段里（流式需加 `stream_options: {"include_usage": True}` 才会在最后 chunk 给）。

---

## 7. 速查卡

```
┌─────────────────────────────────────────────────────────┐
│ 调 LLM API 最小检查清单                                    │
├─────────────────────────────────────────────────────────┤
│ □ 知道模型上下文窗口多大，输入+输出会不会超                   │
│ □ 每轮请求都重发历史 → 长对话有截断/摘要策略                 │
│ □ temperature 按任务定（抽取=0，对话=0.7），别拍脑袋          │
│ □ max_tokens 永远设                                         │
│ □ 429/5xx 指数退避+抖动重试；4xx 不重试                      │
│ □ finish_reason 四种值全部处理                              │
│ □ JSON 输出：schema 约束 + 解析 try/except + 失败回喂重试     │
│ □ 工具调用：arguments 是字符串要 json.loads + 业务校验        │
│ □ 流式：按行解析 data:、拼 delta、[DONE] 收尾、               │
│   Nginx proxy_buffering off                                │
│ □ 日志记录 token 用量和延迟（含首 token）                     │
└─────────────────────────────────────────────────────────┘
```

## 参考

- OpenAI API 文档：https://platform.openai.com/docs（协议事实标准，vLLM/各家兼容协议都参照它）
- Anthropic "Building effective agents"：agent 与工具调用的工程模式
- Attention Is All You Need（2017）：Transformer 原论文
- 本地 vLLM 部署的 OpenAI 兼容端点：`http://vllm:38081/v1`（本项目环境）
