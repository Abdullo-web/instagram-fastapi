"""
routers/search.py — ЭТАП 8: ПОИСК.

Эндпоинты:
  GET /search/users?q=...   — найти людей по нику или имени
  GET /search/tags?q=...    — найти хештеги
  GET /tags/{tag}/posts     — посты с хештегом (только те, что мне можно видеть)

Аналогия: «человек ищет знакомых».

Как работает поиск: SQL-оператор LIKE с шаблоном.
  username LIKE 'iva%'   → ники, которые НАЧИНАЮТСЯ с «iva»   (% — «что угодно дальше»)
  full_name LIKE '%ив%'  → имена, где «ив» встречается ГДЕ УГОДНО
ilike — то же, но без учёта регистра букв.
(Учебное ограничение: SQLite не различает регистр только у ЛАТИНСКИХ букв,
 поэтому «иван» не найдёт «Иван» в имени. В PostgreSQL такой проблемы нет.)
"""

# Из FastAPI: APIRouter, Depends, HTTPException, Query, status.
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Из SQLAlchemy: func (count), or_ («ИЛИ»), select; Session.
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db
from dependencies import get_current_user
from models.post import Post
from models.profile import Profile
from models.tag import Tag, post_tags
from models.user import User
from routers.posts import build_post_out        # готовая сборка поста (из этапов 3, 5, 8)
from schemas.post import PostOut
from schemas.search import TagOut, UserSearchOut
from services.access import following_ids, get_follow
from services.files import file_url
from services.hashtags import escape_like

router = APIRouter(tags=["Search"])


# ===========================================================================
# GET /search/users — ПОИСК ЛЮДЕЙ
# ===========================================================================
@router.get("/search/users", response_model=list[UserSearchOut], summary="Найти людей")
def search_users(
    q: str = Query(..., min_length=1, max_length=50, description="Ник или имя, например: iva"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # «@ivan» и «ivan» — одно и то же; ники хранятся в нижнем регистре.
    text = q.strip().lstrip("@").lower()
    if not text:
        return []
    pattern = escape_like(text)   # защищаем «_» и «%» (см. services/hashtags.py)

    # Кандидаты: ник НАЧИНАЕТСЯ с текста ИЛИ имя СОДЕРЖИТ текст.
    # escape="\\" — говорим базе, что «\» в шаблоне означает «следующий символ обычный».
    candidates = db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(
                User.username.like(pattern + "%", escape="\\"),
                User.full_name.ilike("%" + pattern + "%", escape="\\"),
            ),
        )
        .limit(100)   # берём с запасом, потом отсортируем и обрежем до limit
    ).all()

    # Сортировка по «полезности» — как в Instagram, сначала самое нужное:
    #   0 — ник совпал полностью
    #   1 — я на него подписан
    #   2 — ник начинается с текста
    #   3 — совпало только имя
    # Внутри группы — по алфавиту. key возвращает пару (группа, ник): сравниваются по порядку.
    my_following = following_ids(db, current_user)

    def rank(user: User) -> tuple[int, str]:
        if user.username == text:
            group = 0
        elif user.id in my_following:
            group = 1
        elif user.username.startswith(text):
            group = 2
        else:
            group = 3
        return (group, user.username)

    result = []
    for user in sorted(candidates, key=rank)[:limit]:
        if user.id == current_user.id:
            follow_status = "self"
        else:
            follow = get_follow(db, current_user, user)
            follow_status = follow.status if follow else "none"
        result.append(
            UserSearchOut(
                username=user.username,
                full_name=user.full_name,
                avatar_url=file_url(user.profile.avatar),
                is_private=user.profile.is_private,
                follow_status=follow_status,
            )
        )
    return result


# ===========================================================================
# GET /search/tags — ПОИСК ХЕШТЕГОВ
# ===========================================================================
@router.get("/search/tags", response_model=list[TagOut], summary="Найти хештеги")
def search_tags(
    q: str = Query(..., min_length=1, max_length=50, description="Начало хештега, например: trav"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),   # искать могут только вошедшие
    db: Session = Depends(get_db),
):
    text = q.strip().lstrip("#").lower()
    if not text:
        return []

    # Новое на этом этапе: JOIN + GROUP BY.
    #   outerjoin  — присоединяем строки связки post_tags к каждому хештегу
    #                (outer — чтобы хештег без постов тоже попал, с числом 0);
    #   group_by   — «склеиваем» строки одного хештега в одну;
    #   func.count — считаем, сколько постов «склеилось».
    # SQL: SELECT tags.name, COUNT(post_tags.post_id) FROM tags
    #      LEFT JOIN post_tags ON ... WHERE tags.name LIKE 'trav%' GROUP BY tags.id
    posts_count = func.count(post_tags.c.post_id)
    rows = db.execute(
        select(Tag.name, posts_count)
        .outerjoin(post_tags, post_tags.c.tag_id == Tag.id)
        .where(Tag.name.like(escape_like(text) + "%", escape="\\"))
        .group_by(Tag.id)
        .order_by(posts_count.desc(), Tag.name)   # популярные сверху
        .limit(limit)
    ).all()
    # Счётчик учитывает все посты, в том числе закрытых аккаунтов (как в Instagram).
    return [TagOut(name=name, posts_count=count) for name, count in rows]


# ===========================================================================
# GET /tags/{tag}/posts — ПОСТЫ С ХЕШТЕГОМ
# ===========================================================================
@router.get("/tags/{tag}/posts", response_model=list[PostOut], summary="Посты по хештегу")
def tag_posts(
    tag: str,   # без «#»: /tags/travel/posts  (решётку в адресе писать нельзя — это «якорь»)
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    found = db.scalars(select(Tag).where(Tag.name == tag.strip().lstrip("#").lower())).first()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Хештег не найден")

    # Чьи закрытые посты мне можно видеть: мои и тех, на кого я подписан.
    allowed_private = following_ids(db, current_user) | {current_user.id}

    # Проверку доступа делаем прямо в SQL, чтобы пагинация (offset/limit) работала честно.
    # Соединяем пост → связку хештегов → автора → его профиль (там is_private).
    posts = db.scalars(
        select(Post)
        .join(post_tags, post_tags.c.post_id == Post.id)
        .join(User, User.id == Post.user_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            post_tags.c.tag_id == found.id,
            User.is_active.is_(True),
            # Открытый аккаунт ИЛИ автор в моём списке разрешённых.
            or_(Profile.is_private.is_(False), Post.user_id.in_(allowed_private)),
        )
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_post_out(db, post, viewer=current_user) for post in posts]
