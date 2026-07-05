# amap_project 项目说明：个人餐饮推荐 Agent

## 1. 项目目标

本项目不是一个简单的餐厅搜索工具，而是一个可扩展的 Agent 框架项目。

当前第一阶段目标是实现一个「个人餐饮推荐 Agent」：

用户输入自然语言，例如：

> 明天中午我在国典华园附近，一个人吃，预算 100 左右，不想吃太辣，帮我推荐一家。

Agent 需要结合：

1. 用户自然语言需求；
2. 用户个人常用信息；
3. 用户历史用餐总结 memory；
4. 高德 MCP Server 返回的附近餐厅信息；
5. 多轮交互上下文；

通过标准 agent-loop 推理，必要时向用户追问，直到给出最终推荐。

项目应设计成可复用框架，未来可以扩展多个 Agent，而不是只写死餐厅推荐逻辑。

---

## 2. 核心设计原则

### 2.1 Agent 独立上下文

每个 Agent 都应该有独立上下文，不同 Agent 之间不能强耦合。

当前餐饮推荐 Agent 的上下文包括：

* 用户常用信息；
* 用户饮食偏好；
* 历史用餐总结；
* 历史踩雷记录；
* 当前会话上下文；
* 可用 MCP 工具说明。

未来其他 Agent，例如旅行 Agent、工作总结 Agent、购物 Agent，也应该能复用同一套 agent-loop 内核，但拥有自己的独立上下文。

---

### 2.2 Agent 独立 LLM 调用层

每个 Agent 可以独立配置自己的 LLM。

当前餐饮推荐 Agent 使用：

* 模型：DeepSeek V4
* 调用方式：OpenAI-compatible API
* API Key 从环境变量读取
* Base URL 从环境变量读取
* Model Name 从环境变量读取

不要把模型调用逻辑写死在主流程中，应封装成独立 `LLMClient`。

---

### 2.3 MCP 作为工具层

高德地图能力通过 MCP Server 接入。

当前项目需要支持高德 MCP Server，并从环境变量读取 API Key。

Agent 不应直接把高德 API 写死在业务逻辑中，而是通过 MCP Client 调用 MCP tools。

未来可以扩展更多 MCP，例如：

* 美团 MCP
* 大众点评 MCP
* 天气 MCP
* 日历 MCP
* 旅行 MCP

---

### 2.4 标准 Agent Loop

Agent 的核心运行方式应为：

1. 接收用户自然语言输入；
2. 加载 Agent 独立上下文；
3. 构造 prompt；
4. 调用 LLM；
5. 如果 LLM 需要调用工具，则调用 MCP tool；
6. 将工具结果注入上下文；
7. 再次调用 LLM；
8. 如果信息不足，则向用户追问；
9. 用户补充后继续进入 loop；
10. 直到 Agent 给出最终答案。

---

## 3. 推荐项目结构

```text
amap_project/
├── README.md
├── PROJECT_SPEC.md
├── requirements.txt
├── .env.example
├── main.py
├── config/
│   ├── settings.py
│   └── prompts.py
├── core/
│   ├── agent_loop.py
│   ├── llm_client.py
│   ├── mcp_client.py
│   ├── message.py
│   └── tool_schema.py
├── agents/
│   ├── base_agent.py
│   └── food_agent/
│       ├── agent.py
│       ├── context.py
│       ├── memory.py
│       ├── prompts.py
│       └── tools.py
├── storage/
│   ├── db.py
│   ├── schema.sql
│   └── repositories.py
├── data/
│   └── food_memory.sqlite
└── tests/
    ├── test_agent_loop.py
    ├── test_food_memory.py
    └── test_mcp_client.py
```

---

## 4. 模块说明

### 4.1 core/agent_loop.py

实现通用 Agent Loop。

它不关心具体业务，只负责循环调度：

* 接收用户输入；
* 维护 messages；
* 调用 Agent 构造上下文；
* 调用 LLM；
* 判断是否需要 tool call；
* 调用 MCP；
* 将工具结果写回上下文；
* 判断是否结束。

核心接口建议：

```python
class AgentLoop:
    def __init__(self, agent, llm_client, mcp_client):
        ...

    async def run(self, user_input: str) -> str:
        ...
```

---

### 4.2 core/llm_client.py

封装 DeepSeek V4 调用。

要求：

* 使用 OpenAI-compatible API；
* 从环境变量读取配置；
* 不在业务逻辑中硬编码 key；
* 支持 messages 输入；
* 支持 tool call 或至少预留 tool call 扩展。

环境变量：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=deepseek-v4
```

---

### 4.3 core/mcp_client.py

负责和 MCP Server 通信。

第一阶段可以先支持高德 MCP Server。

需要预留两种运行方式：

1. stdio：本地进程方式；
2. streamable HTTP：远程 HTTP MCP Server。

MCP Client 对外暴露统一接口：

```python
class MCPClient:
    async def list_tools(self) -> list:
        ...

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        ...
```

业务 Agent 不应感知 MCP 底层连接方式。

---

### 4.4 agents/base_agent.py

定义所有 Agent 的抽象基类。

建议接口：

```python
class BaseAgent:
    name: str

    async def build_system_prompt(self) -> str:
        ...

    async def build_context(self, user_input: str) -> dict:
        ...

    async def get_available_tools(self) -> list:
        ...

    async def should_finish(self, messages: list) -> bool:
        ...
```

---

### 4.5 agents/food_agent/agent.py

实现餐饮推荐 Agent。

职责：

* 加载个人饮食上下文；
* 加载历史用餐 memory；
* 根据用户输入判断是否需要追问；
* 判断是否需要调用高德 MCP；
* 综合用户偏好和高德结果做推荐；
* 输出推荐理由。

---

### 4.6 agents/food_agent/context.py

维护餐饮 Agent 的静态上下文。

例如：

```python
USER_PROFILE = {
    "home_area": "北京市朝阳区国典华园附近",
    "default_city": "北京",
    "common_budget_lunch": "50-150",
    "preference_notes": [
        "希望推荐不要只看大众热门，而要结合个人偏好",
        "不喜欢过度排队",
        "更看重实际体验和复吃价值"
    ]
}
```

后续这些信息可以迁移到数据库或配置文件。

---

### 4.7 agents/food_agent/memory.py

管理用户历史用餐 memory。

第一阶段使用 SQLite。

需要支持：

* 添加用餐记录；
* 查询历史记录；
* 按菜系查询；
* 按评分查询；
* 查询踩雷记录；
* 生成用户偏好摘要。

示例记录字段：

```text
id
restaurant_name
location
cuisine
avg_price
rating
dishes
scenario
companions
comment
pros
cons
revisit_willingness
created_at
```

---

### 4.8 storage/

负责数据库初始化和 CRUD。

不要把 SQL 混在 Agent 推理逻辑中。

---

## 5. Agent Prompt 设计

餐饮推荐 Agent 的 system prompt 应强调：

```text
你是用户的私人餐饮推荐 Agent。

你不是大众点评排行榜复读机，而是要结合用户的长期饮食偏好、历史用餐记忆、当前位置、预算、场景和实时地图信息，给出个性化推荐。

当信息不足时，你可以向用户追问，但不要过度追问。优先基于已有信息做合理推断。

你可以调用高德 MCP 工具查询附近餐厅、地址、距离、营业状态和路线信息。

你的最终回答应包括：
1. 首推餐厅；
2. 推荐理由；
3. 适合点什么；
4. 预计预算；
5. 距离或交通建议；
6. 备选餐厅；
7. 为什么没有推荐某些类型。
```

---

## 6. Agent Loop 行为要求

### 6.1 信息充足时

用户输入：

> 明天中午国典华园附近，一个人，预算 100，不想吃辣。

Agent 应：

1. 识别地点：国典华园附近；
2. 识别时间：明天中午；
3. 识别人数：一个人；
4. 识别预算：100；
5. 识别偏好：不辣；
6. 调用高德 MCP 搜索附近餐厅；
7. 结合历史 memory；
8. 输出推荐。

---

### 6.2 信息不足时

用户输入：

> 明天中午吃什么？

Agent 可以追问：

> 你是在家附近吃，还是公司附近吃？预算大概多少？

但如果用户上下文里已有常用地点，也可以默认使用常用地点，并说明假设。

---

### 6.3 有历史偏好时

如果 memory 中显示用户高频喜欢：

* 韩餐；
* 粤菜；
* 面食；
* 安静小店；

则推荐时应体现：

> 结合你之前对韩餐和安静小店评分较高，我优先推荐……

---

## 7. MVP 阶段任务

第一阶段不要做复杂前端。

优先实现命令行版本。

### 必须实现

1. DeepSeek LLM Client；
2. MCP Client 基础封装；
3. FoodAgent；
4. AgentLoop；
5. SQLite 用餐记录；
6. CLI 入口。

CLI 示例：

```bash
python main.py chat
python main.py add-meal
python main.py list-meals
python main.py search-nearby
```

---

## 8. 前后端设计建议

第一阶段：纯 CLI。

原因：

* 最快验证 agent-loop；
* 避免前端拖慢进度；
* 适合 vibe coding；
* 方便后续接入 ChatGPT / Cursor / Web。

第二阶段：FastAPI 后端。

提供：

```text
POST /chat
POST /meal
GET /meals
GET /memory/summary
```

第三阶段：轻量 Web UI。

可以使用：

* Streamlit；
* Gradio；
* Next.js；
* 或简单 HTML + FastAPI。

不要一开始就做复杂前端。

---

## 9. 推荐实现顺序

### Step 1：项目骨架

创建目录结构、README、env 示例。

### Step 2：配置系统

实现 settings.py，从 `.env` 读取：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=
AMAP_MCP_MODE=stdio
AMAP_MCP_COMMAND=
AMAP_MCP_ARGS=
AMAP_MAPS_API_KEY=
DATABASE_URL=sqlite:///data/food_memory.sqlite
```

### Step 3：SQLite memory

先实现添加和查询历史用餐记录。

### Step 4：LLM Client

实现 DeepSeek V4 调用。

### Step 5：Food Agent Prompt

先不接 MCP，只让 Agent 能结合 memory 进行推荐。

### Step 6：MCP Client

接入高德 MCP tools。

### Step 7：Agent Loop

实现 LLM → tool call → tool result → LLM 的循环。

### Step 8：CLI Chat

实现自然语言交互。

---

## 10. 系统环境说明

本项目为 Python 项目，运行环境基于当前目录下的 **uv 虚拟环境**。

要求：

* 使用 `uv` 管理 Python 依赖；
* 所有依赖通过 `requirements.txt` 或 `pyproject.toml` 管理；
* 项目运行前需在当前目录初始化 uv 环境，例如：

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

或使用：

```bash
uv sync
```

运行项目时默认使用该 uv 环境中的 Python 解释器。

---

## 11. 非目标

第一阶段不要实现：

* 用户登录；
* 复杂 Web 前端；
* 多用户系统；
* 复杂推荐模型；
* 向量数据库；
* 美团/大众点评自动化；
* 自动下单；
* 自动预约。

这些都放到后续迭代。

---

## 12. 最终验收标准

当运行：

```bash
python main.py chat
```

用户输入：

> 明天中午我在国典华园附近，一个人，预算 100 左右，不想吃太辣，推荐一家。

系统应该能够：

1. 识别需求；
2. 读取用户偏好；
3. 查询历史用餐 memory；
4. 调用高德 MCP 查附近餐厅；
5. 结合结果进行推荐；
6. 必要时追问；
7. 给出自然语言推荐。

最终回答不能只是列餐厅，而要给出明确决策：

> 首推 A，因为……
> 备选 B，如果你想……
> 不推荐 C，因为……
