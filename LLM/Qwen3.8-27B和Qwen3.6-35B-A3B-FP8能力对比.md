# Qwen3.8-27B 和 Qwen3.6-35B-A3B-FP8 能力对比

> 撰写日期：2026-08-16
> 数据来源（均为 ModelScope 官方仓库的 README 与仓库元数据，采集于 2026-08-16）：
> - [Qwen/Qwen3.8-27B](https://modelscope.cn/models/Qwen/Qwen3.8-27B)（2026-08-12 上传）
> - [Qwen/Qwen3.6-35B-A3B-FP8](https://modelscope.cn/models/Qwen/Qwen3.6-35B-A3B-FP8)（2026-04-16 上传）
>
> 注意：两个模型的官方 README 均**没有**把对方作为对比基线，本文中的"直接对比"基于两者 README 中**同名基准**的分数拼合而成，评测脚手架（harness）存在差异，差距数字仅供参考（详见文末"注意事项"）。
> 3月初是在Ollama上安装一些小模型, 3月30日开始在vLLM上使用Qwen3.5-35B-A3B-FP8， 4月17日开始使用Qwen3.6-35B-A3B-FP8, 8月15日安装Qwen3.8-27B。

---

## 一、结论速览（TL;DR)

| 维度 | 更强的一方 | 说明 |
|---|---|---|
| 纯模型能力（编码/推理/Agent） | **Qwen3.8-27B** | 更新的世代；8 个同名可比基准全部领先 3.2~12.9 分 |
| 多模态 Agent（电脑/浏览器/手机操控） | **Qwen3.8-27B** | OSWorld 84.3 等一组 3.6-A3B 未公布的强项 |
| 视觉理解（图文/文档/视频） | **Qwen3.8-27B（微弱）** | 重叠基准上仅领先 0.6~5.7 分，基本同档 |
| 推理效率 / 单 token 成本 | **Qwen3.6-35B-A3B-FP8** | MoE 每 token 仅激活约 3B 参数，理论计算量约为 27B 稠密的 1/9 |
| 高并发在线服务性价比 | **Qwen3.6-35B-A3B-FP8** | 解码算力需求低 + FP8 权重，吞吐/成本优势明显 |
| 本地/边缘部署门槛 | **Qwen3.6-35B-A3B-FP8** | 官方支持 KTransformers CPU+GPU 异构推理 |
| 思考深度控制 | **Qwen3.8-27B** | 独有 `reasoning_effort`（xhigh/medium/low）官方档级调节 |

一句话总结：**Qwen3.8-27B 是"能力优先"的新一代稠密旗舰（27B 全激活），Qwen3.6-35B-A3B-FP8 是"效率优先"的上一代 MoE 主力（35B 总参/3B 激活，FP8 量化）。前者单点能力全面占优，后者在每 token 成本、吞吐和本地部署上占优。选谁取决于你的约束是"要最强的效果"还是"要最便宜的可接受效果"。**

---

## 二、两个模型是谁

### Qwen3.8-27B（2026-08 发布，4 天前上线 ModelScope）

官方定位引自其 README：

> "Qwen3.8, the most capable generation in the Qwen open-model family to date... a compact, deployment-friendly dense model: a native vision-language model that understands images and videos, with flexible thinking control."

- 官方称之为"Qwen 开源家族迄今最强的一代"，主打编码、专业工作、研究和长程 Agent 任务。
- 发布 4 天，下载量 30,907，处于 ModelScope 置顶位（IsTop=99、IsNewModel）。
- 官方同时预告 Qwen Cloud 托管版"coming soon"：默认 1M 上下文、官方内置工具。
- 对比表中 Qwen 把 **Opus4.6 Max** 作为基线之一：Qwen3.8-27B 在 SWE-bench Pro（61.7 vs 53.4）、QwenSWEBench（79.0 vs 63.8）、OSWorld（84.3 vs 72.7）、IFBench（79.5 vs 62.5）上超过该闭源旗舰，在 Terminal Bench 2.1（73.0 vs 78.2）、GPQA Diamond（89.2 vs 91.3）、HLE（30.8 vs 40.0）上落后——即"开源 27B 逼近/部分超过闭源旗舰"的定位。

### Qwen3.6-35B-A3B-FP8（2026-04 发布）

- Qwen3.6 世代的**首个开放权重变体**（FP8 量化版），基座为 `Qwen/Qwen3.6-35B-A3B`，官方量化说明：
  > "The quantization method is fine-grained fp8 quantization with block size of 128, and its performance metrics are nearly identical to those of the original model."
  即下文引用 Qwen3.6-35B-A3B 原版分数时，默认 FP8 版性能"几乎一致"（官方口径，非独立复测）。
- 官方定位：强调**稳定性与真实生产力**，"prioritizes stability and real-world utility"，重点升级 Agentic Coding（前端工作流、仓库级推理）。
- 上线 4 个月，下载量 1,242,934，80 star，社区验证充分；DashScope（阿里云百炼）提供 `Qwen3.6-35B-A3B` 托管服务。

> 命名提示：Qwen3.8 README 里的对比基线 "Qwen3.6-27B" 是 3.6 世代的**稠密 27B**，与本文主角 Qwen3.6-**35B-A3B**（MoE）不是同一个模型，阅读时不要混淆。

---

## 三、规格与架构对比

| 项目 | Qwen3.8-27B | Qwen3.6-35B-A3B-FP8 |
|---|---|---|
| ModelScope 上传时间 | 2026-08-12 | 2026-04-16 |
| 世代 | Qwen3.8（新） | Qwen3.6（旧一代） |
| 模型类型 | **稠密（Dense）** | **MoE（混合专家）** |
| 参数规模 | 27B（全部激活） | 总 35B / **每 token 激活约 3B** |
| 层数 | 64 | 40 |
| 隐藏维度 | 5120 | 2048 |
| 词表/Embedding | 248,320（Padded） | 248,320（Padded） |
| 层布局 | 16 × (3×(Gated DeltaNet→FFN) + 1×(Gated Attention→FFN)) | 10 × (3×(Gated DeltaNet→MoE) + 1×(Gated Attention→MoE)) |
| Gated DeltaNet（线性注意力） | V 48 头 / QK 16 头，head dim 128 | V 32 头 / QK 16 头，head dim 128 |
| Gated Attention（全注意力） | Q 24 头 / KV 4 头，head dim 256，RoPE 64 | Q 16 头 / KV 2 头，head dim 256，RoPE 64 |
| FFN / MoE | 稠密 FFN，intermediate dim 17,408 | **256 专家，激活 8 routed + 1 shared**，expert intermediate dim 512 |
| MTP（多 token 预测） | 多步训练 | 多步训练（SGLang NEXTN×3 / vLLM qwen3_next_mtp 投机解码） |
| 视觉编码器 | 有（原生图像+视频，宣称支持小时级视频） | 有（原生图像+视频，长视频同样需调大 longest_edge） |
| 权重精度 | BF16，**约 27.78 GB** | 细粒度 FP8（block 128）+ 部分 BF16，**约 35.95 GB**（仓库存储 37.5 GB） |
| 上下文 | 原生 262,144，YaRN 扩至 **1,000,000** | 原生 262,144，YaRN 扩至 **1,010,000** |
| 许可证 | Apache-2.0 | Apache-2.0 |
| 架构类名 | Qwen3_5ForConditionalGeneration | Qwen3_5MoeForConditionalGeneration |

**架构解读：**

1. 两者同为 Qwen3.5 系混合注意力架构：3/4 层用 Gated DeltaNet（线性注意力，状态大小固定、长上下文成本极低），1/4 层用 Gated Attention（KV cache 随长度增长）。上下文上限因此都能轻松拉到 ~1M。
2. 关键分叉在 FFN：
   - **3.8-27B 是稠密**：每 token 过完整 27B 参数，理论计算量 ≈ 2×27B = 54 GFLOP/token [估算]，"每一分能力都要付全额算力"。
   - **3.6-35B-A3B 是 MoE**：256 专家中只激活 8+1 个，每 token 理论计算量 ≈ 2×3B = 6 GFLOP/token [估算]，**约为稠密 27B 的 1/9**。代价是所有专家权重都要驻留显存（35.95 GB > 27.78 GB），即"权重更重、计算更轻"。
3. 长上下文内存 [按注意力头配置估算]：KV cache 每 token 元素量，3.8-27B = 16 层×2×4 KV 头×256 ≈ 32,768；3.6-A3B = 10 层×2×2×256 ≈ 10,240，**前者约为后者 3.2 倍**；线性注意力状态前者也约为后者 2.4 倍。跑满 1M 上下文时，3.6-A3B 的显存压力更小。

---

## 四、功能（Feature）差异

| 功能 | Qwen3.8-27B | Qwen3.6-35B-A3B-FP8 |
|---|---|---|
| 思考模式 | 默认开，可按请求关闭 | 默认开，可按请求关闭（不支持 `/think` `/nothink` 软开关） |
| 思考深度调节 | **官方 `reasoning_effort`：xhigh（默认）/ medium / low** | README 未提供该档级参数 |
| 历史思考保留 `preserve_thinking` | **默认开启**（保留全部历史消息的思考块） | 默认关闭（只保留最近一轮思考，可显式开启） |
| 官方推荐采样 | 思考：t=1.0, top_p=0.95, top_k=20, min_p=0, presence=0.0；非思考：t=0.7, top_p=0.8, presence=1.5 | 思考(通用)：t=1.0, top_p=0.95, top_k=20, presence=1.5；思考(编码)：t=0.6；非思考同左 |
| 官方推荐输出长度 | 思考 ≤262,144 + 最终 ≤131,072（1M 上下文内） | 常规 32,768；竞赛级复杂题 81,920 |
| 工具调用/Agent | 支持；chat template 内建多步工具调用；托管版将带"官方内置工具" | 支持；提供 `qwen3_coder` tool-call parser、Qwen-Agent / Qwen Code 官方示例 |
| 视频理解 | 支持，宣称小时级视频 | 支持，长视频需调 `longest_edge=469,762,048`（224k 视频 token） |
| 长上下文方案 | YaRN（vLLM/SGLang/TokenSpeed 均给出具体参数） | YaRN（transformers/vLLM/SGLang/KTransformers 均给出具体参数） |
| 推理框架 | SGLang / vLLM / **TokenSpeed** 官方 cookbook/recipe | SGLang≥0.5.10 / vLLM≥0.19.0 / **KTransformers** / transformers serve |
| CPU+GPU 异构 | 未提及 | **官方支持（KTransformers）** |
| 托管服务 | Qwen Cloud 版即将上线（默认 1M 上下文） | DashScope 已上线（`Qwen3.6-35B-A3B`） |
| 文本-only 部署 | — | vLLM `--language-model-only` 跳过视觉编码器省显存 |

**功能层面的实质差异：**

- 3.8 多了 **`reasoning_effort` 三档**（xhigh/medium/low），可以在"质量-成本"之间官方化地调档；README 还特别提示：多步 Agent 任务中调低 reasoning effort 未必省总时长（可能因分析不足而重试）。
- 3.8 默认 `preserve_thinking=true`（全量保留历史思考），3.6 默认 false（仅最近一轮）——3.8 更激进地押注"完整推理链延续"对 Agent 的一致性收益。
- 3.6 独有 KTransformers 官方支持，这是**消费级/边缘硬件跑 35B 级模型**的官方通路，3.8 的 27B 稠密目前没有对等选项。

---

## 五、推理效率与部署成本

| 项目 | Qwen3.8-27B（BF16 稠密） | Qwen3.6-35B-A3B-FP8（FP8 MoE） |
|---|---|---|
| 权重体积 | ~27.8 GB | ~35.9 GB（FP8） |
| 每 token 激活参数 | 27B | ~3B |
| 每 token 理论计算量 | ~54 GFLOP [估算] | ~6 GFLOP [估算]（约 1/9） |
| 单流解码速度 | 较慢（计算密集） | **快得多**（只读激活专家的权重） |
| 并发吞吐/单请求成本 | 高成本 | **低成本**（典型"小激活 MoE 跑高并发"场景） |
| 长上下文（→1M）显存 | KV 增长更快（约为对方 3.2 倍 [估算]） | 更省 |
| 最低硬件形态 | 建议专业 GPU（多卡或大显存单卡+缩短上下文） | 可 KTransformers CPU+GPU 异构；vLLM 官方示例 TP8@262K |
| 投机解码 | MTP（多步训练） | MTP（官方给出 NEXTN×3 / 2 draft token 命令） |

**部署判断：**

- 同样的 GPU 上，**3.6-A3B 的单 token 解码速度和高并发吞吐显著占优**——这是 MoE 的结构性优势，与量化无关；FP8 再叠加一层显存/带宽节省。
- 3.8-27B 的算力成本约为对方的 9 倍 [估算]，**单流延迟敏感、批量小的场景**（如交互式 Agent 单用户深推理）差距会被放大；若走官方托管版（1M 上下文 + 内置工具）则把成本问题外包给 Qwen Cloud。
- 两者在 262K 上下文下都不是"一张消费级显卡轻松跑"的量级；3.6 的差异化答案是 KTransformers，3.8 目前答案是多卡/托管。

---

## 六、基准测试对比

### 6.1 两 README 重叠的同名基准（直接对比）

> Qwen3.6 侧分数为其原版（BF16）模型成绩；FP8 版按官方口径"几乎一致"。
> ⚠️ 两侧评测脚手架不同（3.8 多用 Claude Code harness、256K 上下文；3.6 SWE 系列用内部 bash+file-edit 脚手架、200K 上下文），**差距是参考值，不是严格 A/B 实验值**。

| 基准 | 能力 | Qwen3.8-27B | Qwen3.6-35B-A3B | 差值 |
|---|---|---:|---:|---:|
| SWE-bench Pro | 仓库级 Agentic 编码 | **61.7** | 49.5 | +12.2 |
| NL2Repo(-Bench) | 仓库级代码生成 | **42.3** | 29.4 | +12.9 |
| LiveCodeBench v6 | 竞赛编程 | **90.3** | 80.4 | +9.9 |
| HLE | 多学科高难推理 | **30.8** | 21.4 | +9.4（判官口径可能不同：3.8 注明 GPT-4o 判分） |
| GPQA (Diamond) | 科研推理 | **89.2** | 86.0 | +3.2（3.6 侧标注为 "GPQA"） |
| RealWorldQA | 真实场景视觉问答 | **85.9** | 85.3 | +0.6 |
| OmniDocBench 1.5 | 文档智能 | **91.1** | 89.9 | +1.2 |
| CharXiv (RQ) | 科学图表分析 | **83.7**（无CI）/ 90.2（有CI） | 78.0 | +5.7 ~ +12.2 |

**结论：8 个可对比基准全部由 Qwen3.8-27B 领先**；文本/编码侧差距大（+9.9~+12.9），视觉侧差距小（+0.6~+5.7）。

### 6.2 各自独有基准（无对方数据，仅作能力画像）

**仅 Qwen3.8-27B 公布**（偏"新一代 Agent 旗舰"画像）：

| 基准 | 分数 | 类别 |
|---|---:|---|
| Terminal Bench 2.1 | 73.0 | 终端 Agentic 编码 |
| QwenSWEBench | 79.0 | 软件工程（自研） |
| DeepSWE 1.1 | 42.2 | 深度 SWE |
| CoWorkBench | 70.7 | 长程办公协作 |
| JobBench | 33.4 | 职业任务 |
| Agents' Last Exam | Pass@1 20.4 / Score 42.9 | 前沿 Agent 任务 |
| IFBench | 79.5 | 指令遵循 |
| OSWorld-Verified | 84.3 | 电脑操控（Computer Use） |
| WebArena-Verified | 64.8 | 浏览器操控 |
| AndroidWorld | 81.9 | 手机操控 |
| RecreationBench | 47.1 | 应用复刻（自研） |
| ClawEval-MM | Pass@3 57.4 / Avg 56.9 | 多模态工具使用 |
| SWE-MM | 38.6 | 多模态软件工程 |
| Vision2Web | 62.9 | 视觉 Web 开发 |
| MathVision | 90.0（无CI）/ 94.6（有CI） | 视觉数学 |
| BabyVision | 65.7 / 85.6 | 视觉推理 |
| ERQA | 65.5 | 具身智能 |

**仅 Qwen3.6-35B-A3B 公布**（偏"上一代生产力主力"画像）：

| 基准 | 分数 | 类别 |
|---|---:|---|
| SWE-bench Verified | 73.4 | SWE（经典口径） |
| SWE-bench Multilingual | 67.2 | 多语言 SWE |
| Terminal-Bench 2.0 | 51.5 | 终端 Agentic 编码（版本与 3.8 的 2.1 不同，不可直接比） |
| Claw-Eval | Avg 68.7 / Pass^3 50.0 | 编码 Agent |
| SkillsBench | Avg5 28.7 | 技能 |
| QwenClawBench | 52.6 | 真实用户分布 Agent（自研） |
| QwenWebBench | 1397（Elo） | 前端代码生成（自研） |
| TAU3-Bench / MCPMark / MCP-Atlas / WideSearch | 67.2 / 37.0 / 62.8 / 60.1 | 通用 Agent/工具调用 |
| MMLU-Pro / MMLU-Redux / SuperGPQA / C-Eval | 85.2 / 93.3 / 64.7 / 90.0 | 知识 |
| HMMT Feb25 / Nov25 / Feb26 | 90.7 / 89.1 / 83.6 | 数学竞赛 |
| IMOAnswerBench / AIME26 | 78.9 / 92.7 | 数学竞赛 |
| MMMU / MMMU-Pro / MathVista / MMBench | 81.7 / 75.3 / 86.4 / 92.8 | 视觉综合 |
| CC-OCR / AI2D | 81.9 / 92.7 | OCR/图表 |
| VideoMME / VideoMMMU / MLVU / MVBench / LVBench | 86.6 / 83.7 / 86.2 / 74.6 / 71.4 | 视频理解 |

### 6.3 家族内定位参照（帮助理解量级）

- **3.8-27B vs Qwen3.6-27B（稠密，来自 3.8 的表）**：全线大幅提升——Terminal Bench 63.4→73.0，SWE-bench Pro 53.5→61.7，OSWorld 63.9→84.3，CoWorkBench 61.0→70.7，LiveCodeBench 83.9→90.3，HLE 24.0→30.8。说明 3.8 相对上一代是**大版本级**跃升，而非小修。
- **3.6-35B-A3B vs Qwen3.5-27B（稠密，来自 3.6 的表）**：Terminal-Bench 2.0 41.6→51.5（+9.9），但 SWE-bench Verified 75.0→73.4、HLE 24.3→21.4、MMLU-Pro 86.1→85.2 略降或持平，数学竞赛与知识基本打平（AIME26 92.7 vs 92.6）。即 3.6-A3B ≈ "3.5-27B 的能力，3B 激活的成本，Agentic 编码更强"。
- 串起来看：**3.8-27B（新稠密）> 3.6-35B-A3B（旧 MoE）>≈ 3.5-27B（旧稠密）**，而 3.6-A3B 与 3.5-27B 是"能力近似、成本悬殊"的一对。

---

## 七、分领域能力判断

1. **Agentic 编码 / 软件工程**：Qwen3.8-27B 明显更强。SWE-bench Pro +12.2、NL2Repo +12.9，且 DeepSWE/QwenSWEBench 这类长程仓库任务分数（42.2 / 79.0）是 3.6-A3B 未涉足的深水区；3.6-A3B 的 SWE-bench Verified 73.4 放在 2026 年仍属第一梯队，只是不再是"最强"。
2. **纯推理 / STEM**：Qwen3.8-27B 领先（LCB v6 90.3 vs 80.4，GPQA 89.2 vs 86.0，HLE 30.8 vs 21.4）。但注意 3.6-A3B 的数学竞赛分数本身很高（AIME26 92.7、HMMT 83.6~90.7），只是 3.8 的表里没有同口径对照，不能断言 3.8 数学全面碾压 [无直接数据]。
3. **知识**：3.6-A3B 的 MMLU-Pro 85.2 / MMLU-Redux 93.3 / C-Eval 90.0 接近稠密 3.5-27B 水平；3.8 未公布 MMLU 系，无法直接比 [无直接数据]，但其 IFBench 79.5（指令遵循）为两者中唯一公布值，很高。
4. **视觉理解**：**基本同档**。重叠项上 3.8 小幅领先（RealWorldQA +0.6、OmniDocBench +1.2、CharXiv +5.7），而 3.6-A3B 有一整套扎实的 VL 成绩（MMMU 81.7、MathVista 86.4、VideoMME 86.6、CC-OCR 81.9），说明其视觉并非短板——"MoE 小激活"在视觉任务上并没有明显掉队。
5. **多模态 Agent（Computer/Browser/Mobile Use）**：目前只有 Qwen3.8-27B 公布了这一组（OSWorld 84.3、WebArena 64.8、AndroidWorld 81.9、RecreationBench 47.1），且 OSWorld 分数超过多个闭源旗舰。**在"看屏幕操作电脑/手机"这类任务上，3.8-27B 是明确的更优选择**（3.6-A3B 无对应数据，不能直接说它弱，但选型时应把这一票投给 3.8）。
6. **视频理解**：都支持小时级长视频（都需调大 `longest_edge`）；3.8 的表未含 VideoMME 类基准 [无直接数据]，3.6-A3B 公布 86.6（带字幕）。此项视为平手。

---

## 八、选型建议

**选 Qwen3.8-27B，当：**

- 目标是"效果上限"：长程 Agentic 编码、仓库级开发、Office/研究类长任务、Computer Use（截图操作电脑/浏览器/手机）。
- 有充足 GPU 算力（或多卡/上 Qwen Cloud 托管），能接受稠密 27B 的算力成本。
- 需要官方 `reasoning_effort` 档级调优、全量 `preserve_thinking` 的 Agent 会话一致性。

**选 Qwen3.6-35B-A3B-FP8，当：**

- 目标是"性价比"：高并发在线服务、多租户 Agent 平台，每 token 成本是主要约束——3B 激活意味着约 1/9 的计算量 [估算] 和更高的单机吞吐。
- 本地/边缘/混合硬件部署：KTransformers CPU+GPU 异构是官方通路；或 vLLM `--language-model-only` 纯文本省显存。
- 任务难度中等（常规 SWE、终端操作、OCR/文档、多模态问答）：3.6-A3B 在这类任务上已是第一梯队（SWE-bench Verified 73.4、CC-OCR 81.9、VideoMME 86.6），且经过 4 个月、百万级下载量的社区验证，成熟度更高。
- 需要今天就用的托管 API（DashScope 已上线）。

**折中策略**：把 3.6-35B-A3B 作为"默认档"高并发入口，把 3.8-27B（或其托管版）作为"难任务升级档"，用路由按任务难度分流——这是两者定位差异天然支持的架构。

---

## 九、注意事项（比较的边界条件）

1. **无官方正面对决**：两个 README 的对比表中没有共同模型，本文重叠基准的拼合比较受两侧评测脚手架影响——3.8 的 SWE 系用 Claude Code harness、256K 上下文，3.6 的 SWE 系用内部 bash+file-edit 脚手架、200K 上下文；Terminal Bench 版本不同（2.1 vs 2.0，不可比）；HLE 判分模型口径可能不同。
2. **FP8 精度**：Qwen3.6 侧分数是原版模型成绩，FP8"几乎一致"是官方声明而非独立复测。
3. **数据新鲜度**：Qwen3.8-27B 发布仅 4 天，无第三方独立评测与社区踩坑记录；Qwen3.6-35B-A3B 有 4 个月积累。3.8 的分数在真实环境中的方差尚待观察。
4. **估算值标注**：文中"每 token 计算量 1/9"、"KV 显存 3.2 倍"等是基于架构参数（激活参数数、注意力层数/KV 头数）的粗略估算，未计入路由开销、注意力与其他小项。
5. **基准覆盖面差异**：3.8 偏 Agent/计算机使用类新基准，3.6 偏经典编码/知识/竞赛数学，部分领域（数学竞赛、MMLU 系、VideoMME 系 vs Computer Use 系）一方有数据另一方没有，对应结论已标注"无直接数据"。

---

## 十、附：两模型关键数字一览

| | Qwen3.8-27B | Qwen3.6-35B-A3B-FP8 |
|---|---|---|
| 参数 | 27B 稠密 | 35B MoE / 3B 激活（256 专家，8+1） |
| 权重体积 | ~27.78 GB（BF16） | ~35.95 GB（FP8 block-128） |
| 层数/隐层 | 64 / 5120 | 40 / 2048 |
| 上下文 | 262K 原生 → 1M | 262K 原生 → 1.01M |
| 思考控制 | 默认思考；reasoning_effort xhigh/medium/low；preserve_thinking 默认开 | 默认思考；preserve_thinking 默认关（可开） |
| 视觉 | 图像+视频（小时级） | 图像+视频 |
| 下载量（2026-08-16） | 30,907 | 1,242,934 |
| 许可证 | Apache-2.0 | Apache-2.0 |

## 十一、vLLM上部署两个模型

### 1. Qwen3.5-35B-A3B-FP8 运行命令

```
    APP_HOME="/home/llm/vllm_qwen36"
    MODEL_PATH="/home/llm/modelscope_models/Qwen3.6-35B-A3B-FP8"
    
	export CUDA_VISIBLE_DEVICES=0
	export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
	export VLLM_USE_FLA=OFF
	export FLASHINFER_DISABLE_VERSION_CHECK=1
	export VLLM_USE_FLASHINFER_SAMPLER=0
	export VLLM_DISABLE_FLASHINFER=1

	nohup $APP_HOME/venv/bin/python -m vllm.entrypoints.openai.api_server \
	  	--model $MODEL_PATH \
		--served-model-name my-coder-llm \
		--api-key sk-xxxxsssssesssssssssssss \
		--host 0.0.0.0 \
		--port 8000 \
		--tensor-parallel-size 1 \
		--max-model-len 262144 \
		--reasoning-parser qwen3 \
		--gpu-memory-utilization 0.9 \
		--enable-auto-tool-choice \
		--enable-prefix-caching \
		--trust-remote-code \
		--max-num-seqs 8 \
		--tool-call-parser qwen3_coder \
		--quantization fp8 \
		--kv-cache-dtype fp8 \
		--enable-chunked-prefill \
		--max-num-batched-tokens 4096 \
		 >>$APP_HOME/vllm.out 2>&1 &
```

### 2. Qwen3.8-27B 运行命令

```
    APP_HOME="/home/qwen38/ai/qwen38-27b"
    MODEL_PATH="/home/qwen38/ai/qwen38-27b/Qwen3.8-27B"

    export CUDA_VISIBLE_DEVICES=0
	export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
	export VLLM_USE_FLA=OFF
	export FLASHINFER_DISABLE_VERSION_CHECK=1
	export VLLM_USE_FLASHINFER_SAMPLER=0
	export VLLM_DISABLE_FLASHINFER=1

	nohup $APP_HOME/venv/bin/python -m vllm.entrypoints.openai.api_server \
	  	--model $MODEL_PATH \
		--served-model-name my-coder-llm \
		--api-key sk-xxxxsssssesssssssssssss \
		--host 0.0.0.0 \
		--port 8000 \
		--chat-template $APP_HOME/qwen38_chat_template_fixed.jinja \
		--tensor-parallel-size 1 \
		--max-model-len 262144 \
		--reasoning-parser qwen3 \
		--gpu-memory-utilization 0.95 \
		--enable-auto-tool-choice \
		--enable-prefix-caching \
		--trust-remote-code \
		--max-num-seqs 64 \
		--tool-call-parser qwen3_coder \
		--dtype bfloat16 \
		--enable-chunked-prefill \
		--max-num-batched-tokens 8192 \
		 >>$APP_HOME/vllm.out 2>&1 &
```

qwen38_chat_template_fixed.jinja是为了解决claude code发送high而异常的问题，把high转为xhigh即可。

### 3. GPU情况

```
$ nvidia-smi 
Sun Aug 16 16:20:15 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.173.02             Driver Version: 580.173.02     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA RTX PRO 6000 Blac...    Off |   00000000:84:00.0 Off |                  Off |
| 30%   33C    P8              4W /  300W |   92676MiB /  97887MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A           39139      C   VLLM::EngineCore                      92666MiB |
+-----------------------------------------------------------------------------------------+
```
