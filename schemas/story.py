"""
schemas/story.py — СХЕМЫ ИСТОРИЙ (Pydantic).

StoryOut       — одна история.
UserStoriesOut — все активные истории ОДНОГО человека (так их показывает лента:
                 кружок с аватаром → внутри несколько историй по очереди).
StoryViewerOut — один человек из списка «кто посмотрел».
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel.
from pydantic import BaseModel

# Наша карточка автора.
from schemas.common import AuthorOut


class StoryOut(BaseModel):
    id: int
    media_url: str           # адрес картинки истории
    created_at: datetime
    expires_at: datetime     # когда исчезнет
    seen: bool               # смотрел ли я её уже (для серого/цветного кружка)


class UserStoriesOut(BaseModel):
    author: AuthorOut
    stories: list[StoryOut]  # от старых к новым — в таком порядке их и смотрят
    all_seen: bool           # все ли истории этого человека я уже посмотрел


class StoryViewerOut(BaseModel):
    viewer: AuthorOut
    viewed_at: datetime
