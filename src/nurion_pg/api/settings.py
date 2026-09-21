"""Validated runtime settings with no secret-value logging."""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    service_name: str = "nurion-pg-api"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8080
    api_keys_json: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        environment=os.getenv("NURION_PG_ENV","development").strip().lower()
        log_level=os.getenv("NURION_PG_LOG_LEVEL","INFO").strip().upper()
        host=os.getenv("NURION_PG_HOST","0.0.0.0").strip()
        raw_port=os.getenv("NURION_PG_PORT","8080")
        if environment not in {"development","test","staging","production"}:raise ValueError("unsupported NURION_PG_ENV")
        if log_level not in {"DEBUG","INFO","WARNING","ERROR","CRITICAL"}:raise ValueError("unsupported NURION_PG_LOG_LEVEL")
        try:port=int(raw_port)
        except ValueError as exc:raise ValueError("NURION_PG_PORT must be an integer") from exc
        if not host or not 1<=port<=65535:raise ValueError("valid host and port required")
        api_keys_json=os.getenv("NURION_PG_API_KEYS_JSON","")
        return cls(environment=environment,log_level=log_level,host=host,port=port,api_keys_json=api_keys_json)

    def public_view(self)->dict[str,object]:
        return {"service_name":self.service_name,"environment":self.environment,"log_level":self.log_level,"host":self.host,"port":self.port}
