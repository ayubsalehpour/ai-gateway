from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.schemas.users import UserCreate, UserResponse
from app.services.user_service import UserService

from app.api.dependencies import get_current_user
from fastapi import Depends


router = APIRouter(prefix="/users", tags=["Users"])
user_service = UserService()


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(user: UserCreate):
    if user_service.repository.get_by_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        return user_service.create_user(user.model_dump())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: dict = Depends(get_current_user),
):
    return current_user


# @router.get("/", response_model=list[UserResponse])
#def get_users(
    current_user: dict = Depends(get_current_user),
#):
#    return user_service.get_users()