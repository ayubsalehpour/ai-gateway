
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.api.dependencies import require_admin
from app.schemas.wallet import (
    AdminWalletCreditRequest,
    AdminWalletCreditResponse,
)
from app.services.wallet_service import WalletService


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

wallet_service = WalletService()


@router.get("/dashboard")
def admin_dashboard(
    current_user: dict = Depends(require_admin),
):
    return {
        "message": "Welcome to the admin dashboard",
        "admin": current_user["username"],
    }


@router.post(
    "/wallets/credit",
    response_model=AdminWalletCreditResponse,
    status_code=status.HTTP_200_OK,
)
def credit_user_wallet(
    payload: AdminWalletCreditRequest,
    current_user: dict = Depends(require_admin),
):
    try:
        result = wallet_service.credit_wallet(
            user_id=payload.user_id,
            amount_toman=payload.amount_toman,
            description=payload.description,
            admin_id=current_user["_id"],
            idempotency_key=payload.idempotency_key,
            reference=payload.reference,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found for this user",
        ) from exc
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Wallet credit could not be completed",
        ) from exc

    return result
