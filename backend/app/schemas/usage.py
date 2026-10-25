
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UsageCreateRequest(BaseModel):
    user_id: str = Field(min_length=24, max_length=24)
    request_id: str = Field(min_length=1, max_length=128)
    provider: Literal["openai", "anthropic", "gemini"]
    model: str = Field(min_length=1, max_length=128)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    status: Literal["success", "failed"]


class UsageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    request_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    status: str
    created_at: datetime
