---
tags: [技术, OCR, 计算机视觉, PaddleOCR]
星期: 星期一
categories: [tech]
---

# PaddleOCR 技术调研

## 1. 前言

> 本文档调研 PaddleOCR 的核心技术架构、模型体系、性能表现及工程部署方案，为后续人脸识别系统中的 OCR 模块选型和集成提供参考。
>
> **关联阅读**：[多模态大模型OCR 文字提取能力分析](2026-08-05%20多模态大模型OCR%20文字提取能力分析.md)（对比 Qwen3.6 多模态模型 OCR 能力）

---

## 2. PaddleOCR 概述

### 2.1 什么是 PaddleOCR？

PaddleOCR 是**百度飞桨（PaddlePaddle）**开源的端到端多语言 OCR 工具包，是业界功能最全、落地最广的开源 OCR 系统之一。

- **GitHub**：https://github.com/PaddlePaddle/PaddleOCR
- **Stars**：30k+
- **协议**：Apache 2.0（商用友好）
- **定位**：不仅是一个工具库，而是一套**完整的 OCR 工程体系**

### 2.2 技术架构

PaddleOCR 采用经典 OCR 三段式流水线：

```
原始图像
    ↓
┌─────────────────┐
│  文本检测        │  PP-OCR / DBNet++ / EAST / CRAFT
│  (Text Detection)│  输出文本区域的边界框（四边形/旋转框）
└────────┬────────┘
         ↓
┌─────────────────┐
│  文字识别        │  SVTR / CRNN / STAR-Net
│  (Text Recognition)│  输出识别文字 + 置信度
└────────┬────────┘
         ↓
    结构化结果
    （坐标 + 文字 + 置信度）
```

**关键优势**：每一段都是可独立替换/升级的模块，且百度提供了从检测→识别→版面分析→信息抽取的完整链路。

---

## 3. 核心模型体系（PP-OCRv4）

### 3.1 PP-OCRv4 整体架构

PaddleOCR 的旗舰方案 **PP-OCRv4** 是目前开源 OCR 精度最高的方案之一，在 OCRBench、ICDAR 等基准上均位居前列。

```
PP-OCRv4 流程：
┌──────────┐    ┌──────────┐    ┌────────────┐
│ 文本检测   │ →  │ 方向分类器 │ →  │ 文字识别    │
│ PP-OCRv4D│    │   (PP-ShiVT)│    │ PP-OCRv4R │
└──────────┘    └──────────┘    └────────────┘
```

### 3.2 文本检测模型（PP-OCRv4-Det）

| 维度 | 参数 |
|------|------|
| Backbone | PPLCNet-HGNetV2 |
| Neck | DB++（不同可微二值化） |
| Head | SAST-style 检测头 |
| 输入尺寸 | 多尺度训练（640~1280） |
| 输出 | 文本区域四边形坐标 |

**关键特性**：
- **DB++**：可微二值化模块，替代传统阈值操作，端到端训练
- **多尺度训练**：自动适应不同分辨率图像，长图/窄图效果都好
- **旋转检测**：支持任意方向文本（水平、倾斜、垂直）

### 3.3 文字识别模型（PP-OCRv4-Rec）

| 维度 | 参数 |
|------|------|
| 架构 | SVTR (Spatial Vision Transformer) |
| Backbone | 混合 CNN+Transformer |
| 语言 | 中英多语言、多方向 |
| 字典 | 中文 3636 字符 + 英文字母数字 |

**关键特性**：
- **SVTR v2**：结合 CNN 的局部特征提取能力和 Transformer 的全局建模能力
- **CTC 解码**：无 CTC 训练、有 CTC 推理，精度提升显著
- **超分预处理**：识别前自动 upscale，模糊小字识别率提升 10%+

### 3.4 方向分类器（PP-OCRv4-Cls）

| 维度 | 参数 |
|------|------|
| 任务 | 判断文本方向（0° / 180°） |
| 模型 | MobileNetV3-Small |
| 精度 | 正向样本准确率 99.7%+ |

**作用**：解决倒置文字识别问题，180° 旋转后送入识别模型。

---

## 4. 模型尺寸与性能

### 4.1 PP-OCRv4 模型尺寸选择

| 模型 | 检测参数量 | 识别参数量 | 总参数量 | 适用场景 |
|------|-----------|-----------|---------|---------|
| **Nano** | 5.6M | 3.8M | **9.4M** | 移动端、边缘设备 |
| **Small** | 19.1M | 9.5M | 28.6M | 轻量服务器 |
| **Medium** | 43.2M | 20.1M | 63.3M | 通用服务器 |
| **Large** | 88.7M | 38.4M | 127.1M | 高精度需求 |

### 4.2 性能数据（ICDAR 2015 / Total-Text / CTW1500）

| 模型 | ICDAR F1 | Total-Text F1 | CTW1500 F1 | CPU 推理(ms/张) |
|------|----------|---------------|------------|-----------------|
| PP-OCRv4-Det (nano) | 85.2% | 78.4% | 76.8% | ~15ms |
| PP-OCRv4-Rec (nano) | — | — | — | ~8ms |
| PP-OCRv4 端到端 | **94.2%** | **85.6%** | **83.1%** | ~30ms |

> 对比：PaddleOCR-VL（多模态大模型方案，0.9B 参数）在 OmniDocBench 上达到 94.5%，但端到端延迟 150-500ms。

---

## 5. PP-Structure：文档分析与信息抽取

PP-OCR 不止于"识别文字"，还包含完整的**文档分析**能力：

### 5.1 PP-StructureV3 架构

```
输入文档图像
    ↓
┌─────────────────────┐
│ 版面分析 (Table/Layout) │  ← DocLayout-YOLO / PaddleX
│  检测：标题、正文、图片、表格  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 表格识别 (Table)      │  ← TableMaster / StructEqTable
│  还原表格 HTML/LaTeX  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 信息抽取 (InfoExtract) │  ← 票据/证照/合同
│  JSON 结构化输出      │
└─────────────────────┘
```

### 5.2 版面分析模型

| 模型 | 任务 | 类别数 | 精度 (COCO mAP) |
|------|------|--------|----------------|
| **DocLayout-YOLO** | 文档版面检测 | 5 类（标题/正文/图片/表格/脚注） | 72.3 |
| **LayoutLMv3** | 版面理解+信息抽取 | 多任务 | 论文 SOTA |

**关键能力**：
- 自动识别文档中的标题、正文、图片、表格等区块
- 支持阅读顺序还原
- 为 OCR 结果添加空间位置信息

### 5.3 表格识别

| 模型 | 特点 | 适用场景 |
|------|------|---------|
| **TableMaster** | 多任务学习，同时识别结构和内容 | 通用表格 |
| **StructEqTable** | 输出 LaTeX 公式，支持复杂数学表格 | 学术论文 |
| **PP-Structure 表格** | 输出 HTML/Markdown 表格 | 日常文档 |

### 5.4 信息抽取（PP-InformationExtract）

专门针对**结构化文档**的信息抽取：

| 类别 | 预置模型 | 输出格式 |
|------|---------|---------|
| 身份证/银行卡 | 预置 6+ 证照模型 | JSON |
| 增值税发票 | 预置发票抽取模型 | JSON |
| 驾驶证/行驶证 | 预置交通证照模型 | JSON |
| 合同/收据 | 支持自定义模板 | JSON (3层嵌套) |
| 通用票据 | 自定义字段抽取 | JSON |

**自定义抽取**：通过模板定义字段名和位置，无需重新训练。

---

## 6. PaddleOCR-VL：多模态大模型 OCR

### 6.1 概述

PaddleOCR 团队也推出了基于**多模态大模型**的方案：

| 维度 | PaddleOCR-VL | PP-OCRv4（传统流水线） |
|------|-------------|----------------------|
| 架构 | 多模态大模型（类似 Qwen2-VL） | 检测→识别→抽取三段式 |
| 参数量 | 0.9B~2B | 9.4M~127M |
| OmniDocBench | 94.5% | ~90% |
| 推理速度 | 150-500ms | 30ms |
| 长文档 | 支持（1M 上下文） | 逐页处理 |
| 表格+公式 | 原生支持 | 需单独模型 |
| 多语言 | 多语言混合 | 需切换字典 |
| 部署成本 | GPU | 可 CPU |

### 6.2 PaddleOCR-VL 适用场景

- **复杂文档解析**：学术论文、财务报表、法律文档
- **多模态理解**：图文混排、图表+文字关联
- **长文档**：PDF 整本解析（利用大上下文窗口）
- **交互式查询**：基于文档内容的自然语言问答

### 6.3 与 Qwen3.6 多模态 OCR 对比

| 维度 | PaddleOCR-VL | Qwen3.6-35B-A3B |
|------|-------------|-----------------|
| OmniDocBench | 94.5 | 89.9 |
| 参数量 | 0.9B~2B | 35B 总 / 3B 激活 |
| 激活效率 | 低（稠密） | 高（MoE） |
| 开源协议 | Apache 2.0 | Apache 2.0 |
| 本地部署 | GPU 需 8GB+ | GPU 需 16GB+ |
| 结构化抽取 | 支持 JSON 模板 | 支持 |
| 公式/表格 | 强 | 强 |
| **最佳场景** | 精度优先 | 理解+推理+性价比 |

---

## 7. 与竞品对比

### 7.1 主流 OCR 方案横向对比

| 维度 | PaddleOCR | Tesseract | EasyOCR | MMOCR | MinerU |
|------|-----------|-----------|---------|-------|--------|
| 开发方 | 百度 | Google | Jinzhen (个人) | 商汤 | 阿里 |
| 检测模型 | PP-OCR | 无内置 | CRAFT | DB/EAST | Paddle/自研 |
| 识别模型 | SVTR/CRNN | LSTM | CRNN | 多种 | 多种 |
| 中文支持 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 表格识别 | ✅ | ❌ | ❌ | ✅ | ✅ |
| 版面分析 | ✅ | ❌ | ❌ | 部分 | ✅ |
| 信息抽取 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 部署难度 | 低 | 极低 | 低 | 中 | 中 |
| CPU速度 | 快 | 快 | 中 | 中 | 中 |
| 文档类型 | 场景+文档 | 文档为主 | 场景文字 | 研究 | 文档解析 |

### 7.2 与商业 OCR 对比

| 维度 | 百度智能云 OCR | 阿里云 OCR | 腾讯云 OCR | PaddleOCR |
|------|-------------|-----------|-----------|----------|
| 免费额度 | 每月 500 次 | 每月 1000 次 | 每月 500 次 | 无限（自部署） |
| 价格/千次 | 0.3-0.5元 | 0.2-0.8元 | 0.3-0.5元 | 0（服务器成本） |
| 数据隐私 | 上传至云端 | 上传至云端 | 上传至云端 | 本地部署 |
| 定制化 | 需联系商务 | 需联系商务 | 需联系商务 | 完全可控 |
| 离线可用 | ❌ | ❌ | ❌ | ✅ |

---

## 8. 安装与使用

### 8.1 安装

```bash
# 方式一：pip 安装（推荐）
pip install paddlepaddle -i https://pypi.org/project/paddlepaddle/
pip install paddleocr

# 方式二：conda 安装
conda install -c conda-forge paddlepaddle
pip install paddleocr

# 方式三：Docker
docker pull paddlepaddle/paddleocr:latest
```

### 8.2 快速使用

```python
from paddleocr import PaddleOCR, draw_ocr

# 初始化（首次会自动下载模型）
ocr = PaddleOCR(
    use_angle_cls=True,    # 开启方向分类
    lang='ch',             # 中文
    use_gpu=False,         # CPU 推理
    show_log=False,
)

# 识别
result = ocr.ocr("image.jpg", cls=True)

# 可视化
from PIL import Image
img = Image.open("image.jpg")
boxes = [line[0] for line in result]
texts = [line[1][0] for line in result]
scores = [line[1][1] for line in result]
im_show = draw_ocr(img, boxes, texts, scores, font_path='./fonts/simfang.ttf')
im_show.save("result.jpg")
```

### 8.3 PP-Structure 文档解析

```python
from paddleocr import PPStructure

table_engine = PPStructure(
    show_log=False,
    region=True,       # 开启版面分析
    table=True,        # 开启表格识别
    ocr=True,          # 开启 OCR
)

result = table_engine(image)
# 返回结构化数据：每个区域的类型 + OCR 结果
```

### 8.4 命令行使用

```bash
# 单张图片 OCR
paddleocr --image_dir ./test.jpg --lang ch --use_angle_cls true

# 批量处理
paddleocr --image_dir ./images/ --lang ch

# 文档解析
paddleocr --use_doc_orientation_classify true --use_doc_unwarping true
```

---

## 9. 性能优化与部署

### 9.1 GPU 加速

```python
ocr = PaddleOCR(
    use_gpu=True,        # 启用 GPU
    gpu_mem_id=0,        # 指定 GPU
    det_limit_side_len=960,  # 检测最大边长
)
```

| 设备 | 检测延迟 | 识别延迟 | 端到端 |
|------|---------|---------|--------|
| RTX 4090 | ~5ms | ~3ms | ~10ms |
| RTX 3060 | ~8ms | ~5ms | ~15ms |
| CPU (i7) | ~15ms | ~8ms | ~30ms |

### 9.2 模型导出与部署

```python
# 导出为 ONNX
from paddleocr import PaddleOCR
# PaddleOCR 模型本身基于 PaddlePaddle，可导出为：
# 1. ONNX（兼容性好）
# 2. Paddle Inference（性能最优）
# 3. TensorRT（NVIDIA GPU 最佳）
```

| 部署方式 | 适合场景 | 性能 |
|---------|---------|------|
| Paddle Inference | 服务端（最高性能） | FP16 加速 |
| ONNX Runtime | 跨平台部署 | 中等 |
| TensorRT | NVIDIA GPU 生产环境 | 最快 |
| Triton | 高并发推理服务 | 高吞吐 |

### 9.3 移动端部署

| 平台 | 方案 | 模型大小 |
|------|------|---------|
| Android | Paddle Lite | ~10MB |
| iOS | Paddle Lite / CoreML | ~10MB |
| 嵌入式 | Paddle Lite (ARM) | ~10MB |

---

## 10. 与其他技术的集成方案

### 10.1 与人脸识别系统的集成架构

基于当前项目需求（人脸检测 + OCR），推荐以下架构：

```
输入图像
    │
    ├──→ YOLO26（人脸检测） → 人脸框 + 姿态
    │       │
    │       ├──→ InsightFace（人脸特征提取） → 512维 embedding
    │       │       │
    │       │       └──→ Milvus（向量检索 1:N）
    │       │
    │       └──→ 人脸区域裁剪
    │               │
    │               └──→ PaddleOCR（文字识别） → 姓名/工号等
    │                       │
    │                       └──→ 结构化结果 (JSON)
    │
    └──→ PaddleOCR（全文 OCR，兜底方案）
            │
            └──→ 非人脸区域文字提取
```

### 10.2 混合 OCR 策略

对于不同场景，推荐组合策略：

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 证件文字提取 | PaddleOCR + 信息抽取 | 高精度、结构化输出 |
| 票据/发票 | PP-InformationExtract | 预置模板 |
| 场景文字（路牌/广告） | PaddleOCR 或 Qwen3.6 | Paddle 快，Qwen 鲁棒 |
| 文档级解析 | Qwen3.6 多模态 或 PaddleOCR-VL | 理解+排版 |
| 混合场景 | PaddleOCR（兜底）+ Qwen3.6（理解） | 兼顾速度与深度理解 |

---

## 11. 局限性与注意事项

| 局限 | 说明 | 应对策略 |
|------|------|---------|
| **重叠文字** | 文字区域重叠时检测精度下降 | 后处理去重/合并 |
| **极小文字** | < 8px 高度的文字难以识别 | 超分辨预处理 |
| **艺术字/手写** | 非标准字体识别率低 | 用 Qwen3.6 辅助 |
| **多语言混合** | 自动语言检测有误差 | 手动指定 lang |
| **长图** | 超大分辨率图片需分块 | 使用 PaddleOCR 的 `det_db_box_thresh` 调整 |
| **模型下载** | 首次使用需下载模型 (~100MB) | 预下载缓存或离线部署 |

---

## 12. 实际测试方案

### 12.1 测试数据集

| 类型 | 数量 | 说明 |
|------|------|------|
| 证件照 | 50 张 | 身份证、银行卡、驾驶证 |
| 票据 | 100 张 | 发票、收据、小票 |
| 场景文字 | 200 张 | 路牌、广告牌、菜单 |
| 文档扫描 | 50 页 | PDF 扫描、扫描件 |
| 混合场景 | 100 张 | 含人脸+文字、图文混排 |

### 12.2 评估指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **字符级准确率 (Char Acc)** | 识别字符正确率 | > 95% |
| **词级准确率 (Word Acc)** | 词整体正确率 | > 93% |
| **检测召回率 (Det Recall)** | 文字区域检出率 | > 90% |
| **端到端延迟** | 单张处理时间 | < 50ms (CPU) |
| **吞吐量** | QPS | > 20 (CPU) |

### 12.3 测试脚本框架

```python
import time
from paddleocr import PaddleOCR
import json

def benchmark_ocr(image_paths, ocr):
    """OCR 性能基准测试"""
    results = []
    for img_path in image_paths:
        start = time.time()
        result = ocr.ocr(img_path, cls=True)
        latency = (time.time() - start) * 1000
        
        # 提取文字和置信度
        texts = []
        for line in result:
            if line:
                texts.append({
                    "text": line[1][0],
                    "confidence": line[1][1],
                    "bbox": line[0]
                })
        
        results.append({
            "image": img_path,
            "latency_ms": latency,
            "texts": texts
        })
    
    return results

# 运行测试
if __name__ == "__main__":
    ocr = PaddleOCR(use_gpu=False, lang='ch')
    test_images = ["test/ID_card.jpg", "test/receipt.jpg", "test/street.jpg"]
    
    results = benchmark_ocr(test_images, ocr)
    
    # 统计
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)
    total_texts = sum(len(r["texts"]) for r in results)
    
    print(f"平均延迟: {avg_latency:.2f}ms")
    print(f"总识别文字数: {total_texts}")
```

---

## 13. 总结与选型建议

### 13.1 PaddleOCR 核心优势

| 优势 | 说明 |
|------|------|
| **开源免费** | Apache 2.0，无调用量限制 |
| **中文最优** | 对中文场景优化最好，字符集完善 |
| **链路完整** | 检测→识别→版面→抽取→信息结构化，一站式 |
| **部署灵活** | CPU/GPU/移动端/边缘设备全覆盖 |
| **社区活跃** | 30k+ Stars，持续迭代（PP-OCRv4 已更新至 2024） |
| **模型体积小** | Nano 模型仅 9.4M 参数，可部署在资源受限设备 |

### 13.2 选型决策

| 需求 | 推荐方案 | 理由 |
|------|---------|------|
| 纯 OCR 文字提取 | **PaddleOCR** | 速度快、精度高、中文最优 |
| 文档结构化解析 | **PaddleOCR + PP-Structure** | 表格/版面/信息抽取一体 |
| 需要语义理解 | **Qwen3.6 多模态** | 识别+理解+推理一体化 |
| 精度极致要求 | **PaddleOCR-VL** | 多模态大模型精度更高 |
| 人脸+文字混合 | **YOLO + InsightFace + PaddleOCR** | 各司其职、模块化 |
| 离线/隐私场景 | **PaddleOCR** | 可完全本地部署 |

### 13.3 本项目推荐架构

结合人脸识别系统和 OCR 需求：

```
┌─────────────────────────────────────────┐
│              输入图像                     │
├─────────────────────────────────────────┤
│  YOLO26 人脸检测 → 人脸框 + 关键点       │
├─────────────────────────────────────────┤
│  InsightFace → 512维人脸特征             │
├─────────────────────────────────────────┤
│  Milvus (IP) → 1:N 人脸检索             │
├─────────────────────────────────────────┤
│  PaddleOCR → 识别文字（姓名/工号/编号）  │
├─────────────────────────────────────────┤
│  输出：JSON { face_id, text, bbox, ... } │
└─────────────────────────────────────────┘
```

**核心决策**：PaddleOCR 作为 OCR 核心组件，YOLO26 + InsightFace 作为人脸检测与特征提取，各司其职，形成"检测→识别→检索→理解"的完整链路。

---

## 14. 生产环境并发性能优化（2080Ti 压测问题与方案）

> 背景：运维在服务器上压测 PaddleOCR（2080Ti，paddlepaddle-gpu>=2.6.0 + paddleocr>=3.0.0）发现：
> 多并发不能提升性能；脚本跑双卡，性能仍无提升。疑似服务实现问题。以下为诊断与优化方案。

### 14.1 问题诊断：为什么"多并发"和"双卡"都没提速

按概率排序的典型原因：

1. **多个并发请求共享同一个 PaddleOCR/predictor 实例**——predictor 不是线程/协程安全的，内部锁导致串行化，并发只是排队，吞吐恒等于单请求速度（最常见原因）。
2. **多进程用 `fork` 方式创建**——Paddle/ONNX Runtime 的 CUDA context 不能在 fork 后的子进程中使用（官方 issue #17144），子进程报错或回退 CPU。
3. **双卡脚本没做设备隔离**——所有进程/实例默认绑 `gpu:0`，第二张卡空闲。
4. **单实例占满 GPU 后多实例互相干扰**——官方 issue #17177 记录单实例持续推理时占满 GPU 调度，其他实例性能下降。正确姿势是"每卡一个进程"，不是"一张卡塞多个实例"。
5. **没有 batch**——PaddleOCR 3.0 的 `predict()` 支持 `batch_size` 参数，逐张调用无法打满 GPU。

**验证方法**（压测时同步执行，5 分钟定位）：
```bash
watch -n 0.5 nvidia-smi   # 看：GPU-Util 是否 <50%？两张卡是否只有一张在动？子进程显存是否为 0？
```
- GPU-Util 高但吞吐不涨 → 锁串行（原因 1）
- 只有卡 0 在动 → 设备隔离问题（原因 3）
- 子进程显存为 0 → fork 问题（原因 2）

### 14.2 优化方案（三层，按收益排序）

#### 第 1 层：单卡单进程优化（零架构改动，预期 1.5~3x）

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_doc_orientation_classify=False,   # 截图场景关掉方向分类子模型（省一次推理）
    use_doc_unwarping=False,              # 关掉文档矫正子模型（截图不需要）
    use_textline_orientation=True,        # 文字行方向分类保留（UI 截图有用）
    enable_hpi=True,                      # 高性能推理：自动 TensorRT 后端 + FP16
    device="gpu:0",
)
# 关键：批量推理
results = ocr.predict([img1, img2, ..., imgN], batch_size=16)
```

- **`batch_size` 是单卡提吞吐的第一杠杆**：1080p 截图建议 16~32 起步（2080Ti 11GB，按 OOM 回退）
- **`enable_hpi=True`**：自动转 TensorRT + FP16，2080Ti（Turing）完全支持，rec 通常再快 1.5~2x；首次运行编译 TRT 引擎需几分钟，之后缓存复用
- **关不需要的子模块**：3.0 默认 pipeline 带方向分类、文档矫正等子模型，截图场景关掉可省 20~40% 推理量
- 不想用 HPI 时退路：TRT 版镜像 `paddlex3.0.1-paddlepaddle3.0.0-gpu-cuda11.8-cudnn8.9-trt8.6`（或 cuda12.6 版）

#### 第 2 层：并发架构——"每卡一进程 + 进程内批处理"（核心改造）

正确模型不是"每请求一次推理"，而是：

```
请求队列(Redis/Kafka/进程内Queue)
   │  攒批：凑够 N 张或等满 20ms 取一批
   ▼
Worker 进程 × GPU 数（每进程独占一张卡）
   ├─ 进程启动时（fork 之后）加载模型，或 multiprocessing spawn
   ├─ CUDA_VISIBLE_DEVICES=0 / =1 隔离设备
   └─ 循环：取一批 → predict(batch) → 结果回队列
```

实现要点：
1. **设备隔离**：每个 worker 启动时 `os.environ["CUDA_VISIBLE_DEVICES"] = "0"`，进程内统一 `device="gpu:0"`（双卡不提速的最可能修复点）
2. **进程创建时机**：模型初始化必须在 fork/spawn **之后**、子进程内完成，或整体用 `mp.get_context("spawn")`
3. **并发入口用进程不用线程**：ThreadPoolExecutor 对 Paddle 推理无效（GIL + predictor 锁）；FastAPI 场景用 `ProcessPoolExecutor(spawn)` 或独立 worker 进程 + 消息队列
4. **worker 数量 = GPU 数量**（每卡 1 个），一卡多实例无收益（issue #17177），显存再空也不塞第二个
5. 后处理（JSON 组装、写 OpenSearch）放 worker 外或独立线程，别占推理循环

#### 第 3 层：系统级微调

- **CPU 侧**：解码/resize 是 CPU 活，worker 的 `OMP_NUM_THREADS` = 核数/卡数，CPU 预处理与推理并行，避免成为瓶颈
- **模型选型**：server 版 det/rec 若精度允许，换 **mobile 版**可快 2~3x（截图 UI 文字场景精度足够）
- **TRT 引擎缓存**：编译产物挂持久卷，避免重启后重新编译
- **显存规划**（2080Ti 11GB）：TRT FP16 下 det+rec 一套约 2~4GB，batch 32 的 1080p 约 4~6GB，留余量给切图二次 OCR

### 14.3 压测方法与验收标准

**压测脚本要求**：
- 用真实截图集（100~500 张混合分辨率），**不要只用 2 张**（测不出 batch 和 GPU 利用率问题）
- 指标：吞吐（张/分钟）、P50/P95 延迟、`nvidia-smi` GPU-Util 采样曲线
- 对照组：优化前基线 / 仅第 1 层 / 第 1+2 层 / 双卡

**预期提升**（1080p 中文 UI 截图，2080Ti）：

| 阶段 | 预期吞吐 |
|---|---|
| 当前（单卡单实例逐张） | 基线 X 张/分 |
| + batch + 关子模块 + TRT FP16 | 2.5~4x |
| + 每卡一进程（双卡） | 再 ~2x |
| 合计双卡 | 约 5~8x 基线 |

### 14.4 最短操作清单

1. `watch nvidia-smi` 观察当前压测双卡利用率 → 确认问题点
2. 服务代码加 `batch_size`（攒批）+ 关 doc_orientation/unwarping → 单卡先测
3. worker 改 spawn 多进程 + `CUDA_VISIBLE_DEVICES` 绑卡 → 双卡再测
4. 确认 TensorRT 已装：`python -c "import tensorrt; print(tensorrt.__version__)"`，装了就开 `enable_hpi=True`
5. 100 张真实图跑压测脚本出报告

---

## 参考资源

- [PaddleOCR 官方仓库](https://github.com/PaddlePaddle/PaddleOCR)
- [PP-OCRv4 技术报告](https://arxiv.org/abs/2208.03371)
- [PP-StructureV3 文档](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/README.md)
- [SVTR 论文](https://arxiv.org/abs/2205.00154)
- [DBNet++ 论文](https://arxiv.org/abs/2002.03227)
- [多模态大模型OCR 文字提取能力分析](2026-08-05%20多模态大模型OCR%20文字提取能力分析.md)
- [基于开源技术的人脸识别系统优化思考](./基于开源技术的人脸识别系统优化思考.md)
- [YOLO初体验](./YOLO初体验.md)
- [使用InsightFace进行人脸检测](./使用InsightFace进行人脸检测.md)