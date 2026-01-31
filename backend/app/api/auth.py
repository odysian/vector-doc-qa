from app.api.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.crud.user import create_user, get_user_by_email, get_user_by_username
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.utils.rate_limit import get_ip_key, limiter
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/hour", key_func=get_ip_key)
def register(
    request: Request,
    user: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user.

    - Checks if username or email already exists
    - Hashes password before storing
    - Returns created user (without password)
    """
    # Check if username already exists
    db_user = get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user (password hashing happens in CRUD)
    return create_user(db, user)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute", key_func=get_ip_key)
def login(
    request: Request,
    user: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Login with username and password.

    - Verifies credentials
    - Returns JWT access token
    """
    # Get user by username
    db_user = get_user_by_username(db, user.username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Verify password
    if not verify_password(user.password, db_user.hashed_password):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Create JWT token
    access_token = create_access_token(data={"sub": str(db_user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.

    Requires authentication (JWT token in Authorization header).
    """
    return current_user
