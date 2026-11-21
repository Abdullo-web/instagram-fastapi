"""
models/token.py — REFRESH-ТОКЕНЫ (таблица refresh_tokens).

Зачем хранить refresh-токены в базе: чтобы работал ВЫХОД (logout).
Сам JWT-токен сервер не может «уничтожить» — он просто строка у клиента.
Поэтому у каждого refresh-токена есть уникальный номер jti, и мы записываем его сюда.
Logout = ставим revoked=True. При продлении проверяем: если токен отозван — отказ.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy.
from sqlalchemy import Boolean, DateTime, ForeignKey, String

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base из database.py, utc_now из services/time_utils.py.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Чей токен.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # jti (JWT ID) — уникальный номер токена. Он же записан внутри самого токена.
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Отозван ли токен (True после logout).
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    # Обратная связь: token.user → пользователь.
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
