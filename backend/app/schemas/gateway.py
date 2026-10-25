from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)


class GatewayGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "anthropic", "gemini"]
    model: str = Field(min_length=1, max_length=128)
    messages: list[GatewayMessage] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=200_000)


class GatewayCostResponse(BaseModel):
    input_cost_toman: int = Field(ge=0)
    output_cost_toman: int = Field(ge=0)
    total_cost_toman: int = Field(ge=0)
    pricing_version: int | None = None


class GatewayGenerateResponse(BaseModel):
    request_id: str
    provider: str
    model: str
    content: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost: GatewayCostResponse