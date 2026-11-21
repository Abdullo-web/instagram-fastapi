"""
routers/stories.py — ЭТАП 3: ИСТОРИИ (живут 24 часа).

Эндпоинты:
  POST   /stories                — выложить историю (одна картинка)
  GET    /stories/feed           — активные истории, сгруппированные по людям
  POST   /stories/{id}/view      — отметить «я посмотрел»
  GET    /stories/{id}/viewers   — кто посмотрел (только автор)
  DELETE /stories/{id}           — удалить историю (только автор)
"""

# timedelta — из стандартного datetime: «+24 часа».
from datetime import timedelta

# Из FastAPI (объяснения в routers/posts.py).
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

# Из SQLAlchemy: select — «выбрать»; Session — тип сессии.
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from config import MAX_POST_IMAGE_SIZE, STORY_LIFETIME_HOURS
from database import get_db
from dependencies import get_current_user
from models.story import Story, StoryView
from models.user import User
from schemas.common import build_author
from schemas.story import StoryOut, StoryViewerOut, UserStoriesOut
from services.access import can_view_content, following_ids  # «кто что видит», «на кого я подписан»
from services.files import delete_file, file_url, save_image
from services.time_utils import utc_now

router = APIRouter(prefix="/stories", tags=["Stories"])


# ===========================================================================
# Вспомогательные функции
# ===========================================================================
def get_active_story_or_404(db: Session, story_id: int) -> Story:
    """История по id. Просроченная считается несуществующей → 404."""
    story = db.get(Story, story_id)
    if story is None or story.expires_at <= utc_now():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "История не найдена или уже исчезла")
    return story


def seen_story_ids(db: Session, viewer: User, story_ids: list[int]) -> set[int]:
    """
    Какие из этих историй viewer уже смотрел. Возвращает множество (set) id.
    in_(...) — SQL-условие «значение входит в список».
    """
    if not story_ids:
        return set()
    rows = db.scalars(
        select(StoryView.story_id).where(
            StoryView.viewer_id == viewer.id, StoryView.story_id.in_(story_ids)
        )
    ).all()
    return set(rows)


# ===========================================================================
# POST /stories — ВЫЛОЖИТЬ ИСТОРИЮ
# ===========================================================================
@router.post("", response_model=StoryOut, status_code=status.HTTP_201_CREATED, summary="Выложить историю")
def create_story(
    file: UploadFile = File(..., description="Картинка JPEG, PNG или WEBP"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # (Видео-истории — отдельная большая тема, в учебной версии только картинки.)
    path = save_image(file, subfolder="stories", max_size=MAX_POST_IMAGE_SIZE)

    now = utc_now()
    story = Story(
        user_id=current_user.id,
        media=path,
        created_at=now,
        expires_at=now + timedelta(hours=STORY_LIFETIME_HOURS),  # «исчезнет через 24 часа»
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return StoryOut(
        id=story.id,
        media_url=file_url(story.media),
        created_at=story.created_at,
        expires_at=story.expires_at,
        seen=True,  # свою историю считаем просмотренной
    )


# ===========================================================================
# GET /stories/feed — ЛЕНТА ИСТОРИЙ
# ===========================================================================
@router.get("/feed", response_model=list[UserStoriesOut], summary="Лента историй")
def stories_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    АКТИВНЫЕ истории — мои и тех, на кого я подписан, — сгруппированные по авторам.
    Порядок: сначала мои, потом те, где есть непросмотренные, потом остальные.
    """
    # 1. Чьи истории показываем: мои подписки (принятые) + я сам.
    author_ids = following_ids(db, current_user) | {current_user.id}

    # 2. Активные истории (expires_at в будущем) этих авторов, от старых к новым.
    stories = db.scalars(
        select(Story)
        .where(Story.user_id.in_(author_ids), Story.expires_at > utc_now())
        .order_by(Story.created_at)
    ).all()
    # Заблокированные аккаунты не показываем.
    stories = [s for s in stories if s.author.is_active]

    # 3. Какие из них я уже смотрел.
    seen = seen_story_ids(db, current_user, [s.id for s in stories])

    # 4. Группируем по автору: словарь {id автора: [истории]}.
    #    dict сохраняет порядок добавления ключей.
    grouped: dict[int, list[Story]] = {}
    for story in stories:
        grouped.setdefault(story.user_id, []).append(story)

    result: list[UserStoriesOut] = []
    for author_id, author_stories in grouped.items():
        items = [
            StoryOut(
                id=s.id,
                media_url=file_url(s.media),
                created_at=s.created_at,
                expires_at=s.expires_at,
                seen=s.user_id == current_user.id or s.id in seen,
            )
            for s in author_stories
        ]
        result.append(
            UserStoriesOut(
                author=build_author(author_stories[0].author),
                stories=items,
                all_seen=all(item.seen for item in items),  # all — «все ли True»
            )
        )

    # 5. Сортировка: мои первые (0), затем с новыми историями (1), затем просмотренные (2).
    #    sort(key=...) сортирует по числу, которое вернула функция.
    def order(group: UserStoriesOut) -> int:
        if group.author.username == current_user.username:
            return 0
        return 2 if group.all_seen else 1

    result.sort(key=order)
    return result


# ===========================================================================
# POST /stories/{story_id}/view — Я ПОСМОТРЕЛ
# ===========================================================================
@router.post("/{story_id}/view", status_code=status.HTTP_204_NO_CONTENT, summary="Отметить просмотр")
def view_story(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    story = get_active_story_or_404(db, story_id)
    if not can_view_content(db, current_user, story.author):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "История не найдена или уже исчезла")

    # Свои просмотры не записываем.
    if story.user_id == current_user.id:
        return

    # Уже смотрел? Тогда ничего не делаем (повторный просмотр не создаёт новую строку).
    already = db.scalars(
        select(StoryView).where(
            StoryView.story_id == story.id, StoryView.viewer_id == current_user.id
        )
    ).first()
    if already is None:
        db.add(StoryView(story_id=story.id, viewer_id=current_user.id))
        db.commit()


# ===========================================================================
# GET /stories/{story_id}/viewers — КТО ПОСМОТРЕЛ
# ===========================================================================
@router.get("/{story_id}/viewers", response_model=list[StoryViewerOut], summary="Кто посмотрел")
def story_viewers(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    story = get_active_story_or_404(db, story_id)
    if story.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Список просмотров видит только автор")

    # Сортируем: кто посмотрел последним — тот первый.
    views = sorted(story.views, key=lambda v: v.viewed_at, reverse=True)
    return [StoryViewerOut(viewer=build_author(v.viewer), viewed_at=v.viewed_at) for v in views]


# ===========================================================================
# DELETE /stories/{story_id} — УДАЛИТЬ ИСТОРИЮ
# ===========================================================================
@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить историю")
def delete_story(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    story = db.get(Story, story_id)  # удалить можно и просроченную
    if story is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "История не найдена")
    if story.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Удалять историю может только автор")

    path = story.media
    db.delete(story)   # cascade удалит и просмотры
    db.commit()
    delete_file(path)
