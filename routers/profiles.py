"""
routers/profiles.py — ЭТАП 2: ПРОФИЛЬ.

Эндпоинты:
  GET    /profiles/me          — мой профиль
  PATCH  /profiles/me          — изменить имя, bio, сайт, приватность
  POST   /profiles/me/avatar   — загрузить аватар (файл)
  DELETE /profiles/me/avatar   — удалить аватар
  GET    /profiles/{username}  — посмотреть чужой профиль

Профиль НЕ создаётся здесь: он появился автоматически при регистрации
(см. routers/auth.py, функция register, строка `user.profile = Profile()`).
"""

# Из FastAPI:
#   APIRouter     — группа эндпоинтов с префиксом /profiles
#   Depends       — внедрение зависимостей
#   File          — «этот параметр — файл из формы»
#   HTTPException — ошибка с кодом
#   UploadFile    — тип загруженного файла
#   status        — имена HTTP-кодов
#   BackgroundTasks — «сделать после ответа» (уведомления, этап 7)
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

# Из SQLAlchemy: select — запрос «выбрать»; func — функции SQL (func.count = «посчитать»);
# Session — тип сессии базы.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from config import MAX_AVATAR_SIZE                         # лимит размера аватара
from database import get_db                                # сессия базы
from dependencies import get_current_user                  # кто вошёл (этап 1)
from models.follow import FOLLOW_ACCEPTED, FOLLOW_PENDING, Follow  # таблица follows (этап 4)
from models.notification import NOTIF_FOLLOW_ACCEPTED, NOTIF_FOLLOW_REQUEST  # типы уведомлений (этап 7)
from models.post import Post                               # таблица posts (этап 3, для счётчика)
from models.user import User                               # таблица users
from schemas.profile import ProfileOut, ProfileUpdate      # схемы профиля
from services.access import get_follow                     # строка подписки (этап 4)
from services.files import delete_file, file_url, save_image  # работа с файлами
from services.notifications import notify, remove_notifications  # уведомления (этап 7)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# ===========================================================================
# Вспомогательная функция: собрать «визитку» из двух таблиц
# ===========================================================================
def build_profile_out(db: Session, user: User, viewer: User | None = None) -> ProfileOut:
    """
    db     — сессия базы (нужна, чтобы посчитать посты);
    user   — чей профиль показываем;
    viewer — кто смотрит (нужно, чтобы понять, свой ли это профиль).
    user.profile — связь из models/user.py: SQLAlchemy сам достанет строку из profiles.
    """
    profile = user.profile

    # Этап 3: настоящее число постов. SQL: SELECT COUNT(*) FROM posts WHERE user_id = ...
    # Считает сама база — это быстрее, чем загружать все посты и считать их в Python.
    posts_count = db.scalar(select(func.count()).select_from(Post).where(Post.user_id == user.id))

    # Этап 4: подписчики = принятые подписки «кто-то → user»,
    #         подписки   = принятые подписки «user → кто-то».
    followers_count = db.scalar(
        select(func.count()).select_from(Follow).where(
            Follow.following_id == user.id, Follow.status == FOLLOW_ACCEPTED
        )
    )
    following_count = db.scalar(
        select(func.count()).select_from(Follow).where(
            Follow.follower_id == user.id, Follow.status == FOLLOW_ACCEPTED
        )
    )

    # Этап 4: отношения между тем, кто смотрит (viewer), и владельцем профиля (user).
    is_me = viewer is not None and viewer.id == user.id
    follow_status = "none"
    follows_you = False
    if viewer is not None and not is_me:
        my_follow = get_follow(db, viewer, user)          # я → он
        if my_follow is not None:
            follow_status = my_follow.status               # "accepted" или "pending"
        their_follow = get_follow(db, user, viewer)       # он → я
        follows_you = their_follow is not None and their_follow.status == FOLLOW_ACCEPTED

    return ProfileOut(
        username=user.username,
        full_name=user.full_name,
        bio=profile.bio,
        avatar_url=file_url(profile.avatar),   # путь из базы → адрес /media/...
        website=profile.website,
        is_private=profile.is_private,
        posts_count=posts_count or 0,
        followers_count=followers_count or 0,
        following_count=following_count or 0,
        is_me=is_me,
        follow_status=follow_status,
        follows_you=follows_you,
    )


# ===========================================================================
# GET /profiles/me — МОЙ ПРОФИЛЬ
# ===========================================================================
@router.get("/me", response_model=ProfileOut, summary="Мой профиль")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),   # этап 3: нужна, чтобы посчитать посты
):
    # Depends(get_current_user) — без токена сюда не попасть (401).
    return build_profile_out(db, current_user, viewer=current_user)


# ===========================================================================
# PATCH /profiles/me — ИЗМЕНИТЬ ПРОФИЛЬ
# ===========================================================================
@router.patch("/me", response_model=ProfileOut, summary="Изменить мой профиль")
def update_my_profile(
    data: ProfileUpdate,
    background_tasks: BackgroundTasks,   # этап 7: уведомления при автопринятии запросов
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # model_dump(exclude_unset=True) — словарь ТОЛЬКО из тех полей, которые клиент
    # реально прислал. Например {"bio": "Привет"} → меняем только bio.
    changes = data.model_dump(exclude_unset=True)

    # full_name хранится в таблице users, остальное — в profiles.
    if "full_name" in changes:
        current_user.full_name = changes.pop("full_name")

    # setattr(объект, "имя_поля", значение) — то же, что profile.bio = значение,
    # но имя поля берётся из переменной. Так обновляем все оставшиеся поля циклом.
    was_private = current_user.profile.is_private

    for field_name, value in changes.items():
        if field_name == "bio" and value is None:
            value = ""  # bio в базе не может быть пустым (None), только пустой строкой
        if field_name == "is_private" and value is None:
            continue    # прислали null — значит «не менять»
        setattr(current_user.profile, field_name, value)

    # Этап 4: аккаунт был закрытым и стал открытым → все ожидающие запросы
    # принимаются автоматически (как в Instagram): у каждого статус pending → accepted.
    if was_private and not current_user.profile.is_private:
        for request in db.scalars(
            select(Follow).where(
                Follow.following_id == current_user.id, Follow.status == FOLLOW_PENDING
            )
        ).all():
            request.status = FOLLOW_ACCEPTED
            # Этап 7: как при ручном принятии — убрать «хочет подписаться» и сообщить подписчику.
            remove_notifications(
                db, recipient_id=current_user.id, actor_id=request.follower_id, type=NOTIF_FOLLOW_REQUEST
            )
            notify(
                db, background_tasks,
                recipient_id=request.follower_id, actor_id=current_user.id, type=NOTIF_FOLLOW_ACCEPTED,
            )

    db.commit()
    return build_profile_out(db, current_user, viewer=current_user)


# ===========================================================================
# POST /profiles/me/avatar — ЗАГРУЗИТЬ АВАТАР
# ===========================================================================
@router.post("/me/avatar", response_model=ProfileOut, summary="Загрузить аватар")
def upload_avatar(
    # File(...) — файл обязателен. В Swagger появится кнопка «Choose File».
    # Файлы приходят формой (multipart/form-data), для этого нужен python-multipart.
    file: UploadFile = File(..., description="Картинка JPEG, PNG или WEBP до 5 МБ"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = current_user.profile

    # 1. Проверяем и сохраняем новый файл (вся логика в services/files.py).
    new_path = save_image(file, subfolder="avatars", max_size=MAX_AVATAR_SIZE)

    # 2. Запоминаем старый путь, записываем новый в базу.
    old_path = profile.avatar
    profile.avatar = new_path
    db.commit()

    # 3. Только ПОСЛЕ успешного сохранения в базу удаляем старый файл с диска.
    delete_file(old_path)

    return build_profile_out(db, current_user, viewer=current_user)


# ===========================================================================
# DELETE /profiles/me/avatar — УДАЛИТЬ АВАТАР
# ===========================================================================
@router.delete("/me/avatar", response_model=ProfileOut, summary="Удалить аватар")
def remove_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = current_user.profile
    old_path = profile.avatar
    profile.avatar = None
    db.commit()
    delete_file(old_path)
    return build_profile_out(db, current_user, viewer=current_user)


# ===========================================================================
# GET /profiles/{username} — ЧУЖОЙ ПРОФИЛЬ
# ===========================================================================
# ВАЖНО: этот эндпоинт объявлен ПОСЛЕ /me. FastAPI проверяет пути сверху вниз,
# и если бы {username} стоял выше, запрос /profiles/me считался бы
# профилем пользователя с ником «me».
@router.get("/{username}", response_model=ProfileOut, summary="Профиль пользователя")
def get_profile(
    username: str,                                   # берётся из адреса: /profiles/ivan_p
    current_user: User = Depends(get_current_user),  # смотреть профили могут только вошедшие
    db: Session = Depends(get_db),
):
    user = db.scalars(select(User).where(User.username == username.lower())).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    # Визитку (имя, аватар, bio) видно даже у приватного аккаунта — как в Instagram.
    # Скрываться будут ПОСТЫ и ИСТОРИИ — это сделаем на этапах 3 и 4.
    return build_profile_out(db, user, viewer=current_user)
