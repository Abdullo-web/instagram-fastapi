"""
services/verification.py — КОДЫ ПОДТВЕРЖДЕНИЯ (EMAIL / SMS).

Функции:
  send_verification_code(db, user, channel) — создать код и «отправить»
  check_verification_code(db, user, code)   — проверить введённый код

В УЧЕБНОЙ версии «отправка» = печать кода в консоль (терминал, где запущен сервер).
Настоящие SMS платные (Twilio и подобные), email требует почтового сервера.
Позже вместо print() можно подключить реальную отправку — менять нужно только здесь.
"""

# timedelta — промежуток времени. Из стандартного модуля datetime.
from datetime import timedelta

# secrets — стандартная библиотека Python для БЕЗОПАСНЫХ случайных чисел.
# (Модуль random для кодов не подходит: его числа можно предсказать.)
import secrets

# select — из SQLAlchemy: построение запроса «выбрать строки из таблицы».
from sqlalchemy import select

# Session — из SQLAlchemy ORM: тип сессии базы (для подсказки типа).
from sqlalchemy.orm import Session

# Наши настройки, модели и функция времени.
from config import VERIFICATION_CODE_EXPIRE_MINUTES, VERIFICATION_MAX_ATTEMPTS
from models.user import User
from models.verification import VerificationCode
from services.time_utils import utc_now


def send_verification_code(db: Session, user: User, channel: str = "email") -> None:
    """
    Создаёт новый код и «отправляет» его.

    Шаги:
      1. Старые неиспользованные коды этого пользователя помечаем использованными —
         действует только самый последний код.
      2. Генерируем 6 случайных цифр.
      3. Сохраняем код в таблицу verification_codes со сроком жизни.
      4. Печатаем в консоль (учебная «отправка»).
    """
    # 1. Находим старые активные коды пользователя.
    old_codes = db.scalars(
        select(VerificationCode).where(
            VerificationCode.user_id == user.id,
            VerificationCode.is_used.is_(False),
        )
    ).all()
    for old in old_codes:
        old.is_used = True

    # 2. secrets.randbelow(1_000_000) — случайное число от 0 до 999999.
    #    f"{...:06d}" — дополняем нулями слева до 6 цифр: 4215 → "004215".
    code = f"{secrets.randbelow(1_000_000):06d}"

    # 3. Сохраняем.
    db.add(
        VerificationCode(
            user_id=user.id,
            code=code,
            channel=channel,
            expires_at=utc_now() + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES),
        )
    )
    db.commit()

    # 4. Учебная «отправка».
    destination = user.phone if channel == "sms" else user.email
    print(
        f"\n=== [{channel.upper()}] код подтверждения для {destination}: {code} "
        f"(действует {VERIFICATION_CODE_EXPIRE_MINUTES} мин.) ===\n"
    )


def check_verification_code(db: Session, user: User, code: str) -> str | None:
    """
    Проверяет код. Возвращает None, если всё хорошо,
    или ТЕКСТ ОШИБКИ, если что-то не так (роутер покажет его клиенту).
    """
    # Берём последний активный код пользователя.
    # order_by(...desc()) — сортировка «от новых к старым», .first() — первый.
    active = db.scalars(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.is_used.is_(False),
        )
        .order_by(VerificationCode.created_at.desc())
    ).first()

    if active is None:
        return "Нет активного кода. Запросите новый через /auth/resend-code"

    if active.expires_at < utc_now():
        active.is_used = True
        db.commit()
        return "Срок действия кода истёк. Запросите новый"

    if active.code != code:
        active.attempts += 1
        # Слишком много ошибок → код «сгорает» (защита от перебора).
        if active.attempts >= VERIFICATION_MAX_ATTEMPTS:
            active.is_used = True
            db.commit()
            return "Слишком много попыток. Запросите новый код"
        db.commit()
        left = VERIFICATION_MAX_ATTEMPTS - active.attempts
        return f"Неверный код. Осталось попыток: {left}"

    # Код верный: помечаем использованным и подтверждаем пользователя.
    active.is_used = True
    user.is_verified = True
    db.commit()
    return None
