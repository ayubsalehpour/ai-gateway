from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user


router = APIRouter(
    prefix="/private",
    tags=["Private"],
)


@router.get("/me")
def get_my_profile(
    current_user: dict = Depends(get_current_user),
):
    return current_user