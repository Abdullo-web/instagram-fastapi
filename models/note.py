"""
models/note.py — ЗАМЕТКИ (таблица notes).

Заметка — короткий текст (до 60 символов) над аватаром, живёт 24 часа.
У пользователя ОДНА заметка: user_id уникален (unique=True).
Новая заметка не создаёт новую строку, а ПЕРЕЗАПИСЫВАЕТ старую.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy.
from sqlalchemy import DateTime, ForeignKey, String

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # unique=True — у одного пользователя может быть только одна строка-заметка.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    # Текст заметки, до 60 символов.
    text: Mapped[str] = mapped_column(String(60))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # note.author → автор. uselist=False на стороне User (одна заметка).
    author: Mapped["User"] = relationship(back_populates="note")
