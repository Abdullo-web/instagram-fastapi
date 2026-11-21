"""
services/files.py — СОХРАНЕНИЕ И УДАЛЕНИЕ ЗАГРУЖЕННЫХ ФАЙЛОВ.

Главная идея: сам файл лежит в папке media/ на диске,
а в базе данных хранится только ПУТЬ к нему (строка, например "avatars/ab12.jpg").

Функции:
  save_image(upload, subfolder, max_size) — проверить картинку и сохранить на диск
  delete_file(relative_path)              — удалить файл (например, старый аватар)
  file_url(relative_path)                 — путь → адрес для браузера (/media/...)

Этот файл пригодится и дальше: на этапе 3 через него же сохраним фото постов и историй.
"""

# pathlib.Path — из стандартной библиотеки. Удобная работа с путями к файлам и папкам.
from pathlib import Path

# uuid — из стандартной библиотеки. uuid4().hex даёт случайное уникальное имя файла,
# чтобы два пользователя с файлом «photo.jpg» не перезаписали друг друга.
import uuid

# Из FastAPI:
#   HTTPException — вернуть ошибку клиенту
#   UploadFile    — тип «загруженный файл» (имя, content-type, содержимое)
#   status        — имена HTTP-кодов
from fastapi import HTTPException, UploadFile, status

# Наши настройки из config.py.
from config import ALLOWED_IMAGE_TYPES, MEDIA_DIR, MEDIA_URL


def save_image(upload: UploadFile, subfolder: str, max_size: int) -> str:
    """
    Проверяет и сохраняет картинку. Возвращает путь ОТНОСИТЕЛЬНО папки media/
    (например "avatars/3f9c...e1.jpg") — именно его кладём в базу.

    Проверки:
      1. Тип файла — только jpeg / png / webp (список в config.py).
      2. Размер — не больше max_size байт.
    """
    # 1. Тип файла. upload.content_type — тип, который прислал клиент.
    extension = ALLOWED_IMAGE_TYPES.get(upload.content_type or "")
    if extension is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Можно загрузить только картинку: JPEG, PNG или WEBP",
        )
    # (Учебное упрощение: content_type сообщает клиент, его можно подделать.
    #  В настоящем проекте содержимое проверяют ещё библиотекой Pillow.)

    # 2. Размер. Читаем на 1 байт больше лимита: если прочиталось больше —
    #    файл слишком большой, и весь огромный файл в память мы не грузим.
    #    upload.file — обычный файловый объект Python, .read(n) читает n байт.
    data = upload.file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,  # 413 = «слишком большой файл»
            f"Файл больше {max_size // (1024 * 1024)} МБ",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл пустой")

    # 3. Папка: media/avatars/. mkdir(parents=True, exist_ok=True) —
    #    создать вместе с родительскими папками, без ошибки, если уже есть.
    folder = Path(MEDIA_DIR) / subfolder
    folder.mkdir(parents=True, exist_ok=True)

    # 4. Уникальное имя и запись байтов на диск.
    filename = f"{uuid.uuid4().hex}{extension}"
    (folder / filename).write_bytes(data)

    # Возвращаем путь с прямыми слешами "avatars/имя.jpg" (одинаково на всех ОС).
    return f"{subfolder}/{filename}"


def delete_file(relative_path: str | None) -> None:
    """
    Удаляет файл из media/. Если пути нет или файла уже нет — тихо ничего не делает.
    missing_ok=True — не выдавать ошибку, если файла не существует.
    """
    if relative_path:
        (Path(MEDIA_DIR) / relative_path).unlink(missing_ok=True)


def file_url(relative_path: str | None) -> str | None:
    """
    Превращает путь из базы в адрес для браузера:
    "avatars/ab12.jpg" → "/media/avatars/ab12.jpg".
    Файлы по этому адресу раздаёт StaticFiles (подключён в main.py).
    """
    return f"{MEDIA_URL}/{relative_path}" if relative_path else None
