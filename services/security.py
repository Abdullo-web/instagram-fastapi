"""
services/security.py — БЕЗОПАСНОСТЬ: ХЕШ ПАРОЛЕЙ И JWT-ТОКЕНЫ.

Функции:
  hash_password(password)          — сделать «отпечаток» пароля для хранения в базе
  verify_password(password, hash)  — проверить, подходит ли пароль к отпечатку
  create_access_token(user_id)     — выдать короткий пропуск (access)
  create_refresh_token(user_id)    — выдать длинный пропуск (refresh) + его номер jti
  decode_token(token, type)        — прочитать и проверить токен
"""

# Из стандартного модуля datetime:
#   datetime  — дата и время (момент, когда токен истечёт)
#   timedelta — «промежуток времени» (например, 30 минут)
#   timezone  — часовой пояс (нужен timezone.utc)
from datetime import datetime, timedelta, timezone

# uuid — стандартная библиотека Python. uuid4() делает случайный уникальный номер.
# Используем его как jti — номер refresh-токена.
import uuid

# bcrypt — установленный пакет (pip install bcrypt). Делает надёжный хеш пароля.
import bcrypt

# jwt — это пакет PyJWT (pip install pyjwt). Создаёт и проверяет JWT-токены.
import jwt

# Настройки из нашего config.py.
from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)


# ===========================================================================
# ПАРОЛИ
# ===========================================================================
def hash_password(password: str) -> str:
    """
    Превращает пароль в хеш.

    bcrypt.gensalt() — случайная «соль». Из-за неё одинаковые пароли
    у двух людей дают РАЗНЫЕ хеши, и их нельзя сравнить между собой.
    .encode() — строка → байты (bcrypt работает с байтами),
    .decode() — байты → строка (чтобы сохранить в базу как текст).
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Проверяет пароль при входе.
    bcrypt.checkpw сам достаёт соль из хеша, хеширует введённый пароль
    и сравнивает отпечатки. Возвращает True (подходит) или False.
    """
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


# ===========================================================================
# ТОКЕНЫ
# ===========================================================================
def _create_token(user_id: int, token_type: str, expires_delta: timedelta, jti: str | None = None) -> str:
    """
    Общая функция создания токена (подчёркивание _ в имени = «внутренняя», для этого файла).

    Внутри токена лежит словарь payload («полезная нагрузка»):
      sub  — subject, «чей токен» (id пользователя, обязательно строкой)
      type — "access" или "refresh", чтобы нельзя было подсунуть один вместо другого
      exp  — expiration, когда токен перестанет действовать
      jti  — номер токена (только у refresh)
    jwt.encode подписывает этот словарь секретным ключом SECRET_KEY.
    Прочитать содержимое может кто угодно, но ПОДДЕЛАТЬ без ключа — нельзя.
    """
    payload = {
        "sub": str(user_id),
        "type": token_type,
        # Для токена берём время с часовым поясом UTC — так требует PyJWT.
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    """Короткий пропуск: живёт ACCESS_TOKEN_EXPIRE_MINUTES минут (из config.py)."""
    return _create_token(user_id, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: int) -> tuple[str, str, timedelta]:
    """
    Длинный пропуск: живёт REFRESH_TOKEN_EXPIRE_DAYS дней.
    Возвращает ТРИ значения: сам токен, его номер jti и срок жизни.
    jti и срок мы сохраним в таблицу refresh_tokens (см. models/token.py),
    чтобы потом можно было сделать logout.
    """
    jti = uuid.uuid4().hex  # .hex — номер в виде строки из 32 символов
    lifetime = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token = _create_token(user_id, "refresh", lifetime, jti=jti)
    return token, jti, lifetime


def decode_token(token: str, expected_type: str) -> dict | None:
    """
    Читает и проверяет токен. Возвращает payload (словарь) или None, если токен плохой.

    jwt.decode сам проверяет:
      - подпись (токен не подделан);
      - срок exp (токен не истёк).
    Если что-то не так, он выбрасывает ошибку jwt.InvalidTokenError — ловим её.
    Затем проверяем тип: на месте access-токена refresh не принимаем и наоборот.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
