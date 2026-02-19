"""Authentication dependency for FastAPI.

Validates session tokens against the neon_auth schema managed by Neon Auth.
When AUTH_REQUIRED=false, returns a dev user without checking headers.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UserInfo:
    """Authenticated user information."""

    id: str
    email: str
    name: str


_DEV_USER = UserInfo(id="dev-user", email="dev@localhost", name="Dev User")


async def get_current_user(request: Request, db: AsyncSession = Depends(get_session)) -> UserInfo:
    """FastAPI dependency that validates the session token and returns the current user.

    When AUTH_REQUIRED=false, returns a dev user without checking headers.
    When AUTH_REQUIRED=true, validates the Bearer token against neon_auth.session.
    """
    settings = get_settings()

    if not settings.auth_required:
        return _DEV_USER

    # Extract Bearer token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = auth_header[7:]  # Strip "Bearer " prefix

    # Query neon_auth schema (managed by Neon Auth, not our Alembic models)
    result = await db.execute(
        text(
            'SELECT u.id, u.email, u.name '
            'FROM neon_auth.session s '
            'JOIN neon_auth."user" u ON s."userId" = u.id '
            'WHERE s.token = :token AND s."expiresAt" > now()'
        ),
        {"token": token},
    )
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return UserInfo(id=str(row.id), email=row.email, name=row.name)
