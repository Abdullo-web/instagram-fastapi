"""
routers/notifications.py — ЭТАП 7: УВЕДОМЛЕНИЯ.

Эндпоинты:
  GET  /notifications               — мои уведомления (новые сверху, порциями)
  GET  /notifications/unread-count  — сколько непрочитанных (для красной точки)
  POST /notifications/read          — отметить все прочитанными

Здесь уведомления только ЧИТАЮТ. Создаются они в других роутерах:
  routers/likes.py    — лайк
  routers/comments.py — комментарий и ответ
  routers/follows.py  — подписка, запрос, принятие запроса
  routers/profiles.py — автопринятие запросов, когда аккаунт стал открытым
Если человек онлайн, новое уведомление сразу приходит ему по WebSocket /ws/chat:
  {"type": "notification", "notification": {...}}
"""

# Из FastAPI: APIRouter, Depends, Query.
from fastapi import APIRouter, Depends, Query

# Из SQLAlchemy: func (count), select, update (изменить много строк одним запросом); Session.
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db
from dependencies import get_current_user
from models.notification import Notification
from models.user import User
from schemas.notification import NotificationOut, UnreadCountOut
from services.notifications import build_notification_out

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def count_unread(db: Session, user: User) -> int:
    """SELECT COUNT(*) FROM notifications WHERE recipient_id = ... AND is_read = false"""
    return db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_id == user.id, Notification.is_read.is_(False)
        )
    ) or 0


# ===========================================================================
# GET /notifications — МОИ УВЕДОМЛЕНИЯ
# ===========================================================================
@router.get("", response_model=list[NotificationOut], summary="Мои уведомления")
def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    # unread_only=true — показать только непрочитанные.
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    notifications = db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_notification_out(n) for n in notifications]


# ===========================================================================
# GET /notifications/unread-count — СКОЛЬКО НЕПРОЧИТАННЫХ
# ===========================================================================
@router.get("/unread-count", response_model=UnreadCountOut, summary="Сколько непрочитанных")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UnreadCountOut(count=count_unread(db, current_user))


# ===========================================================================
# POST /notifications/read — ОТМЕТИТЬ ВСЕ ПРОЧИТАННЫМИ
# ===========================================================================
@router.post("/read", response_model=UnreadCountOut, summary="Отметить все прочитанными")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # update(...) — один SQL-запрос меняет сразу ВСЕ подходящие строки:
    # UPDATE notifications SET is_read = true WHERE recipient_id = ... AND is_read = false
    db.execute(
        update(Notification)
        .where(Notification.recipient_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return UnreadCountOut(count=0)
