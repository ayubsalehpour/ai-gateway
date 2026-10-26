from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from app.api.dependencies import require_admin
from app.core.database import gateway_requests_collection
from app.services.reconciliation_service import ReconciliationService


router = APIRouter(
    prefix="/admin/reconciliation",
    tags=["Admin Reconciliation"],
)

reconciliation_service = ReconciliationService(gateway_requests_collection)


@router.post("/run", status_code=status.HTTP_200_OK)
def run_reconciliation(
    older_than_minutes: int = Query(default=10, ge=1, le=1440),
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(require_admin),
) -> dict[str, int]:
    """Mark stale processing requests for manual reconciliation.

    This endpoint intentionally does not refund wallet reservations or retry
    provider calls. Only administrators may trigger it.
    """
    try:
        return reconciliation_service.flag_stale_processing_requests(
            older_than_minutes=older_than_minutes,
            limit=limit,
        )
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reconciliation could not access the request store",
        ) from exc
