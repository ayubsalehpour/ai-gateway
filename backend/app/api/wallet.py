
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.schemas.wallet import WalletResponse, WalletTransactionResponse
from app.services.wallet_service import WalletService


router = APIRouter(prefix="/wallet", tags=["Wallet"])
wallet_service = WalletService()


@router.get("/", response_model=WalletResponse)
def get_my_wallet(current_user: dict = Depends(get_current_user)):
    wallet = wallet_service.get_wallet(current_user["_id"])

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    return wallet


@router.get(
    "/transactions",
    response_model=list[WalletTransactionResponse],
)
def get_my_wallet_transactions(
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0, le=10_000),
    current_user: dict = Depends(get_current_user),
):
    return wallet_service.get_transactions(
        user_id=current_user["_id"],
        limit=limit,
        skip=skip,
    )
