"""
routers/chat.py — ЭТАП 6: ЧАТ (DIRECT) — HTTP + WEBSOCKET.

HTTP-эндпоинты (проверяются в Swagger):
  POST /chats                     — начать диалог с человеком (или получить уже существующий)
  GET  /chats                     — мои диалоги (как список в Direct)
  GET  /chats/{id}/messages       — история сообщений (порциями)
  POST /chats/{id}/messages       — отправить сообщение через HTTP
  POST /chats/{id}/read           — отметить прочитанным

WebSocket (в Swagger НЕ проверяется — для него страница /chat-test):
  WS /ws/chat?token=<access_token>

Что ходит по WebSocket (всё в формате JSON):
  клиент → сервер:
    {"type": "message", "conversation_id": 1, "text": "Привет!"}   — отправить сообщение
    {"type": "read",    "conversation_id": 1}                      — я прочитал
    {"type": "typing",  "conversation_id": 1}                      — я печатаю
  сервер → клиент:
    {"type": "message", "message": {...}}                          — новое сообщение
    {"type": "read",    "conversation_id": 1, "username": "...", "last_read_message_id": 7}
    {"type": "typing",  "conversation_id": 1, "username": "..."}
    {"type": "error",   "detail": "..."}                           — что-то не так

Схема «Анна и Иван говорят о погоде» — в учебнике, этап 6.
"""

# json — стандартная библиотека Python: текст JSON ↔ словарь Python.
import json

# Из FastAPI:
#   WebSocket           — объект открытого соединения
#   WebSocketDisconnect — ошибка «клиент отключился» (её ловим, чтобы убрать его из книги)
#   остальное — как в прошлых роутерах
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

# ValidationError — из Pydantic: ошибка «данные не прошли проверку схемы».
# В HTTP FastAPI ловит её сам (ответ 422), а в WebSocket — ловим мы.
from pydantic import ValidationError

# Из SQLAlchemy: select; Session — тип сессии.
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import SessionLocal, get_db       # SessionLocal — для WebSocket (там нет Depends(get_db))
from dependencies import get_current_user
from models.message import Conversation, ConversationParticipant, Message
from models.user import User
from schemas.chat import ConversationOut, MessageCreate, MessageOut, StartChatRequest
from schemas.common import build_author
from services.chat import (
    build_message_out,
    create_direct_conversation,
    find_direct_conversation,
    get_participant,
    mark_read,
    participant_ids,
    save_message,
    unread_count,
)
from services.connection_manager import manager   # «кто онлайн» и рассылка
from services.security import decode_token        # проверка токена для WebSocket

router = APIRouter(tags=["Chat"])


# ===========================================================================
# Вспомогательные функции
# ===========================================================================
def get_my_participant_or_404(db: Session, conversation_id: int, user: User) -> ConversationParticipant:
    """Я участник этого чата? Если нет — чужой чат для меня «не найден» (404)."""
    participant = get_participant(db, conversation_id, user)
    if participant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чат не найден")
    return participant


def build_conversation_out(db: Session, me: ConversationParticipant) -> ConversationOut:
    """Строка списка чатов: собеседник, последнее сообщение, непрочитанные."""
    conversation = me.conversation

    # Собеседник — участник, который не я.
    other = next(p for p in conversation.participants if p.user_id != me.user_id)

    # Последнее сообщение: самый большой id в этом чате.
    last = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
    ).first()

    return ConversationOut(
        id=conversation.id,
        other=build_author(other.user),
        other_is_online=manager.is_online(other.user_id),
        last_message=build_message_out(last) if last else None,
        unread_count=unread_count(db, me),
        other_last_read_message_id=other.last_read_message_id,
        updated_at=conversation.updated_at,
    )


async def broadcast_message(db: Session, message: Message) -> None:
    """Разослать новое сообщение всем участникам чата, кто сейчас онлайн."""
    data = {
        "type": "message",
        # model_dump(mode="json") — схема → словарь, где даты уже превращены в текст
        # (send_json не умеет отправлять объект datetime).
        "message": build_message_out(message).model_dump(mode="json"),
    }
    await manager.send_to_users(participant_ids(db, message.conversation_id), data)


async def broadcast_read(db: Session, participant: ConversationParticipant, last_id: int) -> None:
    """Сообщить ДРУГИМ участникам: «я прочитал до сообщения №last_id»."""
    others = [uid for uid in participant_ids(db, participant.conversation_id) if uid != participant.user_id]
    await manager.send_to_users(
        others,
        {
            "type": "read",
            "conversation_id": participant.conversation_id,
            "username": participant.user.username,
            "last_read_message_id": last_id,
        },
    )


# ===========================================================================
# POST /chats — НАЧАТЬ ДИАЛОГ
# ===========================================================================
@router.post("/chats", response_model=ConversationOut, summary="Начать диалог")
def start_chat(
    data: StartChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    other = db.scalars(select(User).where(User.username == data.username.strip().lower())).first()
    if other is None or not other.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if other.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя начать чат с самим собой")

    # Диалог двоих всегда один: если уже есть — возвращаем его, а не создаём новый.
    conversation = find_direct_conversation(db, current_user, other)
    if conversation is None:
        conversation = create_direct_conversation(db, current_user, other)

    me = get_participant(db, conversation.id, current_user)
    return build_conversation_out(db, me)


# ===========================================================================
# GET /chats — МОИ ДИАЛОГИ
# ===========================================================================
@router.get("/chats", response_model=list[ConversationOut], summary="Мои диалоги")
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Все мои «места» в чатах; join — соединяем с таблицей чатов, чтобы
    # отсортировать по времени последнего сообщения (новые сверху).
    my_rows = db.scalars(
        select(ConversationParticipant)
        .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
        .where(ConversationParticipant.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [build_conversation_out(db, me) for me in my_rows]


# ===========================================================================
# GET /chats/{id}/messages — ИСТОРИЯ СООБЩЕНИЙ
# ===========================================================================
@router.get("/chats/{conversation_id}/messages", response_model=list[MessageOut], summary="История сообщений")
def list_messages(
    conversation_id: int,
    limit: int = Query(30, ge=1, le=100),
    # before_id — «курсор»: дай сообщения СТАРШЕ сообщения №before_id.
    # Почему не offset: пока я листаю вверх, приходят новые сообщения,
    # и offset «съезжает». Курсор по id всегда указывает на одно и то же место.
    before_id: int | None = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_my_participant_or_404(db, conversation_id, current_user)

    query = select(Message).where(Message.conversation_id == conversation_id)
    if before_id is not None:
        query = query.where(Message.id < before_id)

    # Берём limit самых новых (desc), а потом переворачиваем,
    # чтобы в ответе они шли сверху вниз: старые → новые, как в чате.
    newest_first = db.scalars(query.order_by(Message.id.desc()).limit(limit)).all()
    return [build_message_out(m) for m in reversed(newest_first)]


# ===========================================================================
# POST /chats/{id}/messages — ОТПРАВИТЬ СООБЩЕНИЕ (HTTP)
# ===========================================================================
# async def — потому что внутри мы ждём (await) рассылку по WebSocket.
# (Учебное упрощение: работа с SQLite внутри async-функции ненадолго блокирует
#  сервер. Для учебного проекта это незаметно.)
@router.post(
    "/chats/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить сообщение",
)
async def send_message_http(
    conversation_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_my_participant_or_404(db, conversation_id, current_user)
    message = save_message(db, me.conversation, current_user, data.text)

    # Собеседник онлайн → получит сообщение мгновенно, не обновляя страницу.
    await broadcast_message(db, message)
    return build_message_out(message)


# ===========================================================================
# POST /chats/{id}/read — ПРОЧИТАНО
# ===========================================================================
@router.post("/chats/{conversation_id}/read", response_model=ConversationOut, summary="Отметить прочитанным")
async def read_chat(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_my_participant_or_404(db, conversation_id, current_user)
    last_id = mark_read(db, me)
    await broadcast_read(db, me, last_id)
    return build_conversation_out(db, me)


# ===========================================================================
# WS /ws/chat — ЖИВОЕ СОЕДИНЕНИЕ
# ===========================================================================
@router.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket,
    # Токен передаём в адресе: /ws/chat?token=...
    # Причина: браузерный WebSocket не умеет добавлять заголовок Authorization.
    # (Минус: адрес с токеном может попасть в логи сервера. Для учёбы — допустимо.)
    token: str = Query(...),
):
    # 1. Кто звонит? Проверяем access-токен так же, как в dependencies.py.
    payload = decode_token(token, expected_type="access")
    user_id = int(payload["sub"]) if payload else None
    with SessionLocal() as db:
        user = db.get(User, user_id) if user_id else None
        if user is None or not user.is_active:
            # 1008 — стандартный код закрытия WebSocket «нарушение правил» (нет доступа).
            await websocket.close(code=1008)
            return

    # 2. «Снимаем трубку» и записываем в телефонную книгу.
    await manager.connect(user_id, websocket)

    try:
        # 3. Бесконечно слушаем, что присылает клиент, пока он не отключится.
        while True:
            raw = await websocket.receive_text()
            await handle_ws_event(websocket, user_id, raw)
    except WebSocketDisconnect:
        # Клиент закрыл вкладку / пропал интернет — это нормально, не ошибка.
        pass
    finally:
        # 4. В любом случае вычёркиваем это соединение из книги.
        manager.disconnect(user_id, websocket)


async def handle_ws_event(websocket: WebSocket, user_id: int, raw: str) -> None:
    """Разобрать одно событие от клиента и выполнить его."""

    async def error(detail: str) -> None:
        """Ответить ошибкой только этому клиенту (соединение при этом не закрываем)."""
        await websocket.send_json({"type": "error", "detail": detail})

    # json.loads — текст → словарь. Если прислали не JSON — ошибка.
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return await error("Ожидается JSON")
    if not isinstance(event, dict):
        return await error("Ожидается JSON-объект {...}")

    event_type = event.get("type")
    conversation_id = event.get("conversation_id")
    if not isinstance(conversation_id, int):
        return await error("Нужно поле conversation_id (число)")

    # Для каждого события — своя короткая сессия базы (with сам её закроет).
    with SessionLocal() as db:
        user = db.get(User, user_id)
        me = get_participant(db, conversation_id, user)
        if me is None:
            return await error("Чат не найден")

        if event_type == "message":
            # Проверяем текст той же схемой, что и в HTTP (длина, не пустой).
            try:
                data = MessageCreate(text=event.get("text", ""))
            except ValidationError:
                return await error("Текст сообщения: от 1 до 1000 символов")
            message = save_message(db, me.conversation, user, data.text)
            await broadcast_message(db, message)

        elif event_type == "read":
            last_id = mark_read(db, me)
            await broadcast_read(db, me, last_id)

        elif event_type == "typing":
            # «Печатает...» — ничего не сохраняем, только пересылаем собеседнику.
            others = [uid for uid in participant_ids(db, conversation_id) if uid != user_id]
            await manager.send_to_users(
                others,
                {"type": "typing", "conversation_id": conversation_id, "username": user.username},
            )

        else:
            await error("Неизвестный type. Можно: message, read, typing")
