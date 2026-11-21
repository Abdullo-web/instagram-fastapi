"""
services/connection_manager.py — МЕНЕДЖЕР WEBSOCKET-СОЕДИНЕНИЙ («кто сейчас онлайн»).

Что такое WebSocket (см. учебник, этап 6):
  обычный HTTP — как письмо: спросил → получил ответ → соединение закрылось;
  WebSocket   — как телефонный звонок: соединение ОСТАЁТСЯ открытым,
                и сервер может сам «позвонить» клиенту, когда пришло новое сообщение.

Менеджер хранит «телефонную книгу»:
  { id пользователя: {соединение1, соединение2, ...} }
У одного человека может быть несколько соединений (телефон + ноутбук + две вкладки),
поэтому храним МНОЖЕСТВО соединений, и сообщение уходит во все.

ВАЖНО (учебное ограничение): книга лежит в памяти ОДНОГО процесса сервера.
Если запустить несколько процессов (workers), каждый будет знать только «своих».
В настоящем проекте для этого используют Redis (pub/sub). Нам хватает одного процесса.
"""

# Any — из стандартного typing: «значение любого типа» (словарь для отправки).
from typing import Any

# WebSocket — из FastAPI: объект одного открытого соединения.
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # Сама «телефонная книга». dict[int, set[WebSocket]] — подсказка типа:
        # ключ — id пользователя, значение — множество его соединений.
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """
        Принять соединение и записать в книгу.
        await websocket.accept() — «снять трубку»: без этого общаться нельзя.
        async/await — функция асинхронная: пока ждём сеть, сервер обслуживает других.
        """
        await websocket.accept()
        # setdefault: если у пользователя ещё нет множества — создать пустое.
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Убрать соединение из книги (человек закрыл вкладку или пропал интернет)."""
        user_sockets = self.connections.get(user_id)
        if not user_sockets:
            return
        user_sockets.discard(websocket)   # discard — удалить, если есть (без ошибки)
        if not user_sockets:
            del self.connections[user_id]  # соединений не осталось → человек офлайн

    def is_online(self, user_id: int) -> bool:
        """Есть ли у пользователя хотя бы одно открытое соединение."""
        return bool(self.connections.get(user_id))

    async def send_to_user(self, user_id: int, data: dict[str, Any]) -> None:
        """
        Отправить данные (словарь → JSON) во ВСЕ соединения пользователя.
        Если пользователь офлайн — ничего не происходит: сообщение уже сохранено
        в базе, и он увидит его, когда откроет чат (GET /chats/{id}/messages).
        """
        # list(...) — копия множества: пока перебираем, оно может измениться.
        for websocket in list(self.connections.get(user_id, set())):
            try:
                await websocket.send_json(data)
            except Exception:
                # Соединение «умерло» без закрытия — просто убираем его из книги.
                self.disconnect(user_id, websocket)

    async def send_to_users(self, user_ids: list[int], data: dict[str, Any]) -> None:
        """Отправить одно и то же нескольким людям (например, всем участникам чата)."""
        for user_id in user_ids:
            await self.send_to_user(user_id, data)


# ОДИН общий менеджер на всё приложение. Его импортируют роутеры:
#   from services.connection_manager import manager
manager = ConnectionManager()
