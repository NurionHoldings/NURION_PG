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
    max_request_bytes: int = 1_048_576
    graceful_shutdown_seconds: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        environment=os.getenv("NURION_PG_ENV","development").strip().lower()
        log_level=os.getenv("NURION_PG_LOG_LEVEL","INFO").strip().upper()
        host=os.getenv("NURION_PG_HOST","0.0.0.0").strip()
        raw_port=os.getenv("NURION_PG_PORT","8080")
        raw_max_request=os.getenv("NURION_PG_MAX_REQUEST_BYTES","1048576")
        raw_shutdown=os.getenv("NURION_PG_GRACEFUL_SHUTDOWN_SECONDS","30")
        if environment not in {"development","test","staging","production"}:raise ValueError("unsupported NURION_PG_ENV")
        if log_level not in {"DEBUG","INFO","WARNING","ERROR","CRITICAL"}:raise ValueError("unsupported NURION_PG_LOG_LEVEL")
        try:port=int(raw_port);max_request_bytes=int(raw_max_request);graceful_shutdown_seconds=int(raw_shutdown)
        except ValueError as exc:raise ValueError("NURION_PG_PORT must be an integer") from exc
        if not host or not 1<=port<=65535:raise ValueError("valid host and port required")
        if not 1024<=max_request_bytes<=10_485_760:raise ValueError("NURION_PG_MAX_REQUEST_BYTES is out of range")
        if not 1<=graceful_shutdown_seconds<=300:raise ValueError("NURION_PG_GRACEFUL_SHUTDOWN_SECONDS is out of range")
        api_keys_json=os.getenv("NURION_PG_API_KEYS_JSON","")
        return cls(environment=environment,log_level=log_level,host=host,port=port,api_keys_json=api_keys_json,max_request_bytes=max_request_bytes,graceful_shutdown_seconds=graceful_shutdown_seconds)

    def public_view(self)->dict[str,object]:
        return {"service_name":self.service_name,"environment":self.environment,"log_level":self.log_level,"host":self.host,"port":self.port,"max_request_bytes":self.max_request_bytes,"graceful_shutdown_seconds":self.graceful_shutdown_seconds}
