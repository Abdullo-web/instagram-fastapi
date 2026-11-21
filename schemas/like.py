"""
schemas/like.py — СХЕМА ОТВЕТА НА ЛАЙК (Pydantic).

После «лайкнуть» или «убрать лайк» клиенту нужно знать две вещи:
закрашено ли сердечко (liked) и какое число показать рядом (likes_count).
"""

# Из Pydantic: BaseModel.
from pydantic import BaseModel


class LikeStatusOut(BaseModel):
    post_id: int
    liked: bool          # True — я лайкнул (сердечко красное)
    likes_count: int     # сколько лайков у поста сейчас
