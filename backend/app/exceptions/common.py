from fastapi import status

from app.exceptions.base import AppException


class NotFoundException(AppException):
    def __init__(self, message="Resource not found"):
        super().__init__(
            message,
            status.HTTP_404_NOT_FOUND,
            "NOT_FOUND",
        )

class ConflictException(AppException):
    def __init__(self, message="Resource conflict"):
        super().__init__(
            message,
            status.HTTP_409_CONFLICT,
            "CONFLICT",
        )
class UnauthorizedException(AppException):
    def __init__(self, message="Unauthorized"):
        super().__init__(
            message,
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
        )