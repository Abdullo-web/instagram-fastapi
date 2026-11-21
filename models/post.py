"""
models/post.py — ПОСТЫ (таблицы posts и post_images).

Аналогия: «человек что-то сделал и оставил след» — пост живёт, пока автор его не удалит.

Почему ДВЕ таблицы:
  в одном посте может быть от 1 до 10 фото (карусель). Хранить список фото
  в одной колонке нельзя, поэтому:
    posts       — сам пост: автор, подпись, даты
    post_images — фото поста: каждое фото = одна строка со ссылкой post_id
  Связи:  User 1 ── * Post 1 ── * PostImage   (один-ко-многим дважды)
"""

# datetime — из стандартного модуля datetime: тип для дат.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing: импорт только для подсказок редактора.
from typing import TYPE_CHECKING

# Типы колонок из SQLAlchemy:
#   DateTime   — дата и время
#   ForeignKey — ссылка на другую таблицу
#   Integer    — целое число (порядковый номер фото)
#   String     — строка ограниченной длины
#   Text       — длинный текст без жёсткого ограничения в базе (для подписи)
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text

# Из SQLAlchemy ORM (объяснение в models/user.py).
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base из database.py, utc_now из services/time_utils.py.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .comment import Comment
    from .like import Like
    from .tag import Tag
    from .user import User


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Автор поста. index=True — быстро находить «все посты пользователя».
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Подпись. Text — потому что может быть длинной (до 2200 символов, проверяет схема).
    caption: Mapped[str] = mapped_column(Text, default="")

    # Когда создан. index=True — посты часто сортируем «от новых к старым».
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # Когда последний раз меняли подпись. onupdate=utc_now — SQLAlchemy сам обновит
    # время при каждом изменении строки. None — пост ещё ни разу не редактировали.
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=utc_now
    )

    # Связь: post.author → пользователь-автор.
    author: Mapped["User"] = relationship(back_populates="posts")

    # Связь: post.images → список фото, отсортированный по position (1-е, 2-е, ...).
    # cascade="all, delete-orphan" — удалили пост → удалились строки его фото.
    images: Mapped[list["PostImage"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImage.position",
    )

    # ---- Этап 5 ----
    # post.likes    → все лайки поста
    # post.comments → все комментарии поста (и верхние, и ответы)
    # cascade: удалили пост → удалились его лайки и комментарии.
    likes: Mapped[list["Like"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

    # ---- Этап 8 ----
    # post.tags → хештеги поста. secondary="post_tags" — связь через таблицу-связку
    # из models/tag.py. Удалили пост → строки связки удалятся сами (сами хештеги остаются).
    tags: Mapped[list["Tag"]] = relationship(secondary="post_tags", back_populates="posts")


class PostImage(Base):
    __tablename__ = "post_images"

    id: Mapped[int] = mapped_column(primary_key=True)

    # К какому посту относится фото.
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )

    # Путь к файлу внутри папки media/, например "posts/ab12.jpg".
    path: Mapped[str] = mapped_column(String(255))

    # Порядковый номер фото в карусели: 0, 1, 2 ...
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Обратная связь: image.post → пост.
    post: Mapped["Post"] = relationship(back_populates="images")
