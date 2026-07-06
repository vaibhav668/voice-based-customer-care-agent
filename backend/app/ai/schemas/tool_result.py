from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    tool: str | None = None
    data: dict[str, Any]
    requires_booking_code: bool = False