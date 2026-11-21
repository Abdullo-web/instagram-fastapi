"""
schemas/note.py — СХЕМЫ ЗАМЕТОК (Pydantic).

NoteCreate — что присылает клиент: только текст.
NoteOut    — что отдаёт сервер.
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel, Field и field_validator (своя проверка поля).
from pydantic import BaseModel, Field, field_validator

# Наши: лимит длины заметки и карточка автора.
from config import MAX_NOTE_LENGTH
from schemas.common import AuthorOut


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH, examples=["Кто идёт в горы? ⛰"])

    @field_validator("text", mode="after")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """Убираем пробелы по краям; заметка из одних пробелов — ошибка."""
        value = value.strip()
        if not value:
            raise ValueError("Заметка не может быть пустой")
        return value


class NoteOut(BaseModel):
    author: AuthorOut
    text: str
    created_at: datetime
    expires_at: datetime
