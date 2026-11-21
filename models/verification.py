"""
models/verification.py — КОДЫ ПОДТВЕРЖДЕНИЯ (таблица verification_codes).

После регистрации создаём 6-значный код и «отправляем» его (в учебной версии —
печатаем в консоль). Пользователь вводит код → аккаунт подтверждён.
Каждая строка таблицы = один выданный код.
"""

# datetime — из стандартного модуля datetime: тип для дат.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing: импорт только для подсказок.
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy (Integer — целое число, остальные см. models/user.py).
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String

# Из SQLAlchemy ORM (см. models/user.py).
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Base — из нашего database.py; utc_now — из нашего services/time_utils.py.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кому выдан код — ссылка на пользователя.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Сам код из 6 цифр. Храним как текст, чтобы не потерять ведущие нули ("004215").
    # (В настоящем проекте код лучше хранить хешем, как пароль. Здесь — просто, для учёбы.)
    code: Mapped[str] = mapped_column(String(6))

    # Куда отправлен: "email" или "sms".
    channel: Mapped[str] = mapped_column(String(10))

    # Сколько раз уже ввели неправильно.
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # Использован ли код (после успешного ввода второй раз его не примем).
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    # Когда создан и когда «сгорает».
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    # Обратная связь: code.user → пользователь.
    user: Mapped["User"] = relationship(back_populates="verification_codes")
