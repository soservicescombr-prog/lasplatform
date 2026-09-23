# netguard/backend/app/services/auth_service.py
"""
NetGuard - Service de Autenticação (login, refresh, registro).
"""

from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.user import UserCreate, Token
from app.utils.time import utcnow_naive


class AuthService:
    """Serviço de autenticação e gestão de usuários."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(
        self, username: str, password: str, ip_address: str = None
    ) -> Token:
        """Autentica usuário e retorna tokens."""
        result = await self.db.execute(
            select(User).where(
                or_(User.username == username, User.email == username)
            )
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            await self._log_action(
                None, "login_failed", "auth",
                details={"username": username},
                ip_address=ip_address,
            )
            return None

        if not user.is_active:
            return None

        # Update last login
        # Os modelos legados usam TIMESTAMP WITHOUT TIME ZONE; gravamos UTC sem tzinfo.
        user.last_login = utcnow_naive()
        await self.db.flush()

        # Log successful login
        await self._log_action(
            user.id, "login_success", "auth",
            ip_address=ip_address,
        )

        return Token(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        """Gera novos tokens a partir do refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        return Token(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id),
        )

    async def register_user(
        self, data: UserCreate, created_by: UUID = None
    ) -> User:
        """Registra novo usuário."""
        # Check duplicates
        existing = await self.db.execute(
            select(User).where(
                or_(User.username == data.username, User.email == data.email)
            )
        )
        if existing.scalar_one_or_none():
            return None

        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=UserRole(data.role) if data.role in UserRole.__members__.values() else UserRole.VIEWER,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        await self._log_action(
            created_by or user.id,
            "user_created",
            "user",
            resource_id=str(user.id),
            details={"username": user.username, "role": user.role.value},
        )

        return user

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Altera senha do usuário."""
        if not verify_password(current_password, user.hashed_password):
            return False

        user.hashed_password = hash_password(new_password)
        await self.db.flush()

        await self._log_action(
            user.id, "password_changed", "user",
            resource_id=str(user.id),
        )
        return True

    async def create_initial_admin(self) -> User:
        """Cria admin padrão se não existir nenhum usuário."""
        result = await self.db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return None

        admin = User(
            username="admin",
            email="admin@netguard.local",
            full_name="Administrador",
            hashed_password=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_superuser=True,
        )
        self.db.add(admin)
        await self.db.flush()
        await self.db.refresh(admin)
        return admin

    async def _log_action(
        self,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str = None,
        details: dict = None,
        ip_address: str = None,
    ):
        """Registra ação no audit log."""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        self.db.add(log)
        await self.db.flush()
