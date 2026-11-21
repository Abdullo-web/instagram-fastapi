"""
main.py — ТОЧКА ВХОДА ПРИЛОЖЕНИЯ.

Что делает:
  1. Создаёт приложение FastAPI (app).
  2. При запуске создаёт таблицы в базе (если их ещё нет).
  3. Подключает роутеры (группы эндпоинтов) из папки routers/.

Запуск (из папки проекта):
  .venv/bin/fastapi dev main.py
Потом открыть в браузере: http://127.0.0.1:8000/docs  ← Swagger
"""

# asynccontextmanager — из стандартного модуля contextlib.
# Помогает описать, что делать ПРИ ЗАПУСКЕ и ПРИ ОСТАНОВКЕ приложения (lifespan).
from contextlib import asynccontextmanager

# pathlib.Path — из стандартной библиотеки: работа с папками (создать media/).
from pathlib import Path

# FastAPI — главный класс фреймворка (pip install "fastapi[standard]").
from fastapi import FastAPI

# StaticFiles — из FastAPI. Раздаёт файлы из папки как обычные адреса в браузере:
# файл media/avatars/ab.jpg будет доступен по http://127.0.0.1:8000/media/avatars/ab.jpg
from fastapi.staticfiles import StaticFiles

# FileResponse — из FastAPI: ответить содержимым файла (нашей тестовой HTML-страницей чата).
from fastapi.responses import FileResponse

# Наши файлы:
from config import MEDIA_DIR, MEDIA_URL  # папка с файлами и её адрес (этап 2)
from database import Base, engine     # Base знает все таблицы, engine — подключение к базе
import models                          # импорт пакета models/ регистрирует ВСЕ таблицы в Base
from routers import auth               # эндпоинты этапа 1: регистрация, вход, выход
from routers import profiles           # эндпоинты этапа 2: профиль
from routers import posts, stories, notes  # эндпоинты этапа 3: посты, истории, заметки
from routers import follows                # эндпоинты этапа 4: подписки
from routers import likes, comments        # эндпоинты этапа 5: лайки и комментарии
from routers import chat                   # эндпоинты этапа 6: чат (HTTP + WebSocket)
from routers import notifications          # эндпоинты этапа 7: уведомления
from routers import search                 # эндпоинты этапа 8: поиск


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Код ДО yield выполняется при запуске сервера, ПОСЛЕ yield — при остановке.
    create_all создаёт таблицы, которых ещё нет в базе (существующие не трогает).
    """
    Base.metadata.create_all(bind=engine)
    yield


# Само приложение. title и description видны вверху страницы Swagger.
app = FastAPI(
    title="Учебный Instagram API",
    description=(
        "Учебный проект на FastAPI.\n\n"
        "Этап 1: регистрация, подтверждение, вход, выход.\n\n"
        "Этап 2: профиль и аватар.\n\n"
        "Этап 3: посты, истории, заметки.\n\n"
        "Этап 4: подписки и лента.\n\n"
        "Этап 5: лайки и комментарии.\n\n"
        "Этап 6: чат. WebSocket проверяется на странице /chat-test\n\n"
        "Этап 7: уведомления (приходят и по WebSocket).\n\n"
        "Этап 8: поиск людей и хештегов."
    ),
    version="0.8.0",
    lifespan=lifespan,
)

# Подключаем роутеры: все эндпоинты из этих файлов появятся в приложении.
app.include_router(auth.router)       # /auth/...
app.include_router(profiles.router)   # /profiles/...
app.include_router(posts.router)      # /posts/... и /profiles/{username}/posts
app.include_router(stories.router)    # /stories/...
app.include_router(notes.router)      # /notes/...
app.include_router(follows.router)    # /users/{username}/follow... и /follow-requests/...
app.include_router(likes.router)      # /posts/{post_id}/like и /likes
app.include_router(comments.router)   # /posts/{post_id}/comments и /comments/...
app.include_router(chat.router)       # /chats/... и WebSocket /ws/chat
app.include_router(notifications.router)  # /notifications/...
app.include_router(search.router)     # /search/... и /tags/{tag}/posts

# Папку media/ создаём сразу (StaticFiles требует, чтобы папка уже существовала).
Path(MEDIA_DIR).mkdir(exist_ok=True)

# mount — «прикрепить» к адресу /media раздачу файлов из папки media/.
# name="media" — внутреннее имя этого подключения.
app.mount(MEDIA_URL, StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/", tags=["Start"], summary="Проверка, что сервер работает")
def root():
    """Простой ответ, чтобы убедиться, что сервер запущен."""
    return {"message": "Сервер работает. Документация: /docs"}


# Путь к папке static/ рядом с этим файлом. Path(__file__) — путь к самому main.py,
# .parent — его папка. Так страница найдётся, откуда бы ни запускали сервер.
STATIC_DIR = Path(__file__).parent / "static"


# include_in_schema=False — не показывать в Swagger (это не API, а страница).
@app.get("/chat-test", include_in_schema=False)
def chat_test_page():
    """Этап 6: тестовая страница для проверки WebSocket-чата в браузере."""
    return FileResponse(STATIC_DIR / "chat-test.html")
