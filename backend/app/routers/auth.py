from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse, UserMeResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=APIResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with unique email and securely hashed password.",
)
def register(
    request: UserRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
):
    user = auth_service.register_user(db, request)
    return APIResponse(
        success=True,
        message="User registered successfully",
        data=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT bearer token",
    description="Authenticates credentials and returns a signed JWT access token.",
)
def login(
    request: UserLoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return auth_service.authenticate_user(db, request)


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user details",
    description="Returns profile information for the currently authenticated user.",
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return UserMeResponse.model_validate(current_user)

