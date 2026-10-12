---
tags: [技术, LLM, 训练, 预训练, 微调, nanoGPT, L20, 部署]
星期: 星期日
categories: [tech]
---

# LLM 训练原理、L20 单卡训练可行性与 nanoGPT 入门

> 范围：① LLM 大模型怎么训练（预训练/后训练全流程与工具栈）、② 训练产物的本质与使用方式、③ L20 48GB 单卡能否训练最小 LLM（从零预训练 vs 微调的规模边界）、④ nanoGPT 是什么、怎么工作。基于 2026-10 对话调研整理。
>
> **关联阅读**：
> - [Qwen3.8-27B 各版本变体调研](2026-09-02%20Qwen3.8-27B各版本变体功能差异调研.md)
> - [LLM 使用教程-Transformer 直觉到生产级调用](../2026-08-31%20LLM使用教程-Transformer直觉到生产级调用.md)
> - [Qwen3.8-27B 和 Qwen3.6-35B-A3B-FP8 能力对比](Qwen3.8-27B和Qwen3.6-35B-A3B-FP8能力对比.md)

---

## 1. LLM 是怎么训练出来的

### 1.1 预训练（pretraining）——90% 以上的算力

- **数据准备**：爬取网页、书籍、代码、论文，清洗去重，用 tokenizer 切成 token（词元）。Llama 3 用了 15 万亿 token。
- **模型结构**：Transformer 解码器，堆几十上百层 attention + MLP 层。训练时给定前文，预测下一个 token 的概率分布，算交叉熵损失，反向传播更新权重。
- **循环**：取一小批 token → 前向计算 → 算损失 → 反向传播 → 更新参数 → 下一批。要跑几百亿步。
- **规模**：Llama 3 70B 用约 10,000 张 H100 跑数周，花费数千万美元；7B 小模型也要几百张卡跑几周。

### 1.2 后训练（post-training）——让模型"会对话、讲规矩"

1. **SFT（监督微调）**：几万~几十万条高质量"问题-回答"对话数据，学会对话格式和指令遵循。
2. **对齐**：早期主流是 RLHF（人类打分 → 训 reward model → PPO 强化学习）；现在主流转向 **DPO/GRPO** 直接偏好优化，不用训奖励模型、更省算力。Qwen、DeepSeek 的开源模型基本都是 DPO 或 GRPO 路线。
3. **长思维链训练**（可选）：用推理题目 + 强化学习（如 DeepSeek-R1 的做法），让模型学会"慢慢想"。

### 1.3 工具栈总览

| 环节 | 主流工具 |
|---|---|
| 基础框架 | PyTorch（绝对主流）、JAX（部分实验室） |
| 分布式并行 | Megatron-LM（张量并行）、DeepSpeed ZeRO/FSDP、3D 并行（TP+PP+DP） |
| 数据管线 | Tokenizers、Data-Juicer |
| 预训练代码 | 各家自研居多；开源：Llama-Factory（微调/训练一体） |
| 微调 | LLaMA-Factory、Axolotl、TRL（SFT/DPO/GRPO） |
| 推理部署 | **vLLM**（PagedAttention，吞吐之王）、TensorRT-LLM、**llama.cpp**（GGUF 量化、消费级显卡）、Ollama、TGI |
| 量化 | bitsandbytes、AWQ、GGUF 导出（llama.cpp 自带） |
| 硬件 | NVIDIA 为主（CUDA），H100/H800 训练，消费卡只能跑小模型或量化推理 |

## 2. 训练出来的大模型到底是什么

**一堆矩阵的数值文件**：

```
qwen3-8b/
├── config.json          # 结构定义：层数、hidden size、注意力头数
├── model-00001.safetensors   # 权重分片（几十 GB）
├── model-00002.safetensors
├── tokenizer.json       # token ↔ 文本的字典
└── generation_config.json
```

- "8B 参数" = 80 亿个浮点数，存在各层 attention/MLP 矩阵里；Q4 量化后 4.4GB，FP16 是 16GB。
- 没有任何"知识"以文字形式存在——知识、语言能力、风格全部**隐式编码**在数字里。
- 同一套权重可量化成 GGUF（llama.cpp）、AWQ（vLLM）、FP8 等格式，本质是同一堆数字的压缩表示。
- 例：本机跑的 `Qwen3.8-27B-MTP-Q4_K_M` = 270 亿参数压到 4bit 的 ~16GB GGUF 文件。

## 3. 怎么使用大模型

**A. 起推理服务（生产/团队用）**

```bash
# vLLM（L20 规划的主力方案）
vllm serve Qwen/Qwen3-8B --port 8080 --tensor-parallel-size 1
```

OpenAI 兼容 API：

```python
import openai
client = openai.OpenAI(base_url="http://localhost:8080/v1", api_key="EMPTY")
resp = client.chat.completions.create(
    model="Qwen3-8B", messages=[{"role": "user", "content": "你好"}])
```

**B. 本地跑（个人/无 GPU 服务器）**

```bash
ollama run qwen3:8b
# 或 llama.cpp
./llama-server -m Qwen3-8B-Q4_K_M.gguf
```

**C. 二次开发（微调）**：LLaMA-Factory / TRL 加载基座权重 → 喂自有数据做 SFT/DPO → 产出新权重 → 走 A/B 部署。

**D. Agent/工具底座**：推理服务 + 框架（如 Hermes）+ 工具调用（function calling）。

一句话总结：**训练 = 用海量文本把几百万个矩阵调到"能接上下文"；产物 = 装矩阵数值的文件夹；使用 = 加载进推理引擎，喂 token 进去、收 token 出来。**

## 4. L20 48GB 单卡能训练最小 LLM 吗

**结论：能。** 分两层——从零预训练和微调都可行，规模差几个数量级。

### 4.1 从零预训练"最小 LLM"（完全可行）

经验公式：训练成本 ≈ **6 × 参数量 × token 数** FLOPs。

| 规模 | 典型配置 | 数据量 | 预计耗时（单 L20） | 显存 |
|---|---|---|---|---|
| nanoGPT 玩具 | 50M~125M 参数 | ~5B token（The Pile 子集/FineWeb-Edu 抽样） | 2~6 天 | 8~16GB |
| GPT-2 Small | 124M 参数 | 10~20B token | 1~2 周 | ~16GB |
| GPT-2 Medium | 350M 参数 | ~100B token | 1~2 个月 | ~30GB |
| 7B 级别 | 从头训 | 需 1.4T+ token | **不可行**（单卡要几年） | 超出单卡 |

50M 模型 × 5B token ≈ 3 PFLOPs，L20 有效算力按 ~15 TFLOPs 算约 5~6 天。7B × 1.4T token ≈ 5.9 EFLOPs，单卡几年——这就是没人单卡训 7B 的原因。

**工具路线**（最透明）：

```bash
# 1. 数据：The Pile 子集或 FineWeb-Edu 小样本，tokenizer 预处理
# 2. 训练：nanoGPT（Karpathy 的 PyTorch 实现，单文件，最适合学习）
git clone https://github.com/karpathy/nanoGPT
# 改 model_config.py（n_layer/n_head/n_embd），bf16 单卡直接跑
# 3. 评测：lm-eval-harness 跑几个 benchmark
# 更工程化：HuggingFace Transformers + FSDP，或 Axolotl / LLaMA-Factory pretrain 模式
```

训出来的 50M 模型语言能力有限（补全短句、学文体），但**流程完整**：数据 → tokenizer → 前向/反向 → 权重文件 → 加载推理，与训 70B 无本质区别，只是规模小。

### 4.2 微调现成模型（L20 的真正主场）

实际工作里 99% 的"训练"，48GB 单卡很舒服：

| 方式 | 能跑的规模 | 显存 | 说明 |
|---|---|---|---|
| QLoRA（4bit 基座 + LoRA） | **7B~14B** 轻松，32B 紧 | 10~30GB | 最主流，bitsandbytes + PEFT |
| LoRA（bf16 基座） | 7B 舒服，13B 上限 | 20~40GB | 效果略好于 QLoRA |
| 全参 SFT | 1B~3B | 30~45GB（带激活检查点） | 7B 全参单卡勉强够、无余量 |

```bash
# 典型 QLoRA 微调 Qwen3-8B
# LLaMA-Factory 或 TRL(SFTTrainer + bitsandbytes nf4 + PEFT)
# 数据：几十~几万条 {instruction, input, output}
# 产出：adapter 几百 MB，合并后得到完整模型文件
```

### 4.3 针对本机环境的建议（双 2080 Ti + L20）

- **学原理/走流程**：2080 Ti 上跑 nanoGPT 训 50M~125M（11GB 显存够），一周内完整走通、看到 loss 收敛。
- **实际产出**：L20 上用 LLaMA-Factory 做 Qwen3-8B QLoRA 微调（运维日志、截图检索描述等业务数据），一天内训完，部署回 vLLM 即用。
- **注意**：L20 已规划 FP8 + vLLM 做推理，训练占满显存会顶掉推理服务——要么分时，要么训练放 2080 Ti（QLoRA 7B 能跑，慢）。

## 5. nanoGPT：是什么、怎么工作

### 5.1 定位

Andrej Karpathy（前 OpenAI 创始成员）写的**极简 GPT 训练框架**——定位"教学 + 可跑通"，不是生产系统。核心代码量极小但结构完整，是理解 LLM 训练最透明的公开实现。对比：生产级训练栈（Megatron-LM / DeepSpeed + 自研脚本）几十万行；nanoGPT 把"真实的 GPT 怎么训"压缩到**一个人几小时能读完全部源码**。

```
nanoGPT/
├── model.py      # GPT 模型本体，~300 行（CausalSelfAttention、MLP、GPT 类）
├── train.py      # 训练循环，~300 行
├── sample.py     # 推理：加载 checkpoint 自回归生成文本
├── bench.py      # 性能基准（TFLOPs 测量）
├── config/       # 超参预设（GPT-Small、GPT-Medium 等）
└── data/         # 数据预处理脚本（莎士比亚字符级、WikiText-103、OpenWebText）
```

### 5.2 工作流程

**数据侧（data/ 脚本）**：用 HuggingFace `tokenizers` 做 BPE 分词（或玩具任务字符级）→ 存成 `train.bin`/`val.bin`（纯 int32 数组，每个数一个 token id）→ 训练时按固定块读取，numpy memmap 切片，无 DataLoader 框架。

**模型侧（model.py）**：标准 decoder-only Transformer：

- `token_embedding`：token id → 向量
- `position_embedding`：位置编码
- N 层 `Block` = 多头因果自注意力（mask 未来位置）+ MLP（4 倍 hidden）+ 残差 + LayerNorm
- 末层 Linear：隐藏态 → 词表，输出每位置"下一个 token 的概率分布"

**训练循环（train.py，核心约 20 行）**：

```python
for step in range(max_iters):
    X, Y = get_batch('train')        # 采样一块 token，Y = X 右移一位
    logits, loss = model(X, Y)       # 前向，交叉熵损失
    model.zero_grad(set_to_none=True)
    loss.backward()                  # 反向
    torch.nn.utils.clip_grad_norm_(params, 1.0)
    optimizer.step()                 # AdamW 更新权重
    # 每 1000 步存 checkpoint（.pt）
```

工程部分：学习率 warmup → cosine 衰减；bf16 混合精度 + fp32 主权重 + 梯度缩放；**梯度检查点**（重算换显存，小显存训深模型的关键开关）；FlashAttention 可选；checkpoint 存完整优化器状态 + step 号可中断续跑；TensorBoard / W&B 日志。

**推理侧（sample.py）**：加载 checkpoint → 起始文本 → 循环"预测下一个 token → 采样 → 拼回序列"，temperature / top-k 控制随机性。

### 5.3 能力边界

| 能力 | nanoGPT | 生产栈（Megatron/DeepSpeed） |
|---|---|---|
| 单卡 / 简单多卡（DDP 数据并行） | ✅ | ✅ |
| 张量并行 / 流水线并行（模型切多卡） | ❌ | ✅ |
| ZeRO 优化器分片 | ❌ | ✅ |
| 复杂数据管线 / 动态采样 | ❌（故意不做） | ✅ |
| 10B+ 参数训练 | ❌ | ✅ |

适用边界：**模型小、能塞进单卡（或几卡数据并行）**——即从零训 50M~350M 的场景。

### 5.4 入门路径

```bash
# 经典入门：字符级莎士比亚（几分钟跑通全流程）
python data/shakespeare_char/prepare.py
python train.py config/shakespeare_char.py   # 十几分钟，8GB 显存够
python sample.py --out_dir=out-shakespeare-char

# 升级到真实语言：WikiText-103，GPT-Small（50M），几十小时
```

训完直接看 loss 曲线、生成质量、`bench.py` TFLOPs，完整闭环一周内可走一遍。可自由改造（换 RoPE、加 GQA、试新 attention 变体），社区不少论文复现基于它。

### 5.5 延伸：nanochat

Karpathy 于 2025 年发布的 **nanochat** 是 nanoGPT 的"完整版"：预训练 → SFT → RLHF 对齐 → Web UI 一条龙，约 10 万行，号称最小可运行 ChatGPT 复刻。目标若是"走通含后训练的完整流程"，看完 nanoGPT 后看它。

---

## 下一步

- [ ] 2080 Ti 上跑通 nanoGPT 莎士比亚字符级 demo，记录显存/耗时
- [ ] 准备 FineWeb-Edu/The Pile 小样本，L20 或 2080 Ti 训 50M~124M 模型
- [ ] LLaMA-Factory + Qwen3-8B QLoRA 微调业务数据试点（运维日志/截图描述）
- [ ] 训练与 vLLM 推理的 L20 分时/分卡排期
