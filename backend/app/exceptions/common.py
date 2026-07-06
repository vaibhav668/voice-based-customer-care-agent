from fastapi import status

from app.exceptions.base import AppException


class NotFoundException(AppException):
    def __init__(self, message="Resource not found"):
        super().__init__(
            message,
            status.HTTP_404_NOT_FOUND,
            "NOT_FOUND",
        )

from fastapi import HTTPException, status


class ConflictException(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        )
class UnauthorizedException(AppException):
    def __init__(self, message="Unauthorized"):
        super().__init__(
            message,
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
        )