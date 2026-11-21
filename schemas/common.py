"""
schemas/common.py — ОБЩИЕ СХЕМЫ, которые используют разные части проекта.

AuthorOut — короткая карточка «кто автор»: ник и аватар.
Её показываем у поста, истории, заметки (а позже — у комментария и сообщения).
"""

# Из Pydantic: BaseModel — родитель всех схем.
from pydantic import BaseModel

# Наши: модель User и функция «путь → адрес картинки».
from models.user import User
from services.files import file_url


class AuthorOut(BaseModel):
    username: str
    avatar_url: str | None


def build_author(user: User) -> AuthorOut:
    """Собирает карточку автора из пользователя (аватар лежит в его профиле)."""
    return AuthorOut(username=user.username, avatar_url=file_url(user.profile.avatar))
