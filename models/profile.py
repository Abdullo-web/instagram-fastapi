"""
models/profile.py — МОДЕЛЬ ПРОФИЛЯ (таблица profiles).

Аналогия: «лицо и визитка человека» — то, что видят другие.
На этапе 1 профиль только СОЗДАЁТСЯ автоматически при регистрации (пустой).
Эндпоинты для просмотра и редактирования профиля появятся на этапе 2.
"""

# TYPE_CHECKING — из стандартного typing: импорт только для подсказок редактора.
from typing import TYPE_CHECKING

# Из SQLAlchemy:
#   Boolean    — колонка да/нет
#   ForeignKey — «ссылка» на строку другой таблицы
#   String     — текстовая колонка
from sqlalchemy import Boolean, ForeignKey, String

# Из SQLAlchemy ORM: Mapped, mapped_column, relationship (см. объяснение в models/user.py).
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Base — из нашего database.py.
from database import Base

if TYPE_CHECKING:
    from .user import User


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)

    # user_id — ЧЕЙ это профиль. ForeignKey("users.id") — ссылка на колонку id
    # таблицы users. unique=True — у одного пользователя только один профиль.
    # ondelete="CASCADE" — удалили пользователя → профиль удаляется тоже.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    # bio — «о себе», до 150 символов. default="" — при создании пустая строка.
    bio: Mapped[str] = mapped_column(String(150), default="")

    # avatar — ПУТЬ к файлу фото (сам файл будет в папке media/). Пока нет — None.
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # website — ссылка на сайт, необязательная.
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # is_private — приватный ли аккаунт. По умолчанию публичный (False).
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    # Обратная связь: profile.user → пользователь, которому принадлежит профиль.
    user: Mapped["User"] = relationship(back_populates="profile")
