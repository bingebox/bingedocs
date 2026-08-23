# MCP（Model Context Protocol）技术知识体系

---

## 目录

1. [MCP 概述](#1-mcp-概述)
2. [MCP 架构](#2-mcp-架构)
3. [核心概念](#3-核心概念)
4. [MCP 服务器](#4-mcp-服务器)
5. [MCP 客户端](#5-mcp-客户端)
6. [MCP 传输层](#6-mcp-传输层)
7. [MCP 数据层协议](#7-mcp-数据层协议)
8. [开发 MCP 服务器](#8-开发-mcp-服务器)
9. [开发 MCP 客户端](#9-开发-mcp-客户端)
10. [开发者工具](#10-开发者工具)
11. [示例与生态](#11-示例与生态)
12. [参考链接](#12-参考链接)

---

## 1. MCP 概述

**Model Context Protocol（模型上下文协议）** 是一个开放标准，用于在 AI 应用与外部系统之间建立连接。它类似于 USB-C 端口——为 AI 提供了一个标准化的接口，以连接数据源、工具和工作流。

### 核心价值

对 **开发者** 而言，MCP 是一个开源标准，无需再为每个 AI 应用编写自定义集成。
对 **AI 应用** 而言，MCP 允许轻松添加对任何外部系统的支持——只需构建一次 MCP 服务器，它就可以与任何支持 MCP 的客户端工作。
对 **用户** 而言，MCP 确保他们的数据和工具得到安全、有控制地访问，用户可以始终掌握最终决定权。

### 生态支持

- **AI 应用**：Anthropic Claude 及其生态系统、各种 AI 平台
- **MCP 服务器**：官方示例服务器（Fetch、Filesystem、Git、Memory 等）
- **MCP 客户端**：支持 MCP 协议的各类客户端实现

---

## 2. MCP 架构

### 参与者模型

MCP 遵循 Host/Client/Server 三层参与者模型：

| 参与者 | 角色描述 | 示例 |
|--------|----------|------|
| **MCP Host** | 提供用户界面的应用程序，管理整体用户体验 | Claude.ai、Claude Desktop、IDE |
| **MCP Client** | 维护和管理与特定服务器的连接 | 每个客户端处理与一个服务器的直接通信 |
| **MCP Server** | 提供特定上下文/能力 | 文件服务器、数据库服务器、API 网关 |

### 分层架构

```
┌─────────────────────────────────────────┐
│         Host Application                │
│  (Claude Desktop / IDE / Agent)         │
├─────────────────────────────────────────┤
│      MCP Client (连接维护者)             │
├─────────────────────────────────────────┤
│    传输层 (Transport Layer)              │
│  - STDIO: 本地进程间通信                 │
│  - Streamable HTTP: 远程多客户端         │
├─────────────────────────────────────────┤
│    数据层 (Data Layer)                  │
│  - 工具 (Tools) - 模型控制              │
│  - 资源 (Resources) - 应用控制          │
│  - 提示 (Prompts) - 用户控制            │
└─────────────────────────────────────────┘
```

---

## 3. 核心概念

### 3.1 能力分类

MCP 通过三大构建块提供功能：

| 能力 | 控制方 | 描述 | 示例 |
|------|--------|------|------|
| **工具 (Tools)** | 模型 | LLM 可主动调用的函数，基于用户请求决定使用。可写数据库、调用外部 API、修改文件或触发其他逻辑 | 搜索航班、发送消息、创建日历事件 |
| **资源 (Resources)** | 应用 | 只读数据源，为上下文提供信息，如文件内容、数据库模式或 API 文档 | 检索文档、访问知识库、读取日历 |
| **提示 (Prompts)** | 用户 | 预构建的指令模板，告诉模型如何与特定工具和资源协作 | 计划假期、总结会议、起草邮件 |

### 3.2 工具（Tools）

**工具使 AI 模型能够执行操作。** 每个工具定义了一个具有类型化输入和输出的特定操作。模型基于上下文请求工具执行。

**协议操作：**

| 方法 | 用途 | 返回 |
|------|------|------|
| `tools/list` | 发现可用工具 | 工具定义数组（含 Schema） |
| `tools/call` | 执行特定工具 | 工具执行结果 |

**工具定义示例：**

```json
{
  "name": "searchFlights",
  "description": "搜索可用航班",
  "inputSchema": {
    "type": "object",
    "properties": {
      "origin": { "type": "string", "description": "出发城市" },
      "destination": { "type": "string", "description": "到达城市" },
      "date": { "type": "string", "format": "date", "description": "旅行日期" }
    },
    "required": ["origin", "destination", "date"]
  }
}
```

**人机协同：** 工具可能需要用户同意后方可执行，确保用户保持对模型操作的控制。

### 3.3 资源（Resources）

**资源提供结构化信息访问**，AI 应用可检索并提供给模型作为上下文。

**工作方式：**
- 每个资源有唯一的 URI（如 `file:///path/to/document.md`）
- 声明 MIME 类型以适当处理内容
- 应用可决定如何使用信息——选择相关部分、嵌入搜索或全部提供给模型

**两种发现模式：**

1. **直接资源**：固定 URI，指向特定数据
   - 示例：`calendar://events/2024` — 返回 2024 年日历可用性

2. **资源模板**：动态 URI，含参数用于灵活查询
   - 示例：`travel://activities/{city}/{category}` — 按城市和分类返回活动

**协议操作：**

| 方法 | 用途 | 返回 |
|------|------|------|
| `resources/list` | 列出可用直接资源 | 资源描述符数组 |
| `resources/templates/list` | 发现资源模板 | 资源模板定义数组 |
| `resources/read` | 检索资源内容 | 含元数据的数据 |
| `resources/subscribe` | 监控资源变更 | 订阅确认 |

**参数补全（Parameter Completion）：**
动态资源支持参数补全。例如输入 `Par` 作为 `weather://forecast/{city}` 的输入，可能建议 `Paris` 或 `Park City`。系统帮助发现有效值，无需精确格式知识。

### 3.4 提示（Prompts）

**提示提供可复用模板。** MCP 服务器作者可提供参数化提示以展示如何使用服务器。

**工作方式：**
- 结构化模板定义预期输入和交互模式
- 用户控制，需显式调用而非自动触发
- 支持参数补全帮助用户发现有效参数值

**协议操作：**

| 方法 | 用途 | 返回 |
|------|------|------|
| `prompts/list` | 发现可用提示 | 提示描述符数组 |
| `prompts/get` | 检索提示详情 | 含参数的完整提示定义 |

**提示定义示例：**

```json
{
  "name": "plan-vacation",
  "title": "计划假期",
  "description": "指导假期规划流程",
  "arguments": [
    { "name": "destination", "type": "string", "required": true },
    { "name": "duration", "type": "number", "description": "天数" },
    { "name": "budget", "type": "number", "required": false },
    { "name": "interests", "type": "array", "items": { "type": "string" } }
  ]
}
```

---

## 4. MCP 服务器

MCP 服务器是暴露特定能力给 AI 应用程序的程序，通过标准化协议接口提供功能。

### 4.1 常见服务器类型

- **文件系统服务器**：用于文档访问
- **数据库服务器**：用于数据查询
- **GitHub 服务器**：用于代码管理
- **Slack 服务器**：用于团队通信
- **日历服务器**：用于调度

### 4.2 服务器功能详解

#### 工具执行

```python
@mcp.tool()
async def get_alerts(state: str) -> str:
    """获取美国天气警报
    
    Args:
        state: 美国州代码（如 CA, NY）
    """
    url = f"https://api.weather.gov/alerts/active/area/{state}"
    data = await make_nws_request(url)
    # ... 处理并返回结果
```

#### 资源访问

```json
{
  "uriTemplate": "weather://forecast/{city}/{date}",
  "name": "weather-forecast",
  "title": "天气预报",
  "description": "获取任何城市/日期的天气预报",
  "mimeType": "application/json"
}
```

#### 提示模板

```json
{
  "name": "plan-vacation",
  "title": "计划假期",
  "description": "指导假期规划流程",
  "arguments": [
    { "name": "destination", "type": "string", "required": true },
    { "name": "duration", "type": "number", "description": "天数" },
    { "name": "budget", "type": "number", "required": false },
    { "name": "interests", "type": "array", "items": { "type": "string" } }
  ]
}
```

### 4.3 多服务器协作

MCP 的真正力量在多个服务器协作时展现：

**旅行规划场景示例：**

```
用户触发提示: {
  "prompt": "plan-vacation",
  "arguments": {
    "destination": "Barcelona",
    "departure_date": "2024-06-15",
    "return_date": "2024-06-22",
    "budget": 3000,
    "travelers": 2
  }
}

服务器协作流程:
1. Travel Server → 处理航班、酒店、行程
2. Weather Server → 提供气候数据和预报
3. Calendar/Email Server → 管理日程和通信
```

**完整流程：**
1. AI 首先读取所有选定资源收集上下文
2. 使用此上下文执行一系列工具
3. 在需要时请求用户批准
4. 通过多个 MCP 服务器，用户研究和预订了巴塞罗那之旅

---

## 5. MCP 客户端

MCP 客户端由主机应用程序实例化以与特定 MCP 服务器通信。主机应用（如 Claude.ai 或 IDE）管理整体用户体验并协调多个客户端。每个客户端处理与一个服务器的直接通信。

### 5.1 核心客户端功能

| 功能 | 说明 | 示例 |
|------|------|------|
| **Elicitation（信息 elicitation）** | 服务器在交互期间请求用户特定信息，提供结构化方式在需要时收集信息 | 旅行预订时询问用户座位偏好、房型或联系电话 |
| **Roots（根路径）** | 允许客户端指定服务器应关注的目录，通过协调机制传达预期范围 | 给旅行预订服务器访问特定目录的权限 |
| **Sampling（采样）** | 允许服务器通过客户端请求 LLM 完成，实现代理式工作流 | 旅行服务器发送航班列表给 LLM 请求推荐最佳航班 |

### 5.2 Elicitation 详解

Elicitation 创建动态信息收集：

```
服务器 → 发起 Elicitation → 呈现 elicitation UI → 返回用户响应
```

**Elicitation 组件示例：**

```json
{
  "method": "elicitation/create",
  "params": {
    "message": "请确认巴塞罗那假期预订详情：",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "confirmBooking": { "type": "boolean" },
        "seatPreference": { "type": "string", "enum": ["window", "aisle", "no preference"] },
        "roomType": { "type": "string", "enum": ["sea view", "city view", "garden view"] },
        "travelInsurance": { "type": "boolean", "default": false }
      },
      "required": ["confirmBooking"]
    }
  }
}
```

**用户交互模型：**
- 请求展示：客户端展示 elicitation 请求时，清楚说明哪个服务器在请求、为何需要信息及如何使用
- 响应选项：用户可通过适当 UI 控件提供信息、拒绝提供或取消操作
- 隐私考虑：Elicitation 从不请求密码或 API 密钥

### 5.3 Roots 详解

Roots 定义服务器操作的文件系统边界：

```json
{
  "uri": "file:///Users/agent/travel-planning",
  "name": "Travel Planning Workspace"
}
```

**设计哲学：**
- Roots 是客户端和服务器之间的协调机制，不是安全边界
- 规范规定服务器 "应尊重根边界"，而非 "必须强制执行"
- 实际安全必须在操作系统层面执行，通过文件权限和/或沙箱

### 5.4 Sampling 详解

Sampling 使服务器能够执行 AI 依赖任务而无需直接集成或付费 AI 模型：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "分析这些航班选项并推荐最佳选择："
    }
  ],
  "modelPreferences": {
    "hints": [{ "name": "claude-sonnet-4-20250514" }],
    "costPriority": 0.3,
    "speedPriority": 0.2,
    "intelligencePriority": 0.9
  },
  "systemPrompt": "你是一个帮助游客寻找最佳航班的旅行专家",
  "maxTokens": 1500
}
```

**安全考虑：**
- 采样请求作为其他操作的一部分发生——如工具分析数据
- 作为单独模型处理，保持不同上下文之间的清晰边界
- 允许更高效使用上下文窗口

---

## 6. MCP 传输层

### 6.1 STDIO（标准输入输出）

- **适用场景**：本地进程间通信
- **特点**：适用于单客户端连接
- **限制**：STDIO 服务器 **永远不要写入 stdout**，这会破坏 JSON-RPC 消息
  - 错误：`print("Processing request")`
  - 正确：`print("Processing request", file=sys.stderr)`

### 6.2 Streamable HTTP

- **适用场景**：远程多客户端连接
- **特点**：支持多个客户端连接到同一服务器
- **优势**：适用于 Web 部署、云端服务

---

## 7. MCP 数据层协议

### 7.1 初始化交换

- 客户端发送初始化消息，声明其能力
- 服务器回复自身能力和支持的协议版本
- 协商成功后建立会话

### 7.2 协议消息结构

- **请求**：客户端到服务器，如 `tools/call`
- **响应**：服务器到客户端，包含结果或错误
- **通知**：服务器到客户端，如资源变更通知

### 7.3 变更通知机制

MCP 使用 **变更通知（Change Notifications）** 而非轮询来保持上下文同步：

- 当资源或配置变更时，服务器主动通知客户端
- 避免不必要的轮询请求，提高效率
- 保障实时同步

---

## 8. 开发 MCP 服务器

### 8.1 快速开始示例

**系统要求：**
- Python 3.10+ 或 Node.js
- 最新版本的 `uv`（Python 包管理器）
- MCP SDK 1.2.0+

**安装环境：**

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建项目
uv init weather
cd weather
uv venv
source .venv/bin/activate
uv add "mcp[cli]" httpx
touch weather.py
```

**完整服务器代码（天气服务器）：**

```python
import sys
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 服务器
mcp = FastMCP("weather")

# 常量
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# 辅助函数
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """向 NWS API 发起请求并处理错误"""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """格式化警报特性为可读字符串"""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
"""

# 工具执行
@mcp.tool()
async def get_alerts(state: str) -> str:
    """获取美国天气警报
    
    Args:
        state: 美国州代码（如 CA, NY）
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)
    if not data or "features" not in data:
        return "无法获取警报或无活动警报。"
    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

# 运行服务器
def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

### 8.2 日志最佳实践

```python
import sys
import logging

# ❌ 错误（STDIO）
print("Processing request")

# ✅ 正确（STDIO）
print("Processing request", file=sys.stderr)

# ✅ 正确（STDIO）
logging.info("Processing request")
```

**关键规则：**
- STDIO 服务器：永远不要向 stdout 写入
- HTTP 服务器：标准输出日志是可以的

### 8.3 配置到 Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory", "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
        "run", "weather.py"
      ]
    }
  }
}
```

---

## 9. 开发 MCP 客户端

### 9.1 完整客户端示例

**系统要求：**
- Mac 或 Windows 计算机
- 最新 Python 版本
- 最新 `uv`
- Anthropic API Key

**安装：**

```bash
uv init mcp-client
cd mcp-client
uv venv
source .venv/bin/activate
uv add mcp anthropic python-dotenv
touch client.py
```

**环境变量设置：**

```bash
echo "ANTHROPIC_API_KEY=your-api-key-goes-here" > .env
echo ".env" >> .gitignore
```

**客户端代码：**

```python
import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """连接到 MCP 服务器"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # 列出可用工具
        response = await self.session.list_tools()
        print("\n已连接到服务器，可用工具：", [tool.name for tool in response.tools])

    async def process_query(self, query: str) -> str:
        """使用 Claude 和可用工具处理查询"""
        messages = [{"role": "user", "content": query}]

        # 获取可用工具
        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # 初始 Claude API 调用
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )

        # 处理响应并处理工具调用
        final_text = []
        assistant_message_content = []

        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # 执行工具调用
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[调用工具 {tool_name}，参数 {tool_args}]")

                assistant_message_content.append(content)
                messages.append({
                    "role": "assistant",
                    "content": assistant_message_content
                })
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result.content
                    }]
                })

                # 从 Claude 获取下一个响应
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=messages,
                    tools=available_tools
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("\nMCP 客户端启动！")
        print("输入查询或输入 'quit' 退出。")
        while True:
            try:
                query = input("\n查询: ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\n错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()

async def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python client.py <服务器脚本路径>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

### 9.2 运行客户端

```bash
uv run client.py path/to/server.py        # Python 服务器
uv run client.py path/to/build/index.js    # Node.js 服务器
```

### 9.3 工作流程

```
用户提交查询
    → 客户端获取可用工具列表
    → 查询连同工具描述发送给 Claude
    → Claude 决定使用哪些工具（如有）
    → 客户端通过服务器执行工具调用
    → 结果发送回 Claude
    → Claude 提供自然语言响应
    → 响应展示给用户
```

---

## 10. 开发者工具

### 10.1 MCP Inspector

**MCP Inspector** 是用于测试和调试 MCP 服务器的交互式开发者工具。

**安装与使用：**

```bash
# 直接通过 npx 运行，无需安装
npx @modelcontextprotocol/inspector <command>
npx @modelcontextprotocol/inspector <command> <arg1> <arg2>
```

**检查 npm/PyPI 服务器：**

```bash
# NPM 包
npx -y @modelcontextprotocol/inspector npx @modelcontextprotocol/server-filesystem /Users/username/Desktop

# Python 包
npx -y @modelcontextprotocol/inspector python -m <package-name> <args>
```

**检查本地开发服务器：**

```bash
npx @modelcontextprotocol/inspector node path/to/server/index.js args...
```

### 10.2 功能概览

| 标签页 | 功能 |
|--------|------|
| **服务器连接窗格** | 选择传输方式连接服务器，支持本地服务器自定义命令行参数和环境变量 |
| **资源标签** | 列出所有可用资源，显示资源元数据（MIME 类型、描述），支持资源内容检查和订阅测试 |
| **提示标签** | 显示可用提示模板，展示提示参数和描述，支持自定义参数测试和消息预览 |
| **工具标签** | 列出可用工具，显示工具 Schema 和描述，支持自定义输入测试和结果显示 |
| **通知窗格** | 展示从服务器记录的所有日志和接收到的通知 |

### 10.3 最佳实践

**开发工作流：**
1. 启动开发 — 用服务器启动 Inspector
2. 验证基本连接 — 检查能力协商
3. 迭代测试 — 修改服务器 → 重建 → 重新连接 → 测试影响功能
4. 监控消息 — 测试边缘情况（无效输入、缺失提示参数、并发操作）
5. 验证错误处理 — 确保错误响应正确

---

## 11. 示例与生态

### 11.1 官方参考服务器

| 服务器 | 描述 |
|--------|------|
| **Everything** | 参考/测试服务器，包含提示、资源和工具 |
| **Fetch** | Web 内容获取和转换，用于高效 LLM 使用 |
| **Filesystem** | 安全文件操作，含可配置访问控制 |
| **Git** | 读取、搜索和操作 Git 仓库的工具 |
| **Memory** | 基于知识图谱的持久记忆系统 |
| **Sequential Thinking** | 通过思考序列进行动态和反思式问题解决 |
| **Time** | 时间和时区转换能力 |

### 11.2 使用示例服务器

```bash
# 使用文件系统服务器
npx @modelcontextprotocol/server-filesystem /path/to/directory
```

---

## 12. 参考链接

1. **MCP 官网**: https://modelcontextprotocol.io
2. **入门指南**: https://modelcontextprotocol.io/docs/getting-started/intro
3. **架构**: https://modelcontextprotocol.io/docs/learn/architecture
4. **服务器概念**: https://modelcontextprotocol.io/docs/learn/server-concepts
5. **客户端概念**: https://modelcontextprotocol.io/docs/learn/client-concepts
6. **构建服务器**: https://modelcontextprotocol.io/docs/develop/build-server
7. **构建客户端**: https://modelcontextprotocol.io/docs/develop/build-client
8. **Inspector 工具**: https://modelcontextprotocol.io/docs/tools/inspector
9. **示例**: https://modelcontextprotocol.io/examples
10. **规范**: https://modelcontextprotocol.io/docs/reference/specification

---

*本文档基于 MCP 官方文档（https://modelcontextprotocol.io）整理，更新日期：2026-07-21*
