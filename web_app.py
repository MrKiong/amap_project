from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from core.agent_loop import AgentLoop
from core.mcp_client import MCPClient


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>餐饮推荐 Agent 测试台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f5f0;
      --panel: #ffffff;
      --ink: #202124;
      --muted: #666b73;
      --line: #ddd8ce;
      --accent: #2f6f5e;
      --accent-dark: #245548;
      --soft: #eef5f1;
      --warn: #8a4b1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    .shell {
      width: min(1040px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0;
      display: grid;
      gap: 18px;
    }
    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }
    h1 {
      margin: 0;
      font-size: clamp(24px, 4vw, 38px);
      line-height: 1.15;
      letter-spacing: 0;
    }
    .status {
      color: var(--muted);
      font-size: 14px;
      white-space: nowrap;
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 18px;
      align-items: start;
    }
    .chat, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .chat {
      min-height: 620px;
      display: grid;
      grid-template-rows: 1fr auto;
      overflow: hidden;
    }
    .messages {
      padding: 18px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .msg {
      max-width: 88%;
      padding: 12px 14px;
      border-radius: 8px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      border: 1px solid var(--line);
    }
    .msg.user {
      align-self: flex-end;
      background: var(--soft);
      border-color: #cfe1d8;
    }
    .msg.agent {
      align-self: flex-start;
      background: #fff;
    }
    .composer {
      border-top: 1px solid var(--line);
      padding: 14px;
      display: grid;
      gap: 10px;
    }
    textarea {
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: inherit;
      line-height: 1.5;
      color: var(--ink);
    }
    textarea:focus {
      outline: 2px solid #9bc7b8;
      border-color: var(--accent);
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 8px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button:disabled {
      opacity: .62;
      cursor: wait;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
    }
    aside {
      padding: 16px;
      display: grid;
      gap: 14px;
    }
    h2 {
      margin: 0;
      font-size: 16px;
      letter-spacing: 0;
    }
    .example {
      width: 100%;
      text-align: left;
      background: #fff;
      color: var(--ink);
      border-color: var(--line);
      line-height: 1.45;
    }
    .example:hover {
      background: var(--soft);
      color: var(--ink);
    }
    .hint {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .error {
      color: var(--warn);
      font-size: 14px;
      min-height: 22px;
    }
    @media (max-width: 840px) {
      main { grid-template-columns: 1fr; }
      .chat { min-height: 560px; }
      header {
        align-items: flex-start;
        flex-direction: column;
      }
      .status { white-space: normal; }
      .msg { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>餐饮推荐 Agent 测试台</h1>
      </div>
      <div class="status" id="status">本地服务已连接</div>
    </header>
    <main>
      <section class="chat" aria-label="Agent 对话">
        <div class="messages" id="messages">
          <div class="msg agent">可以直接输入用餐需求。我会走当前项目里的 AgentLoop、memory 和 MCP 配置；未配置 LLM 时会直接提示模型不可用。</div>
        </div>
        <form class="composer" id="form">
          <textarea id="input" placeholder="例如：明天中午我在国典华园附近，一个人，预算100左右，不想吃太辣，推荐一家。"></textarea>
          <div class="error" id="error"></div>
          <div class="actions">
            <button class="secondary" type="button" id="clear">清空</button>
            <button type="submit" id="send">发送</button>
          </div>
        </form>
      </section>
      <aside>
        <h2>示例输入</h2>
        <button class="example" type="button">明天中午我在国典华园附近，一个人，预算100左右，不想吃太辣，推荐一家。</button>
        <button class="example" type="button">今天晚上想吃点清淡的，别排太久，预算150以内。</button>
        <button class="example" type="button">附近有什么适合一个人快速吃完的面食或简餐？</button>
        <p class="hint">启动真实高德 MCP：在 .env 中配置 AMAP_MCP_MODE=streamable_http、AMAP_MCP_URL 和 AMAP_MAPS_API_KEY。</p>
      </aside>
    </main>
  </div>
  <script>
    const form = document.querySelector("#form");
    const input = document.querySelector("#input");
    const messages = document.querySelector("#messages");
    const send = document.querySelector("#send");
    const clear = document.querySelector("#clear");
    const error = document.querySelector("#error");
    const status = document.querySelector("#status");

    function appendMessage(role, text) {
      const el = document.createElement("div");
      el.className = `msg ${role}`;
      el.textContent = text;
      messages.appendChild(el);
      messages.scrollTop = messages.scrollHeight;
    }

    async function sendMessage(text) {
      error.textContent = "";
      send.disabled = true;
      status.textContent = "Agent 正在思考";
      appendMessage("user", text);
      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "请求失败");
        appendMessage("agent", data.answer);
        status.textContent = "本地服务已连接";
      } catch (err) {
        error.textContent = err.message;
        status.textContent = "请求出错";
      } finally {
        send.disabled = false;
        input.focus();
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      sendMessage(text);
    });

    clear.addEventListener("click", () => {
      messages.innerHTML = "";
      appendMessage("agent", "对话区已清空，可以开始新的测试。");
      error.textContent = "";
      input.focus();
    });

    document.querySelectorAll(".example").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.textContent;
        input.focus();
      });
    });
  </script>
</body>
</html>
"""


class AgentWebServer:
    def __init__(self, agent_loop: AgentLoop, mcp_client: MCPClient):
        self.agent_loop = agent_loop
        self.mcp_client = mcp_client

    def make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    self._send_html(INDEX_HTML)
                    return
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                if self.path != "/api/chat":
                    self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                    return

                try:
                    payload = self._read_json()
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        self._send_json({"error": "message 不能为空"}, status=HTTPStatus.BAD_REQUEST)
                        return
                    answer = asyncio.run(server.agent_loop.run(message))
                    self._send_json({"answer": answer})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

            def log_message(self, format: str, *args: Any) -> None:
                print(f"{self.address_string()} - {format % args}")

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw or "{}")

            def _send_html(self, html: str) -> None:
                body = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def serve(self, host: str, port: int) -> None:
        httpd = ThreadingHTTPServer((host, port), self.make_handler())
        print(f"餐饮推荐 Agent 测试页面已启动：http://{host}:{port}")
        print("按 Ctrl+C 停止服务。")
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()
            asyncio.run(self.mcp_client.close())
