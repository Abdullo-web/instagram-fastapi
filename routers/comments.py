"""
routers/comments.py — ЭТАП 5: КОММЕНТАРИИ И ОТВЕТЫ.

Эндпоинты:
  POST   /posts/{post_id}/comments    — написать комментарий (или ответ, если есть parent_id)
  GET    /posts/{post_id}/comments    — верхние комментарии поста (без ответов)
  GET    /comments/{comment_id}/replies — ответы на комментарий
  DELETE /comments/{comment_id}       — удалить (автор комментария ИЛИ автор поста)

Как устроены ответы (как в Instagram, один уровень):
  комментарий №5 (parent_id = None)
    ├── ответ №6 (parent_id = 5)
    └── ответ на ответ №6 → тоже получит parent_id = 5 (прикрепляем к верхнему)

Этап 7 — уведомления при новом комментарии:
  автору поста                       → «anna комментирует ваш пост: …»
  автору комментария, на который ответ → «anna отвечает на ваш комментарий: …»
  (если это один и тот же человек — одно уведомление «ответ», а не два)
При удалении комментария база сама удалит уведомления о нём (ondelete="CASCADE").
"""

# Из FastAPI: APIRouter, Depends, HTTPException, Query, status;
# BackgroundTasks — «сделать после ответа» (отправка уведомлений, этап 7).
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

# Из SQLAlchemy: func (func.count), select; Session — тип сессии.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db
from dependencies import get_current_user
from models.comment import Comment
from models.notification import NOTIF_COMMENT, NOTIF_REPLY   # типы уведомлений (этап 7)
from models.user import User
from schemas.comment import CommentCreate, CommentOut
from schemas.common import build_author
from services.access import can_view_content, get_visible_post_or_404
from services.notifications import notify                    # этап 7

router = APIRouter(tags=["Comments"])


# ===========================================================================
# Вспомогательные функции
# ===========================================================================
def build_comment_out(db: Session, comment: Comment, viewer: User) -> CommentOut:
    """Комментарий из базы → ответ клиенту."""
    replies_count = db.scalar(
        select(func.count()).select_from(Comment).where(Comment.parent_id == comment.id)
    )
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author=build_author(comment.author),
        text=comment.text,
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        replies_count=replies_count or 0,
        # Удалить может автор комментария или автор поста (хозяин «своей территории»).
        can_delete=viewer.id in (comment.user_id, comment.post.user_id),
    )


# ===========================================================================
# POST /posts/{post_id}/comments — НАПИСАТЬ КОММЕНТАРИЙ
# ===========================================================================
@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Написать комментарий или ответ",
)
def create_comment(
    post_id: int,
    data: CommentCreate,
    background_tasks: BackgroundTasks,   # этап 7: для отправки уведомлений после ответа
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_visible_post_or_404(db, current_user, post_id)

    parent_id = None
    parent = None
    if data.parent_id is not None:
        parent = db.get(Comment, data.parent_id)
        # Отвечать можно только на комментарий ЭТОГО ЖЕ поста.
        if parent is None or parent.post_id != post.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Комментарий для ответа не найден")
        # Ответ на ответ → прикрепляем к верхнему комментарию (один уровень).
        parent_id = parent.parent_id if parent.parent_id is not None else parent.id

    comment = Comment(post_id=post.id, user_id=current_user.id, parent_id=parent_id, text=data.text)
    db.add(comment)
    db.flush()   # flush — получить comment.id до commit (нужен для уведомления)

    # ---- Этап 7: уведомления ----
    reply_to_user_id = None
    if parent is not None:
        # Отвечаем на конкретный комментарий → уведомляем его автора.
        reply_to_user_id = parent.user_id
        notify(
            db, background_tasks,
            recipient_id=parent.user_id, actor_id=current_user.id, type=NOTIF_REPLY,
            post_id=post.id, comment_id=comment.id,
        )
    if post.user_id != reply_to_user_id:
        # Автору поста — «комментирует ваш пост» (если он не получил уже «ответ»).
        notify(
            db, background_tasks,
            recipient_id=post.user_id, actor_id=current_user.id, type=NOTIF_COMMENT,
            post_id=post.id, comment_id=comment.id,
        )

    db.commit()   # комментарий и уведомления сохраняются вместе
    db.refresh(comment)
    return build_comment_out(db, comment, current_user)


# ===========================================================================
# GET /posts/{post_id}/comments — КОММЕНТАРИИ ПОСТА
# ===========================================================================
@router.get("/posts/{post_id}/comments", response_model=list[CommentOut], summary="Комментарии поста")
def list_comments(
    post_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_visible_post_or_404(db, current_user, post_id)

    # Только ВЕРХНИЕ комментарии (parent_id IS NULL), от старых к новым — как переписка.
    # Ответы загружаются отдельно: GET /comments/{id}/replies.
    comments = db.scalars(
        select(Comment)
        .where(Comment.post_id == post.id, Comment.parent_id.is_(None))
        .order_by(Comment.created_at, Comment.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_comment_out(db, c, current_user) for c in comments]


# ===========================================================================
# GET /comments/{comment_id}/replies — ОТВЕТЫ НА КОММЕНТАРИЙ
# ===========================================================================
@router.get("/comments/{comment_id}/replies", response_model=list[CommentOut], summary="Ответы на комментарий")
def list_replies(
    comment_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parent = db.get(Comment, comment_id)
    # Комментарий к посту, который мне нельзя видеть, — тоже «не найден».
    if parent is None or not can_view_content(db, current_user, parent.post.author):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Комментарий не найден")

    replies = db.scalars(
        select(Comment)
        .where(Comment.parent_id == parent.id)
        .order_by(Comment.created_at, Comment.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_comment_out(db, r, current_user) for r in replies]


# ===========================================================================
# DELETE /comments/{comment_id} — УДАЛИТЬ КОММЕНТАРИЙ
# ===========================================================================
@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить комментарий",
)
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(Comment, comment_id)
    if comment is None or not can_view_content(db, current_user, comment.post.author):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Комментарий не найден")

    # Удалить может автор комментария или автор поста.
    if current_user.id not in (comment.user_id, comment.post.user_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Удалить комментарий может только его автор или автор поста",
        )

    db.delete(comment)   # cascade удалит и все ответы на него
    db.commit()
