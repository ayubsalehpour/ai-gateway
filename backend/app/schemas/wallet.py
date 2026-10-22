
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    id: str
    user_id: str
    balance_toman: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class WalletTransactionResponse(BaseModel):
    id: str
    wallet_id: str
    user_id: str
    type: Literal["credit", "debit"]
    amount_toman: int = Field(gt=0)
    balance_after: int = Field(ge=0)
    description: str
    reference: str | None = None
    created_at: datetime



class AdminWalletCreditRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    amount_toman: int = Field(strict=True, gt=0, le=100_000_000)
    description: str = Field(min_length=3, max_length=250)
    reference: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=16, max_length=128)



class AdminWalletCreditResponse(BaseModel):
    wallet: WalletResponse
    transaction: WalletTransactionResponse



class WalletDebitRequest(BaseModel):
    amount_toman: int = Field(strict=True, gt=0, le=100_000_000)
    description: str = Field(min_length=3, max_length=250)
    reference: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=16, max_length=128)


class WalletDebitResponse(BaseModel):
    wallet: WalletResponse
    transaction: WalletTransactionResponse
