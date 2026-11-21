"""
routers/auth.py — ЭТАП 1: РЕГИСТРАЦИЯ, ПОДТВЕРЖДЕНИЕ, ВХОД, ВЫХОД.

Эндпоинты:
  POST /auth/register     — регистрация (+ автоматически создаётся профиль, + код)
  POST /auth/verify       — ввод кода подтверждения
  POST /auth/resend-code  — отправить код ещё раз
  POST /auth/login        — вход, выдаёт access- и refresh-токены
  POST /auth/refresh      — новый access-токен по refresh-токену
  POST /auth/logout       — выход (refresh-токен отзывается)
  GET  /auth/me           — «кто я?» (нужен access-токен)

Цепочка любого запроса здесь:
  клиент → этот роутер → схема (schemas/) → логика (services/) → модель (models/) → база
"""

# Из FastAPI:
#   APIRouter     — «группа эндпоинтов» с общим префиксом /auth
#   Depends       — внедрение зависимостей (база, текущий пользователь, форма логина)
#   HTTPException — вернуть ошибку с кодом
#   status        — имена HTTP-кодов
from fastapi import APIRouter, Depends, HTTPException, status

# OAuth2PasswordRequestForm — из FastAPI. Форма логина с полями username и password.
# Используем её, чтобы вход работал и через кнопку Authorize в Swagger.
from fastapi.security import OAuth2PasswordRequestForm

# Из SQLAlchemy: select — запрос «выбрать», or_ — условие «ИЛИ».
from sqlalchemy import or_, select

# Session — тип сессии базы.
from sqlalchemy.orm import Session

# ---- Наши файлы ----
from database import get_db                                   # сессия базы
from dependencies import get_current_user                     # кто вошёл
from models.profile import Profile                            # таблица profiles
from models.token import RefreshToken                         # таблица refresh_tokens
from models.user import User                                  # таблица users
from schemas.auth import (                                    # схемы входа/токенов/кодов
    AccessToken,
    Message,
    RefreshRequest,
    ResendCodeRequest,
    TokenPair,
    VerifyRequest,
)
from schemas.user import UserCreate, UserOut                  # схемы пользователя
from services.security import (                               # пароли и токены
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from services.time_utils import utc_now                       # текущее время
from services.verification import (                           # коды подтверждения
    check_verification_code,
    send_verification_code,
)

# prefix="/auth" — все пути ниже начинаются с /auth.
# tags=["Auth"] — в Swagger эти эндпоинты будут собраны в группу «Auth».
router = APIRouter(prefix="/auth", tags=["Auth"])


# ===========================================================================
# Вспомогательная функция (не эндпоинт)
# ===========================================================================
def find_user_by_login(db: Session, login: str) -> User | None:
    """
    Ищет пользователя по username ИЛИ email (login — то, что ввёл человек).
    .lower() — потому что при регистрации мы сохранили их в нижнем регистре.
    or_(A, B) — SQL-условие «A ИЛИ B».
    """
    login = login.strip().lower()
    return db.scalars(
        select(User).where(or_(User.username == login, User.email == login))
    ).first()


# ===========================================================================
# POST /auth/register — РЕГИСТРАЦИЯ
# ===========================================================================
@router.post(
    "/register",
    response_model=UserOut,                 # ответ пройдёт через схему UserOut (без пароля)
    status_code=status.HTTP_201_CREATED,    # 201 = «создано»
    summary="Регистрация нового пользователя",
)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """
    data — уже ПРОВЕРЕННЫЕ данные (FastAPI проверил их по схеме UserCreate).
    Если формат неправильный, сюда мы даже не попадём — будет ошибка 422.
    """
    # 1. Проверяем, не заняты ли username / email / телефон → иначе 409 (конфликт).
    if db.scalars(select(User).where(User.username == data.username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот username уже занят")
    if db.scalars(select(User).where(User.email == data.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот email уже зарегистрирован")
    if data.phone and db.scalars(select(User).where(User.phone == data.phone)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот телефон уже зарегистрирован")

    # 2. Создаём пользователя. Пароль сохраняем ТОЛЬКО хешем.
    user = User(
        username=data.username,
        email=data.email,
        phone=data.phone,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )

    # 3. АВТОМАТИЧЕСКИ создаём пустой профиль (этап 2 будет его показывать и менять).
    #    Присваивая user.profile, мы связываем их: user_id профиля заполнится сам.
    user.profile = Profile()

    # 4. Сохраняем в базу. add — «положить в корзину», commit — «оплатить» (записать).
    db.add(user)
    db.commit()
    db.refresh(user)  # перечитать из базы: теперь у user есть id и created_at

    # 5. Отправляем код подтверждения (в учебной версии — печать в консоль).
    #    Если указан телефон — по SMS, иначе на email.
    send_verification_code(db, user, channel="sms" if user.phone else "email")

    # 6. Возвращаем пользователя. FastAPI превратит его в JSON по схеме UserOut.
    return user


# ===========================================================================
# POST /auth/verify — ПОДТВЕРЖДЕНИЕ КОДОМ
# ===========================================================================
@router.post("/verify", response_model=Message, summary="Подтвердить аккаунт кодом")
def verify(data: VerifyRequest, db: Session = Depends(get_db)):
    user = find_user_by_login(db, data.login)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if user.is_verified:
        return Message(detail="Аккаунт уже подтверждён")

    # Вся проверка (срок, попытки, совпадение) — в services/verification.py.
    error = check_verification_code(db, user, data.code)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return Message(detail="Аккаунт подтверждён. Теперь можно войти")


# ===========================================================================
# POST /auth/resend-code — ОТПРАВИТЬ КОД ЕЩЁ РАЗ
# ===========================================================================
@router.post("/resend-code", response_model=Message, summary="Отправить код ещё раз")
def resend_code(data: ResendCodeRequest, db: Session = Depends(get_db)):
    user = find_user_by_login(db, data.login)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if user.is_verified:
        return Message(detail="Аккаунт уже подтверждён")
    if data.channel == "sms" and not user.phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У пользователя не указан телефон")

    send_verification_code(db, user, channel=data.channel)
    return Message(detail=f"Новый код отправлен ({data.channel})")


# ===========================================================================
# POST /auth/login — ВХОД
# ===========================================================================
@router.post("/login", response_model=TokenPair, summary="Вход: получить токены")
def login(
    # Depends() без аргумента: FastAPI сам заполнит форму из полей username и password.
    # В поле username можно ввести и username, и email.
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = find_user_by_login(db, form.username)

    # Одна и та же ошибка для «нет пользователя» и «неверный пароль»:
    # так нельзя узнать, существует ли такой логин.
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")
    if not user.is_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Аккаунт не подтверждён. Введите код в /auth/verify"
        )

    # Выдаём два токена.
    access = create_access_token(user.id)
    refresh, jti, lifetime = create_refresh_token(user.id)

    # refresh-токен записываем в базу (нужно для logout).
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=utc_now() + lifetime))
    db.commit()

    return TokenPair(access_token=access, refresh_token=refresh)


# ===========================================================================
# POST /auth/refresh — НОВЫЙ ACCESS-ТОКЕН
# ===========================================================================
@router.post("/refresh", response_model=AccessToken, summary="Продлить сессию")
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    # 1. Проверяем сам токен (подпись, срок, тип "refresh").
    payload = decode_token(data.refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный refresh-токен")

    # 2. Ищем его номер jti в базе: не отозван ли (после logout — отозван).
    stored = db.scalars(select(RefreshToken).where(RefreshToken.jti == payload.get("jti"))).first()
    if stored is None or stored.revoked or stored.expires_at < utc_now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия завершена. Войдите заново")

    # 3. Всё хорошо → новый access-токен.
    return AccessToken(access_token=create_access_token(stored.user_id))


# ===========================================================================
# POST /auth/logout — ВЫХОД
# ===========================================================================
@router.post("/logout", response_model=Message, summary="Выход")
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный refresh-токен")

    stored = db.scalars(select(RefreshToken).where(RefreshToken.jti == payload.get("jti"))).first()
    if stored is None or stored.revoked:
        return Message(detail="Вы уже вышли")

    # Отзываем токен: продлить сессию по нему больше нельзя.
    stored.revoked = True
    db.commit()
    # Примечание: уже выданный access-токен доживёт свои ≤30 минут —
    # клиент (приложение) должен просто удалить его у себя.
    return Message(detail="Вы вышли из аккаунта")


# ===========================================================================
# GET /auth/me — КТО Я?
# ===========================================================================
@router.get("/me", response_model=UserOut, summary="Данные текущего пользователя")
def me(current_user: User = Depends(get_current_user)):
    """
    Depends(get_current_user) — вся проверка токена происходит в dependencies.py.
    Если мы попали внутрь функции, значит токен правильный.
    """
    return current_user
