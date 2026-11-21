"""
database.py — ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ.

Что здесь есть:
  engine        — «двигатель»: само подключение к файлу базы instagram.db
  SessionLocal  — «фабрика сессий»: каждая сессия = один разговор с базой
  Base          — родительский класс для всех моделей (таблиц) из папки models/
  get_db()      — функция-зависимость: выдаёт сессию в эндпоинт и закрывает её после
"""

# Generator — из стандартного модуля typing (встроен в Python).
# Нужен только для подсказки типа: get_db() «выдаёт» значение через yield.
from typing import Generator

# create_engine — из SQLAlchemy (pip install sqlalchemy). Создаёт подключение к базе.
# event — из SQLAlchemy: «подписаться на событие» (например, «открылось соединение»).
from sqlalchemy import create_engine, event

# DeclarativeBase — из SQLAlchemy. От него наследуем Base, а от Base — все модели.
# sessionmaker  — из SQLAlchemy. Создаёт «фабрику», которая делает сессии.
# Session       — из SQLAlchemy. Тип сессии (для подсказки типа).
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# DATABASE_URL — из нашего файла config.py: адрес базы данных.
from config import DATABASE_URL

# ---------------------------------------------------------------------------
# engine — подключение к базе.
# connect_args={"check_same_thread": False} нужен только для SQLite:
# FastAPI может обработать запрос в другом потоке, и без этой настройки
# SQLite выдал бы ошибку «объект создан в другом потоке».
# ---------------------------------------------------------------------------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# ---------------------------------------------------------------------------
# Этап 7: включаем в SQLite проверку внешних ключей (ForeignKey).
# Особенность SQLite: по умолчанию он НЕ следит за ForeignKey и не выполняет
# ondelete="CASCADE". Команда PRAGMA foreign_keys=ON включает это.
# Нужна, например, чтобы при удалении поста база сама удалила уведомления о нём.
# @event.listens_for(engine, "connect") — эта функция вызывается
# автоматически каждый раз, когда открывается новое соединение с базой.
# ---------------------------------------------------------------------------
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    # dbapi_connection — само «сырое» соединение SQLite.
    # connection_record — SQLAlchemy передаёт его всегда; нам он не нужен.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# ---------------------------------------------------------------------------
# SessionLocal — фабрика сессий.
# autoflush=False — не отправлять изменения в базу автоматически, только по commit().
# autocommit по умолчанию выключен: изменения сохраняются, только когда
# мы сами вызовем db.commit(). Так мы управляем сохранением сами.
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """
    Родитель всех моделей.
    Каждый класс-модель (User, Profile, ...) наследуется от Base,
    и SQLAlchemy так узнаёт: «это таблица в базе данных».
    """
    pass


def get_db() -> Generator[Session, None, None]:
    """
    Зависимость (dependency) для FastAPI.

    Как работает:
      1. Перед выполнением эндпоинта создаётся новая сессия db.
      2. `yield db` — сессия отдаётся в эндпоинт (там пишем `db: Session = Depends(get_db)`).
      3. Когда эндпоинт закончил (даже с ошибкой), выполняется `finally`
         и сессия закрывается. Так соединения с базой не «утекают».
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
