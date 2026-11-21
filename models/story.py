"""
models/story.py — ИСТОРИИ (таблицы stories и story_views).

История — фото, которое живёт 24 часа.
Как это сделано: при создании записываем expires_at = сейчас + 24 часа.
Когда показываем истории, берём только те, у которых expires_at ещё в будущем.
Ничего «удалять по таймеру» не нужно — просроченные просто не показываются.

story_views — кто посмотрел историю. Это связь «многие-ко-многим»:
одну историю смотрят многие люди, один человек смотрит много историй.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy.
# UniqueConstraint — правило «эта ПАРА колонок не может повторяться».
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Автор истории.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Путь к картинке внутри media/, например "stories/cd34.jpg".
    media: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Когда история «исчезнет». index=True — часто фильтруем по этой колонке.
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # story.author → автор; story.views → список просмотров.
    author: Mapped["User"] = relationship(back_populates="stories")
    views: Mapped[list["StoryView"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


class StoryView(Base):
    __tablename__ = "story_views"

    # Один человек = один просмотр одной истории.
    # Пара (story_id, viewer_id) не может повториться: смотреть можно сколько угодно,
    # но в списке «кто посмотрел» человек будет один раз.
    __table_args__ = (UniqueConstraint("story_id", "viewer_id", name="uq_story_viewer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # view.story → история; view.viewer → кто посмотрел.
    story: Mapped["Story"] = relationship(back_populates="views")
    viewer: Mapped["User"] = relationship()
