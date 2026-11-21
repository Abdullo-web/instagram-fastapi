"""
schemas/auth.py — СХЕМЫ ДЛЯ ВХОДА, ТОКЕНОВ И КОДОВ ПОДТВЕРЖДЕНИЯ (Pydantic).
"""

# Literal — из стандартного typing: «только одно из перечисленных значений».
from typing import Literal

# Из Pydantic: BaseModel — родитель схем, Field — правила для поля.
from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    """Ответ на успешный вход: два токена."""

    access_token: str     # короткий пропуск — прикладывать к каждому запросу
    refresh_token: str    # длинный пропуск — чтобы получить новый access
    # token_type="bearer" — стандартное слово. Заголовок запроса выглядит так:
    # Authorization: Bearer <access_token>
    token_type: str = "bearer"


class AccessToken(BaseModel):
    """Ответ на продление: только новый access-токен."""

    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Тело запроса для /auth/refresh и /auth/logout."""

    refresh_token: str


class VerifyRequest(BaseModel):
    """Тело запроса для /auth/verify: кто вы и какой код пришёл."""

    # login — username ИЛИ email.
    login: str = Field(examples=["ivan_petrov"])

    # Ровно 6 цифр: \d{6}.
    code: str = Field(pattern=r"^\d{6}$", examples=["123456"])


class ResendCodeRequest(BaseModel):
    """Тело запроса для /auth/resend-code."""

    login: str = Field(examples=["ivan_petrov"])

    # Куда отправить: только "email" или "sms". По умолчанию email.
    channel: Literal["email", "sms"] = "email"


class Message(BaseModel):
    """Простой ответ с текстом, например {"detail": "Вы вышли"}."""

    detail: str
