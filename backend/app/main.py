import time
import uuid
import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.database.connection import get_db
from app.api.v1.router import api_router
from app.core.logging import setup_logging, request_id_var
from contextlib import asynccontextmanager
import asyncio

# Setup structured logging
setup_logging()
logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(req_id)
        
        start_time = time.time()
        logger.info(f"Request started", extra={"method": request.method, "path": request.url.path})
        
        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Set response header
            response.headers["X-Request-ID"] = req_id
            
            logger.info(
                f"Request completed", 
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            )
            return response
        finally:
            request_id_var.reset(token)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.worker import run_worker_loop
    worker_task = asyncio.create_task(run_worker_loop())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.app_name,
    description="Invoice Exception & Verification API",
    version=settings.app_version,
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception", extra={"method": request.method, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": f"{settings.app_name} API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/health/database")
async def health_database(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database connection failed")
