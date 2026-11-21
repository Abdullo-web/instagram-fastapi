"""
services/hashtags.py — ХЕШТЕГИ: НАЙТИ В ТЕКСТЕ И ПРИВЯЗАТЬ К ПОСТУ.

Функции:
  extract_hashtags(text)       — вынуть хештеги из подписи: "Горы #Travel #горы" → ["travel", "горы"]
  set_post_tags(db, post)      — сохранить хештеги подписи в базу и привязать к посту
  escape_like(text)            — защитить текст для поиска через LIKE (используется в routers/search.py)

Вызывается из routers/posts.py: при создании поста и при изменении подписи.
"""

# re — стандартная библиотека Python для регулярных выражений (поиск по шаблону).
import re

# Из SQLAlchemy: select; Session.
from sqlalchemy import select
from sqlalchemy.orm import Session

# Наши: настройки, модели поста и хештега.
from config import MAX_TAG_LENGTH, MAX_TAGS_PER_POST
from models.post import Post
from models.tag import Tag

# Шаблон хештега:  #  и за ним одна или больше «букв слова».
#   \w  — буква (любого алфавита, в том числе русская), цифра или «_»
#   +   — один или больше раз
#   ( ) — «запомнить» то, что внутри (само слово без решётки)
# re.compile — заранее «собрать» шаблон, чтобы не делать это при каждом вызове.
HASHTAG_PATTERN = re.compile(r"#(\w+)")


def extract_hashtags(text: str) -> list[str]:
    """
    Найти все хештеги в тексте.
      - приводим к нижнему регистру: #Travel и #travel — один хештег;
      - убираем повторы, сохраняя порядок;
      - слишком длинные пропускаем, всего берём не больше MAX_TAGS_PER_POST.
    """
    result: list[str] = []
    # findall возвращает список всего, что попало в скобки ( ) шаблона.
    for word in HASHTAG_PATTERN.findall(text):
        tag = word.lower()
        if len(tag) <= MAX_TAG_LENGTH and tag not in result:
            result.append(tag)
        if len(result) >= MAX_TAGS_PER_POST:
            break
    return result


def set_post_tags(db: Session, post: Post) -> None:
    """
    Привязать к посту хештеги из его подписи (старые связи заменяются).
    Хештега ещё нет в таблице tags → создаём. Есть → используем существующий.
    Без commit — его делает эндпоинт вместе с сохранением поста.
    """
    tags: list[Tag] = []
    for name in extract_hashtags(post.caption):
        tag = db.scalars(select(Tag).where(Tag.name == name)).first()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)

    # Просто присваиваем список — SQLAlchemy сам добавит и удалит строки в post_tags.
    post.tags = tags


def escape_like(text: str) -> str:
    """
    Защита поиска через LIKE.
    В LIKE символы % («что угодно») и _ («один любой символ») — особые.
    А «_» часто бывает в никах (ivan_p)! Без защиты поиск «ivan_» нашёл бы и «ivanX».
    Ставим перед ними «\\» — тогда они ищутся как обычные символы.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
