---
tags: 工作日记
星期:  星期一
---
# 使用InsightFace进行人脸检测



## 1. 前言

InsightFace 是目前开源领域最领先的 2D/3D 人脸分析项目之一，由 deepinsight 团队维护（核心成员包括郭迦 Jian Guo 和邓建 Kang Deng），GitHub Star 数 29,000+，被广泛认为是开源人脸识别方案的"事实标准"。

本项目最早以 MXNet 为基础框架，后扩展至 PyTorch，代码采用 **MIT 协议**（学术与商用均无限制），而预训练模型遵循非商用研究许可。自 v0.2 起，推理后端从 MXNet 迁移至 **ONNX Runtime**，大幅降低了部署门槛——只需 `pip install insightface onnxruntime` 即可在 CPU 或 GPU 上运行。

2026 年 InsightFace 1.0 进一步推出了 **InsightFace Evaluation Studio**（跨平台桌面 GUI）、**InsightFace Server**（类 AWS Rekognition 的自托管 REST API），以及面向生产环境的 **InspireFace** C/C++ SDK。

本文档聚焦 InsightFace 的人脸检测与识别能力，梳理其技术架构、核心模型、性能表现及实际使用方式，为后续在 HermesAgent 系统中集成人脸检测/识别模块提供技术选型依据。

## 2. InsightFace 技术架构全景

### 2.1 整体架构概览

InsightFace 是一个面向人脸分析的完整工具链，涵盖检测、对齐、识别、属性分析、人脸识别检索、人脸交换（Face Swap）和 3D 人脸重建七大模块：

```
┌─────────────────────────────────────────────────────────┐
│                    InsightFace 1.0                       │
├──────────┬──────────┬───────────┬──────────┬───────────┤
│ │  人脸检测  │  人脸对齐  │ 人脸识别   │ 属性分析  │ 人脸交换  │
│ │         │         │           │          │           │
│ │ SCRFD   │ 2d106   │ ArcFace   │ Gender   │ in-swapper│
│ │ RetinaFace │3d68   │ PartialFC │ Age      │ inswapper-│
│ │ BlazeFace│         │ VPL       │          │ 512-live  │
│ └──────────┴──────────┴───────────┴──────────┴───────────┤
│                                                          │
│  3D 人脸重建    │ Gaze 估计  │ 活体检测  │ FRVT 评测   │
│  (face3d)      │           │  (FAS)    │  (MegaFace) │
│                                                          │
│  推理后端: ONNX Runtime (v0.2+) / MXNet (<=0.1.5)        │
│  部署形态: Python 包 / REST API Server / C++ SDK         │
│  评估工具: 桌面 GUI (PySide6) / CLI / Web Demo            │
└─────────────────────────────────────────────────────────┘
```

### 2.2 人脸检测模块（Face Detection）

InsightFace 提供三种人脸检测模型：

| 模型 | 来源 | 特点 | 用途 |
|------|------|------|------|
| **SCRFD** (ICLR 2022) | 自研 | 检测精度-速度最优比，多规格可选 (500M~34G FLOPs) | **生产推荐** |
| **RetinaFace** (CVPR 2020) | 自研 | 经典高精度检测，含抗遮挡变体 | 高精度场景 |
| **BlazeFace** | Paddle/Google | 超轻量，适合移动端/嵌入式 | 端侧部署 |

SCRFD（Scale-aware and Replicable Face Detector）是 InsightFace 最核心的检测模型。其核心创新：

1. **尺度感知特征金字塔 (Scale-aware FPN)**：不同大小的检测头分别处理不同尺度的人脸（小/中/大），解决了小人脸检测精度低的问题。
2. **可复制的网络搜索**（Replicable Network Search）：通过两阶段搜索（先搜 Backbone，再搜整体网络），自动化设计最优检测网络结构。
3. **Anchor-free 设计**：与传统 Anchor-based 方法不同，SCRFD 直接预测人脸中心及其宽高，简化了推理流程。
4. **多尺度推理**：支持在多个分辨率上并行推理（如 128×128 + 640×640），通过联合 NMS 融合结果，大幅提升多尺度人脸的召回率。

**SCRFD 模型规格对比**（VGA 分辨率下）：

| 模型 | 精度 (Easy/Med/Hard) | 参数量 | FLOPs | 推理时间 |
|------|---------------------|--------|-------|---------|
| SCRFD-500MF | 90.57 / 88.12 / 68.51 | 0.57M | 500M | 3.6ms |
| **SCRFD-2.5GF** | **93.78 / 92.16 / 77.87** | 0.67M | 2.5G | 4.2ms |
| **SCRFD-10GF** | **95.16 / 93.87 / 83.05** | 3.86M | 10G | 4.9ms |
| SCRFD-34GF | 96.06 / 94.92 / 85.29 | 9.80M | 34G | 11.7ms |

> 对比业界：在 Hard 子集上，SCRFD-10GF (83.05) 远超 RetinaFace (64.17) 和 DSFD (71.39)，同时参数量仅为 RetinaFace 的 13%。

**CPU 性能**（SCRFD-0.5GF，AMD Ryzen 9 3950X，单线程）：
- 640×480 输入：28.3ms/帧
- 320×240 输入：11.4ms/帧

这意味着即使在 CPU 上，单帧检测也仅需 10~30ms，足以支撑实时视频流处理。

### 2.3 人脸识别模块（Face Recognition）

InsightFace 提供多种深度度量学习方案，核心损失函数包括：

| 损失函数 | 发表 | 核心思想 |
|----------|------|---------|
| **ArcFace** (CVPR 2019) | Additive Angular Margin | 在角度空间添加边际，使类间距离最大化 |
| **SubCenter ArcFace** (ECCV 2020) | 多子中心 ArcFace | 每个类别使用多个子中心，缓解不平衡问题 |
| **Partial FC** (CVPR 2022) | 部分全分类器 | 仅用部分类别参与梯度计算，支撑超大规模人脸库训练 |
| **VPL** (CVPR 2021) | 可视学习度量 | 利用可见性特征增强鲁棒性 |

主流 Backbones：
- **IResNet** 系列（IR-SE-50, IR-SE-100）：推荐配置，精度高
- **MobileFaceNet**：移动端轻量方案
- **InceptionResNet_v2** / **DenseNet**：经典学术 backbone

### 2.4 模型 Pack（Model Pack）

InsightFace 提供多个预训练模型 Pack，打包了检测+识别+对齐+属性分析模型：

| Pack 名 | 检测模型 | 识别模型 | 对齐 | 属性 | 大小 |
|---------|---------|---------|------|------|------|
| **buffalo_l** | SCRFD-10GF | ResNet50@WebFace600K | 2d106 & 3d68 | Gender&Age | 326MB |
| buffalo_m | SCRFD-10GF | ResNet100@Glint360K | 2d106 & 3d68 | Gender&Age | 407MB |
| buffalo_s | SCRFD-500MF | MBF@WebFace600K | 2d106 & 3d68 | Gender&Age | 159MB |
| buffalo_sc | SCRFD-500MF | MBF@WebFace600K | - | - | 16MB |

**buffalo_l** 是当前推荐默认模型 Pack（auto-download）。识别精度对比：

| Pack | MR-ALL | LFW | CFP-FP | AgeDB-30 | IJB-C(E4) |
|------|--------|-----|--------|----------|-----------|
| buffalo_l | 91.25 | **99.83** | **99.33** | **98.23** | **97.25** |
| buffalo_s | 71.87 | 99.70 | 98.00 | 96.58 | 95.02 |

### 2.5 特征维度与输出格式

识别模型输出的 **embedding 为 512 维 L2 归一化向量**，可直接用于余弦相似度计算。这与 Milvus 等向量数据库的 IP（内积）索引完美匹配。

检测模型输出包括：
- 人脸边界框 (x1, y1, x2, y2)
- 5 个或 106 个关键点对齐坐标（视模型 pack 而定）
- 人脸质量分数 (detection score)
- 可选：性别、年龄预测

## 3. 核心能力与使用

### 3.1 快速入门

#### 安装

```bash
# CPU 推理
pip install insightface onnxruntime

# GPU 推理
pip install insightface onnxruntime-gpu

# 含 GUI 评估工具
pip install "insightface[gui]"
insightface-gui
```

#### 最简人脸检测与识别示例

```python
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# 初始化：自动下载 buffalo_l 模型（含 SCRFD 检测 + ArcFace 识别）
app = FaceAnalysis(
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
    name='buffalo_l'
)
app.prepare(ctx_id=0)  # 自动双尺度检测：128x128 + 640x640

# 输入图像
img = cv2.imread("input.jpg")
faces = app.get(img)

# 输出每张人脸
for face in faces:
    # 人脸框
    bbox = face.bbox  # [x1, y1, x2, y2]
    # 5 个关键点
    landmarks = face.kps  # [[x1, y1], [x2, y2], ..., [x5, y5]]
    # 512 维特征向量（L2 归一化）
    embedding = face.embedding  # shape: (512,)
    # 相似度分数（用于 1:1 对比）
    score = np.dot(embedding, query_embedding)
    # 性别 & 年龄（buffalo_l 等 Pack 支持）
    gender = face.gender  # 0=Male, 1=Female
    age = face.age        # 预测年龄
    # 检测置信度
    det_score = face.det_score

# 可视化结果
rimg = app.draw_on(img, faces)
cv2.imwrite("output.jpg", rimg)
```

### 3.2 纯检测模式

如果仅需人脸检测（不提取特征），可启用最小化模型加载：

```python
app = FaceAnalysis(allowed_modules=['detection'])
app.prepare(ctx_id=0)
faces = app.get(img)
for face in faces:
    print(face.bbox, face.det_score)
```

### 3.3 1:1 人脸验证

```python
import numpy as np
from insightface.app import FaceAnalysis

app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0)

img1 = cv2.imread("person_a.jpg")
img2 = cv2.imread("person_b.jpg")

faces1 = app.get(img1)
faces2 = app.get(img2)

if faces1 and faces2:
    sim = np.dot(faces1[0].embedding, faces2[0].embedding)
    print(f"相似度: {sim:.4f}")  # > 0.6 通常判定为同一人
```

### 3.4 1:N 人脸检索

```python
from insightface.app import FaceAnalysis
from insightface.data.builtin import get_vector

app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0)

# 构建人脸库
db = app.get_database("/path/to/gallery")

# 查询
img = cv2.imread("query.jpg")
faces = app.get(img)
for face in faces:
    result = db.get_topk(face.embedding, k=5)
    for r in result:
        print(f"匹配: {r.name}, 相似度: {r.score:.4f}")
```

### 3.5 自定义模型加载

用户训练的检测/识别模型转为 ONNX 后，可直接加载：

```python
# 加载自定义检测模型
detector = insightface.model_zoo.get_model('my_scrfd.onnx')
detector.prepare(ctx_id=0)

# 加载自定义识别模型
recognizer = insightface.model_zoo.get_model('my_arcface.onnx')
recognizer.prepare(ctx_id=0)
```

### 3.6 模型 pack 选型建议

| 场景 | 推荐 Pack | 理由 |
|------|-----------|------|
| 桌面/服务器，精度优先 | **buffalo_l** | 精度最高，含属性分析 |
| 边缘设备 / 实时视频流 | **buffalo_s** | 精度高+速度适中 (159MB) |
| 嵌入式 / 内存受限 | **buffalo_sc** | 最小体积 (16MB)，不含对齐/属性 |
| 大规模底库，极端精度 | **buffalo_m** | GLINT360K 训练，跨种族泛化更强 |

## 4. 结束语

InsightFace 是目前开源人脸分析领域最成熟的方案，其核心价值在于：

1. **检测精度高且快**：SCRFD 在多尺度人脸检测上远超 RetinaFace，同时推理仅需 4~30ms。
2. **识别精度对标商业系统**：buffalo_l 的 LFW 精度 99.83%、IJB-C 97.25%，与商汤、旷视等商用方案处于同一水平。
3. **部署极其方便**：Python 包 + ONNX Runtime 后端，一行代码即可运行；无需安装 MXNet 等重型框架。
4. **生态完善**：从检测、对齐、识别、属性分析到人脸交换、3D 重建、活体检测，覆盖完整人脸分析链路。
5. **多平台部署**：Python SDK → REST API Server → C++ SDK (InspireFace) → 移动端 (NCNN/MNN/TNN)，可覆盖云-边-端全场景。

后续在 HermesAgent 系统中集成时，建议采用如下链路：

```
输入帧 → SCRFD 检测 → 仿射对齐 → ArcFace 提取 512 维 embedding
                                              ↓
                                    Milvus IP 索引检索
                                              ↓
                                      阈值决策 + 质量过滤
```

这一步中，`app.prepare()` 自动执行的双尺度检测（128×128 + 640×640）和多关键点对齐，已经涵盖了商业系统的核心步骤——不再需要额外开发对齐和质量评估模块即可达到可商用的效果。

---

## 附录：参考资源

- InsightFace 开源项目：https://github.com/deepinsight/insightface
- SCRFD 论文：Deng et al., "SCRFD: Self-Calibrating and Replicable Face Detector", ICLR 2022
- ArcFace 论文：Deng et al., "ArcFace: Additive Angular Margin Loss for Deep Face Recognition", CVPR 2019
- PartialFC 论文：An et al., "Partial FC: Training Large Face Recognition Models on Thousands of GPUs", CVPR 2022
- Model Zoo：https://github.com/deepinsight/insightface/wiki/Model-Zoo
- InsightFace Server：https://github.com/deepinsight/insightface/tree/master/server
- InspireFace C++ SDK：https://github.com/deepinsight/insightface/tree/master/cpp-package/inspireface

