
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.gateway import (
    GatewayGenerateRequest,
    GatewayGenerateResponse,
)
from app.services.gateway_service import GatewayService


router = APIRouter(prefix="/gateway", tags=["Gateway"])
gateway_service = GatewayService()


@router.post(
    "/generate",
    response_model=GatewayGenerateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate(
    payload: GatewayGenerateRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
    ),
    current_user: dict = Depends(get_current_user),
):
    try:
        return await gateway_service.generate(
            user_id=current_user["_id"],
            idempotency_key=idempotency_key,
            provider_name=payload.provider,
            model=payload.model,
            messages=[
                message.model_dump() for message in payload.messages
            ],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "idempotency" in message.lower()
            or "reservation" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=code,
            detail=message,
        ) from exc

    except RuntimeError as exc:
        message = str(exc)
        lower_message = message.lower()
        code = (
            status.HTTP_409_CONFLICT
            if "already in progress" in lower_message
            or "reconciliation" in lower_message
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=message) from exc
