"""
routers/follows.py — ЭТАП 4: ПОДПИСКИ (follow).

Эндпоинты:
  POST   /users/{username}/follow       — подписаться (на закрытый аккаунт — отправить запрос)
  DELETE /users/{username}/follow       — отписаться (или отменить свой запрос)
  DELETE /users/{username}/follower     — убрать человека из СВОИХ подписчиков
  GET    /users/{username}/followers    — подписчики человека
  GET    /users/{username}/following    — на кого человек подписан
  GET    /follow-requests               — входящие запросы (для закрытого аккаунта)
  POST   /follow-requests/{id}/accept   — принять запрос
  POST   /follow-requests/{id}/decline  — отклонить запрос

Схема (см. учебник, этап 4):
  подписаться → аккаунт закрытый? нет → подписка сразу ("accepted")
                                  да  → запрос ("pending") → владелец принял / отклонил

Этап 7 — уведомления:
  подписка на открытый аккаунт → ему «anna — новый подписчик»
  запрос к закрытому аккаунту  → ему «anna хочет подписаться на вас»
  запрос принят                → подписчику «ivan принимает ваш запрос на подписку»
  отписка / отмена / отклонение → соответствующие уведомления удаляются
"""

# Из FastAPI (объяснения в прошлых роутерах);
# BackgroundTasks — «сделать после ответа» (отправка уведомлений, этап 7).
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

# Из SQLAlchemy: select — «выбрать»; Session — тип сессии.
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db
from dependencies import get_current_user
from models.follow import FOLLOW_ACCEPTED, FOLLOW_PENDING, Follow
from models.notification import (                       # типы уведомлений (этап 7)
    NOTIF_FOLLOW,
    NOTIF_FOLLOW_ACCEPTED,
    NOTIF_FOLLOW_REQUEST,
)
from models.user import User
from schemas.common import AuthorOut, build_author
from schemas.follow import FollowRequestOut, FollowStatusOut
from services.access import can_view_content, get_follow
from services.notifications import notify, remove_notifications  # этап 7

# Префикса нет: здесь пути и /users/..., и /follow-requests/...
router = APIRouter(tags=["Follows"])


# ===========================================================================
# Вспомогательные функции
# ===========================================================================
def get_user_or_404(db: Session, username: str) -> User:
    """Найти активного пользователя по нику или вернуть 404."""
    user = db.scalars(select(User).where(User.username == username.lower())).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return user


def get_my_request_or_404(db: Session, request_id: int, me: User) -> Follow:
    """
    Найти ВХОДЯЩИЙ запрос (pending), адресованный мне.
    Чужой запрос или уже принятый — для меня «не найден».
    """
    follow = db.get(Follow, request_id)
    if follow is None or follow.following_id != me.id or follow.status != FOLLOW_PENDING:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запрос не найден")
    return follow


# ===========================================================================
# POST /users/{username}/follow — ПОДПИСАТЬСЯ
# ===========================================================================
@router.post("/users/{username}/follow", response_model=FollowStatusOut, summary="Подписаться")
def follow_user(
    username: str,
    background_tasks: BackgroundTasks,   # этап 7: для отправки уведомления после ответа
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = get_user_or_404(db, username)

    # Нельзя подписаться на себя (то же правило стоит и в базе — CheckConstraint).
    if target.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя подписаться на себя")

    # Уже подписан или запрос уже отправлен — просто сообщаем текущий статус.
    # Повторное нажатие «Подписаться» ничего не ломает.
    existing = get_follow(db, current_user, target)
    if existing is not None:
        return FollowStatusOut(username=target.username, status=existing.status)

    # Закрытый аккаунт → запрос ждёт ответа. Открытый → подписка сразу.
    new_status = FOLLOW_PENDING if target.profile.is_private else FOLLOW_ACCEPTED
    db.add(Follow(follower_id=current_user.id, following_id=target.id, status=new_status))

    # Этап 7: «новый подписчик» или «хочет подписаться» — в зависимости от статуса.
    notify(
        db, background_tasks,
        recipient_id=target.id, actor_id=current_user.id,
        type=NOTIF_FOLLOW_REQUEST if new_status == FOLLOW_PENDING else NOTIF_FOLLOW,
    )
    db.commit()
    return FollowStatusOut(username=target.username, status=new_status)


# ===========================================================================
# DELETE /users/{username}/follow — ОТПИСАТЬСЯ / ОТМЕНИТЬ ЗАПРОС
# ===========================================================================
@router.delete(
    "/users/{username}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отписаться или отменить запрос",
)
def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = get_user_or_404(db, username)
    follow = get_follow(db, current_user, target)
    # Не был подписан — результат тот же («не подписан»), поэтому тоже 204.
    if follow is not None:
        db.delete(follow)
        # Этап 7: убираем у него «новый подписчик» / «хочет подписаться».
        for notif_type in (NOTIF_FOLLOW, NOTIF_FOLLOW_REQUEST):
            remove_notifications(db, recipient_id=target.id, actor_id=current_user.id, type=notif_type)
        db.commit()


# ===========================================================================
# DELETE /users/{username}/follower — УБРАТЬ ПОДПИСЧИКА
# ===========================================================================
@router.delete(
    "/users/{username}/follower",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Убрать человека из моих подписчиков",
)
def remove_follower(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обратное действие: не я отписываюсь, а ОН перестаёт быть моим подписчиком."""
    follower = get_user_or_404(db, username)
    follow = get_follow(db, follower, current_user)   # «он → я»
    if follow is not None:
        db.delete(follow)
        # Этап 7: у меня больше нет уведомления «он — новый подписчик».
        remove_notifications(db, recipient_id=current_user.id, actor_id=follower.id, type=NOTIF_FOLLOW)
        db.commit()


# ===========================================================================
# GET /users/{username}/followers и /following — СПИСКИ
# ===========================================================================
def _list_people(
    db: Session, viewer: User, owner: User, column, other_column, limit: int, offset: int
) -> list[AuthorOut]:
    """
    Общая логика двух списков (подчёркивание _ = «внутренняя функция»).
      column       — по какой колонке ищем владельца
      other_column — из какой колонки берём «других людей»
    Для подписчиков: ищем following_id == owner, берём follower_id.
    Для подписок:    ищем follower_id  == owner, берём following_id.
    """
    # Закрытый аккаунт: списки видят только его подписчики (как в Instagram).
    if not can_view_content(db, viewer, owner):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это закрытый аккаунт")

    # Только принятые подписки; новые сверху; порциями.
    people_ids = db.scalars(
        select(other_column)
        .where(column == owner.id, Follow.status == FOLLOW_ACCEPTED)
        .order_by(Follow.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    # db.get для каждого id и карточка «ник + аватар».
    return [build_author(db.get(User, person_id)) for person_id in people_ids]


@router.get("/users/{username}/followers", response_model=list[AuthorOut], summary="Подписчики")
def list_followers(
    username: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = get_user_or_404(db, username)
    return _list_people(db, current_user, owner, Follow.following_id, Follow.follower_id, limit, offset)


@router.get("/users/{username}/following", response_model=list[AuthorOut], summary="Подписки")
def list_following(
    username: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = get_user_or_404(db, username)
    return _list_people(db, current_user, owner, Follow.follower_id, Follow.following_id, limit, offset)


# ===========================================================================
# ЗАПРОСЫ НА ПОДПИСКУ (для закрытого аккаунта)
# ===========================================================================
@router.get("/follow-requests", response_model=list[FollowRequestOut], summary="Входящие запросы")
def list_follow_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requests = db.scalars(
        select(Follow)
        .where(Follow.following_id == current_user.id, Follow.status == FOLLOW_PENDING)
        .order_by(Follow.created_at.desc())
    ).all()
    return [
        FollowRequestOut(id=r.id, user=build_author(r.follower), created_at=r.created_at)
        for r in requests
    ]


@router.post("/follow-requests/{request_id}/accept", response_model=FollowStatusOut, summary="Принять запрос")
def accept_follow_request(
    request_id: int,
    background_tasks: BackgroundTasks,   # этап 7
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follow = get_my_request_or_404(db, request_id, current_user)
    follow.status = FOLLOW_ACCEPTED   # «рукопожатие состоялось»

    # Этап 7: запрос обработан — уведомление «хочет подписаться» у меня убираем,
    # а подписчику сообщаем «ivan принимает ваш запрос на подписку».
    remove_notifications(
        db, recipient_id=current_user.id, actor_id=follow.follower_id, type=NOTIF_FOLLOW_REQUEST
    )
    notify(
        db, background_tasks,
        recipient_id=follow.follower_id, actor_id=current_user.id, type=NOTIF_FOLLOW_ACCEPTED,
    )
    db.commit()
    # В ответе — кто теперь мой подписчик.
    return FollowStatusOut(username=follow.follower.username, status=FOLLOW_ACCEPTED)


@router.post(
    "/follow-requests/{request_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отклонить запрос",
)
def decline_follow_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follow = get_my_request_or_404(db, request_id, current_user)
    db.delete(follow)   # запрос просто удаляется; человек сможет отправить новый
    # Этап 7: уведомление «хочет подписаться» больше не нужно.
    remove_notifications(
        db, recipient_id=current_user.id, actor_id=follow.follower_id, type=NOTIF_FOLLOW_REQUEST
    )
    db.commit()
