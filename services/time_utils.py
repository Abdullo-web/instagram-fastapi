"""
services/time_utils.py — РАБОТА СО ВРЕМЕНЕМ.

Одна маленькая функция utc_now(), которую используют все остальные файлы.
Зачем отдельно: SQLite не хранит часовой пояс. Если сравнивать время
«с поясом» и «без пояса», Python выдаст ошибку. Поэтому везде в проекте
мы храним и сравниваем время в UTC БЕЗ указания пояса — одинаково.
"""

# datetime — класс «дата + время», timezone — часовые пояса.
# Оба из стандартного модуля datetime (встроен в Python).
from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Возвращает текущее время в UTC (мировое время) без информации о поясе.

    datetime.now(timezone.utc) — «сейчас» по UTC (с поясом),
    .replace(tzinfo=None)      — убираем пояс, чтобы совпадало с тем, что хранит SQLite.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
