Autocad Assistance Bot
======================

Телеграм-бот для подготовки и конвертации чертежных данных: генерация DXF из таблиц, преобразование KML↔DXF с учётом проекций, а также административная панель с метриками использования.

Возможности
- Генерация DXF по загруженным таблицам (txt/csv) с кодами объектов, уровнями, комментариями.
- Конвертация KML → DXF с выбором проекции и проверкой корректности координат.
- Конвертация DXF → KML (линии и блоки).
- Базовые проверки вводимых файлов и кодов, подсветка слоёв/префиксов.
- Админ-панель (/admin): список пользователей, последние ошибки, удаление статистики по диапазону дат, просмотр истории пользователя.
- Логирование действий в SQLite (путь настраивается, по умолчанию внешний том).

Стек и структура
- Python 3.11+.
- Телеграм: python-telegram-bot v21.
- Геоданные: pyproj, shapely, pandas.
- DXF: ezdxf.
- Ключевые модули: `bot/` (команды и диалоги), `dxf_generator/`, `kml_generator/`, `templates/`.

Переменные окружения (.env)
- `BOT_TOKEN` — токен бота.
- `ADMIN_IDS` — список Telegram ID через запятую, имеющих доступ к /admin.
- `DB_PATH` — путь к SQLite. По умолчанию `/data/usage_stats.db` (смонтированный том).
- `DATA_DIR` — папка для данных/БД внутри контейнера (по умолчанию `/data`).
- `DOCKER_IMAGE` — имя Docker-образа (для compose/CI).

Локальный запуск (без Docker)
1) Создайте `.env` в корне (см. переменные выше).
2) Установите зависимости:
   ```
   pip install -r autocad_assistance/requirements.txt
   ```
3) Запустите бота:
   ```
   python autocad_assistance/main.py
   ```

Docker
- Сборка:
  ```
  docker build -t autocad_assistance .
  ```
- Запуск с сохранением БД на хосте:
  ```
  docker compose up -d
  ```
  Compose монтирует `./data` в контейнер `/data`, поэтому `usage_stats.db` переживает пересборки.

CI/CD (GitHub Actions)
- Workflow `.github/workflows/cicd.yml` собирает образ и публикует в GHCR (`ghcr.io/pkg89/autocad_assistance:latest`).
- Для деплоя по SSH нужны секреты: `SSH_HOST`, `SSH_USER`, `SSH_KEY` (опц. `SSH_PORT`, `REMOTE_PATH`, `GHCR_READ_TOKEN`). Перед деплоем на сервере должен существовать `.env` с `BOT_TOKEN`, `ADMIN_IDS`, `DB_PATH`/`DATA_DIR`.

Полезные заметки
- БД по умолчанию лежит в `/data/usage_stats.db`; меняйте `DB_PATH` при необходимости.
- Не коммитьте `.env` и содержимое `data/` — они в `.gitignore`.
- Для разработки можно использовать `docker-compose.dev.yml`:
  ```
  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
  ```
