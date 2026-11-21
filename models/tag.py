"""
models/tag.py — ХЕШТЕГИ (таблицы tags и post_tags).

Хештег — слово с решёткой в подписи поста: «Были в горах #travel #горы».
Каждый хештег хранится ОДИН раз в таблице tags, а какой пост с каким
хештегом связан — в таблице-связке post_tags.

Это связь МНОГИЕ-КО-МНОГИМ:
  в одном посте много хештегов, у одного хештега много постов.
  Post * ── post_tags ── * Tag

Новое на этом этапе: post_tags — «чистая» таблица-связка (Table), а не класс.
У неё нет своих данных, кроме двух ссылок, поэтому отдельная модель не нужна.
SQLAlchemy сам добавляет и удаляет в ней строки, когда мы меняем post.tags.
"""

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy:
#   Column, Table — описание таблицы без класса (для таблицы-связки)
#   ForeignKey, String — как раньше
from sqlalchemy import Column, ForeignKey, String, Table

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Base — из нашего database.py.
from database import Base

if TYPE_CHECKING:
    from .post import Post


# Таблица-связка: две колонки, и обе вместе — главный ключ (пара не повторяется).
# Base.metadata — «каталог всех таблиц», чтобы create_all создал и эту.
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Имя хештега без «#», в нижнем регистре: "travel", "горы".
    # unique — каждый хештег один раз; index — быстрый поиск «начинается с...».
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # tag.posts → все посты с этим хештегом.
    # secondary=post_tags — «связь идёт ЧЕРЕЗ таблицу-связку».
    posts: Mapped[list["Post"]] = relationship(secondary=post_tags, back_populates="tags")
