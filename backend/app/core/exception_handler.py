from fastapi import FastAPI, Request

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