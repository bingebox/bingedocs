---
tags: [技术, TypeScript, Vue, AI应用, 学习计划, 前端]
星期: 星期三
categories: [tech]
---

# TypeScript 学习方案（Vue 开发 + AI 应用方向）

> **目标**：在 4 周内从"会 JavaScript"到"能用 TS 独立交付 Vue + AI 应用功能"，不追求成为类型体操高手，追求**生产可用 + AI 场景刚需**。
>
> **关联阅读**：
> - [AI coding从辅助编程走向全流程接管](AICoding/2026-07-02%20AI%20coding从辅助编程走向全流程接管.md)（AI 辅助写 TS 的效率红利）
> - [LLM使用教程-Transformer直觉到生产级调用](2026-08-31%20LLM使用教程-Transformer直觉到生产级调用.md)（AI 应用章节的 LLM 调用基础）

## 1. 总体结论

- **值得学，且投入产出比高**：Vue 3 官方模板已全面 TS 化，AI 应用开发（Vercel AI SDK 6.x、LangChain.js 1.x、Mastra）全部是 TypeScript-first，类型系统是消费 LLM 输出（结构化数据、tool schema）的核心安全网。
- **学习重心不是"类型系统全掌握"**，而是三块：① 类型推断与常用泛型（占日常 80%）；② Vue 组合式 API 的类型（`ref`/`reactive`/`defineProps`）；③ AI SDK + Zod 的类型化 LLM 输出。类型体操（条件类型递归、模板字面量高级技巧）用到再查，不必前置学习。
- **版本事实（2026-09 核实）**：
  - TypeScript 6.0（2026-03 发布）是最后一个 JS 编译器版本，为 7.0 对齐做准备；
  - **TypeScript 7.0 已发布（npm 可装 `typescript@7`，VS Code 内置可切换）——用 Go 重写的原生编译器，速度数量级提升**；语言特性与 5.x/6.x 基本一致；
  - 结论：**直接学 6.0/7.0，不要找只讲 4.x/5.x 的旧教程**（旧教程内容 90% 仍适用，但 tsconfig 推荐值已更新）。
- **AI 应用库选型（与 Vue 搭配）**：
  | 库 | 定位 | 版本（2026-09 核实） | 何时选 |
  |---|---|---|---|
  | **Vercel AI SDK** | 流式 UI + tool calling + 结构化输出，provider 无关（100+ 模型），官方支持 Vue | ai@6.x | 首选。Vue/Next 前端直接 `useChat`（Vue 版 hooks）接 LLM |
  | **LangChain.js / LangGraph.js** | RAG、多步 Agent 编排、200+ 数据源 loader | langchain@1.4.x | 后端重编排、复杂 RAG 管线时补充 |
  | **Mastra** | TS 原生 Agent 框架 | 活跃 | 想 TS 全栈做 Agent 时备选 |
  | **Zod** | 运行时 schema 校验 + 类型推导（AI 场景事实标准） | 3.x | 必学，是 TS×AI 的粘合剂 |

## 2. 环境准备（半天搞定，之后不用动）

```bash
# Node 20+（推荐 22 LTS），全局工具
npm i -g typescript@latest tsx   # tsc 检查 + tsx 直接跑 .ts 文件，学习期不配打包器

# 单文件练习目录
mkdir ts-learning && cd ts-learning
npx tsc --init   # 生成 tsconfig.json，改两处即可
```

```jsonc
// tsconfig.json 学习期配置
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,            // 从第一天就开，后面补很痛苦
    "noUnusedLocals": true,
    "skipLibCheck": true,
    "noEmit": true             // 学习期只看类型错误，不产出 js
  }
}
```

工具链：**VS Code + 官方 Vue 语言特性插件（Volar）**。TS 学习的正确方式是"边写边看 IDE 悬浮提示和红色波浪线"，不配好 IDE 等于白学一半。

## 3. 四周学习计划（每天 1–1.5 小时）

### 第 1 周：类型系统核心（脱离框架，纯 .ts 文件 + tsx 跑）

| 天 | 内容 | 验收标准 |
|---|---|---|
| D1 | 基础类型、`interface` vs `type`、类型推断 | 手写 5 个接口描述"用户/订单/检索结果"，零 `any` |
| D2 | 联合类型 + **类型收窄**（`in`、`instanceof`、`discriminated union`） | 写一个处理 `{type:'image'}\|{type:'text'}\|{type:'video'}` 多模态结果的函数 |
| D3 | 函数类型、泛型入门（`<T>`、约束 `extends`、默认泛型） | 写泛型 `parseResult<T>(raw: unknown): T` |
| D4 | `unknown` vs `any`、类型断言、`as const`、可空处理 | 给一组 `any` 旧代码重写为 strict 安全版本 |
| D5-6 | **Zod**（重点，AI 场景刚需）：`z.object` 定义 schema → `z.infer` 推导类型 → `parse` 运行时校验 | 用 Zod 定义"LLM 返回的检索结果" schema 并校验 mock 数据 |
| D7 | 复盘 + 官方 Handbook 的 "Narrowing / Generics" 章节查漏补缺 | — |

**核心心智模型**：TypeScript 的 80% 日常 = "推断出什么类型 + 收窄到确定分支"。`any` 是逃生舱不是常态。

### 第 2 周：Vue 3 中的 TypeScript（Composition API 为主线）

以 `npm create vue@latest`（选 TypeScript + Vite + Pinia + Vue Router）为脚手架，全程用 `script setup`：

| 天 | 内容 | 验收标准 |
|---|---|---|
| D1 | `ref`/`reactive` 的泛型参数、`Ref<T>`、解构 `toRefs` | 写一个带类型状态的计数器组件 |
| D2 | `defineProps<T>()` / `defineEmits<T>()` 类型化（**Vue 3.3+ 泛型语法**，编译期类型、零运行时开销） | 写一个子组件，父传 props 时故意传错类型验证 IDE 报错 |
| D3 | 组件泛型（`<script setup generic="T">`）、`shallowRef` 与大型对象 | 写一个泛型 `DataTable<T>` 组件 |
| D4 | **Pinia 类型化 store**：`defineStore` 的 Setup 语法写法 | 建一个 `searchStore`（query、results、loading 全带类型） |
| D5 | Vue Router 类型：路由 meta 泛型、`RouteParams` | 给路由参数 `/search/:id` 做类型推导 |
| D6-7 | 综合练习：**给一个既有 JS 版 Vue 页面加类型**（最贴近公司实际：存量改造） | 完成一个页面的 JS→TS 迁移，`tsc` 零错误 |

要点：
- Vue 的 `ref` 自动解包是类型系统里最容易踩的坑（`ref` 在对象里和单独用行为不同），D1 重点体会；
- 公司存量项目若是 Options API + JS，迁移顺序：先装 TS 只迁移新文件（`allowJs: true` 过渡），不要一次性全量迁移。

### 第 3 周：AI 应用开发（Vercel AI SDK 6.x + 内网 vLLM）

AI SDK 官方支持 Vue（hooks 库），且 provider 无关——**直接对接内网 vLLM 的 OpenAI 兼容端点**（本机 `http://vllm:38081/v1`，模型 Qwen3.8-27B）：

```ts
// 1) 对接 OpenAI 兼容端点（内网 vLLM）
import { createOpenAI } from "@ai-sdk/openai";
import { streamText, generateObject, tool } from "ai";
import { z } from "zod";

const vllm = createOpenAI({
  baseURL: "http://vllm:38081/v1",
  apiKey: "not-needed",        // vLLM 默认无鉴权，占位
  compatibility: "strict",
});
```

```ts
// 2) 结构化输出：Zod schema 同时充当 ①请求时给 LLM 的格式约束 ②返回的 TS 类型 ③运行时校验
const searchResultSchema = z.object({
  matched_files: z.array(z.object({
    path: z.string(),
    confidence: z.number().min(0).max(1),
    ocr_text: z.string().optional(),
    faces: z.array(z.object({ name: z.string(), score: z.number() })).default([]),
  })),
  summary: z.string(),
});

const { object: result } = await generateObject({
  model: vllm("Qwen3.8-27B-MTP-Q4_K_M"),
  schema: searchResultSchema,
  prompt: "根据用户描述在截图库中检索：办公大楼门口下午拍的照片",
});
// result: 编译期即 searchResultSchema 推导类型，运行期已被 zod 校验
```

```ts
// 3) Tool calling + 流式 UI（Vue 端用 useChat，ai 包 6.x 提供 Vue hooks）
const tools = {
  searchScreenshots: tool({
    description: "按语义描述检索截图库",
    parameters: z.object({ query: z.string(), topK: z.number().default(5) }),
    execute: async ({ query, topK }) => { /* 调后端检索 API */ },
  }),
};

// 后端 route:
// streamText({ model: vllm("..."), messages, tools })
// 前端: const { messages, input, handleInputChange } = useChat({ url: "/api/chat" })
```

| 天 | 内容 | 验收标准 |
|---|---|---|
| D1-2 | AI SDK 核心 API：`generateText` / `streamText` / `useChat`（Vue 端），跑通与内网 vLLM 的流式对话 | 一个 Vue 聊天页面流式吐字 |
| D3-4 | **`generateObject` + Zod 结构化输出**（LLM 不可靠输出的正解：schema 约束 + 校验 + 自动重试） | LLM 输出的"检索结果对象"100% 通过 zod 校验 |
| D5 | **tool calling**：定义 TS 类型化工具、LLM 决定调用、循环执行 | LLM 能自主调 `searchScreenshots` 工具并汇总回答 |
| D6-7 | 结合公司场景做小 demo：**截图多模态检索系统的前端对话入口**（接现有检索后端，LLM 做查询理解 + 结果总结） | 完整可演示的小闭环 |

为什么 AI 应用必须 TS：LLM 输出本质是"不可信数据"，`Zod 校验 + z.infer 类型推导` 让运行时校验结果直接变成编译期类型，一条链路覆盖"防幻觉字段 + 编辑器补全"。这是 JS 做不到的。

### 第 4 周：综合实战 + 工程化收尾

- **D1-3：迷你项目**：「截图检索 AI 助手」= Vue3 + TS + Pinia + AI SDK + vLLM，功能：自然语言查询 → LLM 解析为结构化检索条件（Zod）→ 调检索 API → 流式展示结果 + LLM 总结。这就是第 3 周 demo 的补全与打磨，也正好是截图检索系统的缺失前端。
- **D4：工程化**：ESLint + Prettier + `tsc --noEmit` 进 CI 习惯；`strict` 下处理第三方 JS 库（`declare module` 补 d.ts 的最简手法）。
- **D5-7：留白**——把迷你项目里卡住的类型问题做成自己的"TS 踩坑笔记"（放本目录追加到本文档末尾）。

## 4. 资料清单（只列主线，不贪多）

| 优先级 | 资料 | 用法 |
|---|---|---|
| 必读 | 官方 Handbook（typescripthandbook.cn 中文版）"类型脚本/类型推断/收窄/泛型" 4 章 | 第 1 周对照读 |
| 必读 | Vue 官方文档 TS 章节（vuejs.org，composition-api + defineProps 类型化） | 第 2 周 |
| 必读 | AI SDK 官方文档 ai-sdk.dev（Vue 章节 + generateObject + tools） | 第 3 周 |
| 选读 | The Modern TypeScript Handbook（mattpocock 版，讲 5.x+ 现代惯用法） | 第 4 周后 |
| 工具 | TypeScript Playground（play.typescriptlang.org） | 任何类型问题先丢进去玩 5 分钟 |
| 辅助 | **AI 辅助编程**：写类型卡壳时直接问 AI"这段为什么报错"，比自己翻手册快；但要先自己读报错信息（见关联阅读 AICoding 系列） | 全程 |

## 5. 风险与常见坑

| 坑 | 缓解 |
|---|---|
| 陷入类型体操，第 1 周就卡在条件类型/高级泛型 | 硬性规则：日常只用"推断+收窄+简单泛型"，高级特性**用到再学**，本方案 D7 前不碰 `infer`/模板字面量递归 |
| `strict` 开着难受、想退回 `any` | 不退回。逃生舱用 `unknown`（强制收窄）而非 `any`；第三方 JS 库用局部断言 |
| 旧教程讲 4.x/5.x，tsconfig 推荐值过时 | 以 typescriptlang.org 当前 Handbook 为准；`npx tsc --init` 生成的基线即可 |
| AI SDK 文档以 React/Next 为主，Vue 示例少 | Vue 支持是官方的（useChat 等 hooks 有 Vue 版）；示例不够时看 vercel/ai 仓库 `packages/vue` 源码，或退一步用 `onMounted` + `streamText` fetch 流自己接（半天能通） |
| 内网 vLLM 端点模型名写错报 404 | 模型名必须与 vLLM 启动的 served model 完全一致，先 `curl http://vllm:38081/v1/models` 确认 |
| 4 周学不完 | 计划按"可交付"而非"学完"设计：2 周末已能写类型化 Vue 页面，3 周末已能接 AI，第 4 周可整体压缩 |

## 6. 下一步 checklist（需拍板）

- [ ] 第 2 周练习用**公司存量 Vue 项目**改造还是新建 demo？（建议新建，避免污染生产仓）
- [ ] 内网 vLLM 的 served model 名称确认（`curl http://vllm:38081/v1/models`）
- [ ] 第 4 周迷你项目是否要接到截图检索系统真实后端？（接上则同时推进检索系统前端）
