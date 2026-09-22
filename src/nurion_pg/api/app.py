"""FastAPI application factory for the production build track."""
from __future__ import annotations

from contextvars import ContextVar
from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4

from fastapi import Depends,FastAPI,Header,Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel,Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse,PlainTextResponse

from .auth import ApiKeyRegistry,Authenticator,Permission,Principal,authorize
from .settings import Settings
from nurion_pg.payments import PaymentCommand,PaymentProblem,PaymentService
from nurion_pg.observability import MetricsRegistry,structured_log

correlation_id_var:ContextVar[str]=ContextVar("correlation_id",default="")
LOGGER=logging.getLogger("nurion_pg.api")


def _configure_logging(level:str)->None:
    logging.basicConfig(level=getattr(logging,level),format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _secure(response,correlation_id:str):
    response.headers["x-correlation-id"]=correlation_id;response.headers["x-content-type-options"]="nosniff";response.headers["x-frame-options"]="DENY";response.headers["referrer-policy"]="no-referrer";response.headers["cache-control"]="no-store";return response


class AuthError(Exception):
    def __init__(self,status_code:int,code:str,message:str)->None:
        self.status_code=status_code;self.code=code;self.message=message


class PaymentIntentCreate(BaseModel):
    amount:int
    currency:str
    external_reference:str|None=None
    metadata:dict[str,object]=Field(default_factory=dict)


class PaymentCommandRequest(BaseModel):
    expected_version:int
    amount:int|None=None


def create_app(settings:Settings|None=None,api_key_registry:Authenticator|None=None,payment_service:PaymentService|None=None)->FastAPI:
    runtime=settings or Settings.from_env();_configure_logging(runtime.log_level)
    registry=api_key_registry or ApiKeyRegistry.from_json(runtime.api_keys_json)
    @asynccontextmanager
    async def lifespan(application:FastAPI):
        connection=None
        if runtime.database_url and api_key_registry is None and payment_service is None:
            import psycopg
            from nurion_pg.storage.auth_repository import PostgresAuthRepository
            from nurion_pg.storage.payment_repository import PostgresPaymentRepository
            from nurion_pg.storage.postgres import PostgresFoundation
            connection=psycopg.connect(runtime.database_url,connect_timeout=5,autocommit=True)
            PostgresFoundation(connection,runtime.database_schema).migrate_up()
            application.state.api_key_registry=PostgresAuthRepository(connection,runtime.database_schema)
            application.state.payment_service=PaymentService(PostgresPaymentRepository(connection,runtime.database_schema))
        try:yield
        finally:
            if connection is not None:connection.close()
    app=FastAPI(title="NURION PG API",version="0.1.0",docs_url="/docs" if runtime.environment!="production" else None,redoc_url=None,lifespan=lifespan)
    durable_ready=bool(runtime.database_url or payment_service is not None)
    app.state.settings=runtime;app.state.ready=runtime.environment in {"development","test"} or durable_ready;app.state.api_key_registry=registry;app.state.payment_service=payment_service;app.state.metrics=MetricsRegistry()

    @app.middleware("http")
    async def request_context(request:Request,call_next):
        incoming=request.headers.get("x-correlation-id","").strip();correlation_id=incoming if 1<=len(incoming)<=128 and incoming.isascii() else str(uuid4());token=correlation_id_var.set(correlation_id);started=time.monotonic()
        try:
            raw_length=request.headers.get("content-length")
            if raw_length:
                try:content_length=int(raw_length)
                except ValueError:return _secure(JSONResponse(status_code=400,content={"error":{"code":"INVALID_CONTENT_LENGTH","message":"Content-Length must be an integer","correlation_id":correlation_id}}),correlation_id)
                if content_length>runtime.max_request_bytes:return _secure(JSONResponse(status_code=413,content={"error":{"code":"REQUEST_TOO_LARGE","message":"Request body exceeds the configured limit","correlation_id":correlation_id}}),correlation_id)
            response=_secure(await call_next(request),correlation_id)
            duration=time.monotonic()-started;app.state.metrics.increment("http_requests_total");app.state.metrics.set("http_request_duration_seconds",duration)
            if response.status_code>=500:app.state.metrics.increment("http_request_errors_total")
            LOGGER.info(structured_log("request_completed",correlation_id=correlation_id,method=request.method,path=request.url.path,status=response.status_code,duration_ms=int(duration*1000)))
            return response
        except Exception:
            app.state.metrics.increment("http_requests_total");app.state.metrics.increment("http_request_errors_total");app.state.metrics.set("http_request_duration_seconds",time.monotonic()-started)
            LOGGER.exception(structured_log("request_failed",correlation_id=correlation_id,method=request.method,path=request.url.path))
            return JSONResponse(status_code=500,content={"error":{"code":"INTERNAL_ERROR","message":"Internal server error","correlation_id":correlation_id}},headers={"x-correlation-id":correlation_id})
        finally:correlation_id_var.reset(token)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request:Request,_exc:RequestValidationError):
        return JSONResponse(status_code=422,content={"error":{"code":"REQUEST_VALIDATION_FAILED","message":"Request validation failed","correlation_id":correlation_id_var.get()}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request:Request,exc:StarletteHTTPException):
        code={404:"ROUTE_NOT_FOUND",405:"METHOD_NOT_ALLOWED"}.get(exc.status_code,"HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code,content={"error":{"code":code,"message":"Request could not be served","correlation_id":correlation_id_var.get()}})

    @app.exception_handler(AuthError)
    async def auth_error(_request:Request,exc:AuthError):
        correlation_id=correlation_id_var.get()
        return JSONResponse(status_code=exc.status_code,content={"error":{"code":exc.code,"message":exc.message,"correlation_id":correlation_id}})

    @app.exception_handler(PaymentProblem)
    async def payment_error(_request:Request,exc:PaymentProblem):
        return JSONResponse(status_code=exc.status_code,content={"error":{"code":exc.code,"message":exc.message,"correlation_id":correlation_id_var.get()}})

    def audit(principal:Principal|None,action:str,outcome:str,merchant_id:str|None=None)->None:
        recorder=getattr(app.state.api_key_registry,"record_audit",None)
        if recorder:recorder(principal.principal_id if principal else None,merchant_id or (principal.merchant_id if principal else None),action,outcome,correlation_id_var.get())

    async def current_principal(x_api_key:str|None=Header(default=None))->Principal:
        principal=app.state.api_key_registry.authenticate(x_api_key or "")
        if principal is None:
            audit(None,"authenticate","denied")
            LOGGER.warning("authentication_failed correlation_id=%s",correlation_id_var.get())
            raise AuthError(401,"UNAUTHENTICATED","Valid API credentials are required")
        audit(principal,"authenticate","allowed")
        LOGGER.info("authentication_succeeded principal_id=%s merchant_id=%s key_id=%s correlation_id=%s",principal.principal_id,principal.merchant_id,principal.key_id,correlation_id_var.get())
        return principal

    def merchant_reader(merchant_id:str,principal:Principal=Depends(current_principal))->Principal:
        if not authorize(principal,Permission.TENANT_READ,merchant_id):
            audit(principal,"tenant:read","denied",merchant_id)
            LOGGER.warning("authorization_denied principal_id=%s requested_merchant_id=%s correlation_id=%s",principal.principal_id,merchant_id,correlation_id_var.get())
            raise AuthError(403,"CROSS_TENANT_ACCESS_DENIED","Access to another merchant is denied")
        audit(principal,"tenant:read","allowed",merchant_id)
        return principal

    def merchant_writer(merchant_id:str,principal:Principal=Depends(current_principal))->Principal:
        if not authorize(principal,Permission.PAYMENT_WRITE,merchant_id):
            audit(principal,"payment:write","denied",merchant_id)
            raise AuthError(403,"PAYMENT_WRITE_DENIED","Payment write permission is required for this merchant")
        audit(principal,"payment:write","allowed",merchant_id);return principal

    def metrics_reader(principal:Principal=Depends(current_principal))->Principal:
        if not authorize(principal,Permission.AUDIT_READ):
            audit(principal,"metrics:read","denied")
            raise AuthError(403,"METRICS_READ_DENIED","Audit read permission is required")
        audit(principal,"metrics:read","allowed");return principal

    def payments()->PaymentService:
        if app.state.payment_service is None:raise PaymentProblem(503,"PAYMENT_STORAGE_UNAVAILABLE","Payment storage is unavailable")
        return app.state.payment_service

    @app.get("/health/live",include_in_schema=False)
    async def live():return {"status":"alive","service":runtime.service_name}

    @app.get("/health/ready",include_in_schema=False)
    async def ready():
        if not app.state.ready:return JSONResponse(status_code=503,content={"status":"not_ready","service":runtime.service_name},headers={"retry-after":"5"})
        return {"status":"ready","service":runtime.service_name,"environment":runtime.environment}

    @app.get("/health/startup",include_in_schema=False)
    async def startup():return {"status":"started","service":runtime.service_name}

    @app.get("/runtime/info",include_in_schema=False)
    async def runtime_info():return runtime.public_view()

    @app.get("/metrics",include_in_schema=False)
    async def metrics(_principal:Principal=Depends(metrics_reader)):return PlainTextResponse(app.state.metrics.render(),media_type="text/plain; version=0.0.4")

    @app.get("/v1/auth/context")
    async def auth_context(principal:Principal=Depends(current_principal)):
        return {"principal_id":principal.principal_id,"merchant_id":principal.merchant_id,"roles":sorted(principal.roles),"permissions":sorted(principal.permissions),"key_id":principal.key_id}

    @app.get("/v1/merchants/{merchant_id}/context")
    async def merchant_context(merchant_id:str,principal:Principal=Depends(merchant_reader)):
        return {"principal_id":principal.principal_id,"merchant_id":merchant_id,"roles":sorted(principal.roles)}

    @app.post("/v1/merchants/{merchant_id}/payment-intents")
    async def create_payment_intent(merchant_id:str,body:PaymentIntentCreate,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),_principal:Principal=Depends(merchant_writer),service:PaymentService=Depends(payments)):
        intent,replayed=service.create(merchant_id,body.amount,body.currency,idempotency_key or "",body.external_reference,body.metadata)
        return JSONResponse(status_code=200 if replayed else 201,content=intent.public_view(),headers={"idempotent-replay":"true" if replayed else "false"})

    @app.get("/v1/merchants/{merchant_id}/payment-intents/{payment_intent_id}")
    async def get_payment_intent(merchant_id:str,payment_intent_id:str,_principal:Principal=Depends(merchant_reader),service:PaymentService=Depends(payments)):
        return service.get(merchant_id,payment_intent_id).public_view()

    async def command_payment(merchant_id:str,payment_intent_id:str,command:PaymentCommand,body:PaymentCommandRequest,idempotency_key:str|None,service:PaymentService):
        intent,replayed=service.request(merchant_id,payment_intent_id,command,body.amount,body.expected_version,idempotency_key or "")
        return JSONResponse(status_code=200 if replayed else 202,content=intent.public_view(),headers={"idempotent-replay":"true" if replayed else "false"})

    @app.post("/v1/merchants/{merchant_id}/payment-intents/{payment_intent_id}/authorize")
    async def authorize_payment(merchant_id:str,payment_intent_id:str,body:PaymentCommandRequest,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),_principal:Principal=Depends(merchant_writer),service:PaymentService=Depends(payments)):
        return await command_payment(merchant_id,payment_intent_id,PaymentCommand.AUTHORIZE,body,idempotency_key,service)

    @app.post("/v1/merchants/{merchant_id}/payment-intents/{payment_intent_id}/capture")
    async def capture_payment(merchant_id:str,payment_intent_id:str,body:PaymentCommandRequest,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),_principal:Principal=Depends(merchant_writer),service:PaymentService=Depends(payments)):
        return await command_payment(merchant_id,payment_intent_id,PaymentCommand.CAPTURE,body,idempotency_key,service)

    @app.post("/v1/merchants/{merchant_id}/payment-intents/{payment_intent_id}/cancel")
    async def cancel_payment(merchant_id:str,payment_intent_id:str,body:PaymentCommandRequest,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),_principal:Principal=Depends(merchant_writer),service:PaymentService=Depends(payments)):
        return await command_payment(merchant_id,payment_intent_id,PaymentCommand.CANCEL,body,idempotency_key,service)

    @app.post("/v1/merchants/{merchant_id}/payment-intents/{payment_intent_id}/refund")
    async def refund_payment(merchant_id:str,payment_intent_id:str,body:PaymentCommandRequest,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),_principal:Principal=Depends(merchant_writer),service:PaymentService=Depends(payments)):
        return await command_payment(merchant_id,payment_intent_id,PaymentCommand.REFUND,body,idempotency_key,service)

    return app
