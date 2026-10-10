from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/dashboard")
def admin_dashboard(
    current_user: dict = Depends(require_admin),
):
    return {
        "message": "Welcome to the admin dashboard",
        "admin": current_user["username"],
    }