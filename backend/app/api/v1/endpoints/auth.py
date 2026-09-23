# netguard/backend/app/api/v1/endpoints/auth.py
"""
NetGuard - Endpoints de Autenticação.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, get_admin_user
from app.models.user import User
from app.schemas.user import (
    LoginRequest, Token, RefreshTokenRequest,
    UserCreate, UserResponse, UserPasswordChange,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Autentica usuário e retorna JWT tokens."""
    service = AuthService(db)
    ip = request.client.host if request.client else None
    tokens = await service.authenticate(data.username, data.password, ip)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Renova tokens via refresh token."""
    service = AuthService(db)
    tokens = await service.refresh_tokens(data.refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )
    return tokens


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Registra novo usuário (apenas admins)."""
    service = AuthService(db)
    user = await service.register_user(data, created_by=admin.id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usuário ou e-mail já cadastrado",
        )
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retorna dados do usuário autenticado."""
    return current_user


@router.post("/change-password")
async def change_password(
    data: UserPasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Altera senha do usuário autenticado."""
    service = AuthService(db)
    success = await service.change_password(
        current_user, data.current_password, data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )
    return {"message": "Senha alterada com sucesso"}
