"""
models/follow.py — ПОДПИСКИ (таблица follows).

Аналогия: «рукопожатие». Одна строка = «КТО (follower) подписан на КОГО (following)».

Это связь МНОГИЕ-КО-МНОГИМ между пользователями:
  я подписан на многих, и на меня подписаны многие.
Обе колонки ссылаются на ОДНУ И ТУ ЖЕ таблицу users — поэтому в relationship
ниже нужно явно указать foreign_keys, иначе SQLAlchemy не поймёт, какая колонка к какой связи.

Статус подписки:
  "accepted" — подписка действует (публичный аккаунт или запрос принят)
  "pending"  — запрос к закрытому аккаунту ждёт ответа
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy:
#   CheckConstraint  — правило проверки строки в самой базе (нельзя подписаться на себя)
#   UniqueConstraint — пара колонок не может повторяться (нельзя подписаться дважды)
#   DateTime, ForeignKey, String — типы колонок
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User

# Возможные статусы — константы, чтобы не ошибиться в написании строки в разных файлах.
FOLLOW_ACCEPTED = "accepted"
FOLLOW_PENDING = "pending"


class Follow(Base):
    __tablename__ = "follows"

    __table_args__ = (
        # Пара (кто, на кого) уникальна: второй раз подписаться нельзя.
        UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),
        # Даже если в коде будет ошибка, база сама не даст подписаться на себя.
        CheckConstraint("follower_id != following_id", name="ck_no_self_follow"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # КТО подписался. index=True — быстро находить «на кого подписан X».
    follower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # НА КОГО подписались. index=True — быстро находить «кто подписан на X».
    following_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # "accepted" или "pending".
    status: Mapped[str] = mapped_column(String(10), default=FOLLOW_ACCEPTED)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # follow.follower  → пользователь, который подписался
    # follow.following → пользователь, на которого подписались
    # foreign_keys=[...] — явно говорим, по какой колонке строится каждая связь.
    follower: Mapped["User"] = relationship(foreign_keys=[follower_id])
    following: Mapped["User"] = relationship(foreign_keys=[following_id])
