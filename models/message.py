"""
models/message.py — ЧАТ: ДИАЛОГИ, УЧАСТНИКИ, СООБЩЕНИЯ.

Аналогия: «люди разговаривают о погоде».

Три таблицы:
  conversations              — «комната» для разговора
  conversation_participants  — кто находится в комнате (+ до какого сообщения он прочитал)
  messages                   — сами сообщения: кто, в какой комнате, текст, когда

Связи:
  Conversation 1 ── * ConversationParticipant * ── 1 User
  Conversation 1 ── * Message * ── 1 User (отправитель)

Почему участники — отдельная таблица, а не две колонки user1/user2:
так в будущем легко сделать групповой чат (в комнате 3, 10, 50 человек).
Сейчас роутер создаёт только диалоги на двоих.

Как считается «прочитано»:
  у каждого участника есть last_read_message_id — номер последнего прочитанного сообщения.
  Непрочитанные = сообщения с id БОЛЬШЕ этого номера, написанные не мной.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# TYPE_CHECKING — из стандартного typing.
from typing import TYPE_CHECKING

# Из SQLAlchemy: типы колонок, UniqueConstraint (пара не повторяется).
from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint

# Из SQLAlchemy ORM.
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Наши: Base и utc_now.
from database import Base
from services.time_utils import utc_now

if TYPE_CHECKING:
    from .user import User


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Время последнего сообщения. По нему сортируем список чатов:
    # где писали недавно — тот выше (как в Direct).
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # conversation.participants → участники; conversation.messages → сообщения.
    participants: Mapped[list["ConversationParticipant"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    # Один человек не может быть в одной комнате дважды.
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conv_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # До какого сообщения участник прочитал. 0 — ещё ничего не читал.
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0)

    # participant.conversation → комната; participant.user → пользователь.
    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    # В какой комнате.
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )

    # Кто написал.
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Текст (длину проверяет схема / роутер: до 1000 символов).
    text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # message.conversation → комната; message.sender → отправитель.
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship()
