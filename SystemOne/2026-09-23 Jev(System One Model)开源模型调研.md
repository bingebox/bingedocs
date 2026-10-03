# Jev 技术（System One Model）开源模型调研

> 调研日期：2026-09-23
> 背景：TypeSafe AI 于 2026-09-15 发布首个 System One Model「Jev」。
> 核心命题：**unstructured state in, typed probabilistic decisions out**——不生成文本，单次前向传播直接返回带校准概率的类型化决策（Choice / Score / Noul 三种基元），70–500ms、$0.042/Mtok 输入（输出免费）。
> 本报告回答：**这个技术方向上有哪些开源模型/实现**，全部经 GitHub API 逐一验证（star/许可证/最近推送）。

---

## 一、Jev 技术要点（判断"同源"的标尺）

| 维度 | Jev 的做法 |
|---|---|
| 输出 | 三种类型化基元：`Choice`（枚举选择+概率分布+置信度）、`Score`（量表打分+概率+置信度）、`Noul`（真/假 0–1 概率） |
| 生成 | **零 token**：单次前向，末位 logits 掩码投影到候选槽位，局部 Softmax |
| 并行 | 一次请求多个问题共享 KV Cache 前缀，并行评估，加问题几乎不增加延迟 |
| 训练 | **RLCD**（面向校准决策的强化学习，优化 ECE 期望校准误差）；不可微调，全账号同一权重 |
| 接口 | `POST /v1/systemone`，`model` 字段选版本（jev-1.13.0 / jev-latest / jev-preview） |
| 基座 | 逆向/社区分析指向 Qwen 系小模型（官方未完全公开架构） |
| 生态 | 官方闭源 API；已接入 Vercel AI Gateway、OpenRouter、Cloudflare AI Gateway；官方开源件只有 `typesafe-ai/system-one-adapter-python`（277★, MIT） |

判断一个开源项目是否属于"Jev 技术"，看四条：**① 类型化问题接口（choice/score/noul 或等价物）② 非自回归/单次前向 ③ 输出校准概率+置信度 ④ 代码可直接消费的结构**。

---

## 二、开源直接替代模型（权重级，核心答案）

### 2.1 全量开源（模型权重 + 代码，多为 RLCD/非自回归原生架构）

| 项目 | Stars | 许可证 | 规模/架构 | 延迟 | 特点 |
|---|---|---|---|---|---|
| **Laya**<br>`NandhaKishorM/laya` | **19,349** | Apache-2.0 | 3 个检查点：ModernBERT-large 421M（EN，512 上下文）/ mmBERT-base 322M（100+ 语言，1024）/ typed-decisions 421M；内置 Router 按请求选检查点 | 33ms/问（T4），批量 7.2ms/问 | **生态最成熟**：PyPI `pip install laya` + HF 模型 + Colab；RLCD 训练（对严格恰当评分规则做 RL）；**Jev 兼容 HTTP 服务器**（`laya[serve]` 说 `POST /v1/systemone`，TypeSafe 客户端改 baseUrl 即可）；MCP server、LangChain/LangGraph、TypeScript 包、ONNX/TileLang 加速、Intel XPU。作者自称**比 Jev 早一年做出来**（dev.to 文章）；0.3.8 版、每日推送 |
| **von**<br>`wfzyx/von` | 547 | Apache-2.0 | 395M 非自回归 | **<15ms** | 定位"本地 Jev 替代"，校准概率 |
| **openJev-verdict-2.0**<br>`Heman10x-NGU/openJev-verdict-2.0` | 274 | NOASSERTION（需自读） | 151M 非自回归决策引擎 | — | 宣称在 LocalLLaMA/typed-decisions 基准上**同时超过 Jev 与 Laya**：77.10% acc、Brier 0.0636、ECE 0.0144；带自测套件。声明需自行验证 |
| **NanoJev**<br>`TianyuCodings/NanoJev` | 2,088 | MIT | 0.6B 并行决策模型 | — | **完整交付训练流水线+权重+数据集**，输出完整概率分布、无输出 token 解码——想自己复训首选参考 |
| **TinyJev**<br>`ankit-aglawe/tinyjev` | 3 | MIT | 596M 指针头模型（pointer-head） | 单次前向 | **MLX 优先**（Apple Silicon），System One 端点，权重在 HF/ModelScope；不确定时显式升级人工（conformal 思想） |
| **JevForge**<br>`zwliJay/jev-forge` | 24 | NOASSERTION | Qwen3.5-0.8B | — | 端到端研究栈：可审计数据构建 + 训练 + 固定 Mind2Web/OOD 评测 + 本地服务 + **RLCD 基线实现** |

### 2.2 接口级开源实现（开放权重兼容服务器，多数免训练）

思路：不造新模型，用现成开源模型 + **logits 投影 / NLI 交叉编码 / 前缀共享** 实现 Jev 接口。

| 项目 | Stars | 许可证 | 基座/方法 | 备注 |
|---|---|---|---|---|
| **SemIf**（前 OpenJev）<br>`TheoLeeCJ/SemIf-OpenJev` | **4,027** | MIT | 冻结 4B 模型（Qwen3.5-4B 等）末位 logits 直读选项概率 | **多后端**：MLX（Apple Silicon 前缀复用/共享态并行）、CUDA、PyTorch/MPS、llama.cpp GGUF（CPU）、**WebGPU 浏览器 Demo**；按工作负载温度校准；"3090 在家跑，无 waitlist" |
| **openjev**<br>`razorback16/openjev` | 345 | Apache-2.0 | **DiffusionGemma** | Jev 兼容决策服务器（扩散 LM 天然支持并行解码） |
| **openjev-sglang**<br>`ekzhang/openjev-sglang` | 291 | — | 开放模型，**prefill-only** | Jev 兼容 API 端点（只做前缀计算，最贴近 Jev 单次前向形态） |
| **Diffusion Jev**<br>`Hangzhi/diffusion-jev-sglang` | 2 | MIT | DiffusionGemma/SGLang | **视觉分类**：从图像像素做类型化 Choice（涂鸦/花卉识别），概率未校准 |
| **OpenDecision**<br>`deepanwadhwa/OpenDecision` | 55 | Apache-2.0 | 本地语义决策引擎 | "Jev 的开源等价物"，从结构化状态+文档回答三基元 |
| **FastJev**<br>`chengyongru/fastjev` | 18 | MIT | 钉住的开放模型 × Torch/vLLM/MLX/llama.cpp/**WebGPU** | 自托管 Python SDK，运行期定义 Choice/Boolean/Score，附逐行基准+校验和 |
| **LitJev**<br>`zhengxuyu/litjev` | 42 | Apache-2.0 | 任意 Qwen 模型 | **免训练**：把任意 Qwen 变成决策模型，同 `/v1/systemone` schema，不生成答案文本 |
| **ruling**<br>`bradAGI/ruling` | 6 | MIT | 任意 MLX 检查点 / OpenAI 兼容端点 | 免训练，从 logits 读三基元答案；官方 SDK 直插；256 条公开判定回放：231 vs Jev 238（McNemar p=0.21，统计上无法区分） |
| **jev-local**<br>`us/jev-local` | 3 | — | 开放权重 | 温度拟合校准，set3 n=1316 总体 0.83 |
| **poorjev**<br>`rupeshpoojary9/poorjev` | 7 | MIT | 商品级零样本 NLI 模型 | **温度缩放 + conformal 弃权**（不确定时弃权而非猜），校准评测 ECE 0.170→0.071，离线可跑、无 API key |
| **laya-mlx**<br>`mizorewww/laya-mlx` | — | — | Laya 检查点的 MLX 移植 | Apple Silicon 原生：13.4ms（多语言检查点 7.4ms）/短决策，零输出 token |
| open-alternative-jev / mini-jev / zhihz/openjev | 小 | — | 本地 LLM 承载 Jev 接口 | 各种小规模复现 |

### 2.3 RLCD / 约束解码研究脉络

| 项目 | 说明 |
|---|---|
| `vicksiyi/qwen-2.5-1b-rlcd`、`shamazharikh/qwen-rlcd` | Jev 发布后两小时内出现的 Qwen2.5-1B RLCD 复现（logits 掩码投影路线） |
| `drinkmoonshine/parallel-constrained-decoding`（HF Space） | RLCD 训练的 Qwen2.5-1B 演示：**开源并行约束解码**作为 Jev 的替代路径 |
| JevForge 的 RLCD 基线 | 目前能看到的最完整的 RLCD 开源参考实现 |

### 2.4 官方开源件

| 项目 | 说明 |
|---|---|
| **`typesafe-ai/system-one-adapter-python`**（277★, MIT） | TypeSafe 官方开源的 drop-in 适配器：在任意 OpenAI/Anthropic 兼容 LLM API 上运行 System One 评测——**官方承认"非 Jev 权重也能跑这个接口"**，等于给整个开源生态发了一张兼容证书 |

---

## 三、同技术脉络的前身/邻接开源模型（Jev 之前的"System 1 们"）

Jev 不是凭空出现：它的技术要素在开源世界各有一支前身。按功能分：

### 3.1 LLM 路由 / 意图选择（"Choice" 基元的直接前身）
| 项目 | Stars | 许可证 | 说明 |
|---|---|---|---|
| `lm-sys/RouteLLM` | 5,537 | Apache-2.0 | LMSYS 出品：强/弱模型路由（BT matrix、LLM-based 等策略），2024-08 后维护放缓 |
| `yuchenlin/LLM-Blender` | 995 | Apache-2.0 | Fuser（选择）+ Ranker（BART 125M–1.3B 小模型做候选排序）——**小模型结构化选择**的早期形态 |
| `stanford-futuredata/FrugalGPT` | 287 | Apache-2.0 | 级联调用策略（便宜模型先答，置信不足升级） |
| 社区新路由 | — | — | Jev 发布后涌现：`prismhq/jev-router`（LiteLLM 基）、Switchboard（"powered by Jev today, **Laya, Kev, Cua-S1** coming soon"——后两者是待上线的同类模型） |

### 3.2 安全/内容分类小模型（"Noul" 基元前身：小、快、出概率）
- **Llama 4 Prompt Guard 2**（Meta，HF）：22M / 415M 提示注入分类器，输出分数——Jev 安全分类用例（Vercel fx 用它替代 GPT，快 5–18×）的直接对照物
- **OpenAI Moderation**（已开源）：8 类内容审核分类
- `baaivision/JudgeLM`（443★, Apache-2.0）：7B 评审模型，输出多维分数

### 3.3 奖励/评审/重排模型（"Score" 基元前身：输出校准分数）
- `Qwen/Qwen2.5-*-RM`、`Skywork/Skywork-Reward-V2-*`（HF，开源奖励模型）
- `promptslab/Prometheus`（2）：结构化评审打分
- BGE-reranker-v2-m3、jina-reranker-m0：交叉编码重排器（premise-hypothesis 打分 = Laya 路线的同款数学）

### 3.4 投机解码草稿模型（最字面意义的"System 1"：快草稿服务慢校验）
| 项目 | Stars | 说明 |
|---|---|---|
| `SafeAILab/EAGLE`（EAGLE-3） | 2,540 | 特征层投机解码草稿模型，活跃（2026-02 推送） |
| `vllm-project/speculators` | 850 | vLLM 官方投机解码工具链，**2026-09-22 仍在推送** |
| Medusa 系列 | — | 多头并行草稿（免独立草稿模型） |

### 3.5 运维/时序决策（工业界的"System 1"老传统）
- `NetManAIOps/OmniAnomaly`（951★, MIT）：多变量时序异常检测（二值判定）
- 同类：DeepLog/MOML（日志异常）、Meta Sage（RL 调度）、Alibaba ARW（弹性伸缩预测）

---

## 四、选型建议（按场景）

| 场景 | 推荐 | 理由 |
|---|---|---|
| **生产环境替换 Jev API**（要稳定、多语言、运维省心） | **Laya** | 19.3k★、Apache-2.0、PyPI/HF/文档/基准齐全；`laya-serve` 直接兼容 `/v1/systemone`，客户端零改造；Router 自动选检查点；CJK 走多语言检查点 |
| **Apple Silicon 本地** | Laya（`laya-mlx` 13ms）/ TinyJev / SemIf（MLX 后端） | 三者都 MLX 优先 |
| **资源极小/边缘** | openJev-verdict-2.0（151M）/ von（395M, <15ms）/ poorjev（零样本 NLI+conformal 弃权） | 注意许可证与声明自证 |
| **想自己训一个** | **NanoJev**（流水线+权重+数据全包）/ JevForge（RLCD 基线+固定评测） | NanoJev 0.6B 门槛最低；JevForge 更偏研究可审计 |
| **不想训、用现成大模型快速验证** | SemIf（4B 直读 logits，多后端含浏览器 Demo）/ LitJev（任意 Qwen）/ ruling（连 OpenAI 端点 logits 都行） | 20 行级复现路径，适合 PoC |
| **多模态决策（图像）** | Diffusion Jev（DiffusionGemma/SGLang） | 目前唯一开源的 Jev 式视觉分类 |
| **学术对标/校准研究** | parallel-constrained-decoding Space + JevForge 基线 + poorjev 的 conformal 弃权 | 校准指标（ECE/Brier）是该领域真正的竞争维度 |

**组合拳（推荐的自建架构）**：Laya（或小检查点）做热路径高频决策 → 低置信度（如 <0.6）按置信度路由升级到 LLM（System 2）→ 用 SemIf/LitJev 做第二意见交叉校验。这正是 Jev 官方文档的 "Confidence-gated routing" 模式的开源等价物。

---

## 五、评测基准与指标

- **LocalLLaMA/typed-decisions**：社区公共基准（verdict-2.0、Laya 都以它为擂台；"51 个应用工作流、51 种语言"口径）
- **校准指标**：ECE（期望校准误差）、Brier score——比裸准确率更能区分 System One 模型（Jev 的核心卖点就是校准）
- **回放法**：ruling 的 256 条公开判定回放 + McNemar 检验，是目前对闭源 Jev 做可复现对比的干净方法
- 延迟口径注意：Jev 官方 70–500ms 是端到端（含网络）；开源项目多为本地前向（15–33ms），对比时要标注是否含 prefill/网络

## 六、风险提示

1. **发布潮水分**：awesome-jev（1,427★）明确警告"同一天批量提交的仓库要特别小心"——Jev 发布 48 小时内涌现几十个复现仓库（star 总量不小但多数 <100★），部分 star 可能是刷的；采用前跑仓库自带评测 + 自己数据验证。
2. **声明需自证**：如 verdict-2.0 "超过 Jev 与 Laya"、Laya "比 Jev 早一年"，都只有自述，无第三方复现。
3. **许可证参差**：verdict-2.0、JevForge 是 NOASSERTION（自定义条款），商用前读 LICENSE。
4. **校准≠能力**：开源小检查点上下文短（512–1024 token），长状态（Jev 支持 32k state）场景差距会拉开；Laya 的 Router/截断策略是补丁，不是同构能力。
5. **闭源事实**：Jev 权重与 RLCD 细节未公开，"Qwen 基座"来自社区逆向，官方未确认；其 64k 上下文并行前缀共享的工程实现（加问题近乎零边际延迟）开源侧目前只有 prefill-only 架构（openjev-sglang）部分逼近。

## 七、资料索引

- Jev 官方：docs.typesafe.ai（Introduction / Models / Patterns: speculative fan-out, confidence-gated routing, composite scoring, intent routing）
- 生态目录：`yibie/awesome-jev`（1,427★，14 个应用类别 340+ 条目）、`Anil-matcha/awesome-jev-by-typesafe`（815★）、`v-modal/awesome-jev-tools`（677★）
- 深度解析：jev.kuhung.me（架构逆向：logits 投影、KV 前缀共享、RLCD）、kelen.cc（发布日全记录）
- 核心仓库：本文件第二节所列（均经 GitHub API 验证，2026-09-16）

