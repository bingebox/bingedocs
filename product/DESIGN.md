# DESIGN.md — 产品风格规范（设计变量）

> 用途：① Agent 出设计前先读本文件；② 可整体导入 OpenPencil 的素材中心（Asset Centre / `op styles`），让 MCP 的 `get_style_guide` 能取到。
> 使用：把占位值替换成你产品的真实 token，并在 OpenPencil 里建对应的**设计变量**（`op vars:set`），设计稿中用 `$变量名` 引用，导出代码时自动映射为 CSS 自定义属性 `var(--xxx)`。

## 品牌基调

- 一句话描述：（例：清爽、克制、面向效率工具的专业感）
- 关键词：（例：clean / focused / calm）
- 反例（不要做的事）：（例：不用渐变按钮、不用超过 3 种主色）

## 颜色

| Token | 值 | 用途 |
|---|---|---|
| `--color-bg` | #FFFFFF | 页面背景 |
| `--color-bg-subtle` | #F7F8FA | 次级背景 / 卡片底 |
| `--color-text` | #1A1D21 | 主文本 |
| `--color-text-muted` | #6B7280 | 次要文本 |
| `--color-primary` | #2563EB | 主操作色 |
| `--color-primary-hover` | #1D4ED8 | 主操作悬停 |
| `--color-danger` | #DC2626 | 危险/错误 |
| `--color-border` | #E5E7EB | 描边/分割线 |

（深色主题在此追加一组 `--dark-*` token）

## 字体

- 中文：PingFang SC / Microsoft YaHei；英文/数字：Inter
- 字号阶梯：`--font-size-xs:12` / `sm:14` / `md:16` / `lg:20` / `xl:28` / `2xl:40`
- 行高：正文 1.6，标题 1.3
- 字重：正文 400，强调 500，标题 600/700

## 间距与圆角

- 间距基数 4px；常用：8 / 12 / 16 / 24 / 32 / 48
- 卡片内边距 24，区块间距 48
- 圆角：`--radius-sm:6` 按钮/输入框 · `--radius-md:12` 卡片 · `--radius-lg:16` 弹窗/大卡片
- 阴影：`--shadow-card: 0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04)`

## 组件约定

- 按钮：高 40（主）/ 32（次）；圆角 8；主按钮实心、次按钮描边、文字按钮无背景
- 输入框：高 40；聚焦态 2px primary 描边
- 表格：表头 12px 大写灰字；行高 48；斑马纹不用，用 hover 高亮
- 表单标签：字段上方，14px，距字段 8px

## 版式

- 桌面内容区最大宽 1200，居中；侧栏 240
- 移动端：390×844 原型；底部安全区留 34
- 栅格：24 列 / 24px gutter（桌面）

## 图标

- 线性风格，1.5px 描边，圆角端点；16/20/24 三档
- 来源：Iconify（OpenPencil 内置图标选择器可直接用）
