"""FastAPI application factory for the production build track."""
from __future__ import annotations

from contextvars import ContextVar
import logging
import time
from uuid import uuid4

from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse

from .settings import Settings

correlation_id_var:ContextVar[str]=ContextVar("correlation_id",default="")
LOGGER=logging.getLogger("nurion_pg.api")


def _configure_logging(level:str)->None:
    logging.basicConfig(level=getattr(logging,level),format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings:Settings|None=None)->FastAPI:
    runtime=settings or Settings.from_env();_configure_logging(runtime.log_level)
    app=FastAPI(title="NURION PG API",version="0.1.0",docs_url="/docs" if runtime.environment!="production" else None,redoc_url=None)
    app.state.settings=runtime;app.state.ready=True

    @app.middleware("http")
    async def request_context(request:Request,call_next):
        incoming=request.headers.get("x-correlation-id","").strip();correlation_id=incoming if 1<=len(incoming)<=128 and incoming.isascii() else str(uuid4());token=correlation_id_var.set(correlation_id);started=time.monotonic()
        try:
            response=await call_next(request);response.headers["x-correlation-id"]=correlation_id
            LOGGER.info("request_completed method=%s path=%s status=%s duration_ms=%d correlation_id=%s",request.method,request.url.path,response.status_code,int((time.monotonic()-started)*1000),correlation_id)
            return response
        except Exception:
            LOGGER.exception("request_failed method=%s path=%s correlation_id=%s",request.method,request.url.path,correlation_id)
            return JSONResponse(status_code=500,content={"error":{"code":"INTERNAL_ERROR","message":"Internal server error","correlation_id":correlation_id}},headers={"x-correlation-id":correlation_id})
        finally:correlation_id_var.reset(token)

    @app.get("/health/live",include_in_schema=False)
    async def live():return {"status":"alive","service":runtime.service_name}

    @app.get("/health/ready",include_in_schema=False)
    async def ready():
        if not app.state.ready:return JSONResponse(status_code=503,content={"status":"not_ready","service":runtime.service_name})
        return {"status":"ready","service":runtime.service_name,"environment":runtime.environment}

    return app
