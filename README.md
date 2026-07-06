# amap_project

个人餐饮推荐 Agent。目标不是做通用点评搜索，而是把个人偏好、当前用餐场景和地图检索结果放在同一个对话流程里，让模型自己决定是否查地点、查周边、查详情。

## 当前状态

- LLM 接入使用 OpenAI-compatible Chat Completions。
- 地图能力通过高德 MCP 接入。
- FoodAgent 只向模型暴露三个地图工具：`maps_geo`、`maps_around_search`、`maps_search_detail`。
- 个人记忆以 SQLite 保存长期饮食偏好，不记录具体餐厅流水账。
- CLI 和本地 Web 共用同一套 AgentLoop。

## 运行入口

- `uv run python main.py chat`
- `uv run python main.py web`
- `uv run python main.py doctor`
- `uv run python main.py add-preference`
- `uv run python main.py list-preferences`
- `uv run python main.py search-nearby`

Windows 下也可以直接使用 `start_cli.bat`，启动时选择 CLI 或 Web。

## 主要结构

- `agents/food_agent/`：餐饮 Agent 的 prompt、用户画像、上下文和 memory 封装。
- `core/agent_loop.py`：对话循环、工具调用循环和消息窗口。
- `core/llm_client.py`：OpenAI-compatible LLM 请求。
- `core/mcp_client.py`：高德 MCP 客户端、工具缓存和响应解析。
- `storage/`：SQLite schema 和 repository。
- `web_app.py`：本地 Web 测试页面。

## MCP 模式

`AMAP_MCP_MODE` 只有两个有效状态：

- `disabled`：不连接高德 MCP，不向模型暴露地图工具。
- `streamable_http`：连接高德 MCP，并向模型暴露受限工具。

高德 key 只从 `AMAP_MAPS_API_KEY` 读取。`AMAP_MCP_URL` 保持为 MCP 服务地址。

## 设计取舍

业务层不预搜索、不手写餐厅推荐规则。Agent 只提供稳定上下文、受限工具和必要约束，具体是否调用工具、用什么关键词、如何取舍候选餐厅交给模型完成。

LLM 未配置或调用失败时，不用本地规则猜测推荐，直接返回不可用信息。
