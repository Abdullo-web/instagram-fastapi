"""
services/chat.py — ЛОГИКА ЧАТА (общая для HTTP и WebSocket).

Сообщение можно отправить двумя путями:
  1. HTTP:      POST /chats/{id}/messages  (как письмо)
  2. WebSocket: {"type": "message", ...}   (как звонок)
Чтобы не писать одно и то же дважды, вся работа с базой — здесь,
а роутер (routers/chat.py) только принимает запрос и рассылает результат.

Функции:
  get_participant(db, conversation_id, user)  — участник ли user этого чата
  find_direct_conversation(db, a, b)          — найти диалог двоих, если он уже есть
  create_direct_conversation(db, a, b)        — создать диалог двоих
  participant_ids(db, conversation_id)        — id всех участников
  save_message(db, conversation, sender, text)— сохранить сообщение
  mark_read(db, participant)                  — отметить всё прочитанным
  unread_count(db, participant)               — сколько непрочитанных
  build_message_out(message)                  — сообщение → схема MessageOut
"""

# Из SQLAlchemy: func (count, max), select; Session — тип сессии.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Наши модели, схемы и функции.
from models.message import Conversation, ConversationParticipant, Message
from models.user import User
from schemas.chat import MessageOut
from schemas.common import build_author
from services.time_utils import utc_now


def get_participant(db: Session, conversation_id: int, user: User) -> ConversationParticipant | None:
    """Строка-участник «user в чате conversation_id» или None (значит, чужой чат)."""
    return db.scalars(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user.id,
        )
    ).first()


def find_direct_conversation(db: Session, a: User, b: User) -> Conversation | None:
    """
    Найти существующий диалог, где есть И a, И b.
    Идея: берём все чаты a, затем ищем среди них тот, где участник — b.
    .in_(подзапрос) — «conversation_id входит в список чатов a».
    """
    chats_of_a = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == a.id
    )
    shared = db.scalars(
        select(ConversationParticipant.conversation_id).where(
            ConversationParticipant.user_id == b.id,
            ConversationParticipant.conversation_id.in_(chats_of_a),
        )
    ).first()
    return db.get(Conversation, shared) if shared is not None else None


def create_direct_conversation(db: Session, a: User, b: User) -> Conversation:
    """Создать комнату и посадить в неё двоих."""
    conversation = Conversation()
    conversation.participants = [
        ConversationParticipant(user_id=a.id),
        ConversationParticipant(user_id=b.id),
    ]
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def participant_ids(db: Session, conversation_id: int) -> list[int]:
    """id всех участников чата — кому рассылать новое сообщение."""
    return list(
        db.scalars(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        ).all()
    )


def save_message(db: Session, conversation: Conversation, sender: User, text: str) -> Message:
    """
    Сохранить сообщение в базу.
    Заодно:
      - поднимаем чат вверх списка (updated_at = сейчас);
      - своё сообщение отправитель, конечно, «прочитал».
    """
    message = Message(conversation_id=conversation.id, sender_id=sender.id, text=text)
    db.add(message)
    conversation.updated_at = utc_now()
    db.flush()  # flush — отправить в базу БЕЗ commit, чтобы узнать message.id

    me = get_participant(db, conversation.id, sender)
    if me is not None:
        me.last_read_message_id = message.id

    db.commit()
    db.refresh(message)
    return message


def mark_read(db: Session, participant: ConversationParticipant) -> int:
    """
    Отметить прочитанными все сообщения чата.
    Возвращает id последнего сообщения (его разошлём собеседнику: «Просмотрено»).
    func.max — самый большой id в чате = самое новое сообщение.
    """
    last_id = db.scalar(
        select(func.max(Message.id)).where(Message.conversation_id == participant.conversation_id)
    ) or 0
    if last_id > participant.last_read_message_id:
        participant.last_read_message_id = last_id
        db.commit()
    return participant.last_read_message_id


def unread_count(db: Session, participant: ConversationParticipant) -> int:
    """Непрочитанные = чужие сообщения с id больше, чем «прочитал до»."""
    return db.scalar(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == participant.conversation_id,
            Message.sender_id != participant.user_id,
            Message.id > participant.last_read_message_id,
        )
    ) or 0


def build_message_out(message: Message) -> MessageOut:
    """Сообщение из базы → схема для ответа (и для отправки через WebSocket)."""
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender=build_author(message.sender),
        text=message.text,
        created_at=message.created_at,
    )
