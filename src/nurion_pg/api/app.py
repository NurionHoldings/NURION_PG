"""FastAPI application factory for the production build track."""
from __future__ import annotations

from contextvars import ContextVar
import logging
import time
from uuid import uuid4

from fastapi import Depends,FastAPI,Header,Request
from fastapi.responses import JSONResponse

from .auth import ApiKeyRegistry,Principal,Role
from .settings import Settings

correlation_id_var:ContextVar[str]=ContextVar("correlation_id",default="")
LOGGER=logging.getLogger("nurion_pg.api")


def _configure_logging(level:str)->None:
    logging.basicConfig(level=getattr(logging,level),format="%(asctime)s %(levelname)s %(name)s %(message)s")


class AuthError(Exception):
    def __init__(self,status_code:int,code:str,message:str)->None:
        self.status_code=status_code;self.code=code;self.message=message


def create_app(settings:Settings|None=None,api_key_registry:ApiKeyRegistry|None=None)->FastAPI:
    runtime=settings or Settings.from_env();_configure_logging(runtime.log_level)
    registry=api_key_registry or ApiKeyRegistry.from_json(runtime.api_keys_json)
    app=FastAPI(title="NURION PG API",version="0.1.0",docs_url="/docs" if runtime.environment!="production" else None,redoc_url=None)
    app.state.settings=runtime;app.state.ready=True;app.state.api_key_registry=registry

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

    @app.exception_handler(AuthError)
    async def auth_error(_request:Request,exc:AuthError):
        correlation_id=correlation_id_var.get()
        return JSONResponse(status_code=exc.status_code,content={"error":{"code":exc.code,"message":exc.message,"correlation_id":correlation_id}})

    async def current_principal(x_api_key:str|None=Header(default=None))->Principal:
        principal=registry.authenticate(x_api_key or "")
        if principal is None:
            LOGGER.warning("authentication_failed correlation_id=%s",correlation_id_var.get())
            raise AuthError(401,"UNAUTHENTICATED","Valid API credentials are required")
        LOGGER.info("authentication_succeeded principal_id=%s merchant_id=%s key_id=%s correlation_id=%s",principal.principal_id,principal.merchant_id,principal.key_id,correlation_id_var.get())
        return principal

    def merchant_reader(merchant_id:str,principal:Principal=Depends(current_principal))->Principal:
        if principal.merchant_id!=merchant_id:
            LOGGER.warning("authorization_denied principal_id=%s requested_merchant_id=%s correlation_id=%s",principal.principal_id,merchant_id,correlation_id_var.get())
            raise AuthError(403,"CROSS_TENANT_ACCESS_DENIED","Access to another merchant is denied")
        if not principal.roles.intersection({Role.MERCHANT_ADMIN,Role.PAYMENT_OPERATOR,Role.AUDITOR}):
            raise AuthError(403,"INSUFFICIENT_ROLE","The principal role does not allow this operation")
        return principal

    @app.get("/health/live",include_in_schema=False)
    async def live():return {"status":"alive","service":runtime.service_name}

    @app.get("/health/ready",include_in_schema=False)
    async def ready():
        if not app.state.ready:return JSONResponse(status_code=503,content={"status":"not_ready","service":runtime.service_name})
        return {"status":"ready","service":runtime.service_name,"environment":runtime.environment}

    @app.get("/v1/auth/context")
    async def auth_context(principal:Principal=Depends(current_principal)):
        return {"principal_id":principal.principal_id,"merchant_id":principal.merchant_id,"roles":sorted(principal.roles),"key_id":principal.key_id}

    @app.get("/v1/merchants/{merchant_id}/context")
    async def merchant_context(merchant_id:str,principal:Principal=Depends(merchant_reader)):
        return {"principal_id":principal.principal_id,"merchant_id":merchant_id,"roles":sorted(principal.roles)}

    return app
