"""
models/like.py — ЛАЙКИ (таблица likes).

Аналогия: «человек реагирует на чужое дело». Одна строка = «КТО лайкнул КАКОЙ пост».
Связь «пользователь ↔ пост» — многие-ко-многим:
  один человек лайкает много постов, у одного поста много лайков.
Пара (user_id, post_id) уникальна: один человек = один лайк на пост.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy: типы колонок и UniqueConstraint (пара не повторяется).
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .post import Post
    from .user import User


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_like_user_post"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кто лайкнул.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Какой пост. index=True — быстро считать «сколько лайков у поста».
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # like.user → кто лайкнул; like.post → какой пост.
    user: Mapped["User"] = relationship()
    post: Mapped["Post"] = relationship(back_populates="likes")
