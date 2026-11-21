"""
routers/likes.py — ЭТАП 5: ЛАЙКИ.

Эндпоинты:
  POST   /posts/{post_id}/like   — поставить лайк
  DELETE /posts/{post_id}/like   — убрать лайк
  GET    /posts/{post_id}/likes  — кто лайкнул

Лайкнуть можно только пост, который тебе можно видеть
(правило — в services/access.py, функция get_visible_post_or_404).
Этап 7: лайк создаёт уведомление автору поста, снятый лайк — удаляет его.
"""

# Из FastAPI: APIRouter, Depends, Query, status;
# BackgroundTasks — «сделать после ответа» (отправка уведомления по WebSocket, этап 7).
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

# Из SQLAlchemy: func (func.count), select; Session — тип сессии.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db
from dependencies import get_current_user
from models.like import Like
from models.notification import NOTIF_LIKE               # тип уведомления «лайк» (этап 7)
from models.user import User
from schemas.common import AuthorOut, build_author
from schemas.like import LikeStatusOut
from services.access import get_visible_post_or_404
from services.notifications import notify, remove_notifications  # этап 7

router = APIRouter(tags=["Likes"])


def count_likes(db: Session, post_id: int) -> int:
    """Сколько лайков у поста. SQL: SELECT COUNT(*) FROM likes WHERE post_id = ..."""
    return db.scalar(select(func.count()).select_from(Like).where(Like.post_id == post_id)) or 0


def find_my_like(db: Session, post_id: int, user: User) -> Like | None:
    """Строка «user лайкнул этот пост» или None."""
    return db.scalars(
        select(Like).where(Like.post_id == post_id, Like.user_id == user.id)
    ).first()


# ===========================================================================
# POST /posts/{post_id}/like — ЛАЙК
# ===========================================================================
@router.post("/posts/{post_id}/like", response_model=LikeStatusOut, summary="Поставить лайк")
def like_post(
    post_id: int,
    background_tasks: BackgroundTasks,   # FastAPI сам создаст и передаст список фоновых задач
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_visible_post_or_404(db, current_user, post_id)

    # Уже лайкнул? Тогда ничего не добавляем: повторный лайк не создаёт второй
    # (в базе ещё стоит UniqueConstraint — двойной лайк невозможен в принципе).
    if find_my_like(db, post.id, current_user) is None:
        db.add(Like(user_id=current_user.id, post_id=post.id))
        # Этап 7: «anna — нравится ваш пост» автору поста (себе не отправляется).
        notify(
            db, background_tasks,
            recipient_id=post.user_id, actor_id=current_user.id, type=NOTIF_LIKE, post_id=post.id,
        )
        db.commit()   # лайк и уведомление сохраняются вместе

    return LikeStatusOut(post_id=post.id, liked=True, likes_count=count_likes(db, post.id))


# ===========================================================================
# DELETE /posts/{post_id}/like — УБРАТЬ ЛАЙК
# ===========================================================================
@router.delete("/posts/{post_id}/like", response_model=LikeStatusOut, summary="Убрать лайк")
def unlike_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_visible_post_or_404(db, current_user, post_id)

    like = find_my_like(db, post.id, current_user)
    if like is not None:
        db.delete(like)
        # Этап 7: лайк убрали — уведомление о нём больше не актуально.
        remove_notifications(
            db, recipient_id=post.user_id, actor_id=current_user.id, type=NOTIF_LIKE, post_id=post.id,
        )
        db.commit()

    # Здесь отвечаем не 204, а данными: клиенту нужно новое число лайков.
    return LikeStatusOut(post_id=post.id, liked=False, likes_count=count_likes(db, post.id))


# ===========================================================================
# GET /posts/{post_id}/likes — КТО ЛАЙКНУЛ
# ===========================================================================
@router.get("/posts/{post_id}/likes", response_model=list[AuthorOut], summary="Кто лайкнул")
def list_likes(
    post_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_visible_post_or_404(db, current_user, post_id)

    # Новые лайки сверху, порциями.
    likes = db.scalars(
        select(Like)
        .where(Like.post_id == post.id)
        .order_by(Like.created_at.desc(), Like.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_author(like.user) for like in likes]
