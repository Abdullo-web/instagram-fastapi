"""
services/access.py — КТО ЧТО МОЖЕТ ВИДЕТЬ (с учётом подписок, этап 4).

Здесь собраны все правила доступа. Их используют посты, истории, заметки,
лента и профиль. Правило меняется в одном месте и сразу работает везде.

Функции:
  get_follow(db, follower, following)  — строка подписки «follower → following» или None
  is_following(db, viewer, owner)      — подписан ли viewer на owner (и подписку приняли)
  can_view_content(db, viewer, owner)  — может ли viewer видеть посты/истории owner
  following_ids(db, user)              — id всех, на кого user подписан (принятые подписки)
  get_visible_post_or_404(db, viewer, post_id) — пост, который viewer можно видеть (этап 5)
"""

# Из FastAPI: HTTPException — ошибка с кодом; status — имена кодов.
from fastapi import HTTPException, status

# Из SQLAlchemy: select — запрос «выбрать»; Session — тип сессии.
from sqlalchemy import select
from sqlalchemy.orm import Session

# Наши модели: подписка (и её статус «принята»), пост и пользователь.
from models.follow import FOLLOW_ACCEPTED, Follow
from models.post import Post
from models.user import User


def get_follow(db: Session, follower: User, following: User) -> Follow | None:
    """Ищет строку «follower подписан на following» (любого статуса)."""
    return db.scalars(
        select(Follow).where(
            Follow.follower_id == follower.id,
            Follow.following_id == following.id,
        )
    ).first()


def is_following(db: Session, viewer: User, owner: User) -> bool:
    """True, если viewer подписан на owner и подписка ПРИНЯТА (не «ждёт ответа»)."""
    follow = get_follow(db, viewer, owner)
    return follow is not None and follow.status == FOLLOW_ACCEPTED


def can_view_content(db: Session, viewer: User, owner: User) -> bool:
    """
    True — viewer может видеть посты, истории и заметки owner.

    Правила:
      1. Свои материалы видно всегда.
      2. Заблокированный аккаунт не видно никому.
      3. Публичный аккаунт видят все вошедшие.
      4. Закрытый аккаунт видят только принятые подписчики.   ← новое на этапе 4
    """
    if viewer.id == owner.id:
        return True
    if not owner.is_active:
        return False
    if not owner.profile.is_private:
        return True
    return is_following(db, viewer, owner)


def following_ids(db: Session, user: User) -> set[int]:
    """
    Множество (set) id людей, на которых user подписан (только принятые подписки).
    Нужно лентам: «покажи посты/истории/заметки тех, на кого я подписан».
    set — потому что порядок не важен, а проверка «id in set» очень быстрая.
    """
    rows = db.scalars(
        select(Follow.following_id).where(
            Follow.follower_id == user.id,
            Follow.status == FOLLOW_ACCEPTED,
        )
    ).all()
    return set(rows)


def get_visible_post_or_404(db: Session, viewer: User, post_id: int) -> Post:
    """
    Этап 5. Найти пост, который viewer МОЖНО видеть, иначе ошибка 404.

    Нужна лайкам и комментариям: лайкнуть или прокомментировать можно
    только тот пост, который ты видишь. Пост закрытого аккаунта для
    не-подписчика — «не найден» (не раскрываем, что он существует).
    """
    post = db.get(Post, post_id)
    if post is None or not can_view_content(db, viewer, post.author):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пост не найден")
    return post
