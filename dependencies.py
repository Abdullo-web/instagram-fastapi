"""
dependencies.py — «КТО СЕЙЧАС ВОШЁЛ?» (ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ).

get_current_user — зависимость (dependency). Любой эндпоинт, которому нужен
вошедший пользователь, пишет в параметрах:
    current_user: User = Depends(get_current_user)
и FastAPI сам: достанет токен из заголовка → проверит → найдёт пользователя.
Если токена нет или он плохой — запрос остановится с ошибкой 401.
"""

# Из FastAPI:
#   Depends        — «внедрить зависимость» (вызвать функцию и передать результат)
#   HTTPException  — выбросить ошибку с HTTP-кодом и текстом
#   status         — набор понятных имён для кодов (status.HTTP_401_UNAUTHORIZED = 401)
from fastapi import Depends, HTTPException, status

# OAuth2PasswordBearer — из FastAPI. Умеет доставать токен из заголовка
# "Authorization: Bearer <токен>". А ещё благодаря ему в Swagger появляется
# кнопка Authorize (замок), где можно войти по логину и паролю.
from fastapi.security import OAuth2PasswordBearer

# Session — из SQLAlchemy ORM: тип сессии базы.
from sqlalchemy.orm import Session

# Наши: get_db (сессия базы), модель User, функция проверки токена.
from database import get_db
from models.user import User
from services.security import decode_token

# tokenUrl — адрес, куда Swagger отправит логин и пароль при нажатии Authorize.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),   # 1) достаём токен из заголовка
    db: Session = Depends(get_db),          # 2) получаем сессию базы
) -> User:
    """Возвращает пользователя, которому принадлежит access-токен."""

    # Одна ошибка на все случаи «пропуск плохой» — не подсказываем взломщику, что именно не так.
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный или просроченный токен",
        # Этот заголовок — стандарт: сообщает клиенту, что нужен Bearer-токен.
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 3) Проверяем подпись, срок и тип токена.
    payload = decode_token(token, expected_type="access")
    if payload is None:
        raise credentials_error

    # 4) В "sub" лежит id пользователя (строкой) → ищем его в базе.
    # db.get(Модель, id) — быстрый поиск строки по главному ключу.
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise credentials_error

    return user
