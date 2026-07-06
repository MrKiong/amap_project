# amap_project

个人餐饮推荐 Agent 的 CLI MVP。

当前版本实现：

- 可复用 `AgentLoop`
- OpenAI-compatible `LLMClient`
- 支持高德 Streamable HTTP 的 `MCPClient`
- FoodAgent 向 LLM 暴露受限的高德 MCP 工具：`maps_geo`、`maps_around_search`、`maps_search_detail`
- 餐饮推荐 `FoodAgent`
- SQLite 个人饮食偏好 memory
- CLI 命令：`chat`、`add-preference`、`list-preferences`、`search-nearby`

## 快速开始

```bash
uv run python main.py chat
```

启动本地 Web 测试页面：

```bash
uv run python main.py web
```

然后打开：

```text
http://127.0.0.1:8765
```

检查当前是否真的会调用高德 MCP：

```bash
uv run python main.py doctor
```

添加一条长期饮食偏好：

```bash
uv run python main.py add-preference --category scenario --preference "一个人吃饭时偏好安静、出餐稳定的小店" --sentiment like --weight 3
```

查看已沉淀的饮食偏好：

```bash
uv run python main.py list-preferences
```

手动测试高德周边搜索：

```bash
uv run python main.py search-nearby --location 国典华园 --radius 1200
```

这个命令只用于人工验证 MCP 连通性，会直接调用高德原生 `maps_geo` 和 `maps_around_search`。Agent 对话模式不会在业务层预搜索餐厅，而是把受限工具 schema 交给 LLM，由 LLM 自主决定是否调用地理编码、周边搜索和详情搜索。

## 配置

复制 `.env.example` 为 `.env`，按需填写：

```env
LOG_LEVEL=INFO
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=deepseek-v4-flash
AMAP_MCP_MODE=disabled
AMAP_MCP_URL=https://mcp.amap.com/mcp
AMAP_MAPS_API_KEY=
DATABASE_URL=sqlite:///data/food_memory.sqlite
```

LLM 配置使用 OpenAI-compatible 接口：`LLM_API_KEY` 填 key，`LLM_BASE_URL` 填 API base url，`LLM_MODEL` 填实际请求里的模型名。

日志等级由 `LOG_LEVEL` 控制，常用值：`DEBUG`、`INFO`、`WARNING`、`ERROR`。默认 `INFO` 会打印 MCP 是否启用、调用了哪个工具、HTTP 状态、响应概要等关键信息，并自动脱敏 URL 中的 key。

高德官方推荐以 Streamable HTTP 方式接入 MCP 服务。启用时可以这样配置：

```env
AMAP_MCP_MODE=streamable_http
AMAP_MCP_URL=https://mcp.amap.com/mcp
AMAP_MAPS_API_KEY=你的高德 key
```

如果日志里出现 `MCP list_tools skipped: mode=disabled`，说明当前没有调用高德，也不会向 LLM 暴露 MCP 工具。把 `.env` 中的 `AMAP_MCP_MODE` 改成 `streamable_http` 并重启 CLI/Web 服务即可。

也兼容直接把 key 写在 URL 中：

```env
AMAP_MCP_MODE=streamable_http
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=你的高德 key
```

没有配置 LLM 时，CLI/Web 会直接提示模型不可用，不会用本地规则猜测推荐。没有启用 MCP 时，LLM 不会获得高德工具。
