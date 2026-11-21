"""
routers/notes.py — ЭТАП 3: ЗАМЕТКИ (короткий текст на 24 часа).

Эндпоинты:
  POST   /notes     — поставить заметку (старая заменяется)
  DELETE /notes/me  — убрать свою заметку
  GET    /notes     — активные заметки (моя первая)
"""

# timedelta — из стандартного datetime.
from datetime import timedelta

# Из FastAPI: APIRouter, Depends, status.
from fastapi import APIRouter, Depends, status

# Из SQLAlchemy: select и Session.
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from config import NOTE_LIFETIME_HOURS
from database import get_db
from dependencies import get_current_user
from models.note import Note
from models.user import User
from schemas.common import build_author
from schemas.note import NoteCreate, NoteOut
from services.access import following_ids   # «на кого я подписан» (этап 4)
from services.time_utils import utc_now

router = APIRouter(prefix="/notes", tags=["Notes"])


def build_note_out(note: Note) -> NoteOut:
    """Заметка из базы → ответ клиенту."""
    return NoteOut(
        author=build_author(note.author),
        text=note.text,
        created_at=note.created_at,
        expires_at=note.expires_at,
    )


# ===========================================================================
# POST /notes — ПОСТАВИТЬ ЗАМЕТКУ
# ===========================================================================
@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED, summary="Поставить заметку")
def set_note(
    data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = utc_now()
    expires = now + timedelta(hours=NOTE_LIFETIME_HOURS)

    # У пользователя одна заметка: если строка уже есть — перезаписываем её,
    # если нет — создаём. current_user.note — связь из models/user.py.
    note = current_user.note
    if note is None:
        note = Note(user_id=current_user.id, text=data.text, created_at=now, expires_at=expires)
        db.add(note)
    else:
        note.text = data.text
        note.created_at = now      # заметка «новая» — отсчёт 24 часов начинается заново
        note.expires_at = expires

    db.commit()
    db.refresh(note)
    return build_note_out(note)


# ===========================================================================
# DELETE /notes/me — УБРАТЬ ЗАМЕТКУ
# ===========================================================================
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Убрать мою заметку")
def delete_my_note(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Если заметки нет — тоже 204: результат тот же, «заметки нет».
    if current_user.note is not None:
        db.delete(current_user.note)
        db.commit()


# ===========================================================================
# GET /notes — ЗАМЕТКИ
# ===========================================================================
@router.get("", response_model=list[NoteOut], summary="Активные заметки")
def list_notes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Активные заметки — моя и тех, на кого я подписан.
    Моя первая, остальные — от новых к старым.
    """
    # Чьи заметки показываем: мои подписки (принятые) + я сам.
    author_ids = following_ids(db, current_user) | {current_user.id}

    notes = db.scalars(
        select(Note)
        .where(Note.user_id.in_(author_ids), Note.expires_at > utc_now())
        .order_by(Note.created_at.desc())
    ).all()
    visible = [n for n in notes if n.author.is_active]

    # sort с key: False идёт раньше True, поэтому «не моя» (True) окажется после моей (False).
    visible.sort(key=lambda n: n.user_id != current_user.id)
    return [build_note_out(n) for n in visible]
