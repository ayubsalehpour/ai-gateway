from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: EmailStr
    role: str = "user"

    model_config = ConfigDict(
        populate_by_name=True,
    )
