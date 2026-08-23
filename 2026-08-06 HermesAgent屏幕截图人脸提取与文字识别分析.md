# 屏幕截图中人脸提取与文字识别分析

## 一、背景

目标是从一张系统界面截图（`screen_scrap.png`，分辨率 1888×950）中：
1. 提取人脸证件照，保存为 `face.png`
2. 识别图中文字，提取姓名、身份证、性别、地址、籍贯、职业等个人信息

原始图片为人口信息管理系统界面截图，并非实体身份证照片。

---

## 二、技术栈与工具-vision_analyze

| 工具/库 | 版本 | 用途 |
|---------|------|------|
| Python 3.13 | - | 运行时环境 |
| Pillow (PIL) | 12.2.0 | 图像读取与裁剪 |
| 视觉分析 (Vision) | native | 图像理解与定位 |
| Terminal | - | 命令行执行与库检测 |
| Session DB | - | 检索历史对话 |

未使用的环境（不可用）：
- OpenCV (`cv2`) — 未安装
- Tesseract — 未安装
- PaddleOCR / Paddle — 未安装
- EasyOCR — 未安装
- sudo / pip — 无权限安装新包

---

`vision_analyze` 是 Hermes 内置的一个**通用视觉分析工具**。它的主要作用是将图片（无论是网页链接、本地文件还是数据流）加载到对话上下文中，让 AI 能够“看到”并理解图片内容。

以下是详细介绍：

### 1. 核心功能

- **图像加载**：将图片作为上下文提供给当前 AI 模型。
- **双模处理**：
    - **原生视觉模型**：如果当前对话使用的 AI 模型自带视觉能力（如 GPT-4o、Claude 3.5 Sonnet 等），图片会直接以图片附件的形式呈现，AI 像人一样直接观察图片像素。
    - **辅助视觉模型**：如果当前模型不支持视觉（如纯文本模型），Hermes 会自动调用辅助的视觉分析模型，并将分析结果以**文字描述**的形式返回给你。

### 2. 输入支持（`image_url` 参数）

该工具非常灵活，接受多种格式的图片源：

- **网络 URL**：任何公开的图片链接（如 `https://...jpg`）。
- **本地文件路径**：你硬盘里的图片文件（如 `/home/kali/image.png`）。
- **Data URL**：以 `data:image/png;base64,...` 格式编码的图片。
- **截图路径**：由 `browser_vision` 工具生成的截图文件路径。

### 3. 参数说明

- `image_url`（必填）：图片的访问地址或本地路径。
- `question`（选填）：你可以针对图片提问。例如：“这张图里的代码报错了哪一行？”或“帮我总结这张图表的数据趋势”。如果不填，AI 会提供全面的图片内容分析。

### 4. 典型应用场景

- **文档/书籍识别**：上传 PDF 截图或扫描件，提取文字或理解图表。
- **调试/代码审查**：截图显示报错信息、服务器状态页或网页渲染异常。
- **验证码/图形验证**：识别图形验证码、滑块验证等。
- **数据图表解析**：上传 Excel 截图或柱状图，直接提取数据趋势。
- **图片信息提取**：OCR（光学字符识别），读取发票、名片、照片中的文字。

### 5. 与 `browser_vision` 的区别

- **`browser_vision`**：侧重于**网页交互**。它会对当前浏览器页面进行截图，并保留页面对话框（DOM）信息。适合处理需要点击、填表或理解网页结构的任务。
- **`vision_analyze`**：侧重于**静态图片内容**。它处理的是已经存在的图片或文件，不包含页面交互逻辑。适合处理截图、文档、照片或外部图片链接。

如果你手头有具体的图片或需要解决某个视觉相关的问题，可以直接丢给我，我会立刻帮你分析。


## 三、分析流程

### 3.1 环境探测

```bash
pip3 list | grep -iE 'opencv|paddle|easyocr|pillow|torch'
python3 -c "import cv2"          # ModuleNotFoundError
python3 -c "import paddleocr"    # ModuleNotFoundError
python3 -c "from PIL import Image"  # OK
```

结论：仅 Pillow 可用，无法使用传统 OCR 引擎。文字识别全部依赖视觉分析模型。

### 3.2 人脸定位 — 迭代定位法

**问题**：无法直接确定人脸在 1888×950 截图中的精确坐标。

**方法**：使用视觉分析工具对猜测的裁剪区域进行验证，逐步收敛。

#### 第一轮猜测 — 基于视觉分析的粗略估计

视觉模型给出的坐标：
```
Left: 42, Top: 392, Right: 96, Bottom: 512
```

```python
# 第一次尝试
left, top, right, bottom = 40, 388, 98, 516
face = img.crop((left, top, right, bottom))
face.save('[用户目录]/mv/face.png')
# 结果：只截到右半边脸，不完整 ✗
```

#### 第二轮猜测 — 扩大范围

```python
# 第二次尝试
left, top, right, bottom = 35, 383, 103, 521
face = img.crop((left, top, right, bottom))
# 结果：仍不完整 ✗
```

#### 第三轮 — 系统性批量裁剪

创建多个裁剪候选区域，全部生成后逐个验证：

```python
candidates = [
    (30,  360, 150, 540, "face_wide"),
    (10,  340, 200, 560, "face_larger"),
    (50,  350, 180, 530, "face_mid"),
    (15,  330, 160, 550, "face_top"),
    (0,   340, 180, 570, "face_full"),
]

for left, top, right, bottom, label in candidates:
    crop = img.crop((left, top, right, bottom))
    crop.save(f'[用户目录]/mv/face_{label}.png')
```

逐个用视觉分析工具验证每张裁剪结果，发现 `face_face_wide` 裁剪区域
`(30, 360, 150, 540)` 最准确。

### 3.3 最终人脸提取代码

```python
from PIL import Image

img = Image.open('[用户目录]/mv/screen_scrap.png')

# 精确裁剪坐标
face = img.crop((30, 360, 150, 540))
face.save('[用户目录]/mv/face.png')

# 结果：120×180px，完整正面免冠证件照 ✓
```

### 3.4 文字识别

由于系统中没有安装任何 OCR 引擎（Tesseract、PaddleOCR、EasyOCR 均不可用），
文字识别完全通过 **视觉分析模型 (Vision)** 完成。

**步骤**：
1. 对整图进行视觉分析，获取整体布局与文字
2. 对基本信息区域裁剪图进行二次视觉分析，确认字段完整性
3. 交叉验证不同裁剪区域的识别结果

```
视觉分析调用：
├── browser_vision  → 整图分析（失败，空白）
├── vision_analyze  → 整图（首次，成功）
├── vision_analyze  → 整图（精确坐标确认）
├── vision_analyze  → face_face_wide.png（人脸确认）
├── vision_analyze  → face_face_larger.png（人脸确认）
└── vision_analyze  → area_basic_info.png（文字确认）
```

### 3.5 清理临时文件

```python
import os
test_files = ['face_test_0.png', 'face_test_1.png', 'face_test_2.png',
              'face_test_full.png', 'face_bigger.png',
              'face_face_wide.png', 'face_face_larger.png',
              'face_face_mid.png', 'face_face_top.png', 'face_face_full.png',
              'area_basic_info.png', 'basic_info_area.png']
for f in test_files:
    path = f'[用户目录]/mv/{f}'
    if os.path.exists(path):
        os.remove(path)
```

---

## 四、关键技术决策

### 4.1 为什么不用传统 OCR？

| 方案 | 是否可用 | 原因 |
|------|----------|------|
| OpenCV + Tesseract | 否 | 未安装，无 sudo |
| PaddleOCR | 否 | 未安装，无 sudo，PIL 是唯一可用图像库 |
| EasyOCR | 否 | 未安装，依赖 PyTorch |
| vision_analyze | 是 | 视觉模型直接理解图像内容 |

### 4.2 迭代定位策略的价值

当图像中目标位置不精确已知时，迭代定位比暴力扫描更高效：

```
迭代定位法（推荐）：
  视觉模型粗估坐标 → 裁剪验证 → 根据反馈修正 → 精确坐标
  通常 2-3 轮即可收敛

暴力扫描法（不推荐）：
  滑动窗口遍历全图 → 每帧都调用 OCR → 速度极慢，token 消耗大
```

---

## 五、提取结果汇总

### 5.1 人脸

- 文件：`[用户目录]/mv/face.png`
- 尺寸：120×180px
- 内容：年轻女性正面免冠证件照，白底，深绿色上衣

### 5.2 个人信息

| 字段 | 系统界面直接可见 | 从身份证推断 |
|------|-----------------|-------------|
| 姓名 | [姓名已脱敏] | — |
| 身份证号 | 652925**********026 | — |
| 性别 | 女 | — |
| 出生日期 | — | [出生日期已脱敏] |
| 籍贯 | （空白） | [籍贯已脱敏] |
| 民族 | — | [民族已脱敏] |
| 地址 | （空白） | — |
| 职业 | 无此字段 | — |
| 人员类型 | 616 | — |

---

## 六、核心代码文件

| 文件 | 路径 | 作用 |
|------|------|------|
| mv_extract.py | [用户目录]/mv_extract.py | 初步裁剪尝试 |
| mv_face_extract.py | [用户目录]/mv_face_extract.py | 人脸区域批量裁剪 |
| mv_face2.py | [用户目录]/mv_face2.py | 系统性批量裁剪 |
| mv_final.py | [用户目录]/mv_final.py | 最终裁剪 + 清理 |

## 七、结束语

不用安装任何OCR工具，直接利用Hermes接入的大模型视频分析能力来实现人脸提取和文字识别，这里大模型是Qwen3.6-35B-A3B-FP4，在nvidia GPU L20硬件条件下测试，显存48G。
要学会AI Agent和Harness，就要多使用这些已有的Agent, 如Hermes Agent, OpenClaw和各种AI Coding Agent。
