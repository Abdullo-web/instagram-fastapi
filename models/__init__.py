"""
models/ — МОДЕЛИ (ТАБЛИЦЫ БАЗЫ ДАННЫХ).

Этот файл импортирует все модели в одном месте. Зачем:
в main.py мы вызываем Base.metadata.create_all(...) — «создай все таблицы».
SQLAlchemy создаёт только те таблицы, классы которых уже были импортированы.
Импортируя здесь все модели, мы гарантируем, что ни одна таблица не забыта.
"""

# Наши модели из файлов этой же папки (точка в начале = «из этой папки»).
# ---- Этап 1 ----
from .user import User                          # таблица users
from .verification import VerificationCode      # таблица verification_codes
from .token import RefreshToken                 # таблица refresh_tokens
# ---- Этап 2 ----
from .profile import Profile                    # таблица profiles
# ---- Этап 3 ----
from .post import Post, PostImage               # таблицы posts и post_images
from .story import Story, StoryView             # таблицы stories и story_views
from .note import Note                          # таблица notes
# ---- Этап 4 ----
from .follow import Follow                      # таблица follows
# ---- Этап 5 ----
from .like import Like                          # таблица likes
from .comment import Comment                    # таблица comments
# ---- Этап 6 ----
from .message import Conversation, ConversationParticipant, Message  # таблицы чата
# ---- Этап 7 ----
from .notification import Notification          # таблица notifications
# ---- Этап 8 ----
from .tag import Tag, post_tags                 # таблицы tags и post_tags (хештеги)

# __all__ — список того, что «экспортирует» пакет (для порядка и подсказок редактора).
__all__ = [
    "User", "VerificationCode", "RefreshToken",
    "Profile",
    "Post", "PostImage", "Story", "StoryView", "Note",
    "Follow",
    "Like", "Comment",
    "Conversation", "ConversationParticipant", "Message",
    "Notification",
    "Tag", "post_tags",
]
