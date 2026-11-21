"""
schemas/post.py — СХЕМЫ ПОСТОВ (Pydantic).

PostOut    — что сервер отдаёт о посте.
PostUpdate — что можно изменить (только подпись).

Обратите внимание: схемы для СОЗДАНИЯ поста здесь нет. Пост создаётся
формой с файлами (multipart/form-data), а не JSON, поэтому поля
описаны прямо в эндпоинте через File(...) и Form(...) — см. routers/posts.py.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel и Field.
from pydantic import BaseModel, Field

# Наши: лимит длины подписи из config.py и карточка автора из schemas/common.py.
from config import MAX_CAPTION_LENGTH
from schemas.common import AuthorOut


class PostOut(BaseModel):
    id: int
    author: AuthorOut                 # кто автор: {"username": ..., "avatar_url": ...}
    caption: str
    images: list[str]                 # адреса фото по порядку: ["/media/posts/a.jpg", ...]
    created_at: datetime
    updated_at: datetime | None       # None — пост не редактировали
    is_mine: bool                     # мой ли это пост (показать кнопки «изменить/удалить»)

    # ---- Этап 5 ----
    likes_count: int = 0              # сколько лайков
    comments_count: int = 0           # сколько комментариев (вместе с ответами)
    liked_by_me: bool = False         # лайкнул ли я (красное сердечко)

    # ---- Этап 8 ----
    tags: list[str] = []              # хештеги без «#»: ["travel", "горы"]


class PostUpdate(BaseModel):
    """PATCH /posts/{id}: меняется только подпись. Фото в Instagram после публикации не меняют."""

    caption: str = Field(max_length=MAX_CAPTION_LENGTH, examples=["Новая подпись к фото"])
