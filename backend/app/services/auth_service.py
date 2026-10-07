from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email address."""
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Fetch a user by primary key ID."""
    return db.get(User, user_id)


def register_user(db: Session, request: UserRegisterRequest) -> User:
    """Register a new user after verifying unique email."""
    normalized_email = request.email.lower().strip()
    existing_user = get_user_by_email(db, normalized_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    user = User(
        name=request.name.strip(),
        email=normalized_email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, request: UserLoginRequest) -> TokenResponse:
    """Validate credentials and generate a bearer JWT access token."""
    normalized_email = request.email.lower().strip()
    user = get_user_by_email(db, normalized_email)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)
    return TokenResponse(access_token=access_token, token_type="bearer")

