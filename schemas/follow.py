"""
schemas/follow.py — СХЕМЫ ПОДПИСОК (Pydantic).

FollowStatusOut  — ответ на «подписаться»: подписка сразу принята или ждёт ответа.
FollowRequestOut — один входящий запрос на подписку (для закрытого аккаунта).
"""

# datetime — из стандартного модуля datetime.
from datetime import datetime

# Literal — из стандартного typing: «только одно из перечисленных значений».
from typing import Literal

# Из Pydantic: BaseModel.
from pydantic import BaseModel

# Наша карточка автора (ник + аватар).
from schemas.common import AuthorOut


class FollowStatusOut(BaseModel):
    username: str                              # на кого подписались
    status: Literal["accepted", "pending"]     # принята сразу или ждёт ответа


class FollowRequestOut(BaseModel):
    id: int                 # номер запроса — его передаём в /accept или /decline
    user: AuthorOut         # кто хочет подписаться
    created_at: datetime
