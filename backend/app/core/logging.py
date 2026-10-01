import logging
import json
import uuid
import contextvars
from typing import Any, Dict
from datetime import datetime, timezone
from app.core.config import settings

# Context variable to hold the request ID for correlation
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

class StructuredJSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for structured logging.
    Redacts or drops sensitive fields if they accidentally make it into `extra`.
    """
    SENSITIVE_KEYS = {
        "gemini_api_key",
        "supabase_service_key",
        "database_url",
        "password",
        "authorization",
        "cookie",
        "document_content",
        "pdf_bytes",
        "image_bytes",
        "raw_response"
    }

    def format(self, record: logging.LogRecord) -> str:
        # Base log fields
        log_record: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request ID if available in the context
        req_id = request_id_var.get()
        if req_id:
            log_record["request_id"] = req_id

        # Add exception info if any
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Merge any extra kwargs passed to logger (e.g. logger.info("...", extra={"key": "val"}))
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord(None, None, "", 0, "", (), None, None).__dict__ and key not in ["message", "asctime"]:
                log_record[key] = value

        # Redact sensitive fields
        redacted_record = {}
        for k, v in log_record.items():
            k_lower = k.lower()
            if any(sensitive in k_lower for sensitive in self.SENSITIVE_KEYS):
                redacted_record[k] = "[REDACTED]"
            elif isinstance(v, str) and any(
                secret in v for secret in [
                    settings.supabase_service_key, 
                    settings.database_url
                ] if secret and len(secret) > 5
            ):
                redacted_record[k] = "[REDACTED_VALUE]"
            else:
                redacted_record[k] = v

        return json.dumps(redacted_record)

def setup_logging():
    """
    Sets up the central logging configuration for the application.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(console_handler)

    # Set external libraries to warning/error to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
