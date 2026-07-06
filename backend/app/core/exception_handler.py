from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.exceptions.base import AppException
from app.utils.response import error_response


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ):
        return error_response(
            message=exc.message,
            status_code=exc.status_code,
            error=exc.error_code,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        return error_response(
            message=exc.detail if isinstance(exc.detail, str) else "Request failed",
            status_code=exc.status_code,
            error="HTTP_ERROR",
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        print(f"[Unhandled Exception] {exc}")
        return error_response(
            message=str(exc) or "Internal server error",
            status_code=500,
            error="INTERNAL_SERVER_ERROR",
        )