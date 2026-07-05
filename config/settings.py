from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    log_level: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    amap_mcp_mode: str
    amap_mcp_url: str
    amap_maps_api_key: str
    database_url: str

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.removeprefix("sqlite:///")
            path = Path(raw_path)
            if not path.is_absolute():
                path = ROOT_DIR / path
            return path
        raise ValueError(f"Only sqlite:/// DATABASE_URL is supported, got {self.database_url!r}")

    @property
    def llm_configured(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_base_url and self.deepseek_model)

    @property
    def amap_mcp_endpoint(self) -> str:
        if not self.amap_mcp_url:
            return ""
        if not self.amap_maps_api_key:
            return self.amap_mcp_url

        parts = urlsplit(self.amap_mcp_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.setdefault("key", self.amap_maps_api_key)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", ""),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        amap_mcp_mode=os.getenv("AMAP_MCP_MODE", "disabled"),
        amap_mcp_url=os.getenv("AMAP_MCP_URL", ""),
        amap_maps_api_key=os.getenv("AMAP_MAPS_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/food_memory.sqlite"),
    )
