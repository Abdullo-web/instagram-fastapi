"""
models/user.py — МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ (таблица users).

Аналогия: «паспорт человека». Здесь только то, что нужно для входа
и безопасности. То, что видят другие люди (био, аватар), лежит в Profile.
"""

# datetime — из стандартного модуля datetime. Тип для полей с датой.
from datetime import datetime

# TYPE_CHECKING — из стандартного модуля typing.
# Равен True только для редактора кода, а при запуске программы — False.
# Нужен, чтобы импортировать классы ТОЛЬКО для подсказок типов
# и не получить «круговой импорт» (user.py импортирует profile.py, а тот — user.py).
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy:
#   String   — текст ограниченной длины
#   Boolean  — да/нет
#   DateTime — дата и время
from sqlalchemy import Boolean, DateTime, String

# Из SQLAlchemy ORM:
#   Mapped        — подсказка типа «это колонка таблицы»
#   mapped_column — описание колонки (тип, уникальность, значение по умолчанию)
#   relationship  — связь с другой моделью (User ↔ Profile)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Base — из нашего database.py: родитель всех моделей.
from database import Base

# utc_now — из нашего services/time_utils.py: текущее время UTC.
from services.time_utils import utc_now

if TYPE_CHECKING:
    # Эти импорты нужны только редактору для подсказок, при запуске не выполняются.
    from .note import Note
    from .post import Post
    from .profile import Profile
    from .story import Story
    from .token import RefreshToken
    from .verification import VerificationCode


class User(Base):
    # Имя таблицы в базе данных.
    __tablename__ = "users"

    # id — уникальный номер пользователя. primary_key=True — «главный ключ»,
    # база сама ставит 1, 2, 3...
    id: Mapped[int] = mapped_column(primary_key=True)

    # username — ник. unique=True — двух одинаковых быть не может.
    # index=True — база строит «оглавление» по этой колонке, поиск идёт быстрее.
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)

    # email — почта, тоже уникальная.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # phone — телефон для SMS. `str | None` и nullable=True — поле необязательное.
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)

    # full_name — имя и фамилия, необязательное.
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # hashed_password — НЕ пароль, а его хеш («отпечаток»). Сам пароль мы не храним.
    hashed_password: Mapped[str] = mapped_column(String(255))

    # is_verified — подтвердил ли пользователь код. По умолчанию False (нет).
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # is_active — активен ли аккаунт (можно будет «заблокировать»). По умолчанию True.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # created_at — когда зарегистрировался. default=utc_now — функция вызовется сама
    # при создании записи. (Пишем utc_now без скобок: передаём функцию, а не результат.)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # -----------------------------------------------------------------------
    # СВЯЗИ (relationship) — это не колонки, а удобный доступ к связанным строкам.
    # user.profile          → профиль этого пользователя
    # user.refresh_tokens   → все его refresh-токены
    # back_populates — имя «обратной» связи в другой модели (profile.user).
    # cascade="all, delete-orphan" — удалили пользователя → удалятся и его записи.
    # -----------------------------------------------------------------------
    profile: Mapped["Profile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )  # uselist=False — профиль ОДИН (связь один-к-одному), а не список

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    verification_codes: Mapped[list["VerificationCode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # ---- Этап 3 ----
    # user.posts   → все посты пользователя (один-ко-многим)
    # user.stories → все его истории (включая просроченные)
    # user.note    → его заметка (одна или None)
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    stories: Mapped[list["Story"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    note: Mapped["Note | None"] = relationship(
        back_populates="author", uselist=False, cascade="all, delete-orphan"
    )
