"""
routers/posts.py — ЭТАП 3: ПОСТЫ.

Эндпоинты:
  POST   /posts                    — создать пост (1–10 фото + подпись)
  GET    /posts/{post_id}          — один пост
  PATCH  /posts/{post_id}          — изменить подпись (только автор)
  DELETE /posts/{post_id}          — удалить пост (только автор)
  GET    /profiles/{username}/posts — все посты человека (порциями)
  GET    /feed                     — лента: мои посты + посты тех, на кого я подписан (этап 4)
"""

# Из FastAPI:
#   APIRouter, Depends, HTTPException, status — как в прошлых этапах
#   File   — параметр-файл из формы
#   Form   — обычное текстовое поле из формы (подпись приходит вместе с файлами)
#   Query  — параметр из адреса после «?», например ?limit=10&offset=20
#   UploadFile — тип загруженного файла
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

# Из SQLAlchemy: select — запрос «выбрать»; func — функции SQL (func.count — «посчитать»);
# Session — тип сессии.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from config import MAX_CAPTION_LENGTH, MAX_POST_IMAGE_SIZE, MAX_POST_IMAGES
from database import get_db
from dependencies import get_current_user
from models.comment import Comment                       # этап 5: для счётчика комментариев
from models.like import Like                             # этап 5: для счётчика лайков
from models.post import Post, PostImage
from models.user import User
from schemas.common import build_author
from schemas.post import PostOut, PostUpdate
from services.access import can_view_content, following_ids  # «кто что видит», «на кого я подписан»
from services.files import delete_file, file_url, save_image
from services.hashtags import set_post_tags              # этап 8: хештеги из подписи

# Префикса нет: пути пишем полностью, потому что здесь есть и /posts/...,
# и /profiles/{username}/posts. tags=["Posts"] — группа в Swagger.
router = APIRouter(tags=["Posts"])


# ===========================================================================
# Вспомогательные функции
# ===========================================================================
def build_post_out(db: Session, post: Post, viewer: User) -> PostOut:
    """
    Пост из базы → ответ клиенту (PostOut).
    db нужна (с этапа 5), чтобы посчитать лайки и комментарии силами базы.
    """
    # SELECT COUNT(*) FROM likes WHERE post_id = ...
    likes_count = db.scalar(select(func.count()).select_from(Like).where(Like.post_id == post.id))
    # SELECT COUNT(*) FROM comments WHERE post_id = ...
    comments_count = db.scalar(
        select(func.count()).select_from(Comment).where(Comment.post_id == post.id)
    )
    # Есть ли строка «я лайкнул этот пост»? .first() вернёт id или None.
    liked_by_me = db.scalars(
        select(Like.id).where(Like.post_id == post.id, Like.user_id == viewer.id)
    ).first() is not None

    return PostOut(
        id=post.id,
        author=build_author(post.author),
        caption=post.caption,
        images=[file_url(image.path) for image in post.images],  # список адресов по порядку
        created_at=post.created_at,
        updated_at=post.updated_at,
        is_mine=post.user_id == viewer.id,
        likes_count=likes_count or 0,
        comments_count=comments_count or 0,
        liked_by_me=liked_by_me,
        tags=[tag.name for tag in post.tags],   # этап 8: хештеги поста
    )


def get_post_or_404(db: Session, post_id: int) -> Post:
    """Найти пост по id или сразу вернуть клиенту ошибку 404."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пост не найден")
    return post


# ===========================================================================
# POST /posts — СОЗДАТЬ ПОСТ
# ===========================================================================
@router.post(
    "/posts",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пост",
)
def create_post(
    # list[UploadFile] — несколько файлов сразу. В Swagger можно добавить
    # несколько полей «Choose File» кнопкой «Add string item».
    files: list[UploadFile] = File(..., description="От 1 до 10 фото (JPEG, PNG, WEBP)"),
    # Form("") — текстовое поле формы, по умолчанию пустая подпись.
    caption: str = Form("", max_length=MAX_CAPTION_LENGTH),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(files) > MAX_POST_IMAGES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"В посте может быть не больше {MAX_POST_IMAGES} фото"
        )

    # 1. Сохраняем файлы. Если 3-й файл окажется плохим, первые два уже лежат
    #    на диске — их нужно удалить, иначе останется «мусор». Для этого try/except.
    saved_paths: list[str] = []
    try:
        for upload in files:
            saved_paths.append(save_image(upload, subfolder="posts", max_size=MAX_POST_IMAGE_SIZE))
    except HTTPException:
        for path in saved_paths:
            delete_file(path)
        raise  # raise без аргумента — «пробросить ту же ошибку дальше» клиенту

    # 2. Создаём пост и строки фото. enumerate даёт пары (номер, значение): (0, путь), (1, путь)...
    post = Post(user_id=current_user.id, caption=caption.strip())
    post.images = [PostImage(path=path, position=index) for index, path in enumerate(saved_paths)]

    # 3. Этап 8: хештеги из подписи (#travel #горы) → таблицы tags и post_tags.
    set_post_tags(db, post)

    db.add(post)
    db.commit()
    db.refresh(post)
    return build_post_out(db, post, viewer=current_user)


# ===========================================================================
# GET /posts/{post_id} — ОДИН ПОСТ
# ===========================================================================
@router.get("/posts/{post_id}", response_model=PostOut, summary="Посмотреть пост")
def get_post(
    post_id: int,   # FastAPI сам проверит, что в адресе число (иначе 422)
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_post_or_404(db, post_id)

    # Пост закрытого аккаунта (если я не подписчик) отвечаем как «не найден» —
    # не раскрываем, что он есть.
    if not can_view_content(db, current_user, post.author):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пост не найден")
    return build_post_out(db, post, viewer=current_user)


# ===========================================================================
# PATCH /posts/{post_id} — ИЗМЕНИТЬ ПОДПИСЬ
# ===========================================================================
@router.patch("/posts/{post_id}", response_model=PostOut, summary="Изменить подпись")
def update_post(
    post_id: int,
    data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_post_or_404(db, post_id)

    # Только автор. 403 = «вы вошли, но вам сюда нельзя».
    if post.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Изменять пост может только автор")

    post.caption = data.caption.strip()
    set_post_tags(db, post)   # этап 8: подпись изменилась → хештеги пересчитываем
    db.commit()        # здесь сработает onupdate=utc_now и заполнится updated_at
    db.refresh(post)
    return build_post_out(db, post, viewer=current_user)


# ===========================================================================
# DELETE /posts/{post_id} — УДАЛИТЬ ПОСТ
# ===========================================================================
@router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,   # 204 = «готово, в ответе ничего нет»
    summary="Удалить пост",
)
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_post_or_404(db, post_id)
    if post.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Удалять пост может только автор")

    # Запоминаем пути файлов ДО удаления из базы.
    paths = [image.path for image in post.images]

    db.delete(post)    # cascade удалит и строки post_images
    db.commit()

    # Файлы удаляем после того, как база успешно сохранила изменения.
    for path in paths:
        delete_file(path)
    # Ничего не возвращаем: код 204 означает пустой ответ.


# ===========================================================================
# GET /profiles/{username}/posts — ПОСТЫ ЧЕЛОВЕКА
# ===========================================================================
@router.get(
    "/profiles/{username}/posts",
    response_model=list[PostOut],
    summary="Посты пользователя",
)
def list_user_posts(
    username: str,
    # Пагинация (отдаём порциями):
    #   limit  — сколько постов вернуть (от 1 до 50, по умолчанию 10)
    #   offset — сколько пропустить с начала (0 = первая страница, 10 = вторая ...)
    # ge = «больше или равно», le = «меньше или равно».
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = db.scalars(select(User).where(User.username == username.lower())).first()
    if owner is None or not owner.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    # Закрытый аккаунт: профиль виден, а посты — только подписчикам. 403 + объяснение.
    if not can_view_content(db, current_user, owner):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Это закрытый аккаунт. Подпишитесь, чтобы видеть посты"
        )

    posts = db.scalars(
        select(Post)
        .where(Post.user_id == owner.id)
        .order_by(Post.created_at.desc(), Post.id.desc())  # от новых к старым
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_post_out(db, post, viewer=current_user) for post in posts]


# ===========================================================================
# GET /feed — ЛЕНТА (этап 4)
# ===========================================================================
@router.get("/feed", response_model=list[PostOut], summary="Лента постов")
def feed(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Мои посты + посты людей, на которых я подписан (подписка принята).
    От новых к старым, порциями. Отдельная проверка приватности не нужна:
    принятая подписка уже означает «мне можно видеть».
    """
    # Множество id авторов: те, на кого я подписан, и я сам (| — объединение множеств).
    author_ids = following_ids(db, current_user) | {current_user.id}

    posts = db.scalars(
        select(Post)
        .where(Post.user_id.in_(author_ids))           # автор входит в список
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [build_post_out(db, post, viewer=current_user) for post in posts]
