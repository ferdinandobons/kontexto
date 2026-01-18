"""Logging middleware."""

import logging
from datetime import datetime
from typing import Any, Callable


class LoggingMiddleware:
    """Middleware for request/response logging."""

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize with optional logger."""
        self.logger = logger or logging.getLogger(__name__)

    def process_request(self, request: dict) -> dict:
        """Log incoming request."""
        request["_start_time"] = datetime.now()

        self.logger.info(
            "Request: %s %s",
            request.get("method", "GET"),
            request.get("path", "/")
        )
        return request

    def process_response(self, request: dict, response: dict) -> dict:
        """Log outgoing response."""
        start_time = request.get("_start_time")
        if start_time:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.info(
                "Response: %d (%.2fms)",
                response.get("status", 200),
                duration
            )
        return response


class RequestLogger:
    """Detailed request logger with structured output."""

    def __init__(self, include_body: bool = False):
        """Initialize logger settings."""
        self.include_body = include_body
        self._logs: list[dict] = []

    def log_request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        body: Any = None
    ) -> str:
        """Log a request and return log ID.

        Args:
            method: HTTP method.
            path: Request path.
            headers: Request headers.
            body: Request body (if include_body is True).

        Returns:
            Unique log ID for this request.
        """
        log_id = f"req_{len(self._logs)}"
        log_entry = {
            "id": log_id,
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "headers": headers or {},
        }

        if self.include_body and body:
            log_entry["body"] = body

        self._logs.append(log_entry)
        return log_id

    def log_response(
        self,
        log_id: str,
        status: int,
        body: Any = None
    ) -> None:
        """Log response for a request."""
        for log in self._logs:
            if log["id"] == log_id:
                log["response_status"] = status
                log["response_time"] = datetime.now().isoformat()
                if self.include_body and body:
                    log["response_body"] = body
                break

    def get_logs(self, limit: int = 100) -> list[dict]:
        """Get recent logs."""
        return self._logs[-limit:]

    def clear_logs(self) -> int:
        """Clear all logs and return count."""
        count = len(self._logs)
        self._logs.clear()
        return count


def log_function_call(func: Callable) -> Callable:
    """Decorator to log function calls.

    Logs function name, arguments, and return value.
    """
    logger = logging.getLogger(func.__module__)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("Calling %s with args=%s kwargs=%s", func.__name__, args, kwargs)
        try:
            result = func(*args, **kwargs)
            logger.debug("%s returned %s", func.__name__, result)
            return result
        except Exception as e:
            logger.error("%s raised %s: %s", func.__name__, type(e).__name__, e)
            raise

    return wrapper
