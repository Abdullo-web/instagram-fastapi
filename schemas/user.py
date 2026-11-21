"""
schemas/user.py — СХЕМЫ ДАННЫХ ПОЛЬЗОВАТЕЛЯ (Pydantic).

Аналогия: «бланк у окошка». Схема говорит, какие поля должны прийти
и какими они должны быть. Если данные неправильные, FastAPI сам вернёт
ошибку 422 ещё ДО того, как выполнится наш код.

UserCreate — что присылает клиент при регистрации (с паролем).
UserOut    — что сервер отдаёт обратно (БЕЗ пароля, никогда!).
"""

# datetime — из стандартного модуля datetime: тип поля created_at.
from datetime import datetime

# Из Pydantic (устанавливается вместе с FastAPI):
#   BaseModel       — родитель всех схем
#   ConfigDict      — настройки схемы
#   EmailStr        — тип «правильный email» (нужен pip install pydantic[email])
#   Field           — правила для поля (мин./макс. длина, шаблон, описание)
#   field_validator — своя проверка поля (функция-проверяльщик)
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Данные для регистрации: POST /auth/register."""

    # username: 3–30 символов, только латиница, цифры, "_" и ".".
    # pattern — регулярное выражение (шаблон):
    #   ^ и $        — начало и конец строки
    #   [a-zA-Z0-9_.] — разрешённые символы
    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_.]+$",
        description="Ник: латиница, цифры, _ и .",
        examples=["ivan_petrov"],
    )

    # EmailStr сам проверит, что это похоже на email (есть @, домен и т.д.).
    email: EmailStr = Field(examples=["ivan@example.com"])

    # Пароль от 8 до 72 символов (72 — предел алгоритма bcrypt).
    password: str = Field(min_length=8, max_length=72, examples=["supersecret123"])

    # Телефон необязательный (None = не указан). Формат: + и 10–15 цифр.
    phone: str | None = Field(
        default=None, pattern=r"^\+?\d{10,15}$", examples=["+992900000000"]
    )

    # Имя и фамилия, необязательно.
    full_name: str | None = Field(default=None, max_length=100, examples=["Иван Петров"])

    # @field_validator — наша дополнительная проверка/обработка поля.
    # mode="after" — выполняется ПОСЛЕ стандартных проверок.
    @field_validator("username", "email", mode="after")
    @classmethod
    def to_lower(cls, value: str) -> str:
        """Приводим username и email к нижнему регистру: Ivan и ivan — один и тот же."""
        return value.lower()


class UserOut(BaseModel):
    """То, что сервер ОТДАЁТ о пользователе. Пароля здесь нет специально."""

    # from_attributes=True — разрешает создавать схему прямо из объекта модели
    # SQLAlchemy (user.id, user.username ...), а не только из словаря.
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    phone: str | None
    full_name: str | None
    is_verified: bool
    created_at: datetime
