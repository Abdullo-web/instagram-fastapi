"""
services/notifications.py — СОЗДАНИЕ И ОТПРАВКА УВЕДОМЛЕНИЙ.

Уведомление появляется ВНУТРИ другого действия. Например, в routers/likes.py:
    лайк сохранён → notify(...) → строка в notifications → (если человек онлайн)
    → мгновенно летит ему по WebSocket.

Функции:
  notify(db, tasks, recipient_id, actor_id, type, post_id, comment_id) — создать и запланировать отправку
  remove_notifications(db, recipient_id, actor_id, type, post_id)      — удалить (например, лайк убрали)
  build_notification_out(notification)                                 — строка из базы → схема

Про BackgroundTasks («фоновые задачи» FastAPI):
  отправка по WebSocket — асинхронная (await), а многие наши эндпоинты обычные (def).
  BackgroundTasks решает это: задача выполняется ПОСЛЕ того, как ответ ушёл клиенту.
  Плюс: к этому моменту commit уже сделан, и уведомление точно есть в базе.
"""

# Из FastAPI: BackgroundTasks — список задач «сделать после ответа».
from fastapi import BackgroundTasks

# Из SQLAlchemy: select (для удаления по условию берём строки и удаляем по одной); Session.
from sqlalchemy import select
from sqlalchemy.orm import Session

# Наши: модель уведомления и её типы, схемы, функции, менеджер соединений.
from models.notification import (
    NOTIF_COMMENT,
    NOTIF_FOLLOW,
    NOTIF_FOLLOW_ACCEPTED,
    NOTIF_FOLLOW_REQUEST,
    NOTIF_LIKE,
    NOTIF_REPLY,
    Notification,
)
from schemas.common import build_author
from schemas.notification import NotificationOut
from services.connection_manager import manager
from services.files import file_url


# Шаблоны текста. {u} — username того, кто сделал действие.
# Формулировки в настоящем времени — они не зависят от пола: «anna отвечает», а не «ответил(а)».
TEXTS = {
    NOTIF_LIKE: "{u} — нравится ваш пост",
    NOTIF_COMMENT: "{u} комментирует ваш пост: «{c}»",
    NOTIF_REPLY: "{u} отвечает на ваш комментарий: «{c}»",
    NOTIF_FOLLOW: "{u} — новый подписчик",
    NOTIF_FOLLOW_REQUEST: "{u} хочет подписаться на вас",
    NOTIF_FOLLOW_ACCEPTED: "{u} принимает ваш запрос на подписку",
}


def build_notification_out(n: Notification) -> NotificationOut:
    """Уведомление из базы → готовый ответ (с текстом и картинкой поста)."""
    comment_text = n.comment.text if n.comment else ""
    if len(comment_text) > 50:
        comment_text = comment_text[:50] + "…"   # длинный комментарий обрезаем для превью

    # Первая картинка поста — маленькое превью справа.
    post_image = n.post.images[0].path if n.post and n.post.images else None

    return NotificationOut(
        id=n.id,
        type=n.type,
        actor=build_author(n.actor),
        # .format(...) подставляет значения вместо {u} и {c} в шаблоне.
        text=TEXTS.get(n.type, "{u}").format(u=n.actor.username, c=comment_text),
        post_id=n.post_id,
        post_image_url=file_url(post_image),
        comment_id=n.comment_id,
        is_read=n.is_read,
        created_at=n.created_at,
    )


def notify(
    db: Session,
    tasks: BackgroundTasks,
    *,                          # * — дальше параметры только по имени: notify(..., type="like")
    recipient_id: int,
    actor_id: int,
    type: str,
    post_id: int | None = None,
    comment_id: int | None = None,
) -> None:
    """
    Создать уведомление и запланировать отправку по WebSocket.

    ВАЖНО: здесь НЕТ commit — его делает эндпоинт вместе со своим действием
    (лайк и уведомление сохраняются одним commit: либо оба, либо ничего).
    """
    # Про свои действия себя не уведомляем (лайк своего поста — не новость).
    if recipient_id == actor_id:
        return

    notification = Notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        type=type,
        post_id=post_id,
        comment_id=comment_id,
    )
    db.add(notification)
    db.flush()                  # отправить в базу без commit, чтобы появились id и связи
    db.refresh(notification)    # подтянуть actor, post, comment для текста

    # Готовим JSON сейчас (пока сессия базы открыта), а отправим после ответа.
    data = {
        "type": "notification",
        "notification": build_notification_out(notification).model_dump(mode="json"),
    }
    # add_task(функция, аргументы...) — FastAPI вызовет manager.send_to_user(recipient_id, data)
    # после отправки ответа. Если человек офлайн — ничего страшного, уведомление уже в базе.
    tasks.add_task(manager.send_to_user, recipient_id, data)


def remove_notifications(
    db: Session,
    *,
    recipient_id: int,
    actor_id: int,
    type: str,
    post_id: int | None = None,
) -> None:
    """
    Удалить уведомления о действии, которое отменили
    (убрали лайк, отписались, отменили запрос). Без commit — его делает эндпоинт.
    """
    query = select(Notification).where(
        Notification.recipient_id == recipient_id,
        Notification.actor_id == actor_id,
        Notification.type == type,
    )
    if post_id is not None:
        query = query.where(Notification.post_id == post_id)
    for n in db.scalars(query).all():
        db.delete(n)
