"""
schemas/comment.py — СХЕМЫ КОММЕНТАРИЕВ (Pydantic).

CommentCreate — что присылает клиент: текст и (необязательно) на какой комментарий ответ.
CommentOut    — что отдаёт сервер.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel, Field и field_validator.
from pydantic import BaseModel, Field, field_validator

# Наши: лимит длины и карточка автора.
from config import MAX_COMMENT_LENGTH
from schemas.common import AuthorOut


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_COMMENT_LENGTH, examples=["Красивое место!"])

    # parent_id — если это ответ, номер комментария, на который отвечаем.
    # None (по умолчанию) — обычный комментарий к посту.
    parent_id: int | None = Field(default=None, examples=[None])

    @field_validator("text", mode="after")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """Убираем пробелы по краям; комментарий из одних пробелов — ошибка."""
        value = value.strip()
        if not value:
            raise ValueError("Комментарий не может быть пустым")
        return value


class CommentOut(BaseModel):
    id: int
    post_id: int
    author: AuthorOut
    text: str
    parent_id: int | None    # None — верхний комментарий, число — это ответ
    created_at: datetime
    replies_count: int       # сколько ответов (кнопка «Посмотреть ответы (3)»)
    can_delete: bool         # могу ли я удалить (я автор комментария или автор поста)
