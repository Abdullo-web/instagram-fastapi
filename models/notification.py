"""
models/notification.py — УВЕДОМЛЕНИЯ (таблица notifications).

Аналогия: «человеку сообщают новости».
Одна строка = одна новость: КОМУ (recipient), ОТ КОГО (actor), ЧТО случилось (type)
и к чему относится (пост / комментарий).

Уведомления НЕ создаются отдельным запросом клиента — они появляются
ВНУТРИ других действий (лайк, комментарий, подписка). См. services/notifications.py.

Типы (type):
  "like"            — actor лайкнул пост recipient
  "comment"         — actor прокомментировал пост recipient
  "reply"           — actor ответил на комментарий recipient
  "follow"          — actor подписался на recipient
  "follow_request"  — actor хочет подписаться на закрытый аккаунт recipient
  "follow_accepted" — actor принял запрос recipient на подписку
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy: типы колонок.
from sqlalchemy import Boolean, DateTime, ForeignKey, String

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .comment import Comment
    from .post import Post
    from .user import User

# Константы типов — чтобы не ошибиться в написании строки в разных файлах.
NOTIF_LIKE = "like"
NOTIF_COMMENT = "comment"
NOTIF_REPLY = "reply"
NOTIF_FOLLOW = "follow"
NOTIF_FOLLOW_REQUEST = "follow_request"
NOTIF_FOLLOW_ACCEPTED = "follow_accepted"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    # КОМУ. index=True — быстро находить «мои уведомления».
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # ОТ КОГО.
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # ЧТО случилось (одна из констант выше).
    type: Mapped[str] = mapped_column(String(20))

    # К какому посту / комментарию относится (у подписок — None).
    # ondelete="CASCADE": удалили пост или комментарий → база сама удалит
    # уведомления о нём (работает, потому что в database.py включены внешние ключи).
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    # Прочитано ли (для красной точки и счётчика).
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # Связи «только для чтения» — удобный доступ к связанным строкам:
    # notification.actor / .post / .comment. foreign_keys — потому что
    # на users ссылаются две колонки (recipient_id и actor_id).
    actor: Mapped["User"] = relationship(foreign_keys=[actor_id])
    post: Mapped["Post | None"] = relationship()
    comment: Mapped["Comment | None"] = relationship()
