from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    GUARDRAIL_STOPPED = "GUARDRAIL_STOPPED"
    SANDBOX_EXEC_ERROR = "SANDBOX_EXEC_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class RlmMcpError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"
