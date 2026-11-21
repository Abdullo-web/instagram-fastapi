"""
schemas/chat.py — СХЕМЫ ЧАТА (Pydantic).

StartChatRequest — начать диалог: с кем.
MessageCreate    — отправить сообщение через HTTP: текст.
MessageOut       — одно сообщение.
ConversationOut  — один диалог в списке чатов (как строка в Direct).
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel, Field, field_validator.
from pydantic import BaseModel, Field, field_validator

# Наши: лимит длины и карточка автора.
from config import MAX_MESSAGE_LENGTH
from schemas.common import AuthorOut


class StartChatRequest(BaseModel):
    username: str = Field(examples=["anna"])


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH, examples=["Привет! Какая у вас погода?"])

    @field_validator("text", mode="after")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """Убираем пробелы по краям; сообщение из одних пробелов — ошибка."""
        value = value.strip()
        if not value:
            raise ValueError("Сообщение не может быть пустым")
        return value


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender: AuthorOut
    text: str
    created_at: datetime


class ConversationOut(BaseModel):
    id: int
    other: AuthorOut                     # собеседник
    other_is_online: bool                # есть ли у него открытое WebSocket-соединение
    last_message: MessageOut | None      # последнее сообщение (для превью в списке)
    unread_count: int                    # сколько непрочитанных мной сообщений
    other_last_read_message_id: int      # до какого сообщения прочитал собеседник («Просмотрено»)
    updated_at: datetime
