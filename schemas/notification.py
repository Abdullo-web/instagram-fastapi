"""
schemas/notification.py — СХЕМЫ УВЕДОМЛЕНИЙ (Pydantic).

NotificationOut — одно уведомление (строка в списке «Действия»).
UnreadCountOut  — сколько непрочитанных (число на красной точке).
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Из Pydantic: BaseModel.
from pydantic import BaseModel

# Наша карточка автора.
from schemas.common import AuthorOut


class NotificationOut(BaseModel):
    id: int
    type: str                       # like / comment / reply / follow / follow_request / follow_accepted
    actor: AuthorOut                # кто сделал действие
    text: str                       # готовый текст для показа: «anna — нравится ваш пост»
    post_id: int | None             # куда перейти по нажатию
    post_image_url: str | None      # маленькая картинка поста справа (как в Instagram)
    comment_id: int | None
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
