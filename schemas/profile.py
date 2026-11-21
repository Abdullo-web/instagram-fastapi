"""
schemas/profile.py — СХЕМЫ ПРОФИЛЯ (Pydantic).

ProfileOut    — что сервер ОТДАЁТ, когда смотрят профиль.
ProfileUpdate — что клиент может ПРИСЛАТЬ, чтобы изменить свой профиль.

Обратите внимание: ProfileOut собирает данные из ДВУХ таблиц —
username и full_name лежат в users, а bio, avatar и т.д. — в profiles.
Клиенту не важно, как мы храним данные, он получает одну «визитку».
"""

# Literal — из стандартного typing: «только одно из перечисленных значений».
from typing import Literal

# Из Pydantic: BaseModel — родитель схем, Field — правила для поля.
from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    """Визитка пользователя."""

    username: str                 # из таблицы users
    full_name: str | None         # из таблицы users
    bio: str                      # из таблицы profiles
    avatar_url: str | None        # адрес картинки, например /media/avatars/ab12.jpg
    website: str | None
    is_private: bool

    # Счётчики: посты (этап 3), подписчики и подписки (этап 4).
    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0

    # is_me — смотрю ли я свой собственный профиль (удобно приложению:
    # показать кнопку «Редактировать» вместо «Подписаться»).
    is_me: bool = False

    # Этап 4. follow_status — моя подписка на этого человека:
    #   "none"     — не подписан       → кнопка «Подписаться»
    #   "pending"  — запрос отправлен  → кнопка «Запрос отправлен»
    #   "accepted" — подписан          → кнопка «Вы подписаны»
    # Literal — только одно из этих значений (из стандартного typing).
    follow_status: Literal["none", "pending", "accepted"] = "none"

    # follows_you — подписан ли он на меня (надпись «Подписан(а) на вас»).
    follows_you: bool = False


class ProfileUpdate(BaseModel):
    """
    Изменение профиля: PATCH /profiles/me.

    Все поля НЕОБЯЗАТЕЛЬНЫЕ (= None). PATCH значит «изменить ЧАСТЬ данных»:
    прислали только bio — меняем только bio, остальное не трогаем.
    """

    full_name: str | None = Field(default=None, max_length=100, examples=["Иван Петров"])
    bio: str | None = Field(default=None, max_length=150, examples=["Люблю горы и фото 📷"])

    # Ссылка должна начинаться с http:// или https://
    website: str | None = Field(
        default=None, max_length=255, pattern=r"^https?://", examples=["https://example.com"]
    )

    is_private: bool | None = Field(default=None, examples=[False])
