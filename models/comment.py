"""
models/comment.py — КОММЕНТАРИИ (таблица comments).

Одна строка = один комментарий: КТО написал, к КАКОМУ посту, ТЕКСТ.

Ответы на комментарии: поле parent_id.
  parent_id = None   → обычный комментарий к посту («верхний уровень»)
  parent_id = 5      → это ответ на комментарий №5
Таблица ссылается САМА НА СЕБЯ (comments.parent_id → comments.id).
Как в Instagram, уровень ответов один: ответ на ответ прикрепляется к тому же
верхнему комментарию (это делает роутер, см. routers/comments.py).
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy: типы колонок (Text — длинный текст).
from sqlalchemy import DateTime, ForeignKey, Text

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .post import Post
    from .user import User


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)

    # К какому посту.
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)

    # Кто написал.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # На какой комментарий это ответ (None — не ответ). Ссылка на эту же таблицу.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Текст комментария (длину проверяет схема: до 2200 символов).
    text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # comment.author → кто написал; comment.post → к какому посту.
    author: Mapped["User"] = relationship()
    post: Mapped["Post"] = relationship(back_populates="comments")

    # Связь «сама с собой»:
    #   comment.parent  → комментарий, на который ответили (или None)
    #   comment.replies → список ответов на этот комментарий
    # remote_side="Comment.id" — подсказка SQLAlchemy: у parent «дальняя сторона» — колонка id.
    # cascade у replies: удалили комментарий → удалились и ответы на него.
    parent: Mapped["Comment | None"] = relationship(
        back_populates="replies", remote_side="Comment.id"
    )
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
