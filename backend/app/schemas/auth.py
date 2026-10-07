from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (at least 6 characters)")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: int | None = None

