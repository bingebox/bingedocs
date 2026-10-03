---
tags: [技术, LLM, AnyJev, Jev, 决策模型, 校准, vLLM, Qwen3.8-27B]
星期: 星期三
categories: [tech]
---

# AnyJev 调研：把任意 LLM 变成 Jev 风格决策模型

> 范围：AnyJev（Nokia Applied Research + 腾讯混元，Apache-2.0）的功能、档位机制、部署方式，以及与我们自建 vLLM + Qwen3.8-27B 推理服务的搭配方案。
> 信息来源：智猩猩 AI 公众号介绍文（2026-09-27 前后）、PyPI `anyjev 0.0.2`（2026-09-21 发布）、GitHub 仓库 `nokia-applied-research/AnyJev`（README 中/英 + `docs/levels.md` + `anyjev/backends/vllm.py` 源码）。
>
> **关联阅读**：
> - [Jev(System One Model)开源模型调研](2026-09-23%20Jev(System%20One%20Model)开源模型调研.md)
> - [Qwen3.8-27B各版本变体功能差异调研](Qwen3.8-27B各版本变体功能差异调研.md)
> - [2026-08-31 LLM使用教程-Transformer直觉到生产级调用](2026-08-31%20LLM使用教程-Transformer直觉到生产级调用.md)

## 结论先行

1. AnyJev 不是模型，是一个**轻量 Python 库**（纯 numpy 核心 + transformers/vLLM 后端，PyPI `anyjev`）。它不改模型权重、不做微调，只修一件事：**让从 next-token logits 里读出的决策可信**——修掉选项顺序偏置（零标签，L0）、修掉概率校准（100–500 条标签，L1）、再给一档最快路径（每题一个闭式 head 读中间层隐状态，L2）。
2. 它解决的核心痛点是运维数字而不是精度数字：Qwen3-8B / BANKING77 上准确率只涨 6 个点，但**"错误率 ≤5% 前提下可交给模型自动决策的流量"从 7.7% 涨到 52.0%**（七倍）。这正是我们平台里"分类/路由/质检类判断能不能免人工复核"的答案。
3. 与现有 vLLM 服务的搭配有两条路：
   - **A 路（推荐先做）**：现有 Qwen3.8-27B `--task generate` 服务 + `VLLMBackend`（走 `/v1/completions` + logprobs），直接跑 L0/L1，**现有服务只加一个 `--enable-prefix-caching` 参数即可**。
   - **B 路（上量后再做）**：另起一个**截断版 checkpoint 的 vLLM embed 服务**（pooler 输出 LAST 隐状态）跑 L2，决策端点 = 一个 pooling 服务 + 几 KB 的 head 文件。L2 比一次完整前向还便宜（8B 上 0.68×）。
4. 注意事项：`VLLMBackend` 依赖 vLLM 的 `allowed_token_ids` 请求参数（较新 vLLM 才有，需确认我们线上版本）；head/L1 artifact 与 (模型权重, 问题) 绑定——**量化 checkpoint（FP8/Q4）必须用同一个 checkpoint 拟合 head**，不能拿 FP16 的 head 迁到量化服务上。

---

## 一、它是什么、解决什么问题

### 1.1 Jev 范式的两个漏洞（AnyJev 的出发点）

Jev（TypeSafe AI，见关联阅读）的做法已被浏览器 Agent 生态广泛复刻（Browser-Use 的 jev-ultrafast、APUS fast-browser-use）：把合法候选映射成单个 Token，一次前向，直接比较候选 Token 的 logits。方向是对的，但**直接读 logits 有两个先天问题**：

| 问题 | 表现 | 后果 |
|---|---|---|
| 位置偏置 | 同一道题、同一个模型，仅把选项列表倒序，argmax 答案就换人（Qwen3-8B 上位置间先验权重差达 6.81 个对数单位，约千倍） | 结果不可复现，答案依赖选项排列顺序 |
| 概率未校准 | 模型说的 0.9 不代表九成把握（ECE 高达 0.240） | 无法设置信度阈值，一切流量都得人工复核，省不下人 |

AnyJev 的定位：**不绑定浏览器、不绑定任务、不微调，只负责让"从 logits 里读出的决策"可信**。模型权重一个字节都不动。开源 5 天 861+ stars（PyPI 显示 ~960）。

### 1.2 类型化问题接口

问题写成三种类型化 `Question`：

- `Question.choice(prompt, [选项...], name)` — 选择题，K 个选项
- `Question.noul(prompt, name)` — 是非题（读 "Yes or No" / "No or Yes" 两种列法）
- `Question.score(prompt, name)` — 量表打分题（序数分箱，不做轮转）

每个选项映射成 tokenizer 里的单 Token，一次前向后直接读这些 Token 的 logits。约束：**字母读法最多 26 个选项**（span 读法在路线图上，代码还没有）。

## 二、四个档位（核心机制）

每个 `Decision` 都带自己的 `level`，下游可以写 `require="L1"` 拒绝在更弱的档位上执行动作。

| 档位 | 需要的标签 | 做了什么 | 不做什么 |
|---|---|---|---|
| `raw` | 无 | 标签 Token 上受限 softmax（`max_tokens=1` + logprobs，即各 Jev clone 的做法） | 任何偏差/校准修正——**官方明说不要上线用它** |
| `L0` | 零 | ① K 种循环移位平掉位置偏置（对数空间几何平均，位置偏置若可加则被精确消掉）② 除掉无标签估出的标签先验（默认 batch 校准，强度 0.75） | 让不确定性可校准 |
| `L1` | 每题 100–500 条 | 在 L0 之上做温度缩放，产物是一个小 JSON artifact（温度 + 先验，按 (模型, 问题哈希) 索引） | 不改变排序，扛不过分布漂移 |
| `L2` | 每题 100–300 条 | 前向停在约 2/3 深度（Qwen3-8B 为 24/36 层），对该层隐状态解一个闭式线性 head（shrunk-LDA/ridge，CPU 上几秒），**每个状态只发一条 prompt** | 不能迁移到别的问题/别的模型 |

另有 `level="auto"`（请求级别，非档位）：每个问题自动走可用的最强档——有 head 走 L2，有温度 artifact 走 L1，否则 L0。

**L0 的代价与轮转预算（rotation budget）**：K 选项的 choice 最坏读 K 遍前向。`adaptive_shifts=True` 后逐轮读选项轮转、领先者拉开即停，停止门槛在**无标签**状态上用 Clopper-Pearson 置信上界校准（参照物是自己读满全轮的结果，所以零标签可证）。实测 Qwen2.5-7B、18 选 1：平均 7.2 轮（300 条里 600 条决策平均 4.1 轮），与完整结果一致率 0.987，vLLM 上吞吐 2.2×。**注意**：此档目前是 opt-in（0.2.0 起），官方在重测表格后会设为默认；停止条件用对数几率差而非概率差（概率差在 1 处饱和，是踩过的坑）。

**L2 的关键性质**：
- 砍深度通常是净赚不是取舍——中间层是比最后一层更好的线性特征空间（最后几层在忙"把答案变成 Token"）。Qwen2.5-7B 从 28 层砍到 18 层准确率略**升**、校准更好还更快。
- head 自己维护自己：解出后只有特征均值/方差在动，且从**无标签**流量里重估——换问法/换选项顺序会路由到同一 head，30 条无标签请求即可把改写后的问题从 0.65–0.70 拉回 0.74–0.75（全量重标注重拟合也只有 0.77）。真正需要新标签的只有全新问题。
- `d.observe(q, state, label)` 让标签从业务回路自己流进来（人工复核改过的、事后真实结果、被替换掉的 LLM 的输出），攒到 30 条自动解 head，之后 60/120 条自动重解。第 0 天零标签跑 L0，L2 自己长出来。
- 随包发布 5 个 Qwen3 模型的 head（`anyjev-heads/`，每模型 23 个 head、1.8–4.4 MB）。

### 2.1 实测数字（官方表格，Qwen 系）

零标签 vs 有标签（Qwen3-8B，BANKING77 20 分类，300 条测试）：

| | raw | L0 | L1 |
|---|:--:|:--:|:--:|
| 选项倒序后答案翻转率 | 0.230 | **0.073** | 0.077 |
| 准确率 | 0.747 | 0.803 | **0.807** |
| 校准误差 ECE | 0.240 | 0.184 | **0.095** |
| ≤5% 错误率下可自动决策流量 | 7.7% | 46.3% | **52.0%** |

L2（LocalLLaMA/typed-decisions，20 题 × 300 标签，2000 条留出）：

| 模型 | L0 | L2 | 读取层 | 相对完整前向开销 |
|---|:--:|:--:|:--:|:--:|
| Qwen3-1.7B | 0.494 | **0.730** | 18/28 | 0.70× |
| Qwen3-4B | 0.564 | **0.786** | 24/36 | 0.69× |
| Qwen3-8B | 0.647 | **0.771** | 24/36 | 0.68× |
| Qwen3-30B-A3B | 0.630 | **0.799** | 40/48 | — |
| Qwen3-32B | 0.700 | **0.798** | 52/64 | 0.84× |

（对照组：Jev 0.727、微调 421M 的 Laya 0.768，均作者公布数字；100 条标签 8B head 就到 0.740。）

### 2.2 局限性（官方自述，重要）

- L2 head 按 (问题, 模型) 拟合，不能迁移到新问题；目前只发布 Qwen3 系列的 head。
- 字母读法 ≤26 选项。
- typed-decisions 上的"准确率"是与教师 LLM 的一致性，不是人工判断。
- **校准救不了答不出来的模型**（迷宫/扫雷类任务没有任何读法能赢平凡基线）。
- L0 不是处处白赚：当某标签占绝对多数时 batch prior 会损失准确率（`docs/when_l0_helps.md` 有 230 个 (模型,问题) 点的测量）。
- 所有决策都是孤立评测的，**放进真实 Agent 循环的端到端对比还在路线图上**——我们在生产里用之前应自己测端到端。
- 2.2–2.7× 吞吐数字是两次运行区间（完整轮数参照值本身有跑间波动），不是单次挑选值。
- SGLang 暂不支持 L2；L2 需要后端能暴露隐状态（transformers 本地或 vLLM embed 服务的 pooler）。

## 三、安装与部署

### 3.1 安装

```bash
pip install "anyjev[hf]"   # 库 + transformers 后端（本地 HF 模型）
pip install anyjev          # 纯库（numpy）+ 自带后端（如对接现有 vLLM）
# 跑 benchmark 需要源码 checkout:
# git clone https://github.com/MorrisZJ/AnyJev && cd AnyJev
# pip install -e ".[hf,bench,dev]"
```

要求 Python ≥3.10。

### 3.2 无 GPU 冒烟测试（合成模型，CPU 一秒跑完 raw/L0/L2 全流程）

```bash
python -m demo.jev_mode --backend fake
```

### 3.3 最小代码（10 行）

```python
from anyjev import Decider, Question
from anyjev.backends.hf import HFBackend          # 本地 transformers 后端

d = Decider(HFBackend("Qwen/Qwen3-8B"))
route = Question.choice("这条工单该由哪个团队处理？",
                        ["账单", "技术", "销售", "其他"], name="route")

# L0 零标签即可跑：
d.decide(ticket_text, [route])["route"].distribution
# → {"账单": 0.81, "技术": 0.07, "销售": 0.02, "其他": 0.10}

# 有标签后：
d.fit_head(route, states, labels, layers=[-1])    # L2，100–300 条，闭式求解
# 或 L1: 温度缩放 artifact（100–500 条）
# 或渐进式: d.observe(route, state, label) 攒到 30 条自动解 head
```

### 3.4 vLLM 服务化部署（官方推荐路径）

```bash
# 1. 截断：只保留决策要读的层（约 2/3 深度）
python -m anyjev.truncate Qwen/Qwen2.5-7B-Instruct 18 ./qwen-b18

# 2. 起 embed 服务，让 pooler 原样交出 L2 要读的隐状态
vllm serve ./qwen-b18 --task embed \
  --override-pooler-config '{"pooling_type":"LAST","normalize":false,"softmax":false}'
```

```python
from anyjev.backends.vllm import VLLMBackend
d = Decider(VLLMBackend("http://localhost:8000", "./qwen-b18"), level="L2")
d.fit_head(route, states, labels, layers=[-1])
d.decide(ticket, [route])["route"].distribution
```

**一条命令全流程**（截断 → 起服务 → 拟合 head → 在留出集上报准确率/ECE/每决策毫秒数 → 全深度对照）：

```bash
python -m anyjev.pipeline Qwen/Qwen2.5-7B-Instruct --labels-from banking20
```

要点：
- L2 部署 = **一个 pooling 服务 + 几 KB 的 head**。不需要 logits、不解析文本、不生成任何 token。
- raw / L0 / L1 跑在 `--task generate` 的服务上，方式相同。
- transformers 上拟合的 head 与 vLLM 上服务的一致性：BANKING77-20 上 99.0% 答案相同，平均 |Δp| 0.0011——跨引擎部署可行。
- `--quantization fp8` 可用但官方**不推荐**（买延迟、损准确率）。
- 计时是 `--repeats` 次中位数（共享机器上单次计时能把同一配置报成又快又慢）。

## 四、与现有 vLLM + Qwen3.8-27B 服务的搭配

现有环境（见 2026-09-02 选型文档）：双 2080 Ti 跑 llama.cpp + Qwen3.8-27B-MTP-Q4_K_M（52 t/s）做实测机；L20 48GB 单卡 FP8 + vLLM 做主力推理服务（`http://vllm:38081/v1`）。

### 4.1 A 路：现有 generate 服务直接跑 L0/L1（零改造成本，先做这个）

`VLLMBackend` 的机制（源码 `anyjev/backends/vllm.py`）：对每个 prompt 发一次 `/v1/completions`，`max_tokens=1`、`temperature=0`、`logprobs=K`、`allowed_token_ids` 限制在候选 Token 上，多线程并发（默认 16 workers）。服务端 logit processor 之后报的 K 个 logprob 正好就是 K 个标签。

```bash
# 现有 vLLM 服务只需加这一个参数（K 个轮转 prompt 共享状态前缀，
# prefix caching 把轮转的重复前缀变便宜）
vllm serve <qwen3.8-27b-fp8> --enable-prefix-caching ...（其余原参数不变）
```

```python
from anyjev import Decider, Question
from anyjev.backends.vllm import VLLMBackend

d = Decider(
    VLLMBackend("http://vllm:38081/v1", "<模型名>",
                tokenizer_name="<tokenizer 本地路径>"),
    level="auto", adaptive_shifts=True)   # 轮转预算，K 选项题推荐开

# 第 0 天：零标签 L0 直接跑
route = Question.choice("这个告警该分派给哪个值班组？",
                        ["存储", "网络", "AI推理", "其他"], name="route")
print(d.decide(alarm_text, [route])["route"].distribution)

# 标签从业务回路流入（人工复核修正、事后真实分派结果）
d.observe(route, alarm_text, "存储")        # 攒到 30 条自动解 head → 该题升级到 L2

# 下游可以强制档位：低置信/低档位的决策走人工
dec = d.decide(alarm_text, [route])["route"]
if dec.level != "L2" or dec.distribution[dec.label] < 0.95:
    to_human_review()
```

**A 路注意事项**：
1. **`allowed_token_ids` 兼容性**：这是较新 vLLM 才有的 completions 请求参数。先在 L20 主力服务上确认当前 vLLM 版本支持；不支持的话要么升级 vLLM，要么把决策端点单独起一个小服务（见 4.2 的 1.7B/4B 选项），不影响现有主力服务的稳定性。
2. **token 一致性**：候选选项必须是 tokenizer 的单 Token（中文字符级 token 一般满足；多字选项需先验证 `tokenizer.encode` 后是否为 1 个 token，不是的话 AnyJev 会报出来）。选项列表 ≤26 个。
3. **量化一致**：L0 的 batch prior 是在线累积的（看到 8 条真实输入后才启用先验修正），换模型/换量化版本后应重置 Decider 实例。
4. 27B FP8 在 L20 上 prefill 很快，L0 的 K 次轮转 + adaptive 早停（平均远小于 K 次）开销可接受；这是"决策类小流量"，不占主力吞吐大头。

### 4.2 B 路：L2 专用截断 embed 服务（高 QPS 决策上量后）

L2 要读中间层隐状态，现有 generate 服务给不了（generate 服务只暴露 logprob）。方案：

```bash
# 1. 从主力 checkpoint 截断（Qwen3.8-27B 若为 64 层，取 2/3 ≈ 42 层；
#    实际层数先查 config.json 的 num_hidden_layers）
python -m anyjev.truncate <27b-fp8-checkpoint> 42 ./qwen3.8-27b-b42

# 2. 单独起一个 embed 服务（截断后模型更小，2080 Ti 16GB 甚至能直接装下
#    截断版，L20 上也只需一部分显存——可双卡并行部署决策端点）
vllm serve ./qwen3.8-27b-b42 --task embed \
  --override-pooler-config '{"pooling_type":"LAST","normalize":false,"softmax":false}' \
  --port 8001
```

```python
d = Decider(VLLMBackend("http://<host>:8001/v1", "./qwen3.8-27b-b42"), level="auto")
# fit_head / observe 流程同 A 路；head 产物是 (模型, 问题) 的小 JSON，
# export_artifacts()/load_artifacts() 可持久化与迁移
```

**B 路架构建议**：

```
业务系统
  │  决策类请求（分派/路由/质检/是否转人工）
  ▼
AnyJev 决策端点（薄 Python 服务，Decider level="auto"）
  ├── 有 head 的问题  ──▶ 27B 截断版 embed 服务（L2，0.68× 一次前向）
  ├── 有温度 artifact ──▶ L1（同一 embed 服务或 generate 服务）
  └── 其余            ──▶ L0（轮转 + 早停）
                              │
   人工复核队列 ◀── 低档位/低置信决策（require="L2" 或阈值兜底）
        │
        └── 修正结果 → d.observe(...) → head 自增长（30/60/120 条自动重解）
```

- 一个 vLLM 服务可同时承载 `--task generate`（L0/L1 走 completions）和 `--task embed`（L2 走 pooler）——但任务类型是服务级参数，所以实际上是**两个服务**（或同一 checkpoint 起两个实例）。用同一 checkpoint 保证 token 空间一致。
- head 文件几 KB~几 MB，按问题存好随服务启动加载（`load_artifacts`），重启不丢。
- **量化一致性硬约束**：head 是隐状态的线性投影，对数值精度敏感。用 FP8 服务拟合 head 就用 FP8 服务上线；从 llama.cpp Q4 实测机迁移到 vLLM FP8 主力时 head 要重拟合（100–300 条标签、秒级，成本可忽略）。

### 4.3 落地路线（建议）

- [ ] 确认 L20 主力 vLLM 版本支持 `allowed_token_ids`（不支持则决策端点单独起服务）
- [ ] 选 1–2 个真实高频决策问题试点（我们平台里典型候选：告警分派到值班组、工单分类、"这个结果能否直接下发"质检判断、截图检索结果是否可用）
- [ ] CPU 冒烟：`python -m demo.jev_mode --backend fake` 走通 raw/L0/L2 全流程
- [ ] 接现有 vLLM 服务跑 L0（A 路），用 300 条真实数据测翻转率/ECE/每决策毫秒数
- [ ] 从复核队列收集标签，`observe()` 攒够 30 条让 L2 head 自己长出来
- [ ] 用 `python -m anyjev.pipeline` 在本地复测官方数字（官方明确要求"别信我们机器的数字"）
- [ ] 端到端验证：把 L2 决策放进真实 agent/工单循环，与被替换的 LLM 文本判断对比（官方 roadmap 未完成项，生产前必须自测）
- [ ] 上量后评估 B 路（截断 embed 服务）的显存/延迟收益，决定是否拆出独立决策端点

## 五、与我们此前 Jev 调研的衔接

- 2026-09-23 那份调研回答的是"Jev 有哪些开源权重级替代"（Kev、Laya/Ollaya、NanoJev 等）；AnyJev 属于另一类——**不造模型，把任意现成 LLM 变成决策模型**，正好补上"我们已有 Qwen3.8-27B 服务、不想再部署专用小模型"的场景。
- 与 Laya（微调 421M）对比：AnyJev L2 用未微调的 4B 追平 Laya（0.786 vs 0.768），用 27B 则远超（0.799 量级，Qwen3-30B-A3B 数字）——前提是愿意为每个问题攒 100–300 条标签。
- 与 Browser-Use jev-ultrafast 的关系：那类项目读 raw logits（AnyJev 的 `raw` 档），AnyJev 可以视作它们的"可信层"升级——同一个前向读法，加上轮转去偏 + 校准 + 档位门禁。
