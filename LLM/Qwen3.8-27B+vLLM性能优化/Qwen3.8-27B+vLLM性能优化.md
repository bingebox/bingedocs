# Qwen3.8-27B + vLLM 性能优化

> 单卡 RTX PRO 6000 Blackwell（96GB）部署 Qwen3.8-27B 编程助手服务，262K 上下文、不牺牲推理效果的前提下，把稳态生成吞吐从 **~27 tok/s 提升到 80~105 tok/s（约 3~4 倍）** 的完整记录。
>
> 素材：本目录下 `vllm-log-01~08.txt`（各阶段真实日志）、`deepseek-web-chat-parse.txt`（与 DeepSeek 官方 web chat 的完整问答）、`serve-help.txt`（`vllm serve --help` 输出）、`grafana-01.webp`（Prometheus/Grafana 监控截图）。

## 1. 部署环境

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX PRO 6000 Blackwell **Max-Q** Workstation Edition，97,887 MiB（~96GB，GDDR7，带宽约 1792 GB/s），TDP 325W |
| 说明 | 机器上另有第二张 NVIDIA L20；vLLM 只跑在 `CUDA_VISIBLE_DEVICES=0`（PRO 6000）上，因此必须 `CUDA_DEVICE_ORDER=PCI_BUS_ID` 防止卡序错乱 |
| 模型 | `qwen38/Qwen3.8-27B`，27B 参数，BF16 权重约 54GB；含线性注意力（GDN 类）层——启动脚本里 `VLLM_USE_FLA=OFF` 就是控制这类算子的 |
| 框架 | vLLM **0.27.1**（`python -m vllm.entrypoints.openai.api_server`），FlashInfer 0.6.16.post3，CUDA 13.0（`/usr/local/cuda-13.0`），Python 3.12，sm_120 |
| 上下文 | `--max-model-len 262144`（256K），需 `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` |
| 服务 | 端口 38081，`my-coder-llm`；同时提供 `/v1/chat/completions` 与 Anthropic 兼容的 `/v1/messages?beta=true`（Claude Code 风格编程客户端在调用） |
| 功能 | `--reasoning-parser qwen3`（思考模式）、`--tool-call-parser qwen3_coder --enable-auto-tool-choice`（Agent 工具调用）、自定义 `qwen38_chat_template_fixed.jinja` 模板 |
| 负载特征 | 长系统提示词 + 代码/截图多模态输入（日志里的 `MM cache hit rate` 即多模态缓存命中率），典型 AI 编程助手流量 |

**优化约束**（本次全部决策的前提）：

1. **不牺牲推理效果**——不做权重量化（AWQ/GPTQ 都排除）；
2. **显存不能 OOM**——服务是生产中的编程助手，不能因为调参把服务搞挂；
3. **稳定优先于极限**——每次只动一个变量，可独立回退。

## 2. 性能基线（09-04，`vllm-log-01`）

优化前的稳态日志（每 10 秒一条统计）：

```
Engine 000: Avg prompt throughput: 91.0 tokens/s, Avg generation throughput: 46.1 tokens/s,
Running: 3 reqs, Waiting: 0 reqs, GPU KV cache usage: 27.7%,
Prefix cache hit rate: 43.4%, MM cache hit rate: 98.3%
```

同一时刻 `nvidia-smi`：

```
|   0  NVIDIA RTX PRO 6000 Blac...    Off | ...
| 54%   80C    P1            300W /  300W |   94292MiB /  97887MiB |    100%      Default |
```

（第一列 54% 是风扇转速，GPU 利用率是 100%；09-04 功耗被限在 300W，09-05 起恢复 325W 默认并开了持久模式。）

基线画像：

| 指标 | 基线值 | 评价 |
|---|---|---|
| 生成吞吐（2~4 并发合计） | 24 ~ 63 tok/s，典型 ~46 tok/s | 偏低：单请求体验约 10~20 tok/s |
| Prefill 吞吐 | 0 ~ 5,803 tok/s 剧烈波动 | 长 prompt 进 prefill 时波动正常 |
| KV Cache 使用率 | 26% ~ 50% | 健康 |
| Prefix cache 命中率 | ~43.5% | 一般，有提升空间 |
| MM cache 命中率 | 98.3% | 优秀（截图输入命中率高） |
| 温度 / 功耗 | 80°C / 300W 封顶 | 散热正常，功耗墙不是瓶颈 |

结论：**显存基本被吃满（94.3GB/97.9GB），但生成吞吐远低于硬件能力**——这是典型"配置没调到位"而非硬件不行。

## 3. 第一轮"AI 优化建议"的问题（重要教训）

把基线日志 + GPU 信息丢给 DeepSeek web chat 后，第一份建议里混着**正确、无用和直接错误**三类内容，必须逐条对照 `serve-help.txt` 甄别：

**方向正确的**：显存接近满载是首要风险、`--enable-chunked-prefill`、`--max-num-batched-tokens` 控制批大小、监控 P99 延迟。

**直接会破坏业务的**（如果照抄）：

```bash
--max-model-len 4096      # 本服务是 262K 上下文的编程助手，直接废掉核心功能
--dtype float16           # 模型是 BF16 权重，这不是精度加速
--quantization awq        # 手里根本没有 AWQ 量化权重，且违反"不牺牲效果"约束
--enforce-eager           # 禁用 CUDA Graph，decode 只会更慢
```

**编造的不存在的参数**：`--scheduler-delay-factor`、`--use-flash-attn`（0.27.x 用 `--attention-backend`）、`--max-num-partial-prefills`、`--enable-multi-step`、`--num-scheduler-steps`、`--use-v1`（V1 早已是默认引擎）等。

> **教训 1**：大模型 web chat 给的"一键优化脚本"是语料拼贴，**每一个参数都要对照自己版本 `vllm serve --help` / 官方文档验证**。
>
> **教训 2**（关于参数形态）：0.27.x 的 `vllm serve --help` 只展示 CLI 的一部分面，完整引擎参数可以用 `--config <file.yaml>` 配置文件方式传入（官方 `configuration/serve_args.html`）。本文 `serve-help.txt` 的抓取里看不到 `--max-num-seqs`、`--enable-chunked-prefill`、`--max-num-batched-tokens` 等经典参数，但实际环境里旧脚本带着它们一直正常运行——判断参数真伪以"服务是否接受 + 官方文档"为准，而不是单看 help 截取。

## 4. 显存预算：为什么这么紧

聊天里对齐过的显存估算（262K 上下文、FP8 KV）：

| 组件 | 大小 | 说明 |
|---|---|---|
| 模型权重 (BF16) | ~54 GB | 27B × 2 bytes，固定开销 |
| KV Cache（262K，FP8） | ~35 GB | 取决于层数 / head_dim，随并发线性增长 |
| 激活值 / 临时缓冲 | ~5 GB | 动态分配 |
| 其它（CUDA 上下文等） | ~2 GB | — |
| **合计** | **~96 GB** | **对 97.9GB 的卡基本没有余量** |

这个预算决定了本次优化的方法论：**不是"把参数往大了堆"，而是在权重 54GB 固定的前提下，把 KV 的精度、块大小、后端选对，同时把"预分配占满但没真正使用"和"真的分配失败"区分开。**

vLLM 启动时按 `--gpu-memory-utilization` **预分配** KV 池，所以显存常年 94~96GB 是正常现象，不代表要 OOM（DeepSeek 当时的比喻：银行备了 100 亿现金只贷出去 2.5 亿）。真正要看的是日志里的 `GPU KV cache usage` 和 `Waiting: N reqs`。

## 5. 踩坑记录

### 5.1 FlashInfer JIT 编译失败：`cuda_runtime.h: No such file or directory`（`vllm-log-02`）

第一次"优化"（FP8 KV + block-size 32 + autotune 等一把梭）启动即崩，根因藏在编译日志里：

```
(EngineCore pid=28878) FAILED: [code=1] .../flashinfer/0.6.16.post3/120f/cached_ops/batch_prefill_with_kv_cache_...
<command-line>: fatal error: cuda_runtime.h: No such file or directory
RuntimeError: Engine core initialization failed.
```

分析：FlashInfer 要为 sm_120 现场 JIT 编译 `batch_prefill_with_kv_cache`（head_dim 256、KV e4m3）内核，调用 `/usr/bin/nvcc` 编译——**编译器存在，但 `nohup` 拉起的后台进程没有继承 `CUDA_HOME` / `PATH`**，nvcc 找不到头文件 include 路径。"装了 CUDA" ≠ "服务进程看得见 CUDA"。

修复：启动脚本里显式导出（见第 9 节最终脚本）：

```bash
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
# LD_LIBRARY_PATH 可选：JIT 编译通常只需 CUDA_HOME+PATH；
# 若加了之后 torch 加载报错（ImportError / driver version insufficient），先注释掉它
```

### 5.2 堆参数 OOM：发一个 `hi` 都崩（`vllm-log-03/04/05`）

按第一版"优化配置"（`max-num-seqs 8`、`kv-cache-dtype fp8_e4m3`、`block-size 32`、`watermark`、`performance-mode interactivity`、`optimization-level 3`、`enable-flashinfer-autotune`、`enable-mfu-metrics` 全部叠加）启动后，服务起来了，但**发一个 "hi" 直接 OOM**：

```
[rank0]:[W905 00:28:47 CUDACachingAllocator.cpp:508] expandable_segments:
memory mapping failed with OOM on device 0 while trying to map 20971520 bytes
(free: 4521984, total: 101971460096)
```

`total: 101971460096`（≈95GiB）几乎全是 PyTorch 分配器已占空间，剩 4.5MB 空闲，连 20MB 都映射不出来。随后 `vllm-log-04` 里同样的告警刷屏。

复盘：问题不在单个参数，而在**一次全量改动**——FP8 KV 省下的显存被 autotune 的基准测试、更大 block、更高并发的预分配瞬间吃掉，加上 JIT 编译的临时缓冲，越过了 0.95 的红线。

**处理**：回退到改动前的稳定脚本（`vllm-log-05` 中的 start 函数：`gpu-memory-utilization 0.95`、`max-num-seqs 16`、`max-num-batched-tokens 8192`、BF16 KV、无 fp8/autotune），恢复"不管多少并发都稳定、只是慢一点"的状态：

```
Engine 000: Avg generation throughput: 26.9 tokens/s, Running: 1 reqs,
Waiting: 0 reqs, GPU KV cache usage: 2.5%, Prefix cache hit rate: 40.6%
```

显存稳定在 94,756 MiB / 97,887 MiB。

> **教训 3**：生产服务调参，**一次只动一个变量，每个变更观察至少一天**；出问题能精确定位是哪个改动引起的。所有"一把梭"式优化脚本，对生产环境都是事故预案。

## 6. 分阶段优化（最终走通的路径）

回退稳定基线后，与 web chat 反复对表（并对照 `serve-help.txt`），确定了下面的路线图——每步独立可回退：

| 阶段 | 改动 | 预期 | 回退方式 |
|---|---|---|---|
| 0 | 补 `CUDA_HOME`/`PATH`，确认 FlashInfer 已装 | 让 JIT 能编译 | 移除 export |
| 1 | 摘 `VLLM_DISABLE_FLASHINFER=1` + 加 `VLLM_ATTENTION_BACKEND=FLASHINFER`，**保留** `VLLM_USE_FLASHINFER_SAMPLER=0` | +10~30% | 加回 DISABLE |
| 2 | 加 `--kv-cache-dtype fp8_e4m3` | KV 带宽减半、容量翻倍 | 删参数 |
| 3 | （可选）FlashInfer autotune | 小幅提升 | 删参数 |
| 4 | （可选）逐个调 `max-num-batched-tokens` / `block-size` / 调度模式 | 各 +5~10% | 逐个回退 |

### 阶段一：启用 FlashInfer 注意力后端

改动只有两处（`VLLM_USE_FLASHINFER_SAMPLER=0` **必须保留**——Blackwell/SM120 上 FlashInfer 采样器有已知问题；`VLLM_USE_FLA=OFF` 保持不动，见第 8 节）：

```bash
# 移除: export VLLM_DISABLE_FLASHINFER=1
export VLLM_ATTENTION_BACKEND=FLASHINFER
```

**首次启动行为**：第一个请求触发 FlashInfer 对 sm_120 的 JIT 编译，服务卡住 2~5 分钟是**正常现象，千万不要重启**，产物缓存到 `~/.cache/flashinfer/` 后复用。随后日志里的这类告警也是正常的：

```
WARNING [jit_monitor.py:135] Triton kernel JIT compilation during inference:
batch_memcpy_kernel. This causes a latency spike;
consider extending warmup to cover this shape/config.
```

含义：某个 shape 的 Triton 内核在首个请求时才 JIT 编译，带来一次性延迟尖峰，之后走缓存。消除办法是启动后发几个不同长度的 mock 请求预热。

**关键插曲——"崩溃假象"窗口（`vllm-log-06`，14:57~14:59）**：阶段一刚上负载时日志非常吓人：

```
Engine 000: Avg prompt throughput: 9455.2 tokens/s, Avg generation throughput: 33.9 tokens/s,
Running: 5 reqs, ..., GPU KV cache usage: 79.8%, Prefix cache hit rate: 0.0%
Engine 000: ... Avg generation throughput: 0.6 tokens/s, Running: 5 reqs,
GPU KV cache usage: 99.0% ...
```

生成吞吐跌到 0.3~0.9 tok/s、KV 打满 99.7%，当时 web chat 的第一反应是"立即回退"。但继续观察（`vllm-log-07`，15:02 起，同一进程）系统自己恢复了：

```
Engine 000: Avg generation throughput: 72.4 tokens/s, Running: 4 reqs,
GPU KV cache usage: 72.0%, Prefix cache hit rate: 42.8%
```

复盘这个窗口：**冷启动 JIT + 长 prompt 批量 prefill**（prompt 吞吐 9,000~13,000 tok/s 的尖峰就是大请求在预填充）把 KV 瞬间打满，请求在 prefill 排队，decode 几乎停摆；等 prefill 消化完、进入 decode 主导的稳态，吞吐立刻回到 50~72 tok/s。

> **教训 4**：下"性能崩溃"结论前先拉开时间窗。10 秒粒度的统计日志里，一个 2~3 分钟的冷启动窗口长什么样，取决于你截图截在哪一秒。Grafana 的时间序列图（`grafana-01.webp`）比日志片段可靠得多。

Grafana 验证（15:00~15:10，阶段一稳态）：

- **Token 吞吐量（Prefill/Decode）**：Prefill 均值 3541 tok/s（峰值 8468），Decode 均值 41.1 tok/s（峰值 55.8）；
- **实时 Token 处理（按 Engine/TP Rank）**：Decode 从 20 爬升到 ~55 后稳定在 ~40 tok/s；
- 顶部 E2E P99 面板：3.30 min / 15.9 min（长上下文编程请求的正常量级）。

### 阶段二：FP8 KV Cache（`vllm-log-08`）

阶段一稳定运行后追加一个参数：

```bash
--kv-cache-dtype fp8_e4m3
```

作用：KV Cache 从 BF16 降为 FP8（e4m3），**KV 读取带宽减半、有效容量翻倍**，长上下文和并发场景受益最大；权重仍是 BF16，推理效果无损。

16:12 首个请求（冷启动 + FP8 相关 kernel 又触发一轮 JIT：`batch_memcpy_kernel`、`_bilinear_pos_embed_kernel`、`_apply_rotary_emb`）：prefill 11,272 tok/s，decode 20.3 tok/s，KV 仅 13.4%。

16:18~16:20 稳态（其间还有一条 `apply_token_bitmask_inplace_kernel` 的 JIT 告警——logprobs 相关内核首次编译，同样是预热问题，无害）：

```
Engine 000: Avg generation throughput: 105.2 tokens/s, Running: 5 reqs,
GPU KV cache usage: 62.9%, Prefix cache hit rate: 24.6%, MM cache hit rate: 50.0%
Engine 000: Avg generation throughput:  82.8 tokens/s, Running: 4 reqs,
GPU KV cache usage: 56.3%, Prefix cache hit rate: 31.1%
```

注意对比阶段一：同样 4~5 并发，KV 使用率从 72% 降到 56~64%——FP8 KV 的容量红利体现出来了，留给突发长上下文的余量更大。

## 7. 优化前后对比

| 指标 | 基线（09-04） | 阶段一：+FlashInfer | 阶段二：+FP8 KV |
|---|---|---|---|
| 稳态生成吞吐（2~6 并发合计） | ~27 tok/s（单请求场景）/ 典型 46 | 50 ~ 72 tok/s | **80 ~ 105 tok/s** |
| 相对基线 | 1× | ~2~3× | **~3~4×** |
| KV Cache 使用率（同并发） | 2.5%~50%（低负载） | 55%~72% | 56%~64%（更省） |
| Prefix cache 命中率 | ~40% | 17%→52%（随会话升温） | 17%~31% |
| 显存占用 | 94,756 MiB | ~96,500 MiB | 95,530 MiB（97.6%） |
| 温度 / 功耗 | 80°C / 300W 封顶 | — | 79°C / 324W（325W TDP 内） |
| 稳定性 | 稳定 | 稳定（冷启动窗口除外） | 稳定 |

## 8. 观念纠偏（web chat 说错/说偏的地方）

优化过程中 web chat 有几个判断需要纠正，记录下来避免误导后续调参：

1. **"超过了理论天花板"是错的**。聊天里用 `1792 GB/s ÷ 54 GB ≈ 33 tok/s` 算出"decode 理论上限"，再看到 105 tok/s 宣称"超出物理极限"。错误在于口径混用：**33 tok/s 是单请求（单流）decode 的带宽上限**——每次 decode 步都要把 54GB 权重从显存读一遍；而 105 tok/s 是 **4~6 个并发请求的合计吞吐**，权重的读取成本被 batch 摊薄了（decode 阶段所有请求共享同一次权重读取）。按每请求折算 ~20~25 tok/s，完全在物理预算内。总吞吐随并发上升、直到 KV/带宽先饱和——这正是 continuous batching 的意义。
2. **`NVIDIA_TF32_OVERRIDE=1` 对本部署基本无效**。TF32 只加速 FP32 的矩阵乘，而本服务权重和激活全程 BF16。它无害，但不是"1.5~2 倍加速"，最终脚本里保留或删掉都行，别把它算进收益。
3. **一批参数是编造的**。对照 `serve-help.txt`（0.27.1 实际抓取），下列在聊天中出现的参数**均不存在**：`--performance-mode`、`--optimization-level`、`--watermark`、`--enable-flashinfer-autotune`、`--enable-mfu-metrics`、`--kernel-config`、`--compilation-config`、`--scheduler-delay-factor`、`--use-flash-attn`、`--enable-long-context-optimization`、`--rope-scaling dynamic`、`--multi-step-model-output`、`--enable-contextual-calculation`。聊天里还自称"搜索了 15 个网页"——**搜索过 ≠ 参数存在**，版本不匹配时 web 语料最容易张冠李戴。（真实存在的对应物：注意力后端用 `--attention-backend FLASHINFER`，KV 精度用 `--kv-cache-dtype fp8_e4m3`，块大小用 `--block-size`。）
4. **`VLLM_USE_FLA` 不是 FlashInfer**。`FLA = Flash Linear Attention`，是给 GDN 类线性注意力层用的算子库，与 FlashInfer（通用注意力/采样加速）是两套东西。分阶段验证期间保持 `OFF` 不动是对的（一次只验证一个变量）；**未来它本身就是一个独立的优化实验项**（试 `VLLM_USE_FLA=ON` 对比 GDN 层吞吐）。
5. **Prefill 吞吐"下降"不是坏事**。Grafana 上 Prefill 从 3500+ 掉到低位，通常只是流量从"大请求预填充阶段"进入"decode 主导阶段"，不是性能退化。
6. **`--disable-log-stats` 之后别瞎找日志**。该参数只关掉 10 秒统计的**日志打印**，Prometheus 指标端点照常可用：`curl -s http://localhost:38081/metrics | grep '^vllm'`，配合 Grafana 就是本文的监控方案（见第 11 节）。

## 9. 最终生产启动脚本

（API key 已打码；`$APP_HOME` 为服务部署目录）

```bash
start()
{
	echo "begin to start model ${MODEL_PATH} for AI coder ......"

	# ====== 1. 硬件 / 环境 ======
	export CUDA_DEVICE_ORDER=PCI_BUS_ID          # 双卡机器（PRO 6000 + L20），固定卡序
	export CUDA_VISIBLE_DEVICES=0                # vLLM 只跑 PRO 6000

	# 【关键修复】nohup 后台进程必须显式继承 CUDA Toolkit 环境，
	# 否则 FlashInfer/Triton 的 JIT 编译报 cuda_runtime.h 找不到（坑 5.1）
	export CUDA_HOME=/usr/local/cuda-13.0
	export PATH=$CUDA_HOME/bin:$PATH
	# export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH  # 可选；torch 加载异常时先注释它

	# ====== 2. vLLM / 内核行为 ======
	export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1       # 允许 262144 这种超长 max-model-len
	export FLASHINFER_DISABLE_VERSION_CHECK=1    # 开发版 vLLM 与 flashinfer 版本校验跳过
	export VLLM_USE_FLASHINFER_SAMPLER=0         # 【必须保留】Blackwell(SM120) 采样器已知问题
	export VLLM_ATTENTION_BACKEND=FLASHINFER     # 【阶段一】FlashInfer 注意力后端
	# export VLLM_DISABLE_FLASHINFER=1           # 【已移除】原本禁 FlashInfer 的保险开关
	export VLLM_USE_FLA=OFF                      # 线性注意力算子库开关，与 FlashInfer 无关，分阶段期间保持不动
	export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # 长上下文防显存碎片
	# export NVIDIA_TF32_OVERRIDE=1              # 对 BF16 模型无效，可留可删，别算收益

	nohup $APP_HOME/venv/bin/python -m vllm.entrypoints.openai.api_server \
	  	--model $MODEL_PATH \
		--served-model-name my-coder-llm \
		--api-key <REDACTED> \
		--host 0.0.0.0 \
		--port 38081 \
		--chat-template $APP_HOME/qwen38_chat_template_fixed.jinja \
		--tensor-parallel-size 1 \
		--max-model-len 262144 \
		--reasoning-parser qwen3 \
		--gpu-memory-utilization 0.95 \
		--enable-auto-tool-choice \
		--enable-prefix-caching \
		--trust-remote-code \
		--max-num-seqs 16 \
		--tool-call-parser qwen3_coder \
		--dtype bfloat16 \
		--enable-chunked-prefill \
		--max-num-batched-tokens 8192 \
		--kv-cache-dtype fp8_e4m3 \               # 【阶段二】KV 降 FP8：带宽减半、容量翻倍
		 >>$APP_HOME/vllm.out 2>&1 &

	echo "end to start."
}
```

与稳定基线相比，净改动只有三行：`VLLM_ATTENTION_BACKEND=FLASHINFER`（移除 `VLLM_DISABLE_FLASHINFER`）、`--kv-cache-dtype fp8_e4m3`、以及 CUDA 环境修复——**每一行都有独立回退路径**。

### 启动后验收清单

1. 首个请求卡 2~5 分钟（JIT）属正常，等完再测；
2. 日志无 `cuda_runtime.h` / `FAILED: [code=1]` 编译错误；
3. `nvidia-smi` 显存 ~95~96GB 属正常（KV 池预分配），看 `GPU KV cache usage` 而非显存绝对值；
4. 稳态生成吞吐进入 80~105 tok/s 区间（4~6 并发）、`Waiting` 长期为 0；
5. 发 1~2 个不同长度的预热请求，消化 `jit_monitor` 的首请求延迟尖峰。

## 10. 超越吞吐量：vLLM 性能的综合评估

第 7 节的前后对比只比了**整机生成吞吐**——这是最容易拿到、也最容易被误读的"标题数字"。生产上评估 vLLM，行业共识是：**吞吐量 / 延迟 / 显存（GPU）利用率构成一个权衡三角**，三者不可能同时最优，任何评估都要多维度交叉、并且锚定 SLO（服务水平目标）来看。

### 10.1 核心评估维度（五类）

1. **吞吐（Throughput）**——整机合计口径：Prompt tokens/s 与 Output tokens/s。
   - 日志字段：`Avg prompt throughput` / `Avg generation throughput`（10 秒窗口合计）
   - Prometheus：`vllm:prompt_tokens_total`、`vllm:generation_tokens_total`
   - 注意两种口径：**全部并发合计**（整机）与**单请求**（≈ 1000 / TPOT(ms)），二者差一个并发数，混用必错（见观念纠偏 1）。
2. **单请求延迟（Latency）**——交互式场景的核心，一律看**百分位**（P50/P90/P99）而非均值：

   | 指标 | 含义 | vLLM Prometheus 指标（Histogram） |
   |---|---|---|
   | TTFT | Time To First Token：请求到达 → 首 token（= 排队 + prefill，prefix cache 命中直接缩短它） | `vllm:time_to_first_token_seconds` |
   | TPOT | Time Per Output Token：首 token 之后每 token 平均耗时（按请求平均） | `vllm:request_time_per_output_token_seconds` |
   | ITL | Inter-Token Latency：逐 token 间隔（按 token 加权），反映流式输出的"流畅感" | `vllm:inter_token_latency_seconds` |
   | E2E | End-to-End：请求到达 → 最后一个 token = TTFT + decode 总时长 | `vllm:e2e_request_latency_seconds` |
   | 排队/分阶段 | 排队时长、prefill 时长、decode 时长（定位 TTFT 高的原因） | `vllm:request_queue_time_seconds`、`vllm:request_prefill_time_seconds`、`vllm:request_decode_time_seconds` |

   vLLM 官方压测工具 `vllm bench serve`（旧版为 `benchmarks/benchmark_serving.py`）输出的正是这组指标的分位数——用它做回归压测，别只看整机吞吐。
3. **排队与调度（Queue）**——`vllm:num_requests_running` / `vllm:num_requests_waiting`；日志里的 `Waiting: N reqs`。Waiting 持续 > 0 意味着 TTFT 开始劣化，是 SLO 风险的最直接信号。
4. **缓存效率（Cache）**——prefix cache 命中率、MM cache 命中率。编程场景里系统提示词每次请求都重复，命中率直接决定 TTFT 下限（log-07 里 17%→52% 的升温曲线就是它在工作）。
5. **资源与稳定（Resources）**——KV cache 使用率（并发的硬约束）、显存占用、温度/功耗（是否触顶降频）、OOM/抢占（preemption/recompute）、MFU（Model FLOPs Utilization，可选深挖）。

### 10.2 Goodput：把"吞吐量"钉在 SLO 上

业界（DistServe 论文的定义，CNCF 的推广）：**Goodput = 每秒完成、且同时满足延迟 SLO 的请求数**。一句话："**没有 SLO 的吞吐量数字是营销，不是工程**"。

完整的提问方式因此是三步：

1. 先给业务定 SLO（TTFT P99 ≤ ?、TPOT P99 ≤ ?、E2E P99 ≤ ?）；
2. 逐步加压找"仍满足 SLO 的最大并发/负载"，该点下的吞吐就是 Goodput；
3. 超过膝点（knee point）后，并发继续涨、整机吞吐继续涨，但 TPOT 同步恶化——**为整机吞吐牺牲单请求延迟，对交互式服务是负收益**。

### 10.3 本服务在权衡三角中的定位与调优侧重点

本服务性质：**交互式 + agentic 编程助手**——人/Agent 实时等 token，一个任务串行发出多条请求。按行业负载分类（[Anyscale](https://docs.anyscale.com/llm/serving/benchmarking/metrics)），交互式场景（chatbot、coding assistant）最敏感的是 **TTFT 与 ITL/TPOT**；吞吐优先属于离线批处理场景，本服务不是后者。

建议的 SLO 起点（按实测流量修正，不是标准答案）：

| SLO | 起点 | 依据 |
|---|---|---|
| TPOT P99 | ≤ 100 ms/token（单请求 ≥ 10 tok/s） | 低于此线 Agent 的"思考速度"体感可用；当前 80~105 tok/s（4~6 并发）折算单请求 14~26 tok/s（TPOT ~38~71ms），已达标 |
| TTFT P99 | 按输入长度分档：短 prompt < 2s；典型 30~100K prompt < 10s | TTFT 下限是 prefill 耗时，262K 长 prefill 可达数秒~数十秒，**必须分输入长度档位看**，单一数字无意义 |
| E2E P99 | 参考 Grafana 现值 3.30 min（典型）/ 15.9 min（尾部） | E2E 由**输出长度 + 长上下文**主导，对比时必须固定输入/输出分布 |

**调优侧重点**（按优先级，对应第 9 节最终脚本的旋钮）：

1. **TTFT → 先缓存、后 prefill**
   - 守住 prefix cache 命中率：本服务系统提示词是固定长文本，复用价值极高。**客户端千万不要在提示词头部放时间戳/随机串**，否则前缀失配、命中率归零（log-06 的 0% 窗口）；
   - `--enable-chunked-prefill` + `--max-num-batched-tokens 8192` 控制 prefill 分块，防止单次大 prefill 饿死 decode（log-06 "崩溃假象"正是 prefill 突发把 decode 挤停的表现）；
   - MM cache（截图输入）98.3% 命中已是优秀，不动。
2. **TPOT/ITL → 并发不是越大越好**：`--max-num-seqs 16` 是上限阀门，实际工作点应该是"满足 TPOT P99 的最大并发"。用 `vllm bench serve` 做并发扫表（1/2/4/8/16…）找膝点，而不是拍脑袋加并发。
3. **显存 → KV 容量就是并发的硬约束**：FP8 KV 已把余量翻倍；`--gpu-memory-utilization 0.95` 是上限别再抬（坑 5.2 的教训）；KV 使用率长期逼近 80% 就该停手。
4. **别追的指标**：裸整机吞吐、MFU——本服务没有离线高并发推理需求，把它们拉高只能以 TPOT/TTFT 为代价，属于"用延迟换数字"。

### 10.4 需要注意的坑（清单）

1. **合计 vs 单请求**：105 tok/s 是整机合计，单请求 ≈ 14~26 tok/s；汇报和调参时两个口径分开写（观念纠偏 1 的延续）。
2. **看百分位不看均值**：均值掩盖长尾；本服务的 262K 级长上下文请求正是长尾，P99 比 P50 更有决策价值。
3. **冷启动窗口污染统计**：启动后前 2~5 分钟（JIT 编译）与空闲后的第一个大请求会把 TTFT/ITL 打尖（log-08 的 `jit_monitor` 告警），评估时剔除或只看稳态——与 log-06"别拿单张快照下结论"是同一课。
4. **Waiting 是先行指标**：`Waiting > 0` / `request_queue_time_seconds` 上升先于 TPOT/TTFT 恶化出现，是 SLO 风险的第一信号，Grafana 上值得单独一个面板。
5. **prefix cache 命中率是"状态"不是"能力"**：随会话升温上升、重启后归零。长期 0% 按顺序排查：(a) 客户端提示词前缀是否不稳定；(b) 是否刚重启；(c) KV 池是否被挤占导致缓存块被逐出。
6. **对比评估必须固定流量分布**：输入/输出长度分布不同时，E2E P99 和吞吐都不可比（Grafana E2E P99 面板的 3.30 min 与 15.9 min 是不同分位/分布，不能直接互比）。
7. **每次配置变更后做标准化回归压测**：固定数据集 + 并发扫表，输出 TTFT/TPOT/ITL/E2E 的 P50/P99 + 满足 SLO 的最大并发（Goodput），与日志一并归档——FLA 实验（第 12 节方向 2）、并发上探（方向 3）上线前各压一次。

> 参考：[vLLM Production Metrics](https://docs.vllm.ai/en/stable/usage/metrics/)（上述指标名与 `/metrics` 输出）、[Anyscale：LLM 延迟与吞吐指标](https://docs.anyscale.com/llm/serving/benchmarking/metrics)（TTFT/TPOT/ITL/E2E 定义与场景选型）、[CNCF：Why goodput matters more than throughput](https://www.cncf.io/blog/2026/07/20/why-goodput-matters-more-than-throughput-for-llm-serving/)（Goodput 与 SLO 视角）、[Revisiting SLO and Goodput Metrics in LLM Serving (arXiv:2410.14257)](https://arxiv.org/html/2410.14257v1)（学术视角）。

## 11. 监控与健康判据

- **Prometheus**：`curl -s http://localhost:38081/metrics | grep '^vllm'`（`--disable-log-stats` 不影响该端点）；
- **Grafana**（`grafana-01.webp` 所用面板）：Token 吞吐量（Prefill/Decode）、实时 Token 处理（按 Engine/TP Rank）、缓存 Token 统计、E2E P99 延迟、Engine Step / CUDA Graph 指标；**建议补充** TTFT/TPOT/ITL 分位面板（数据源 `vllm:time_to_first_token_seconds`、`vllm:inter_token_latency_seconds` 等，指标定义见第 10 节）；
- **健康判据**（来自本次各日志窗口的经验值）：
  - `GPU KV cache usage` 长期 < 80%（99% 以上 + 生成吞吐贴地 = 排队/抢占，见坑 5.2 与 log-06 窗口）；
  - `Waiting: 0 reqs`（出现 Waiting 说明调度已经追不上）;
  - `Prefix cache hit rate` 随会话升温上升（17%→52% 的曲线说明复用生效；长期 0% 说明缓存没起作用或刚重启）；
  - `MM cache hit rate` 高（98.3%）说明多模态输入复用良好。

## 12. 结论与后续方向

**结论**：在"不动权重、不降效果、显存不越界"的三重约束下，单卡 96GB 跑 27B + 262K 上下文的编程助手，瓶颈从来不在硬件（1792 GB/s 带宽、325W TDP 余量都够用），而在三处配置：

1. **环境**——JIT 编译器可见性（CUDA_HOME/PATH）；
2. **注意力后端**——Blackwell 上 FlashInfer 替代默认后端（+100% 左右）；
3. **KV 精度**——FP8 KV（带宽减半，同并发下 KV 占用 72%→56~64%）。

方法论沉淀：**显存预算先行 → 稳定基线锚定 → 单变量分阶段 → 每阶段独立回退 → Grafana 拉长时间窗验证 → 用 SLO/Goodput 锚定评估口径（第 10 节）**。

后续可选方向（按风险从低到高）：

1. **预热完善**：启动后自动发 mock 请求覆盖常见 shape，消灭 `jit_monitor` 首请求尖峰；
2. **`VLLM_USE_FLA=ON` 实验**：单独验证线性注意力（GDN）层换 FLA 算子的收益（独立变量，单独跑一天）;
3. **并发上探**：FP8 KV 释放了容量，可把 `--max-num-seqs 16` 逐步往上试（观察 KV 使用率，逼近 80% 即止）；
4. **权重量化**：如果未来"不牺牲效果"的约束松动，BF16→FP8 权重（或 4-bit）可把 54GB 权重压到 27GB 以下，KV 余量翻倍——本次因约束排除，不是技术上不可行（机器上实际也备有 FP8 权重版本实例做对照）；
5. **多卡**：条件允许时双卡 `--tensor-parallel-size 2`，或双实例负载均衡。

## 附录：素材清单

| 文件 | 内容 |
|---|---|
| `vllm-log-01.txt` | 09-04 基线：吞吐统计 + nvidia-smi + 提问"性能是否正常" |
| `vllm-log-02.txt` | 09-05 首次优化启动失败：FlashInfer JIT 找不到 `cuda_runtime.h`，EngineCore 初始化失败 |
| `vllm-log-03.txt` | 保守配置后首个请求 OOM：`expandable_segments` mapping 失败 + nvidia-smi |
| `vllm-log-04.txt` | 09-05 凌晨持续的 OOM 告警 |
| `vllm-log-05.txt` | 回退后的稳定基线 start 脚本 + 稳定日志 + 提问"稳定基础上能否提速" |
| `vllm-log-06.txt` | 阶段一冷启动"崩溃假象"窗口：KV 99.7%、生成 0.3~0.9 tok/s |
| `vllm-log-07.txt` | 阶段一稳态：生成 28~72 tok/s、prefix cache 17%→52% |
| `vllm-log-08.txt` | 阶段二（+FP8 KV）稳态：生成 78~105 tok/s + Triton JIT 告警 |
| `deepseek-web-chat-parse.txt` | 与 DeepSeek 官方 web chat 的完整问答（含 Kimi 方案 PK、分阶段路线图、Grafana 解读） |
| `serve-help.txt` | `vllm serve --help`（vLLM 0.27.1）抓取，用于参数真伪甄别 |
| `grafana-01.webp` | 阶段一稳态的 Grafana 面板截图（Prefill 3541 / Decode 41.1 tok/s 均值） |
