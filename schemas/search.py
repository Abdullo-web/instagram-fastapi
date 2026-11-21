"""
schemas/search.py — СХЕМЫ ПОИСКА (Pydantic).

UserSearchOut — найденный человек (строка в результатах поиска).
TagOut        — найденный хештег и сколько у него постов.
"""

# Literal — из стандартного typing.
from typing import Literal

# Из Pydantic: BaseModel.
from pydantic import BaseModel


class UserSearchOut(BaseModel):
    username: str
    full_name: str | None
    avatar_url: str | None
    is_private: bool
    # Моя подписка на него (как в профиле): кнопка «Подписаться» прямо в поиске.
    follow_status: Literal["none", "pending", "accepted", "self"]


class TagOut(BaseModel):
    name: str            # без «#»
    posts_count: int     # сколько постов с этим хештегом
